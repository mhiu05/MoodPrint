import { useWorkspaceStore } from "../../app/store";
import type { SupportDraft, TrustedPerson } from "../../types";
import type {
  ArticleState,
  KnowledgeStatePort,
  School,
  Share,
  SupportPort,
  TrustedContactPort,
} from "../ports";
import { readAllPages, type ApiClient } from "./client";
import { commitForOwner, currentOwner, jsonBody } from "./cache";
import { mapSupport } from "./mappers";
export function createContactPort(api: ApiClient): TrustedContactPort {
  return {
    async list() {
      return readAllPages<TrustedPerson>(api, "/v1/trusted-contacts");
    },
    async save(item) {
      const owner = currentOwner();
      const existing = useWorkspaceStore
        .getState()
        .trustedPeople.some((value) => value.id === item.id);
      const result = await api<TrustedPerson>(
        existing ? `/v1/trusted-contacts/${item.id}` : "/v1/trusted-contacts",
        jsonBody(
          existing ? "PATCH" : "POST",
          existing ? { label: item.label, role: item.role } : item,
        ),
      );
      commitForOwner(owner, (state) => state.addTrustedPerson(result));
      return result;
    },
    async remove(id) {
      const owner = currentOwner();
      await api(`/v1/trusted-contacts/${id}`, { method: "DELETE" });
      commitForOwner(owner, (state) => state.removeTrustedPerson(id));
    },
  };
}
export function createSupportPort(api: ApiClient): SupportPort {
  return {
    async list() {
      return (await readAllPages<SupportDraft>(api, "/v1/support-drafts")).map(
        mapSupport,
      );
    },
    async save(item) {
      if (!["draft", "prepared"].includes(item.status))
        throw new Error(
          "Trạng thái mô phỏng không thể lưu vào tài khoản thật.",
        );
      const owner = currentOwner();
      const exists = useWorkspaceStore
        .getState()
        .drafts.some((value) => value.id === item.id);
      const {
        id,
        caseId,
        recipientType,
        identityMode,
        content,
        compose,
        status,
        version,
      } = item;
      const result = mapSupport(
        await api<SupportDraft>(
          exists ? `/v1/support-drafts/${id}` : "/v1/support-drafts",
          jsonBody(exists ? "PATCH" : "POST", {
            ...(exists ? {} : { id }),
            caseId: caseId ?? null,
            recipientType,
            identityMode,
            content,
            compose: compose ?? {},
            status,
            ...(exists && version !== undefined ? { version } : {}),
          }),
        ),
      );
      commitForOwner(owner, (state) => state.putDraft(result));
      return result;
    },
    async remove(id) {
      const owner = currentOwner();
      await api(`/v1/support-drafts/${id}`, { method: "DELETE" });
      commitForOwner(owner, () =>
        useWorkspaceStore.setState((state) => ({
          drafts: state.drafts.filter((value) => value.id !== id),
        })),
      );
    },
    listSchools: () => readAllPages<School>(api, "/v1/schools"),
    listShares: () => readAllPages<Share>(api, "/v1/shares"),
    createShare: (input) => api("/v1/shares", jsonBody("POST", input)),
    previewShare: (id) => api(`/v1/shares/${id}/preview`),
    submitShare: (id, confirmationVersion, previewHash) =>
      api(
        `/v1/shares/${id}/submit`,
        jsonBody("POST", { confirmed: true, confirmationVersion, previewHash }),
      ),
    withdrawShare: (id) => api(`/v1/shares/${id}/withdraw`, { method: "POST" }),
  };
}
export function createKnowledgeStatePort(api: ApiClient): KnowledgeStatePort {
  const put = async (id: string, patch: Partial<ArticleState>) => {
    const owner = currentOwner();
    const state = useWorkspaceStore.getState();
    const current = {
      bookmarked: state.bookmarks.includes(id),
      readAt: state.readIds.includes(id) ? new Date().toISOString() : null,
    };
    const result = await api<ArticleState>(
      `/v1/knowledge/article-states/${encodeURIComponent(id)}`,
      jsonBody("PUT", { ...current, ...patch }),
    );
    commitForOwner(owner, () =>
      useWorkspaceStore.setState((state) => ({
        bookmarks: result.bookmarked
          ? [...new Set([...state.bookmarks, id])]
          : state.bookmarks.filter((value) => value !== id),
        readIds: result.readAt
          ? [...new Set([...state.readIds, id])]
          : state.readIds.filter((value) => value !== id),
      })),
    );
  };
  return {
    list: () => readAllPages<ArticleState>(api, "/v1/knowledge/article-states"),
    toggleBookmark: (id) =>
      put(id, {
        bookmarked: !useWorkspaceStore.getState().bookmarks.includes(id),
      }),
    markRead: (id) => put(id, { readAt: new Date().toISOString() }),
  };
}
