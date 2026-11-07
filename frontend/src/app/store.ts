import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";
import type {
  ActionPlan,
  Analysis,
  ChatSession,
  DemoUser,
  Evidence,
  Incident,
  RoleplaySession,
  SupportDraft,
  TrustedPerson,
} from "../types";
import { personas, seedCases, seedPlans } from "../mocks/data/seed";
export const uid = (prefix: string) =>
  useWorkspaceStore.getState().workspace.kind === "real"
    ? crypto.randomUUID()
    : `${prefix}-${crypto.randomUUID()}`;
interface PersonalScope {
  bookmarks: string[];
  readIds: string[];
  trustedPeople: TrustedPerson[];
}
const personalDefaults = (): PersonalScope => ({
  bookmarks: ["KB-01", "KB-13"],
  readIds: [],
  trustedPeople: [
    { id: "TRUST-1", label: "Giáo viên mình tin tưởng", role: "Giáo viên" },
  ],
});
function clearFormDrafts() {
  try {
    for (const key of Object.keys(sessionStorage)) {
      if (
        key.startsWith("moodprint-case-draft-v1:") ||
        key.startsWith("moodprint-plan-draft-v1:") ||
        key.startsWith("moodprint-support-draft-v1:")
      )
        sessionStorage.removeItem(key);
    }
  } catch {
    /* Storage may be unavailable; canonical in-memory reset still works. */
  }
}
export interface WorkspaceState {
  workspace: { kind: "demo" | "real"; userId: string | null };
  hydration: {
    status: "initializing" | "loading" | "ready" | "error";
    error?: string;
  };
  activateReal: (userId: string) => void;
  scopes: Record<string, PersonalScope>;
  user: DemoUser | null;
  cases: Incident[];
  plans: ActionPlan[];
  evidence: Evidence[];
  chats: ChatSession[];
  analyses: Analysis[];
  roleplays: RoleplaySession[];
  drafts: SupportDraft[];
  bookmarks: string[];
  readIds: string[];
  trustedPeople: TrustedPerson[];
  preferences: { reducedMotion: boolean };
  failNextSave: boolean;
  toast: string;
  login: (
    personaId: string,
    nickname?: string,
    ageBand?: DemoUser["ageBand"],
  ) => void;
  logout: () => void;
  reset: () => void;
  updateUser: (patch: Partial<DemoUser>) => void;
  putCase: (item: Incident) => void;
  deleteCase: (id: string) => void;
  putPlan: (item: ActionPlan) => void;
  putEvidence: (item: Evidence) => void;
  putChat: (item: ChatSession) => void;
  putAnalysis: (item: Analysis) => void;
  putRoleplay: (item: RoleplaySession) => void;
  putDraft: (item: SupportDraft) => void;
  toggleBookmark: (id: string) => void;
  markRead: (id: string) => void;
  addTrustedPerson: (item: TrustedPerson) => void;
  removeTrustedPerson: (id: string) => void;
  setPreferences: (patch: Partial<WorkspaceState["preferences"]>) => void;
  setFailNextSave: (value: boolean) => void;
  notify: (message: string) => void;
}
const upsert = <T extends { id: string }>(items: T[], item: T) =>
  items.some((i) => i.id === item.id)
    ? items.map((i) => (i.id === item.id ? item : i))
    : [...items, item];
