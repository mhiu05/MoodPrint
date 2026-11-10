import { useWorkspaceStore } from "../app/store";

export function clearUserSessionData(userId: string) {
  try {
    for (const key of Object.keys(sessionStorage)) {
      if (
        /^moodprint-[a-z-]+-draft-v1:/.test(key) &&
        key.split(":")[1] === userId
      )
        sessionStorage.removeItem(key);
    }
    localStorage.removeItem(`moodprint-sim-v1:${userId}`);
    for (const key of Object.keys(localStorage)) {
      if (key.startsWith(`tus::moodprint-upload-v1:${userId}:`))
        localStorage.removeItem(key);
    }
  } catch {
    /* The in-memory account cache is always cleared below. */
  }
  const state = useWorkspaceStore.getState();
  if (state.workspace.kind === "real" && state.workspace.userId === userId) {
    state.activateReal(userId);
    useWorkspaceStore.setState({ hydration: { status: "ready" } });
  }
}

export function preserveExpiredSession() {
  const state = useWorkspaceStore.getState();
  if (state.workspace.kind === "real") {
    // Form recovery is deliberately left in sessionStorage for this account.
    state.activateReal(state.workspace.userId ?? "");
    useWorkspaceStore.setState({ hydration: { status: "ready" } });
  }
}

export function saveSimulation() {
  const state = useWorkspaceStore.getState();
  if (state.workspace.kind !== "real" || !state.workspace.userId) return;
  const userId = state.workspace.userId;
  try {
    localStorage.setItem(
      `moodprint-sim-v1:${userId}`,
      JSON.stringify({
        chats: state.chats.filter((item) => item.ownerId === userId),
        analyses: state.analyses.filter((item) => item.ownerId === userId),
        roleplays: state.roleplays.filter((item) => item.ownerId === userId),
        // Only fixture evidence belongs to simulated analysis, never uploaded files.
        evidence: state.evidence.filter(
          (item) => item.origin === "mock_fixture",
        ),
      }),
    );
  } catch {
    /* Simulation remains usable without browser storage. */
  }
}

export function restoreSimulation(userId: string) {
  try {
    const value = JSON.parse(
      localStorage.getItem(`moodprint-sim-v1:${userId}`) ?? "null",
    );
    if (!value || typeof value !== "object") return;
    const owned = <T extends { ownerId: string }>(items: T[] | undefined) =>
      Array.isArray(items)
        ? items.filter((item) => item.ownerId === userId)
        : [];
    useWorkspaceStore.setState({
      chats: owned(value.chats),
      analyses: owned(value.analyses),
      roleplays: owned(value.roleplays),
      evidence: Array.isArray(value.evidence)
        ? value.evidence.filter(
            (item: { origin?: string }) => item.origin === "mock_fixture",
          )
        : [],
    });
  } catch {
    /* Ignore a damaged simulation cache, which is never canonical data. */
  }
}
