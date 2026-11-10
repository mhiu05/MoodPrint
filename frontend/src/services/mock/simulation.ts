import { useWorkspaceStore } from "../../app/store";
import type {
  Analysis,
  ChatSession,
  Evidence,
  RoleplaySession,
} from "../../types";
import { saveSimulation } from "../session-reset";
function save<T extends { ownerId: string }>(
  item: T,
  write: () => void,
): Promise<T> {
  const state = useWorkspaceStore.getState();
  if (
    state.workspace.kind === "real" &&
    item.ownerId !== state.workspace.userId
  )
    return Promise.reject(new Error("Phiên làm việc đã thay đổi."));
  write();
  saveSimulation();
  return Promise.resolve(item);
}
export const simulatedChat = {
  simulated: true as const,
  save: (item: ChatSession) =>
    save(item, () => useWorkspaceStore.getState().putChat(item)),
};
export const simulatedRoleplay = {
  simulated: true as const,
  save: (item: RoleplaySession) =>
    save(item, () => useWorkspaceStore.getState().putRoleplay(item)),
};
export const simulatedAnalysis = {
  simulated: true as const,
  save: (item: Analysis) =>
    save(item, () => useWorkspaceStore.getState().putAnalysis(item)),
  saveEvidence: (item: Evidence) => {
    if (item.origin !== "mock_fixture")
      return Promise.reject(
        new Error("Phân tích mẫu chỉ nhận nguồn mô phỏng."),
      );
    useWorkspaceStore.getState().putEvidence(item);
    saveSimulation();
    return Promise.resolve(item);
  },
};
