import { useCallback, useEffect, useState } from "react";
import type { SessionView } from "../../api/contracts";
import type { TourStep } from "./tourSteps";

export type TourState = {
  version: "tour-v1";
  status: "idle" | "waiting" | "showing" | "skipped" | "completed";
  stepId: TourStep["id"] | null;
  promptDismissed: boolean;
};
type Action =
  | { type: "start" | "skip" | "finish" | "reset" }
  | { type: "step"; id: TourStep["id"] };
export function initialTourState(): TourState {
  return {
    version: "tour-v1",
    status: "idle",
    stepId: null,
    promptDismissed: false,
  };
}
export function transitionTourState(
  state: TourState,
  action: Action,
): TourState {
  if (action.type === "reset") return initialTourState();
  if (action.type === "start")
    return { ...state, status: "waiting", promptDismissed: true };
  if (action.type === "step")
    return { ...state, status: "showing", stepId: action.id };
  return {
    ...state,
    status: action.type === "finish" ? "completed" : "skipped",
    stepId: null,
    promptDismissed: true,
  };
}
export function restoreTourState(value: unknown): TourState {
  if (!value || typeof value !== "object") return initialTourState();
  const row = value as Partial<TourState>;
  if (
    row.version !== "tour-v1" ||
    !["idle", "waiting", "showing", "skipped", "completed"].includes(
      row.status || "",
    ) ||
    typeof row.promptDismissed !== "boolean"
  )
    return initialTourState();
  const status =
    row.status === "skipped" || row.status === "completed"
      ? row.status
      : "idle";
  return {
    version: "tour-v1",
    status,
    stepId: null,
    promptDismissed: row.promptDismissed,
  };
}
export function useTourState(session: SessionView) {
  const key =
    session.accountKind === "guest"
      ? null
      : `moodprint:tour:tour-v1:registered:${session.userId}`;
  const [state, setState] = useState<TourState>(() => {
    if (key)
      try {
        return restoreTourState(
          JSON.parse(localStorage.getItem(key) || "null"),
        );
      } catch {
        /* preference storage is optional */
      }
    return initialTourState();
  });
  useEffect(() => {
    if (key)
      try {
        localStorage.setItem(key, JSON.stringify(state));
      } catch {
        /* no storage: guidance still works */
      }
  }, [key, state]);
  const dispatch = useCallback(
    (action: Action) => setState((old) => transitionTourState(old, action)),
    [],
  );
  return {
    state,
    start: useCallback(() => dispatch({ type: "start" }), [dispatch]),
    skip: useCallback(() => dispatch({ type: "skip" }), [dispatch]),
    finish: useCallback(() => dispatch({ type: "finish" }), [dispatch]),
    reset: useCallback(() => dispatch({ type: "reset" }), [dispatch]),
    setStep: useCallback(
      (id: TourStep["id"]) => dispatch({ type: "step", id }),
      [dispatch],
    ),
  };
}
