// Live Companion HTTP adapter. All network access stays in services/http.
import { readAllPages, type ApiClient, type StreamClient } from "./client";
import { jsonBody } from "./cache";
import { readEvents } from "./chat-stream";
import type {
  AnalysisView,
  ChatTurn,
  LiveCompanion,
  ConversationSummary,
  LiveEvent,
  MemoryCandidateView,
  MemoryView,
  PendingApproval,
  RoleplayScenario,
  RoleplaySessionView,
  RunInfo,
} from "../composition/companion-types";

interface Page<T> {
  items: T[];
}
const SSE: RequestInit["headers"] = { Accept: "text/event-stream" };

export function createCompanionHttp(client: StreamClient): LiveCompanion {
  const api: ApiClient = client;
  async function* stream(
    path: string,
    init: RequestInit,
  ): AsyncGenerator<LiveEvent> {
    const response = await client.stream(path, {
      ...init,
      headers: { ...(SSE as Record<string, string>) },
    });
    yield* readEvents(response, init.signal ?? undefined);
  }
  const items = async <T>(path: string) => (await api<Page<T>>(path)).items;

  return {
    live: true,
    conversations: {
      list: () => items<ConversationSummary>("/v1/conversations?limit=50"),
      create: (input) =>
        api<ConversationSummary>(
          "/v1/conversations",
          jsonBody("POST", {
            id: input.id,
            title: input.title ?? "",
            ...(input.linkedCaseId ? { linkedCaseId: input.linkedCaseId } : {}),
          }),
        ),
      remove: async (id) => {
        await api(`/v1/conversations/${id}`, { method: "DELETE" });
      },
      messages: (id) =>
        readAllPages<ChatTurn>(api, `/v1/conversations/${id}/messages`),
      attachments: async (id) => {
        const rows = await items<{ messageId: string; evidenceIds: string[] }>(
          `/v1/conversations/${id}/attachments`,
        );
        return Object.fromEntries(
          rows.map((r) => [r.messageId, r.evidenceIds]),
        );
      },
    },
    send: (conversationId, input, signal) =>
      stream(`/v1/conversations/${conversationId}/messages`, {
        method: "POST",
        body: JSON.stringify({
          clientMessageId: input.clientMessageId,
          content: input.content,
          attachments: input.attachments ?? [],
        }),
        signal,
      }),
    approve: (runId, approvalId, decision, signal) =>
      stream(`/v1/runs/${runId}/approvals/${approvalId}`, {
        method: "POST",
        body: JSON.stringify({ decision }),
        signal,
      }),
    cancel: async (runId) =>
      (
        await api<{ status: string }>(`/v1/runs/${runId}/cancel`, {
          method: "POST",
        })
      ).status,
    pendingApprovals: (runId) =>
      items<PendingApproval>(`/v1/runs/${runId}/approvals`),
    run: (runId) => api<RunInfo>(`/v1/runs/${runId}`),
    memory: {
      candidates: () =>
        items<MemoryCandidateView>("/v1/memory-candidates?limit=50"),
      decide: async (id, decision, editedContent) => {
        await api(
          `/v1/memory-candidates/${id}/decision`,
          jsonBody("POST", {
            decision,
            ...(editedContent ? { editedContent } : {}),
          }),
        );
      },
      list: () => items<MemoryView>("/v1/memories?limit=100"),
      edit: async (id, content) => {
        await api(`/v1/memories/${id}`, jsonBody("PATCH", { content }));
      },
      remove: async (id) => {
        await api(`/v1/memories/${id}`, { method: "DELETE" });
      },
    },
    analyses: {
      create: (input) =>
        api<AnalysisView>(
          "/v1/analyses",
          jsonBody("POST", {
            id: input.id,
            evidenceId: input.evidenceId,
            consent: { version: input.consentVersion, accepted: true },
          }),
        ),
      get: (id) => api<AnalysisView>(`/v1/analyses/${id}`),
    },
    roleplay: {
      scenarios: () => items<RoleplayScenario>("/v1/roleplay/scenarios"),
      create: (input) =>
        api<RoleplaySessionView>(
          "/v1/roleplay/sessions",
          jsonBody("POST", input),
        ),
      get: (id) => api<RoleplaySessionView>(`/v1/roleplay/sessions/${id}`),
      list: () => items<RoleplaySessionView>("/v1/roleplay/sessions"),
      complete: (id) =>
        api<RoleplaySessionView>(`/v1/roleplay/sessions/${id}/complete`, {
          method: "POST",
        }),
      abandon: (id) =>
        api<RoleplaySessionView>(`/v1/roleplay/sessions/${id}/abandon`, {
          method: "POST",
        }),
    },
  };
}
