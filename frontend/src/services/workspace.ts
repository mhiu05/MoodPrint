import { restoreDemoWorkspace, useWorkspaceStore } from "../app/store";
import type { AgeBand } from "../types";
import { getServices } from "./composition";
import { getSupabase, isRealAuthConfigured } from "./supabase";
import {
  clearUserSessionData,
  preserveExpiredSession,
  restoreSimulation,
} from "./session-reset";
import { stopActiveUploads } from "./http/evidence";
let initialization: Promise<void> | undefined;
let hydrateTask: { userId: string; promise: Promise<void> } | undefined;
let authSubscribed = false;
const lastWorkspace = "moodprint-last-workspace-v1";
const remember = (value: string) => {
  try {
    sessionStorage.setItem(lastWorkspace, value);
  } catch {
    /* Session storage optional. */
  }
};
export async function hydrateWorkspace(
  options: { background?: boolean } = {},
): Promise<void> {
  const state = useWorkspaceStore.getState();
  const userId = state.workspace.userId;
  if (state.workspace.kind !== "real" || !userId) return;
  if (hydrateTask?.userId === userId) return hydrateTask.promise;
  const task = (async () => {
    if (!options.background)
      useWorkspaceStore.setState({ hydration: { status: "loading" } });
    try {
      const services = getServices();
      const [profile, cases, evidence, contacts, drafts, articleStates] =
        await Promise.all([
          services.profile.get(),
          services.cases.list(),
          services.evidence.list(),
          services.contacts.list(),
          services.support.list(),
          services.knowledgeState.list(),
        ]);
      const plans = await Promise.all(
        cases
          .filter((item) => item.linkedPlanId)
          .map((item) => services.plans.getForCase(item.id)),
      );
      if (useWorkspaceStore.getState().workspace.userId !== userId) return;
      const simulatedEvidence = useWorkspaceStore
        .getState()
        .evidence.filter((item) => item.origin === "mock_fixture");
      useWorkspaceStore.setState({
        user: profile.user,
        preferences: { reducedMotion: profile.reducedMotion },
        cases,
        evidence: [...evidence, ...simulatedEvidence],
        plans: plans.filter((item) => item !== null),
        trustedPeople: contacts,
        drafts,
        bookmarks: articleStates
          .filter((item) => item.bookmarked)
          .map((item) => item.articleId),
        readIds: articleStates
          .filter((item) => item.readAt)
          .map((item) => item.articleId),
        hydration: { status: "ready" },
      });
    } catch (error) {
      if (
        !options.background &&
        useWorkspaceStore.getState().workspace.userId === userId
      )
        useWorkspaceStore.setState({
          hydration: {
            status: "error",
            error:
              error instanceof Error
                ? error.message
                : "Chưa tải được dữ liệu. Hãy thử lại.",
          },
        });
      throw error;
    }
  })();
  hydrateTask = { userId, promise: task };
  try {
    await task;
  } finally {
    if (hydrateTask?.promise === task) hydrateTask = undefined;
  }
}
export async function restoreRealSession(userId?: string): Promise<void> {
  const session = userId ? { userId } : await getServices().auth.getSession();
  if (!session) throw new Error("Hãy đăng nhập để tiếp tục.");
  const state = useWorkspaceStore.getState();
  if (
    state.workspace.kind !== "real" ||
    state.workspace.userId !== session.userId
  ) {
    await stopActiveUploads();
    state.activateReal(session.userId);
    restoreSimulation(session.userId);
  }
  remember("real");
  await hydrateWorkspace();
}
export function initializeWorkspace(): Promise<void> {
  if (initialization) return initialization;
  initialization = (async () => {
    // Fresh stores already start in this state. A persisted store writes on
    // setState: writing before rehydration would replace the demo login/data
    // with the fresh in-memory defaults on every full document reload.
    if (useWorkspaceStore.getState().hydration.status !== "initializing")
      useWorkspaceStore.setState({ hydration: { status: "initializing" } });
    if (isRealAuthConfigured() && !authSubscribed) {
      authSubscribed = true;
      getSupabase().auth.onAuthStateChange((event, session) => {
        // Keep async Auth calls outside the SDK callback's lock.
        setTimeout(() => {
          if (event === "SIGNED_OUT") {
            void stopActiveUploads();
            preserveExpiredSession();
            return;
          }
          if (
            session &&
            (event === "SIGNED_IN" || event === "PASSWORD_RECOVERY")
          ) {
            const state = useWorkspaceStore.getState();
            if (
              state.workspace.kind !== "real" ||
              state.workspace.userId !== session.user.id
            )
              void restoreRealSession(session.user.id).catch(() => {});
          }
        }, 0);
      });
    }
    const session = await getServices().auth.getSession();
    if (session) {
      await restoreRealSession(session.userId);
      return;
    }
    let previous: string | null = null;
    try {
      previous = sessionStorage.getItem(lastWorkspace);
    } catch {
      /* Storage optional. */
    }
    if (previous !== "real") await restoreDemoWorkspace();
    useWorkspaceStore.setState({ hydration: { status: "ready" } });
  })().catch((error) => {
    useWorkspaceStore.setState({
      hydration: {
        status: "error",
        error:
          error instanceof Error ? error.message : "Chưa khởi tạo được phiên.",
      },
    });
    initialization = undefined;
  });
  return initialization;
}
export async function enterDemo(
  personaId: string,
  nickname?: string,
  ageBand?: AgeBand,
) {
  const session = await getServices().auth.getSession();
  if (session)
    throw new Error("Hãy đăng xuất tài khoản hiện tại trước khi vào demo.");
  await stopActiveUploads();
  await restoreDemoWorkspace();
  useWorkspaceStore.getState().login(personaId, nickname, ageBand);
  remember("demo");
}
export async function logoutWorkspace() {
  const state = useWorkspaceStore.getState();
  if (state.workspace.kind === "real") {
    await getServices().auth.signOut();
    await stopActiveUploads();
    if (state.workspace.userId) clearUserSessionData(state.workspace.userId);
    remember("real");
  } else {
    state.logout();
    remember("demo");
  }
}
export function clearDemoData() {
  try {
    localStorage.removeItem("moodprint-demo");
    localStorage.removeItem("moodprint-school-demo");
  } catch {
    throw new Error("Chưa xóa được dữ liệu demo trong trình duyệt này.");
  }
}
