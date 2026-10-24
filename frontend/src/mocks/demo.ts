import { initialState } from "./fixtures";
import { reducer } from "../state/reducer";
import type { State } from "../domain/types";

// This entry point creates fictional survey data only. Domain defaults and
// production-style age/permission policies remain fail-closed.
export function demoState(epoch = 1): State {
  const harness = import.meta.env.DEV
    ? new URLSearchParams(location.search)
    : new URLSearchParams();
  const fixture = harness.get("fixture");
  if (fixture === "unknown" || fixture === "under16") {
    const s = initialState(epoch);
    s.age = fixture === "under16" ? "under16" : "unknown";
    return s;
  }
  const age = fixture === "teen" ? "teen" : "adult";
  let s = reducer(initialState(epoch), {
    type: "START",
    age,
    permissions: {
      AI: harness.get("ai") !== "off",
      MEM: harness.get("mem") !== "off",
      MATCH: age === "adult" && fixture !== "fresh",
      VOICE: harness.get("voice") === "on",
    },
    preset: fixture === "fresh" ? "fresh" : "adult-ready-to-publish",
  });
  if (fixture !== "fresh" && age === "adult")
    s = reducer(s, { type: "PUBLISH", profile: s.draft });
  s.fixtureId = "consumer-demo";
  s.notice = "";
  return s;
}
