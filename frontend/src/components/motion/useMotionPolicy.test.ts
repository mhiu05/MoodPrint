import { describe, expect, it } from "vitest";
import { resolveMotionPolicy } from "./useMotionPolicy";

describe("resolveMotionPolicy", () => {
  it("animates only when motion is allowed and the page is visible", () => {
    expect(resolveMotionPolicy(false, true)).toEqual({ animate: true });
  });
  it("never animates under reduced motion", () => {
    expect(resolveMotionPolicy(true, true)).toEqual({ animate: false });
  });
  it("never animates a hidden page", () => {
    expect(resolveMotionPolicy(false, false)).toEqual({ animate: false });
    expect(resolveMotionPolicy(true, false)).toEqual({ animate: false });
  });
});
