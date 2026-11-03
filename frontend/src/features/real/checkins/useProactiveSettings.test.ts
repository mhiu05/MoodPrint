import { describe, expect, it, vi } from "vitest";
import { ApiClient, ApiError } from "../../../api/client";
import type { components } from "../../../api/generated/schema";
import { createProactiveStore, getProactiveStore } from "./useProactiveSettings";

type View = components["schemas"]["ProactiveView"];
function fixture(): View {
  return {
    available: true,
    settings: { timezone: "Asia/Bangkok", quietStart: "22:00", quietEnd: "07:00", badgesEnabled: true, journalContextEnabled: true, policyVersion: "proactive-v1", version: 0 },
    limits: { dailyCap: 4, enabledSlots: 0, stepMinutes: 15, windows: { morning: ["05:00", "11:30"], evening: ["17:00", "22:30"] } },
    schedules: ["dieuphoi", "nhatky"].flatMap((botId) => ["morning", "evening"].map((slot) => ({ botId, slot, enabled: false, localTime: slot === "morning" ? "07:30" : "20:00", weekdays: [1,2,3,4,5,6,7], version: 0, autoPaused: false, legacy: false, eligibility: { allowed: true, reason: null } }))) as View["schedules"],
  };
}
function setup() {
  const api = new ApiClient();
  let view = fixture();
  const request = vi.spyOn(api, "request").mockImplementation(async (_path, options) => {
    if (!options?.method) return structuredClone(view);
    throw new Error("Unexpected write");
  });
  return { api, request, store: createProactiveStore(api), server: (next: View) => { view = next; } };
}

