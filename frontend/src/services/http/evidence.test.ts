import { beforeEach, describe, expect, it } from "vitest";
import { useWorkspaceStore } from "../../app/store";
import { createEvidencePort } from "./evidence";
import type { ApiClient } from "./client";
const uploaded = {
  id: "evidence",
  kind: "image",
  origin: "user_upload",
  uploadStatus: "uploaded",
  originalFilename: "synthetic.svg",
  originalText: null,
  reviewStatus: "unreviewed",
  limitations: [],
};
const capability = {
  url: "http://localhost:54321/storage/v1/upload/resumable/sign",
  token: "signed-test-capability",
  chunkSize: 6291456,
  objectName: "users/owner/originals/evidence/random.svg",
  bucketName: "incident-evidence",
  expiresAt: new Date(Date.now() + 7200000).toISOString(),
};
describe("evidence capability lifecycle", () => {
  it("finishes recovered metadata when the original upload already reached Storage", async () => {
    const file = new File(["synthetic"], "synthetic.svg", {
      type: "image/svg+xml",
      lastModified: 123,
    });
    sessionStorage.setItem(
      `moodprint-upload-draft-v1:owner:synthetic.svg:${file.size}:123:`,
      "pending-existing",
    );
    const paths: string[] = [];
    const api: ApiClient = async <T>(path: string) => {
      paths.push(path);
      return (
        path.endsWith("/complete")
          ? uploaded
          : {
              evidence: { ...uploaded, uploadStatus: "pending" },
              upload: capability,
            }
      ) as T;
    };
    const controller = createEvidencePort(api).upload(file);
    await controller.pause();
    await expect(controller.done).resolves.toMatchObject({
      uploadStatus: "uploaded",
    });
    expect(paths).toEqual([
      "/v1/evidence/uploads",
      "/v1/evidence/pending-existing/complete",
    ]);
  }, 1000);
  beforeEach(() => {
    sessionStorage.clear();
    localStorage.clear();
    useWorkspaceStore.getState().activateReal("owner");
  });
  it("uses an idempotently completed upload without uploading or deleting the original again", async () => {
    const methods: string[] = [];
    const api: ApiClient = async <T>(_path: string, init?: RequestInit) => {
      methods.push(init?.method ?? "GET");
      return { evidence: uploaded, upload: capability } as T;
    };
    const controller = createEvidencePort(api).upload(
      new File(["synthetic"], "synthetic.svg", { type: "image/svg+xml" }),
    );
    expect((await controller.done).uploadStatus).toBe("uploaded");
    await controller.cancel();
    expect(methods).toEqual(["POST"]);
    expect(useWorkspaceStore.getState().evidence[0].originalFilename).toBe(
      "synthetic.svg",
    );
  });
  it("cancels a paused pending upload without exposing evidence as uploaded", async () => {
    const paths: string[] = [];
    const api: ApiClient = async <T>(path: string, init?: RequestInit) => {
      paths.push(`${init?.method} ${path}`);
      return (
        init?.method === "DELETE"
          ? undefined
          : {
              evidence: { ...uploaded, uploadStatus: "pending" },
              upload: capability,
            }
      ) as T;
    };
    const controller = createEvidencePort(api).upload(
      new File(["synthetic"], "synthetic.svg", { type: "image/svg+xml" }),
    );
    const rejected = expect(controller.done).rejects.toMatchObject({
      name: "AbortError",
    });
    await controller.pause();
    await controller.cancel();
    await rejected;
    expect(paths).toHaveLength(2);
    expect(paths[1]).toContain("DELETE /v1/evidence/");
    expect(useWorkspaceStore.getState().evidence).toEqual([]);
  });
  it("rejects fixture evidence before making a real API request", async () => {
    let called = false;
    const api: ApiClient = async () => {
      called = true;
      throw Error("unexpected");
    };
    await expect(
      createEvidencePort(api).save({
        id: "fixture",
        kind: "screenshot",
        origin: "mock_fixture",
        shownTimestamp: "",
        originalText: "Synthetic",
        extractedText: "",
        reviewStatus: "confirmed",
        limitations: [],
      }),
    ).rejects.toThrow("Bộ ảnh mẫu");
    expect(called).toBe(false);
  });
});
