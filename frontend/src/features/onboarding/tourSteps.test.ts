import { describe, expect, it } from "vitest";
import type { SessionView } from "../../api/contracts";
import { getTourSteps } from "./tourSteps";
import {
  initialTourState,
  restoreTourState,
  transitionTourState,
} from "./useTourState";
import {
  clearTourBlockers,
  getTourActivity,
  setTourBlocker,
} from "./tourActivity";

const registered = {
  accountKind: "registered",
  ageBand: "adult",
  eligible: true,
} as SessionView;
const guest = { ...registered, accountKind: "guest" } as SessionView;

describe("approved tour steps", () => {
  it("guest has four steps and never matching even with optional opt-in", () => {
    expect(getTourSteps(guest).map((step) => step.id)).toEqual([
      "assistants",
      "mood",
      "memory",
      "privacy",
    ]);
    expect(
      getTourSteps(guest, true).some((step) => step.id === "matching"),
    ).toBe(false);
    expect(getTourSteps(guest).at(-1)?.description).toContain(
      "không mở lại được sau khi hết giờ",
    );
  });
  it("registered teen has four and eligible adult optional fifth only", () => {
    expect(getTourSteps(registered)).toHaveLength(4);
    expect(getTourSteps(registered, true)).toHaveLength(5);
    expect(getTourSteps({ ...registered, ageBand: "teen" }, true)).toHaveLength(
      4,
    );
    expect(getTourSteps({ ...registered, eligible: false }, true)).toHaveLength(
      0,
    );
  });
  it("selectors/routes are stable teaching targets, never private values", () => {
    for (const step of getTourSteps(guest)) {
      expect(step.route).toMatch(/^\/(assistants|self|memory|settings)$/);
      expect(step.target).toMatch(/^\[data-tour='[a-z-]+'\]$/);
    }
  });
});

describe("tour state", () => {
  it("skip/finish/replay/version reset never auto-starts restored work", () => {
    const waiting = transitionTourState(initialTourState(), { type: "start" });
    expect(waiting.status).toBe("waiting");
    const shown = transitionTourState(waiting, { type: "step", id: "mood" });
    expect(shown.status).toBe("showing");
    expect(restoreTourState(shown).status).toBe("idle");
    expect(transitionTourState(shown, { type: "skip" }).status).toBe("skipped");
    const complete = transitionTourState(shown, { type: "finish" });
    expect(complete.status).toBe("completed");
    expect(complete.promptDismissed).toBe(true);
    expect(transitionTourState(complete, { type: "reset" })).toEqual(
      initialTourState(),
    );
    expect(restoreTourState({ ...complete, version: "old" })).toEqual(
      initialTourState(),
    );
    expect(restoreTourState({ status: "showing", comment: "private" })).toEqual(
      initialTourState(),
    );
  });
  it("content-free blocker registry aggregates and clears all owners", () => {
    clearTourBlockers();
    const initial = getTourActivity();
    expect(initial).toEqual({
      aiBusy: false,
      voiceBusy: false,
      hasDraft: false,
    });
    expect(getTourActivity()).toBe(initial);
    setTourBlocker("component-a", "draft", true);
    setTourBlocker("component-b", "ai", true);
    expect(getTourActivity()).toEqual({
      aiBusy: true,
      voiceBusy: false,
      hasDraft: true,
    });
    setTourBlocker("component-a", "draft", false);
    expect(getTourActivity().hasDraft).toBe(false);
    clearTourBlockers();
    expect(getTourActivity()).toEqual(initial);
  });
});
