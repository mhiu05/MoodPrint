import { useEffect, useId, useSyncExternalStore } from "react";

export type TourActivity = {
  aiBusy: boolean;
  voiceBusy: boolean;
  hasDraft: boolean;
};
type Kind = "ai" | "voice" | "draft";
const owners = new Map<string, Kind>();
const listeners = new Set<() => void>();
let snapshot: TourActivity = {
  aiBusy: false,
  voiceBusy: false,
  hasDraft: false,
};
function publish() {
  const values = Array.from(owners.values());
  const next = {
    aiBusy: values.includes("ai"),
    voiceBusy: values.includes("voice"),
    hasDraft: values.includes("draft"),
  };
  if (
    next.aiBusy === snapshot.aiBusy &&
    next.voiceBusy === snapshot.voiceBusy &&
    next.hasDraft === snapshot.hasDraft
  )
    return;
  snapshot = next;
  listeners.forEach((listener) => listener());
}
export function setTourBlocker(id: string, kind: Kind, active: boolean): void {
  const key = `${kind}:${id}`;
  if (active) owners.set(key, kind);
  else owners.delete(key);
  publish();
}
export function clearTourBlockers(): void {
  owners.clear();
  publish();
}
export function getTourActivity(): TourActivity {
  return snapshot;
}
function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}
export function useTourActivity(): TourActivity {
  return useSyncExternalStore(subscribe, getTourActivity, getTourActivity);
}
export function useTourBlocker(kind: Kind, active: boolean): void {
  const id = useId();
  useEffect(() => {
    setTourBlocker(id, kind, active);
    return () => setTourBlocker(id, kind, false);
  }, [id, kind, active]);
}
