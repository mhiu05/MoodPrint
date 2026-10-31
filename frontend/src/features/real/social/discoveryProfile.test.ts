import { describe, expect, it } from "vitest";
import {
  hydrateEditor,
  reduceEditor,
  toDraftProfile,
  validateReview,
  isDirty,
  incompatibleProfile,
} from "./discoveryProfile";
import type { Profile, Taxonomy } from "./profileRules";

const profile: Profile = {
  interests: [
    "reading",
    "music",
    "coffee",
    "walking",
    "running",
    "cycling",
    "yoga",
    "football",
    "badminton",
    "drawing",
  ],
  values: ["respect", "kindness"],
  languages: ["vi", "en"],
  goal: "language-practice",
  style: "direct",
  activities: ["focus"],
  availability: ["weekday_evening"],
  strictGoal: true,
};
const empty = () =>
  hydrateEditor(
    {
      profile: { style: "balanced", goal: "friendship", strictGoal: false },
      version: 0,
      publishedVersion: 0,
    },
    null,
  );
const legacy = () =>
  hydrateEditor({ profile, version: 4, publishedVersion: 9 }, null);

describe("lossless discovery editing (T02–T09/T20)", () => {
  it("projects only featured interests; opening legacy profile is clean and preserves all facets", () => {
    const state = legacy();
    expect(state.featuredInterests).toEqual(profile.interests!.slice(0, 3));
    expect(isDirty(state)).toBe(false);
    const output = toDraftProfile(
      reduceEditor(state, { type: "SET_APPROACH", value: "lively" }),
    );
    expect(output).toMatchObject(profile);
    expect(output.interests).toEqual(profile.interests);
  });
  it("follows intention only before first save or explicit canonical override", () => {
    let state = reduceEditor(empty(), {
      type: "SET_INTENTION",
      value: "study",
    });
    expect(toDraftProfile(state).goal).toBe("study-buddy");
    state = reduceEditor(state, {
      type: "SAVE_SUCCEEDED",
      draft: {
        profile: toDraftProfile(state),
        version: 1,
        publishedVersion: 0,
      },
    });
    state = reduceEditor(state, { type: "SET_INTENTION", value: "talk" });
    expect(toDraftProfile(state).goal).toBe("study-buddy");
    const saved = reduceEditor(legacy(), {
      type: "SET_INTENTION",
      value: "study",
    });
    expect(toDraftProfile(saved).goal).toBe("language-practice");
    state = reduceEditor(empty(), {
      type: "PATCH_CANONICAL",
      patch: { goal: "language-practice" },
    });
    expect(
      toDraftProfile(
        reduceEditor(state, { type: "SET_INTENTION", value: "study" }),
      ).goal,
    ).toBe("language-practice");
  });
  it("rejects a fourth feature and retains focus-independent data and order", () => {
    let state = empty();
    for (const id of ["music", "drawing", "badminton"])
      state = reduceEditor(state, { type: "FEATURE", id });
    const rejected = reduceEditor(state, { type: "FEATURE", id: "coffee" });
    expect(toDraftProfile(rejected)).toEqual(toDraftProfile(state));
    expect(rejected.notice).toContain("3 sở thích nổi bật");
    expect(state.featuredInterests).toEqual(["music", "drawing", "badminton"]);
  });
  it("de-features tentative additions but keeps saved interests; explicit delete removes both", () => {
    let state = reduceEditor(empty(), { type: "FEATURE", id: "music" });
    expect(
      toDraftProfile(reduceEditor(state, { type: "DEFEATURE", id: "music" }))
        .interests,
    ).toEqual([]);
    state = reduceEditor(state, {
      type: "SAVE_SUCCEEDED",
      draft: {
        profile: toDraftProfile(state),
        version: 1,
        publishedVersion: 0,
      },
    });
    state = reduceEditor(state, { type: "DEFEATURE", id: "music" });
    expect(toDraftProfile(state).interests).toEqual(["music"]);
    expect(
      toDraftProfile(
        reduceEditor(state, { type: "DELETE_FULL_INTEREST", id: "music" }),
      ).interests,
    ).toEqual([]);
  });
  it("never replaces a retained interest at full max", () => {
    let state = reduceEditor(legacy(), { type: "DEFEATURE", id: "reading" });
    state = reduceEditor(state, { type: "FEATURE", id: "travel" });
    expect(toDraftProfile(state).interests).toEqual(profile.interests);
    expect(state.notice).toContain("10 sở thích");
  });
  it("requires new questions and canonical minimums, never inventing values/languages", () => {
    const state = empty();
    expect(validateReview(state).map((issue) => issue.question)).toEqual([
      0, 1, 2,
    ]);
    expect(toDraftProfile(state).values).toEqual([]);
    expect(toDraftProfile(state).languages).toEqual([]);
  });
  it("invalidates a server review on edits while preserving style/activity", () => {
    let state = legacy();
    state = reduceEditor(state, {
      type: "PREVIEW_SUCCEEDED",
      preview: { profile, draftVersion: 4, previewDigest: "server-token" },
    });
    state = reduceEditor(state, {
      type: "SET_APPROACH",
      value: "activity-first",
    });
    expect(state.serverPreview).toBeNull();
    expect(state.stage).not.toBe("review-ready");
    expect(toDraftProfile(state).style).toBe("direct");
    expect(toDraftProfile(state).activities).toEqual(["focus"]);
  });
  it("blocks incompatible taxonomy instead of dropping unknown saved fields", () => {
    const taxonomy: Taxonomy = {
      version: "v2",
      categories: {},
      categoryLabels: {},
      limits: {},
      interests: { music: "Âm nhạc" },
      values: {},
      languages: {},
      styles: {},
      goals: {},
      activities: {},
      availability: {},
    };
    expect(incompatibleProfile(profile, taxonomy)).toBe(true);
    expect(toDraftProfile(legacy()).interests).toEqual(profile.interests);
  });
  it("saving no featured interests does not silently re-feature retained data", () => {
    let state = legacy();
    for (const id of ["reading", "music", "coffee"])
      state = reduceEditor(state, { type: "DEFEATURE", id });
    state = reduceEditor(state, {
      type: "SAVE_SUCCEEDED",
      draft: {
        profile: toDraftProfile(state),
        version: 5,
        publishedVersion: 9,
      },
    });
    expect(state.featuredInterests).toEqual([]);
    expect(isDirty(state)).toBe(false);
    expect(state.publishedVersion).toBe(9);
  });
  it("a failed draft save keeps the builder rather than bypassing the required questions", () => {
    const state = reduceEditor(legacy(), { type: "PREVIEW_INVALIDATED" });
    expect(state.stage).toBe("builder");
    expect(validateReview(state).map((issue) => issue.question)).toEqual([
      0, 2,
    ]);
  });
});
