import { useEffect, useSyncExternalStore } from "react";
import { ApiClient, ApiError } from "../../../api/client";
import type { components } from "../../../api/generated/schema";
import { checkInError } from "./checkinsModel";

export type ProactiveView = components["schemas"]["ProactiveView"];
export type Schedule = components["schemas"]["ScheduleView"];
export type Settings = components["schemas"]["ProactiveSettingsView"];
export type SchedulePatch = Partial<Pick<Schedule, "enabled" | "localTime" | "weekdays" | "pausedUntil">>;
// Versions and policy are always taken from the fresh server snapshot, never from a form.
export type SettingsPatch = Partial<Pick<Settings, "timezone" | "quietStart" | "quietEnd" | "badgesEnabled" | "journalContextEnabled">>;
export type CheckInStatus = { key: string; text: string; error?: boolean; code?: string };
type Snapshot = { view?: ProactiveView; loading: boolean; error?: unknown; saving: string | null; status?: CheckInStatus };

/** One serialized controller shared by all panels for this authenticated lifecycle. */
export function createProactiveStore(api: ApiClient, userId = "") {
  const epoch = api.epoch;
  let state: Snapshot = { loading: true, saving: null };
  let pending: Promise<void> | undefined;
  let invalidated = false;
  let channel: BroadcastChannel | undefined;
  const listeners = new Set<() => void>();
  const live = () => api.epoch === epoch;
  const set = (patch: Partial<Snapshot>) => {
    if (!live()) return;
    state = { ...state, ...patch };
    listeners.forEach((listener) => listener());
  };
  const read = async () => {
    const view = await api.request<ProactiveView>("/ai/proactive");
    set({ view, error: undefined, loading: false });
    return view;
  };
  const load = (): Promise<void> => {
    if (!live()) return Promise.resolve();
    if (state.saving) { invalidated = true; return Promise.resolve(); }
    if (pending) return pending;
    set({ loading: !state.view, error: undefined });
    pending = read().then(() => {}, (error: unknown) => set({ error, loading: false })).finally(() => { pending = undefined; });
    return pending;
  };
  const refreshAfterWrite = async () => {
    if (!live()) return;
    try { await read(); }
    catch (error) { set({ error, loading: false }); }
  };
  const failure = async (key: string, reason: unknown, refresh = false) => {
    const code = reason instanceof ApiError ? reason.code : undefined;
    if (code === "STALE_VERSION" || code === "SCHEDULE_IN_QUIET_HOURS" || refresh) await refreshAfterWrite();
    set({ status: { key, error: true, code, text: checkInError(code, state.view?.limits.dailyCap, state.view?.limits.windows.evening?.[1]) } });
  };
  const finish = () => {
    set({ saving: null });
    channel?.postMessage("refresh"); // No settings, consent or journal content is broadcast.
    if (invalidated) { invalidated = false; void load(); }
  };
  const start = async (key: string) => {
    // A foreground refresh must settle before an edit uses its version.
    if (state.saving || !live()) return false;
    set({ saving: key, status: undefined });
    if (pending) await pending;
    if (!live() || !state.view) { set({ saving: null }); return false; }
    return true;
  };
  const store = {
    getSnapshot: () => state,
    subscribe: (listener: () => void) => {
      listeners.add(listener);
      if (listeners.size === 1 && typeof window !== "undefined") {
        window.addEventListener("focus", onFocus);
        document.addEventListener("visibilitychange", onVisible);
        if (typeof BroadcastChannel !== "undefined" && userId) {
          channel = new BroadcastChannel(`moodprint-checkins-${userId}`);
          channel.onmessage = () => { void load(); };
        }
      }
      return () => {
        listeners.delete(listener);
        if (!listeners.size && typeof window !== "undefined") {
          window.removeEventListener("focus", onFocus);
          document.removeEventListener("visibilitychange", onVisible);
          channel?.close(); channel = undefined;
        }
      };
    },
    load,
    async saveSchedule(schedule: Schedule, patch: SchedulePatch) {
      if (!await start(schedule.botId)) return;
      const before = state.view!;
      const current = before.schedules.find((item) => item.botId === schedule.botId && item.slot === schedule.slot);
      if (!current) { finish(); return; }
      set({ view: { ...before, schedules: before.schedules.map((item) => item === current ? { ...item, ...patch } : item) } });
      try {
        const next = await api.request<Schedule>(`/ai/proactive/schedules/${current.botId}/${current.slot}`, {
          method: "PUT", body: { enabled: current.enabled, localTime: current.localTime, weekdays: current.weekdays, pausedUntil: current.pausedUntil ?? null, ...patch, expectedVersion: current.version },
        });
        if (!live()) return;
        set({ view: { ...state.view!, schedules: state.view!.schedules.map((item) => item.botId === next.botId && item.slot === next.slot ? next : item) } });
        // Refresh rather than deriving the account-wide cap or creating a settings version locally.
        await refreshAfterWrite();
        set({ status: { key: current.botId, text: "Đã lưu" } });
      } catch (reason) {
        set({ view: before });
        await failure(current.botId, reason);
      } finally { finish(); }
    },
    async saveSettings(patch: SettingsPatch, key = "general") {
      if (!await start(key)) return false;
      let base = state.view!;
      set({ view: { ...base, settings: { ...base.settings, ...patch } } });
      const put = (settings: Settings) => api.request<Settings>("/ai/proactive/settings", {
        method: "PUT", body: {
          timezone: settings.timezone, quietStart: settings.quietStart, quietEnd: settings.quietEnd,
          badgesEnabled: settings.badgesEnabled, journalContextEnabled: settings.journalContextEnabled,
          policyVersion: settings.policyVersion, ...patch, expectedVersion: settings.version,
        },
      });
      try {
        let next: Settings;
        try { next = await put(base.settings); }
        catch (reason) {
          if (!(reason instanceof ApiError && reason.code === "STALE_VERSION")) throw reason;
          // Rebase only the person's edited fields on fresh consent/policy/version.
          // Keep this fresh base even if the retry fails; never restore revoked consent.
          base = await read();
          if (!live()) return;
          next = await put(base.settings);
        }
        if (!live()) return;
        set({ view: { ...state.view!, settings: next } });
        await refreshAfterWrite();
        set({ status: { key, text: "Đã lưu" } });
        return true;
      } catch (reason) {
        set({ view: base });
        await failure(key, reason);
        return false;
      } finally { finish(); }
    },
    async migrate(schedule: Schedule) {
      if (!schedule.migrateTo || !await start(schedule.botId)) return;
      try {
        const current = state.view!.schedules.find((item) => item.botId === schedule.botId && item.slot === schedule.slot)!;
        await api.request(`/ai/proactive/schedules/${current.botId}/${current.slot}/migrate`, { method: "POST", body: { expectedVersion: current.version } });
        await refreshAfterWrite();
        set({ status: { key: schedule.botId, text: "Đã chuyển lịch" } });
      } catch (reason) { await failure(schedule.botId, reason); }
      finally { finish(); }
    },
    async remove(botId: string) {
      if (!await start(botId)) return false;
      try {
        for (const schedule of state.view!.schedules.filter((item) => item.botId === botId && item.version > 0)) {
          if (!live()) return false;
          await api.request(`/ai/proactive/schedules/${botId}/${schedule.slot}`, { method: "DELETE", body: { expectedVersion: schedule.version } });
        }
        await refreshAfterWrite();
        set({ status: { key: botId, text: "Đã xóa lịch hỏi thăm" } });
        return true;
      } catch (reason) { await failure(botId, reason, true); return false; }
      finally { finish(); }
    },
  };
  function onFocus() { void load(); }
  function onVisible() { if (document.visibilityState === "visible") void load(); }
  return store;
}

const stores = new WeakMap<ApiClient, { epoch: number; users: Map<string, ReturnType<typeof createProactiveStore>> }>();
export function getProactiveStore(api: ApiClient, userId: string) {
  let entry = stores.get(api);
  if (!entry || entry.epoch !== api.epoch) {
    entry = { epoch: api.epoch, users: new Map() }; stores.set(api, entry);
  }
  let store = entry.users.get(userId);
  if (!store) { store = createProactiveStore(api, userId); entry.users.set(userId, store); }
  return store;
}

export function useProactiveSettings(api: ApiClient, userId: string) {
  const store = getProactiveStore(api, userId);
  const snapshot = useSyncExternalStore(store.subscribe, store.getSnapshot, store.getSnapshot);
  useEffect(() => { void store.load(); }, [store]);
  return { ...snapshot, load: store.load, saveSchedule: store.saveSchedule, saveSettings: store.saveSettings, migrate: store.migrate, remove: store.remove };
}
export type ProactiveController = ReturnType<typeof useProactiveSettings>;