describe("shared proactive controller", () => {
  it("shares one source per API, user and session epoch; opening only reads", async () => {
    const { api, request } = setup();
    const first = getProactiveStore(api, "user-a");
    expect(getProactiveStore(api, "user-a")).toBe(first);
    expect(getProactiveStore(api, "user-b")).not.toBe(first);
    await Promise.all([first.load(), first.load()]);
    expect(request).toHaveBeenCalledTimes(1);
    expect(request.mock.calls[0][0]).toBe("/ai/proactive");
    api.reset();
    expect(getProactiveStore(api, "user-a")).not.toBe(first);
  });

  it("creates a version-zero schedule and refreshes server settings and account-wide cap", async () => {
    const { store, request, server } = setup();
    await store.load();
    const schedule = store.getSnapshot().view!.schedules[0];
    request.mockImplementationOnce(async (_path, options) => {
      expect(options?.body).toEqual({ enabled: true, localTime: "07:30", weekdays: [1,2,3,4,5,6,7], pausedUntil: null, expectedVersion: 0 });
      const next = { ...schedule, enabled: true, version: 1 };
      const fresh = fixture();
      fresh.settings.version = 1;
      fresh.schedules[0] = next;
      fresh.limits.enabledSlots = 4; // Includes schedules outside this panel.
      server(fresh);
      return next;
    });
    await store.saveSchedule(schedule, { enabled: true });
    expect(store.getSnapshot().view!.settings.version).toBe(1);
    expect(store.getSnapshot().view!.limits.enabledSlots).toBe(4);
    expect(store.getSnapshot().status?.text).toBe("Đã lưu");
  });

  it("moves a control optimistically, locks all panels, and rolls back failed writes", async () => {
    const { store, request } = setup();
    await store.load();
    let reject!: (error: unknown) => void;
    request.mockImplementationOnce(() => new Promise((_resolve, fail) => { reject = fail; }));
    const before = store.getSnapshot().view!;
    const pending = store.saveSchedule(before.schedules[0], { enabled: true });
    await Promise.resolve(); // The controller first awaits any in-flight read before editing its version.
    expect(store.getSnapshot().view!.schedules[0].enabled).toBe(true);
    expect(store.getSnapshot().saving).toBe("dieuphoi");
    await store.saveSettings({ badgesEnabled: false });
    expect(request).toHaveBeenCalledTimes(2);
    reject(new Error("offline"));
    await pending;
    expect(store.getSnapshot().view).toEqual(before);
    expect(store.getSnapshot().status?.error).toBe(true);
    expect(store.getSnapshot().saving).toBeNull();
  });

  it("rebases just the edited settings field after 409, preserving revoked journal consent", async () => {
    const { store, request, server } = setup();
    await store.load();
    const fresh = fixture();
    fresh.settings = { ...fresh.settings, journalContextEnabled: false, version: 8, policyVersion: "current-policy" };
    request.mockImplementationOnce(async () => { server(fresh); throw new ApiError(409, "STALE_VERSION", "stale"); });
    request.mockImplementationOnce(async () => structuredClone(fresh));
    request.mockImplementationOnce(async (_path, options) => {
      expect(options?.body).toEqual({ ...fresh.settings, version: undefined, timezone: "Asia/Tokyo", expectedVersion: 8 });
      const saved = { ...fresh.settings, timezone: "Asia/Tokyo", version: 9 };
      server({ ...fresh, settings: saved });
      return saved;
    });
    await store.saveSettings({ timezone: "Asia/Tokyo" });
    expect(store.getSnapshot().view!.settings.journalContextEnabled).toBe(false);
    expect(store.getSnapshot().view!.settings.timezone).toBe("Asia/Tokyo");
    expect(store.getSnapshot().status?.error).not.toBe(true);
  });

  it("keeps fresh revoked consent when the rebased settings write fails", async () => {
    const { store, request } = setup();
    await store.load();
    const fresh = fixture();
    fresh.settings = { ...fresh.settings, journalContextEnabled: false, version: 5 };
    request.mockRejectedValueOnce(new ApiError(409, "STALE_VERSION", "stale"));
    request.mockResolvedValueOnce(fresh);
    request.mockRejectedValueOnce(new Error("offline"));
    await store.saveSettings({ badgesEnabled: false });
    expect(store.getSnapshot().view!.settings).toEqual(fresh.settings);
    expect(store.getSnapshot().status?.error).toBe(true);
  });

  it("reloads stale schedules without replaying a toggle and ignores an old session response", async () => {
    const { api, store, request, server } = setup();
    await store.load();
    const fresh = fixture();
    fresh.schedules[0].version = 7;
    server(fresh);
    request.mockRejectedValueOnce(new ApiError(409, "STALE_VERSION", "stale"));
    await store.saveSchedule(store.getSnapshot().view!.schedules[0], { enabled: true });
    expect(store.getSnapshot().view!.schedules[0].version).toBe(7);
    expect(request.mock.calls.filter(([, options]) => options?.method === "PUT")).toHaveLength(1);
    let resolve!: (view: unknown) => void;
    request.mockImplementationOnce(() => new Promise((done) => { resolve = done; }));
    const pending = store.load();
    api.reset();
    resolve({ ...fresh, settings: { ...fresh.settings, journalContextEnabled: true } });
    await pending;
    expect(store.getSnapshot().view!.schedules[0].version).toBe(7);
  });

  it("refreshes a quiet-hour conflict introduced by another agent so its schedule can be linked", async () => {
    const { store, request, server } = setup();
    await store.load();
    const fresh = fixture();
    fresh.schedules[2] = { ...fresh.schedules[2], enabled: true, localTime: "08:00", version: 2 };
    server(fresh);
    request.mockRejectedValueOnce(new ApiError(409, "SCHEDULE_IN_QUIET_HOURS", "conflict"));
    await store.saveSettings({ quietEnd: "09:00" });
    expect(store.getSnapshot().view!.schedules[2].enabled).toBe(true);
    expect(store.getSnapshot().status?.code).toBe("SCHEDULE_IN_QUIET_HOURS");
  });

  it("refreshes after a partially completed delete and does not report success", async () => {
    const { store, request, server } = setup();
    await store.load();
    const fresh = fixture();
    fresh.schedules[0].version = 2;
    fresh.schedules[1].version = 3;
    server(fresh);
    await store.load();
    request.mockImplementationOnce(async (_path, options) => {
      expect(options).toMatchObject({ method: "DELETE", body: { expectedVersion: 2 } });
      const after = structuredClone(fresh);
      after.schedules[0].version = 0;
      server(after);
      return { status: "ok" };
    });
    request.mockRejectedValueOnce(new Error("offline"));
    expect(await store.remove("dieuphoi")).toBe(false);
    expect(store.getSnapshot().view!.schedules[0].version).toBe(0);
    expect(store.getSnapshot().view!.schedules[1].version).toBe(3);
    expect(store.getSnapshot().status?.error).toBe(true);
  });
});
