import { useWorkspaceStore } from "../../app/store";
import type { Incident, TimelineEvent } from "../../types";
import type { CasePort } from "../ports";
import { ApiError, readAllPages, type ApiClient } from "./client";
import { commitForOwner, currentOwner, jsonBody } from "./cache";
import {
  mapIncident,
  serializeCase,
  serializeEvent,
  type CaseDTO,
} from "./mappers";

export function createCasePort(api: ApiClient): CasePort {
  const cache = (owner: string | null, data: CaseDTO) => {
    const item = mapIncident(data);
    commitForOwner(owner, (state) => {
      state.putCase(item);
      useWorkspaceStore.setState((state) => ({
        evidence: state.evidence.map((evidence) => {
          if (evidence.origin === "mock_fixture") return evidence;
          if (item.evidenceIds.includes(evidence.id))
            return { ...evidence, caseId: item.id };
          return evidence.caseId === item.id
            ? { ...evidence, caseId: undefined }
            : evidence;
        }),
      }));
    });
    return item;
  };
  const get: CasePort["get"] = async (id) => {
    const owner = currentOwner();
    return cache(owner, await api(`/v1/cases/${id}`));
  };
  const eventMutation = async (
    caseId: string,
    event: TimelineEvent,
    method: "POST" | "PATCH",
  ) => {
    const owner = currentOwner();
    const result = await api<TimelineEvent>(
      `/v1/cases/${caseId}/events${method === "PATCH" ? `/${event.id}` : ""}`,
      jsonBody(method, serializeEvent(event)),
    );
    commitForOwner(owner, (state) => {
      const item = state.cases.find((item) => item.id === caseId);
      if (item)
        state.putCase({
          ...item,
          events: [
            ...item.events.filter((item) => item.id !== result.id),
            result,
          ],
        });
    });
    // Timeline writes can advance the parent version; always read canonical detail.
    if (currentOwner() === owner) await get(caseId);
    return result;
  };
  return {
    get,
    async list(query = {}) {
      const params = new URLSearchParams();
      if (query.status) params.set("status", query.status);
      if (query.q) params.set("q", query.q);
      if (query.sort) params.set("sort", query.sort);
      const rows = await readAllPages<CaseDTO>(
        api,
        `/v1/cases${params.size ? `?${params}` : ""}`,
      );
      return Promise.all(rows.map((row) => get(row.id)));
    },
    async save(item: Incident) {
      const owner = currentOwner();
      const existing = useWorkspaceStore
        .getState()
        .cases.find((value) => value.id === item.id);
      for (const event of item.events) serializeEvent(event);
      if (
        item.evidenceIds.some(
          (id) =>
            useWorkspaceStore.getState().evidence.find((e) => e.id === id)
              ?.origin === "mock_fixture",
        )
      )
        throw new Error("Nguồn mô phỏng không thể gắn vào hồ sơ thật.");
      try {
        const body = serializeCase(item);
        const { id: _id, ...patch } = body;
        void _id;
        const result = await api<CaseDTO>(
          existing ? `/v1/cases/${item.id}` : "/v1/cases",
          jsonBody(
            existing ? "PATCH" : "POST",
            existing
              ? patch
              : {
                  ...body,
                  firstEvent: item.events[0]
                    ? serializeEvent(item.events[0])
                    : undefined,
                  evidenceIds: item.evidenceIds,
                },
          ),
        );
        // Whole-model UI saves retain explicit edits to their timeline and attachments.
        // Timeline evidence references require the file to belong to this case.
        // Link new attachments before writing any event that refers to them.
        const previousIds = existing?.evidenceIds ?? result.evidenceIds ?? [];
        for (const id of item.evidenceIds)
          if (!previousIds.includes(id))
            await api(`/v1/cases/${item.id}/evidence/${id}/link`, {
              method: "POST",
            });
        const originalEvents = existing?.events ?? result.events ?? [];
        for (const event of item.events) {
          const previous = originalEvents.find(
            (value) => value.id === event.id,
          );
          if (!previous)
            await api(
              `/v1/cases/${item.id}/events`,
              jsonBody("POST", serializeEvent(event)),
            );
          else if (JSON.stringify(previous) !== JSON.stringify(event))
            await api(
              `/v1/cases/${item.id}/events/${event.id}`,
              jsonBody("PATCH", serializeEvent(event)),
            );
        }
        for (const event of originalEvents)
          if (!item.events.some((value) => value.id === event.id))
            await api(`/v1/cases/${item.id}/events/${event.id}`, {
              method: "DELETE",
            });
        for (const id of previousIds)
          if (!item.evidenceIds.includes(id))
            await api(`/v1/cases/${item.id}/evidence/${id}/link`, {
              method: "DELETE",
            });
        return cache(owner, await api(`/v1/cases/${item.id}`));
      } catch (error) {
        if (
          error instanceof ApiError &&
          error.code === "version_conflict" &&
          error.details.latest
        )
          error.details.latest = mapIncident(error.details.latest as CaseDTO);
        throw error;
      }
    },
    async remove(id) {
      const owner = currentOwner();
      await api(`/v1/cases/${id}`, { method: "DELETE" });
      commitForOwner(owner, (state) => state.deleteCase(id));
    },
    addEvent: (id, event) => eventMutation(id, event, "POST"),
    updateEvent: (id, event) => eventMutation(id, event, "PATCH"),
    async removeEvent(id, eventId) {
      const owner = currentOwner();
      await api(`/v1/cases/${id}/events/${eventId}`, { method: "DELETE" });
      if (currentOwner() === owner) await get(id);
    },
    async related(id) {
      const rows = await readAllPages<CaseDTO>(api, `/v1/cases/${id}/related`);
      return Promise.all(rows.map((row) => get(row.id)));
    },
  };
}
