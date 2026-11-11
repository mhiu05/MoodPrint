import { beforeEach, describe, expect, it, vi } from "vitest";
import { createRealServices, getServices } from "./composition";
import { useWorkspaceStore } from "../app/store";
import { ApiError, type ApiClient, type StreamClient } from "./http/client";
import { seedCases } from "../mocks/data/seed";
import * as knowledge from "./composition/knowledge";
import * as chat from "./composition/chat";

const asStreamClient = (api: ApiClient): StreamClient =>
  Object.assign(api, {
    stream: async () => {
      throw Error("unexpected stream");
    },
  });

describe("service composition", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
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
    await expect(
      createRealServices(asStreamClient(api)).cases.get("a"),
    ).rejects.toThrow("Offline");
    expect(useWorkspaceStore.getState().cases).toEqual([]);
  });
  it("uses local labeled AI ports in a real workspace without writing server data", async () => {
    useWorkspaceStore.getState().activateReal("owner");
    let requests = 0;
    const api: ApiClient = async () => {
      requests++;
      throw Error("unexpected request");
    };
    const services = createRealServices(asStreamClient(api));
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
    expect(localStorage.getItem("safevoice-sim-v1:owner")).toContain(
      "Synthetic",
    );
  });
  it.each(["demo", "real"])(
    "leaves future live adapters disabled in %s",
    (workspace) => {
      if (workspace === "real")
        useWorkspaceStore.getState().activateReal("owner");
      else useWorkspaceStore.getState().login("USER-AN");
      expect(getServices().knowledgeSearch).toBeNull();
      expect(getServices().companion).toBeNull();
    },
  );
  it("connects phase-owned factories to the stream client while keeping demo isolated", () => {
    const knowledgeFactory = vi
      .spyOn(knowledge, "createKnowledgeSearchPort")
      .mockReturnValue({ live: true });
    const companionFactory = vi
      .spyOn(chat, "createCompanionService")
      .mockReturnValue({ live: true });
    const api = asStreamClient(async () => {
      throw Error("unexpected request");
    });
    const services = createRealServices(api);
    expect(services.knowledgeSearch).toEqual({ live: true });
    expect(services.companion).toEqual({ live: true });
    expect(knowledgeFactory).toHaveBeenCalledWith(api);
    expect(companionFactory).toHaveBeenCalledWith(api);
    useWorkspaceStore.getState().login("USER-AN");
    expect(getServices().knowledgeSearch).toBeNull();
    expect(getServices().companion).toBeNull();
  });
});
