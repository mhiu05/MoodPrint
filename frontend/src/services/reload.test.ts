import { expect, it, vi } from "vitest";

it("restores a demo login and edits after a fresh document initializes", async () => {
  localStorage.clear();
  sessionStorage.clear();
  vi.resetModules();
  const first = await import("../app/store");
  first.useWorkspaceStore.getState().login("USER-AN");
  const item = first.useWorkspaceStore.getState().cases[0];
  first.useWorkspaceStore
    .getState()
    .putCase({ ...item, title: "Synthetic reload edit" });
  const saved = localStorage.getItem("moodprint-demo");
  vi.resetModules();
  const workspace = await import("./workspace");
  const second = await import("../app/store");
  expect(second.useWorkspaceStore.getState().user).toBeNull();
  await workspace.initializeWorkspace();
  expect(second.useWorkspaceStore.getState().user?.id).toBe("USER-AN");
  expect(second.useWorkspaceStore.getState().cases[0].title).toBe(
    "Synthetic reload edit",
  );
  expect(localStorage.getItem("moodprint-demo")).toBe(saved);
});