const initial = () => ({
  workspace: { kind: "demo" as "demo" | "real", userId: null as string | null },
  hydration: {
    status: "ready" as "initializing" | "loading" | "ready" | "error",
  },
  user: null,
  scopes: {} as Record<string, PersonalScope>,
  cases: structuredClone(seedCases),
  plans: structuredClone(seedPlans),
  evidence: [],
  chats: [],
  analyses: [],
  roleplays: [],
  drafts: [],
  ...personalDefaults(),
  preferences: { reducedMotion: false },
  failNextSave: false,
  toast: "",
});
let persistencePaused = false;
const safeStorage: Storage = {
  getItem: (key) => {
    try {
      return localStorage.getItem(key);
    } catch {
      return null;
    }
  },
  setItem: (key, value) => {
    try {
      if (
        !persistencePaused &&
        JSON.parse(value).state?.workspace?.kind !== "real"
      )
        localStorage.setItem(key, value);
    } catch {
      /* In-memory demo remains usable when storage is unavailable. */
    }
  },
  removeItem: (key) => {
    try {
      localStorage.removeItem(key);
    } catch {
      /* No remote storage exists. */
    }
  },
  clear: () => {},
  key: () => null,
  length: 0,
};
export const useWorkspaceStore = create<WorkspaceState>()(
  persist(
    (set) => ({
      ...initial(),
      hydration: { status: "initializing" },
      activateReal: (userId) =>
        set({
          ...initial(),
          workspace: { kind: "real", userId },
          user: null,
          cases: [],
          plans: [],
          evidence: [],
          chats: [],
          analyses: [],
          roleplays: [],
          drafts: [],
          bookmarks: [],
          readIds: [],
          trustedPeople: [],
          scopes: {},
          hydration: { status: "loading" },
        }),
      login: (personaId, nickname, ageBand) =>
        set((s) => {
          const user = {
            ...(personas.find((p) => p.id === personaId) ?? personas[0]),
            ...(nickname ? { nickname } : {}),
            ...(ageBand ? { ageBand } : {}),
          };
          const scopes = { ...s.scopes };
          if (s.user)
            scopes[s.user.id] = {
              bookmarks: s.bookmarks,
              readIds: s.readIds,
              trustedPeople: s.trustedPeople,
            };
          return {
            user,
            workspace: { kind: "demo" as const, userId: user.id },
            hydration: { status: "ready" as const },
            scopes,
            ...(scopes[user.id] ?? personalDefaults()),
          };
        }),
      logout: () =>
        set((s) => ({
          user: null,
          scopes: s.user
            ? {
                ...s.scopes,
                [s.user.id]: {
                  bookmarks: s.bookmarks,
                  readIds: s.readIds,
                  trustedPeople: s.trustedPeople,
                },
              }
            : s.scopes,
          ...personalDefaults(),
        })),
      reset: () => {
        clearFormDrafts();
        set(initial());
      },
      updateUser: (patch) =>
        set((s) => ({ user: s.user ? { ...s.user, ...patch } : null })),
      putCase: (item) => set((s) => ({ cases: upsert(s.cases, item) })),
      deleteCase: (id) => {
        try {
          for (const key of Object.keys(sessionStorage)) {
            if (
              (key.startsWith("moodprint-case-draft-v1:") ||
                key.startsWith("moodprint-plan-draft-v1:")) &&
              key.endsWith(`:${id}`)
            )
              sessionStorage.removeItem(key);
          }
        } catch {
          /* The canonical case is still removed when session storage is blocked. */
        }
        set((s) => ({
          cases: s.cases.filter((c) => c.id !== id),
          plans: s.plans.filter((p) => p.caseId !== id),
          evidence: s.evidence.flatMap((e) =>
            e.caseId !== id
              ? [e]
              : s.analyses.some((a) => a.evidenceIds.includes(e.id))
                ? [{ ...e, caseId: undefined }]
                : [],
          ),
          chats: s.chats.map((c) =>
            c.linkedCaseId === id ? { ...c, linkedCaseId: undefined } : c,
          ),
          analyses: s.analyses.map((a) =>
            a.caseId === id
              ? { ...a, caseId: undefined, status: "review" as const }
              : a,
          ),
          drafts: s.drafts.map((d) =>
            d.caseId === id ? { ...d, caseId: undefined } : d,
          ),
        }));
      },
      putPlan: (item) =>
        set((s) => ({
          plans: upsert(s.plans, item),
          cases: s.cases.map((c) =>
            c.id === item.caseId ? { ...c, linkedPlanId: item.id } : c,
          ),
        })),
      putEvidence: (item) =>
        set((s) => ({ evidence: upsert(s.evidence, item) })),
      putChat: (item) => set((s) => ({ chats: upsert(s.chats, item) })),
      putAnalysis: (item) =>
        set((s) => ({ analyses: upsert(s.analyses, item) })),
      putRoleplay: (item) =>
        set((s) => ({ roleplays: upsert(s.roleplays, item) })),
      putDraft: (item) => set((s) => ({ drafts: upsert(s.drafts, item) })),
      toggleBookmark: (id) =>
        set((s) => ({
          bookmarks: s.bookmarks.includes(id)
            ? s.bookmarks.filter((i) => i !== id)
            : [...s.bookmarks, id],
        })),
      markRead: (id) =>
        set((s) => ({ readIds: [...new Set([...s.readIds, id])] })),
      addTrustedPerson: (item) =>
        set((s) => ({ trustedPeople: upsert(s.trustedPeople, item) })),
      removeTrustedPerson: (id) =>
        set((s) => ({
          trustedPeople: s.trustedPeople.filter((p) => p.id !== id),
        })),
      setPreferences: (patch) =>
        set((s) => ({ preferences: { ...s.preferences, ...patch } })),
      setFailNextSave: (failNextSave) => set({ failNextSave }),
      notify: (toast) => set({ toast }),
    }),
    {
      name: "moodprint-demo",
      skipHydration: true,
      version: 1,
      storage: createJSONStorage(() => safeStorage),
      partialize: (s) => ({
        workspace: s.workspace,
        user: s.user,
        scopes: s.scopes,
        cases: s.cases,
        plans: s.plans,
        evidence: s.evidence,
        chats: s.chats,
        analyses: s.analyses,
        roleplays: s.roleplays,
        drafts: s.drafts,
        bookmarks: s.bookmarks,
        readIds: s.readIds,
        trustedPeople: s.trustedPeople,
        preferences: s.preferences,
      }),
    },
  ),
);

// Compatibility alias for existing demo readers and fixtures.
export const useDemoStore = useWorkspaceStore;

export async function restoreDemoWorkspace() {
  persistencePaused = true;
  try {
    useWorkspaceStore.setState(initial());
    await useWorkspaceStore.persist.rehydrate();
  } finally {
    persistencePaused = false;
  }
}
