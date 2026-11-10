import { useWorkspaceStore } from "../../app/store";
import { demoService } from "../../mocks/services/demo";
import type { Evidence, TimelineEvent } from "../../types";
import type { AuthPort, Services } from "../ports";
import {
  simulatedAnalysis,
  simulatedChat,
  simulatedRoleplay,
} from "./simulation";
import { createKnowledgeCatalogPort } from "../composition/knowledge";
const store = () => useWorkspaceStore.getState();
const missing = () => new Error("Mình chưa tìm thấy dữ liệu này.");
const getCase = (id: string) => {
  const item = store().cases.find(
    (item) => item.id === id && item.ownerId === store().user?.id,
  );
  if (!item) throw missing();
  return item;
};
const changeEvent = (caseId: string, event: TimelineEvent) =>
  demoService.run(() => {
    const item = getCase(caseId);
    store().putCase({
      ...item,
      events: [...item.events.filter((value) => value.id !== event.id), event],
    });
    return event;
  });
export function createMockServices(auth: AuthPort): Services {
  return {
    auth,
    run: async (work, delay) => await demoService.run(work, delay),
    profile: {
      async get() {
        if (!store().user) throw missing();
        return {
          user: store().user!,
          reducedMotion: store().preferences.reducedMotion,
        };
      },
      async save(patch) {
        store().updateUser(patch);
        if (patch.reducedMotion !== undefined)
          store().setPreferences({ reducedMotion: patch.reducedMotion });
        return {
          user: store().user!,
          reducedMotion: store().preferences.reducedMotion,
        };
      },
      async remove() {
        store().reset();
      },
    },
    cases: {
      async list(query = {}) {
        let items = store().cases.filter(
          (item) => item.ownerId === store().user?.id,
        );
        if (query.status)
          items = items.filter((item) => item.status === query.status);
        if (query.q)
          items = items.filter((item) =>
            (item.title + " " + item.summary)
              .toLocaleLowerCase()
              .includes(query.q!.toLocaleLowerCase()),
          );
        return items;
      },
      async get(id) {
        return getCase(id);
      },
      async save(item) {
        await demoService.saveCase(item);
        return item;
      },
      async remove(id) {
        await demoService.run(() => store().deleteCase(id));
      },
      addEvent: changeEvent,
      updateEvent: changeEvent,
      async removeEvent(id, eventId) {
        await demoService.run(() => {
          const item = getCase(id);
          store().putCase({
            ...item,
            events: item.events.filter((event) => event.id !== eventId),
          });
        });
      },
      async related(id) {
        return store()
          .cases.filter(
            (item) => item.ownerId === store().user?.id && item.id !== id,
          )
          .slice(0, 3);
      },
    },
    evidence: {
      async list(options = {}) {
        return store().evidence.filter((item) =>
          options.caseId
            ? item.caseId === options.caseId
            : options.unlinked
              ? !item.caseId
              : true,
        );
      },
      async get(id) {
        const item = store().evidence.find((item) => item.id === id);
        if (!item) throw missing();
        return item;
      },
      async save(item) {
        return demoService.run(() => {
          store().putEvidence(item);
          return item;
        });
      },
      async createNote(data) {
        const item: Evidence = {
          ...data,
          id: data.id ?? crypto.randomUUID(),
          kind: "text_note",
          origin: "user_entered",
          shownTimestamp: data.shownTimestamp ?? "",
          extractedText: "",
          reviewStatus: "confirmed",
          limitations: [],
        };
        return demoService.run(() => {
          store().putEvidence(item);
          return item;
        });
      },
      async review(id, patch) {
        return demoService.run(() => {
          const item = store().evidence.find((value) => value.id === id);
          if (!item) throw missing();
          const result = { ...item, ...patch };
          store().putEvidence(result);
          return result;
        });
      },
      upload() {
        throw new Error("Chế độ demo sử dụng bộ tệp mẫu.");
      },
      async link(caseId, id) {
        const item = store().evidence.find((item) => item.id === id);
        if (item) store().putEvidence({ ...item, caseId });
        const incident = getCase(caseId);
        store().putCase({
          ...incident,
          evidenceIds: [...new Set([...incident.evidenceIds, id])],
        });
      },
      async unlink(caseId, id) {
        const incident = getCase(caseId);
        const item = store().evidence.find((item) => item.id === id);
        if (item) store().putEvidence({ ...item, caseId: undefined });
        store().putCase({
          ...incident,
          evidenceIds: incident.evidenceIds.filter((value) => value !== id),
          events: incident.events.map((event) => ({
            ...event,
            evidenceIds: event.evidenceIds.filter((value) => value !== id),
          })),
        });
      },
      async remove(id) {
        useWorkspaceStore.setState((state) => ({
          evidence: state.evidence.filter((value) => value.id !== id),
        }));
      },
      async getDownloadUrl(id) {
        const item = store().evidence.find((value) => value.id === id);
        if (!item?.assetPath) throw missing();
        return { url: item.assetPath, expiresAt: "" };
      },
    },
    plans: {
      async save(item) {
        await demoService.savePlan(item);
        return item;
      },
      async getForCase(id) {
        return store().plans.find((item) => item.caseId === id) ?? null;
      },
      async active() {
        return (
          store().plans.find(
            (item) =>
              item.status !== "completed" &&
              store().cases.some(
                (value) =>
                  value.id === item.caseId &&
                  value.ownerId === store().user?.id,
              ),
          ) ?? null
        );
      },
      async setItemStatus(planId, itemId, status, notes) {
        const item = store().plans.find((item) => item.id === planId);
        if (!item) throw missing();
        const result = {
          ...item,
          items: item.items.map((value) =>
            value.id === itemId
              ? { ...value, status, ...(notes === undefined ? {} : { notes }) }
              : value,
          ),
          lastUpdated: new Date().toISOString(),
        };
        await demoService.savePlan(result);
        return result;
      },
    },
    contacts: {
      async list() {
        return store().trustedPeople;
      },
      async save(item) {
        return demoService.run(() => {
          store().addTrustedPerson(item);
          return item;
        });
      },
      async remove(id) {
        await demoService.run(() => store().removeTrustedPerson(id));
      },
    },
    support: {
      async list() {
        return store().drafts.filter(
          (item) => item.ownerId === store().user?.id,
        );
      },
      async save(item) {
        await demoService.saveDraft(item);
        return item;
      },
      async remove(id) {
        useWorkspaceStore.setState((state) => ({
          drafts: state.drafts.filter((value) => value.id !== id),
        }));
      },
      async listSchools() {
        return [];
      },
      async listShares() {
        return [];
      },
      async createShare() {
        throw new Error("Chia sẻ ở demo chỉ là mô phỏng.");
      },
      async previewShare() {
        throw missing();
      },
      async submitShare() {
        throw missing();
      },
      async withdrawShare() {
        throw missing();
      },
    },
    knowledgeState: {
      async list() {
        return [...new Set([...store().bookmarks, ...store().readIds])].map(
          (articleId) => ({
            articleId,
            bookmarked: store().bookmarks.includes(articleId),
            readAt: store().readIds.includes(articleId)
              ? new Date().toISOString()
              : null,
          }),
        );
      },
      async toggleBookmark(id) {
        store().toggleBookmark(id);
      },
      async markRead(id) {
        store().markRead(id);
      },
    },
    chat: simulatedChat,
    analysis: simulatedAnalysis,
    roleplay: simulatedRoleplay,
    voice: { simulated: true },
    knowledgeCatalog: createKnowledgeCatalogPort,
    knowledgeSearch: null,
    companion: null,
  };
}
