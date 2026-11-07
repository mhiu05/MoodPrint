import { Upload, DetailedError } from "tus-js-client";
import { useWorkspaceStore } from "../../app/store";
import type { Evidence } from "../../types";
import type { EvidencePort, UploadController } from "../ports";
import { ApiError, readAllPages, type ApiClient } from "./client";
import { commitForOwner, currentOwner, jsonBody } from "./cache";
import { mapEvidence, type EvidenceDTO } from "./mappers";
interface SignedUpload {
  url: string;
  token: string;
  chunkSize: number;
  objectName: string;
  bucketName: string;
  expiresAt: string;
}
interface UploadInit {
  evidence: EvidenceDTO;
  upload: SignedUpload;
}
const activeUploads = new Set<UploadController>();
export async function stopActiveUploads() {
  await Promise.all([...activeUploads].map((upload) => upload.pause()));
  activeUploads.clear();
}
export function createEvidencePort(api: ApiClient): EvidencePort {
  const cache = (owner: string | null, data: EvidenceDTO) => {
    const item = mapEvidence(data);
    commitForOwner(owner, (state) => state.putEvidence(item));
    return item;
  };
  const get: EvidencePort["get"] = async (id) => {
    const owner = currentOwner();
    return cache(owner, await api(`/v1/evidence/${id}`));
  };
  const review: EvidencePort["review"] = async (id, patch) => {
    const owner = currentOwner();
    return cache(
      owner,
      await api(`/v1/evidence/${id}`, jsonBody("PATCH", patch)),
    );
  };
  const createNote: EvidencePort["createNote"] = async (data) => {
    const owner = currentOwner();
    return cache(
      owner,
      await api(
        "/v1/evidence/notes",
        jsonBody("POST", { ...data, id: data.id ?? crypto.randomUUID() }),
      ),
    );
  };
  return {
    get,
    review,
    createNote,
    async list(options = {}) {
      const query = new URLSearchParams();
      if (options.caseId) query.set("caseId", options.caseId);
      if (options.unlinked) query.set("unlinked", "true");
      return (
        await readAllPages<EvidenceDTO>(
          api,
          `/v1/evidence${query.size ? `?${query}` : ""}`,
        )
      ).map(mapEvidence);
    },
    async save(item) {
      if (item.origin === "mock_fixture")
        throw new Error("Bộ ảnh mẫu không thể lưu vào hồ sơ thật.");
      const exists = useWorkspaceStore
        .getState()
        .evidence.some((value) => value.id === item.id);
      if (!exists && item.kind === "text_note") return createNote(item);
      if (!exists)
        throw new Error("Hãy dùng chức năng tải tệp để lưu bằng chứng gốc.");
      return review(item.id, {
        userEditedText: item.userEditedText,
        reviewStatus: item.reviewStatus,
        limitations: item.limitations,
      });
    },
    async link(caseId, evidenceId) {
      const owner = currentOwner();
      await api(`/v1/cases/${caseId}/evidence/${evidenceId}/link`, {
        method: "POST",
      });
      commitForOwner(owner, (state) => {
        const evidence = state.evidence.find(
          (value) => value.id === evidenceId,
        );
        if (evidence) state.putEvidence({ ...evidence, caseId });
        const item = state.cases.find((value) => value.id === caseId);
        if (item)
          state.putCase({
            ...item,
            evidenceIds: [...new Set([...item.evidenceIds, evidenceId])],
          });
      });
    },
    async unlink(caseId, evidenceId) {
      const owner = currentOwner();
      await api(`/v1/cases/${caseId}/evidence/${evidenceId}/link`, {
        method: "DELETE",
      });
      commitForOwner(owner, (state) => {
        const evidence = state.evidence.find(
          (value) => value.id === evidenceId,
        );
        if (evidence) state.putEvidence({ ...evidence, caseId: undefined });
        const item = state.cases.find((value) => value.id === caseId);
        if (item)
          state.putCase({
            ...item,
            evidenceIds: item.evidenceIds.filter((id) => id !== evidenceId),
            events: item.events.map((event) => ({
              ...event,
              evidenceIds: event.evidenceIds.filter((id) => id !== evidenceId),
            })),
          });
      });
    },
    async remove(id) {
      const owner = currentOwner();
      await api(`/v1/evidence/${id}`, { method: "DELETE" });
      commitForOwner(owner, () =>
        useWorkspaceStore.setState((state) => ({
          evidence: state.evidence.filter((value) => value.id !== id),
        })),
      );
    },
    getDownloadUrl: (id) => api(`/v1/evidence/${id}/download-url`),
    upload(file, metadata = {}, callbacks = {}) {
      const owner = currentOwner();
      const recoveryKey = `moodprint-upload-draft-v1:${owner}:${encodeURIComponent(file.name)}:${file.size}:${file.lastModified}:${metadata.caseId ?? ""}`;
      let id: string = crypto.randomUUID();
      let recovered = false;
      try {
        const saved = sessionStorage.getItem(recoveryKey);
        if (saved) {
          id = saved;
          recovered = true;
        } else sessionStorage.setItem(recoveryKey, id);
      } catch {
        /* TUS can still resume within this page. */
      }
      let upload: Upload | undefined;
      let signed: SignedUpload;
      let paused = false;
      let cancelled = false;
      let settled = false;
      let refreshes = 0;
      let resolve!: (item: Evidence) => void;
      let reject!: (error: Error) => void;
      const done = new Promise<Evidence>((yes, no) => {
        resolve = yes;
        reject = no;
      });
      const failure = (error: unknown) => {
        const safe =
          error instanceof Error
            ? error
            : new Error("Chưa tải được tệp. Hãy thử lại.");
        callbacks.onError?.(safe);
        if (!callbacks.onError && !settled) {
          settled = true;
          reject(safe);
          activeUploads.delete(controller);
        }
      };
      const refresh = async () => {
        const renewed = await api<UploadInit>(
          `/v1/evidence/${id}/upload-token`,
          { method: "POST" },
        );
        signed = renewed.upload;
      };
      const ready = Promise.resolve()
        .then(async () => {
          const result = await api<UploadInit>(
            "/v1/evidence/uploads",
            jsonBody("POST", {
              id,
              ...metadata,
              filename: file.name,
              mimeType: file.type || "application/octet-stream",
              byteSize: file.size,
            }),
          );
          signed = result.upload;
          if (cancelled) return;
          if (recovered && result.evidence.uploadStatus === "pending") {
            try {
              result.evidence = await api<EvidenceDTO>(
                `/v1/evidence/${id}/complete`,
                { method: "POST" },
              );
            } catch (error) {
              if (!(error instanceof ApiError && error.status === 409))
                throw error;
            }
          }
          if (result.evidence.uploadStatus === "uploaded") {
            settled = true;
            try {
              sessionStorage.removeItem(recoveryKey);
            } catch {
              /* Storage optional. */
            }
            resolve(cache(owner, result.evidence));
            activeUploads.delete(controller);
            return;
          }
          upload = new Upload(file, {
            endpoint: signed.url,
            chunkSize: signed.chunkSize,
            retryDelays: [0, 1000, 3000, 5000],
            removeFingerprintOnSuccess: true,
            // The same owner/file can find its pending evidence after a page reload.
            fingerprint: async () =>
              `moodprint-upload-v1:${owner}:${file.name}:${file.type}:${file.size}:${file.lastModified}:${metadata.caseId ?? ""}`,
            metadata: {
              bucketName: signed.bucketName,
              objectName: signed.objectName,
              contentType: file.type || "application/octet-stream",
              cacheControl: "3600",
            },
            onBeforeRequest: async (req) => {
              if (currentOwner() !== owner)
                throw new Error("Phiên làm việc đã thay đổi.");
              if (Date.parse(signed.expiresAt) - Date.now() < 30000)
                await refresh();
              req.setHeader("x-signature", signed.token);
            },
            onAfterResponse: async (_req, res) => {
              if (res.getStatus() === 401 && refreshes < 1) {
                refreshes++;
                await refresh();
              }
            },
            onShouldRetry: (error, attempt) =>
              !cancelled &&
              attempt < 4 &&
              (error.originalResponse?.getStatus() === 401 ||
                !error.originalResponse ||
                error.originalResponse.getStatus() >= 500),
            onProgress: (sent, total) =>
              callbacks.onProgress?.(
                total ? Math.round((sent / total) * 100) : 0,
              ),
            onError: (error) => {
              if (
                error instanceof DetailedError &&
                error.originalResponse?.getStatus() === 401 &&
                refreshes < 1
              ) {
                refreshes++;
                void refresh()
                  .then(() => upload?.start())
                  .catch(failure);
              } else
                failure(
                  new Error(
                    "Tải tệp bị gián đoạn. Nội dung vẫn được giữ; hãy thử lại.",
                  ),
                );
            },
            onSuccess: () => {
              void api<EvidenceDTO>(`/v1/evidence/${id}/complete`, {
                method: "POST",
              })
                .then((data) => {
                  if (cancelled) return;
                  settled = true;
                  try {
                    sessionStorage.removeItem(recoveryKey);
                  } catch {
                    /* Storage optional. */
                  }
                  resolve(cache(owner, data));
                  activeUploads.delete(controller);
                })
                .catch(failure);
            },
          });
          const previous = await upload.findPreviousUploads();
          // Resume only the matching evidence key. Backend idempotency owns metadata.
          const match = previous.find(
            (value) => value.metadata.objectName === signed.objectName,
          );
          if (match) upload.resumeFromPreviousUpload(match);
          if (!paused && !cancelled) upload.start();
        })
        .catch((error) => {
          if (!settled) {
            settled = true;
            reject(
              error instanceof Error
                ? error
                : new Error("Chưa khởi tạo được tải tệp."),
            );
          }
          callbacks.onError?.(
            error instanceof Error
              ? error
              : new Error("Chưa khởi tạo được tải tệp."),
          );
          activeUploads.delete(controller);
        });
      const controller: UploadController = {
        done,
        async pause() {
          paused = true;
          await upload?.abort(false);
        },
        async resume() {
          await ready;
          if (cancelled || settled) return;
          paused = false;
          await refresh();
          refreshes = 0;
          upload?.start();
        },
        async cancel() {
          if (settled) return;
          cancelled = true;
          await upload?.abort(false);
          await ready;
          await api(`/v1/evidence/${id}`, { method: "DELETE" });
          if (!settled) {
            settled = true;
            reject(new DOMException("Đã hủy tải tệp.", "AbortError"));
          }
          try {
            sessionStorage.removeItem(recoveryKey);
          } catch {
            /* Storage optional. */
          }
          activeUploads.delete(controller);
        },
      };
      activeUploads.add(controller);
      return controller;
    },
  };
}
