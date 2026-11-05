import { describe, expect, it } from "vitest";
import {
  canAdvance,
  counterText,
  limitsOf,
  toggle,
  type Profile,
} from "./profileRules";

const limits = limitsOf({
  limits: {
    interests: [3, 10],
    values: [2, 4],
    languages: [1, 2],
    activities: [0, 4],
    availability: [0, 6],
  },
});
const base: Profile = {
  interests: ["reading", "music", "walking"],
  values: ["respect", "kindness"],
  style: "balanced",
  goal: "friendship",
  languages: ["vi"],
  activities: [],
  availability: [],
  strictGoal: false,
};

describe("profile editor rules", () => {
  it("requires three interests before continuing", () => {
    expect(canAdvance("interests", { ...base, interests: ["reading", "music"] }, limits)).toBe(false);
    expect(canAdvance("interests", base, limits)).toBe(true);
    const eleven = Array.from({ length: 11 }, (_, i) => `t${i}`);
    expect(canAdvance("interests", { ...base, interests: eleven }, limits)).toBe(false);
  });

  it("checks values, languages and the optional facets per step", () => {
    expect(canAdvance("values", { ...base, values: ["respect"] }, limits)).toBe(false);
    expect(canAdvance("style", { ...base, languages: [] }, limits)).toBe(false);
    expect(canAdvance("activities", base, limits)).toBe(true); // optional
    expect(canAdvance("preview", base, limits)).toBe(true);
    expect(canAdvance("preview", { ...base, values: [] }, limits)).toBe(false);
  });

  it("counts towards minimums and caps selections at the maximum", () => {
    expect(counterText(2, [3, 10])).toBe("Đã chọn 2 · cần ít nhất 3");
    expect(counterText(4, [3, 10])).toBe("Đã chọn 4/10");
    expect(counterText(1, [0, 4])).toBe("Đã chọn 1 (không bắt buộc, tối đa 4)");
    expect(toggle(["a", "b"], "c", 2)).toEqual(["a", "b"]);
    expect(toggle(["a", "b"], "a", 2)).toEqual(["b"]);
    expect(toggle(["a"], "b", 2)).toEqual(["a", "b"]);
  });

  it("falls back to the documented limits when the taxonomy has none", () => {
    expect(limitsOf(undefined).interests).toEqual([3, 10]);
  });
});
