import { beforeEach, describe, expect, it } from "vitest";
import { restoreDemoWorkspace, useWorkspaceStore } from "../app/store";
import {
  clearUserSessionData,
  preserveExpiredSession,
  saveSimulation,
} from "./session-reset";

describe("workspace separation", () => {
  beforeEach(() => {
    localStorage.clear();
    sessionStorage.clear();
    useWorkspaceStore.getState().reset();
  });
  it("does not persist real records into the demo snapshot", () => {
    useWorkspaceStore.getState().login("USER-AN");
    const snapshot = localStorage.getItem("safevoice-demo");
    useWorkspaceStore.getState().activateReal("real-a");
    expect(useWorkspaceStore.getState().cases).toEqual([]);
    expect(useWorkspaceStore.getState().trustedPeople).toEqual([]);
    useWorkspaceStore.getState().updateUser({ id: "real-a", nickname: "Real" });
    expect(localStorage.getItem("safevoice-demo")).toBe(snapshot);
  });
  it("stores simulation separately and only for its current real owner", () => {
    useWorkspaceStore.getState().activateReal("real-a");
    useWorkspaceStore.getState().putChat({
      id: "sim",
      ownerId: "real-a",
      title: "Synthetic",
      scenarioId: "SC-01",
      messages: [],
      cursor: 0,
    });
    saveSimulation();
    expect(localStorage.getItem("safevoice-sim-v1:real-a")).toContain(
      "Synthetic",
    );
    expect(localStorage.getItem("safevoice-demo")).not.toContain("Synthetic");
    useWorkspaceStore.getState().activateReal("real-b");
    expect(useWorkspaceStore.getState().chats).toEqual([]);
  });
  it("restores demo fixtures without copying a real account or clearing its recoverable draft", async () => {
    const snapshot = localStorage.getItem("safevoice-demo");
    useWorkspaceStore.getState().activateReal("real-a");
    useWorkspaceStore.getState().updateUser({ id: "real-a", nickname: "Real" });
    sessionStorage.setItem("safevoice-case-draft-v1:real-a:new", "draft");
    await restoreDemoWorkspace();
    expect(useWorkspaceStore.getState().cases.length).toBeGreaterThan(0);
    expect(useWorkspaceStore.getState().user).toBeNull();
    expect(localStorage.getItem("safevoice-demo")).toBe(snapshot);
    expect(sessionStorage.getItem("safevoice-case-draft-v1:real-a:new")).toBe(
      "draft",
    );
  });
  it("preserves drafts on expired auth but removes only the outgoing user's data on logout", () => {
    useWorkspaceStore.getState().activateReal("real-a");
    sessionStorage.setItem(
      "safevoice-case-draft-v1:real-a:new",
      "keep until logout",
    );
    sessionStorage.setItem("safevoice-case-draft-v1:real-b:new", "other user");
    localStorage.setItem("safevoice-sim-v1:real-a", "{}");
    preserveExpiredSession();
    expect(sessionStorage.getItem("safevoice-case-draft-v1:real-a:new")).toBe(
      "keep until logout",
    );
    clearUserSessionData("real-a");
    expect(
      sessionStorage.getItem("safevoice-case-draft-v1:real-a:new"),
    ).toBeNull();
    expect(sessionStorage.getItem("safevoice-case-draft-v1:real-b:new")).toBe(
      "other user",
    );
    expect(localStorage.getItem("safevoice-sim-v1:real-a")).toBeNull();
    expect(useWorkspaceStore.getState().user).toBeNull();
  });
});
