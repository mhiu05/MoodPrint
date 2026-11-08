import { useWorkspaceStore, type WorkspaceState } from "../../app/store";
export const currentOwner = () => useWorkspaceStore.getState().workspace.userId;
export function commitForOwner(
  owner: string | null,
  work: (state: WorkspaceState) => void,
) {
  const state = useWorkspaceStore.getState();
  if (state.workspace.kind === "real" && state.workspace.userId === owner)
    work(state);
}
export const jsonBody = (method: string, data: unknown): RequestInit => ({
  method,
  body: JSON.stringify(data),
});
