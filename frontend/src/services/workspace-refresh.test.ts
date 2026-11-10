import { beforeEach, expect, it, vi } from "vitest";
import { useWorkspaceStore } from "../app/store";
import { hydrateWorkspace } from "./workspace";

const profile = vi.hoisted(() => vi.fn());
vi.mock("./composition", () => ({
  getServices: () => ({
    profile: { get: profile },
    cases: { list: async () => [] },
    evidence: { list: async () => [] },
    contacts: { list: async () => [] },
    support: { list: async () => [] },
    knowledgeState: { list: async () => [] },
  }),
}));

beforeEach(() => {
  profile.mockReset();
  useWorkspaceStore.getState().activateReal("owner-a");
  useWorkspaceStore.setState({ hydration: { status: "ready" } });
});

it("refreshes approved data without replacing the active conversation with a loading screen", async () => {
  let finish!: (value: unknown) => void;
  profile.mockReturnValue(
    new Promise((resolve) => {
      finish = resolve;
    }),
  );
  const pending = hydrateWorkspace({ background: true });
  expect(useWorkspaceStore.getState().hydration.status).toBe("ready");
  finish({ user: { id: "owner-a", nickname: "Mây" }, reducedMotion: true });
  await pending;
  expect(useWorkspaceStore.getState().user?.nickname).toBe("Mây");
  expect(useWorkspaceStore.getState().hydration.status).toBe("ready");
});

it("keeps the current screen usable if background refresh fails", async () => {
  profile.mockRejectedValue(new Error("network"));
  await expect(hydrateWorkspace({ background: true })).rejects.toThrow(
    "network",
  );
  expect(useWorkspaceStore.getState().hydration.status).toBe("ready");
});
