import { beforeEach, describe, expect, it } from "vitest";
import { createRealServices, getServices } from "./composition";
import { useWorkspaceStore } from "../app/store";
import { ApiError, type ApiClient } from "./http/client";
import { seedCases } from "../mocks/data/seed";

describe("service composition", () => {
  beforeEach(() => {
    localStorage.clear();
    useWorkspaceStore.getState().reset();
  });
  it("retains the mock save failure control in demo", async () => {
    useWorkspaceStore.getState().login("USER-AN");
    useWorkspaceStore.getState().setFailNextSave(true);
    await expect(getServices().cases.save(seedCases[0])).rejects.toThrow(
      "mô phỏng",
    );
  });
  it("does not fall back to a mock case after an HTTP failure", async () => {
    useWorkspaceStore.getState().activateReal("owner");
    const api: ApiClient = async () => {
      throw new ApiError(503, "upstream_error", "Offline");
    };
    await expect(createRealServices(api).cases.get("a")).rejects.toThrow(
      "Offline",
    );
    expect(useWorkspaceStore.getState().cases).toEqual([]);
  });
  it("uses local labeled AI ports in a real workspace without writing server data", async () => {
    useWorkspaceStore.getState().activateReal("owner");
    let requests = 0;
    const api: ApiClient = async () => {
      requests++;
      throw Error("unexpected request");
    };
    const services = createRealServices(api);
    await services.chat.save({
      id: "sim",
      ownerId: "owner",
      title: "Synthetic",
      messages: [],
      scenarioId: "SC-01",
      cursor: 0,
    });
    expect(services.chat.simulated).toBe(true);
    expect(services.analysis.simulated).toBe(true);
    expect(requests).toBe(0);
    expect(localStorage.getItem("moodprint-sim-v1:owner")).toContain(
      "Synthetic",
    );
  });
});
