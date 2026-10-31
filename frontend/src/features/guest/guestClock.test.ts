import { describe, expect, it } from "vitest";
import { remainingGuestMs, remainingLabel, WARNING_MS } from "./guestClock";

describe("guest clock", () => {
  it("warns when fifteen minutes remain", () => {
    expect(WARNING_MS).toBe(15 * 60_000);
  });

  it("guestClockDoesNotExtendOnRefreshOrWallClockChange", () => {
    const expires = "2026-10-28T02:00:00Z";
    const server = "2026-10-28T00:00:00Z";
    expect(remainingGuestMs(expires, server, 0, 7_200_000)).toBe(0);
    expect(remainingGuestMs(expires, server, 0, 9_000_000)).toBe(0);
    // Same T no matter when the page observed the server time: elapsed monotonic time counts.
    expect(remainingGuestMs(expires, server, 1_000, 61_000)).toBe(7_140_000);
    // A refresh re-reads a *newer* server time and gets a smaller remainder, never a larger one.
    const first = remainingGuestMs(expires, server, 0, 60_000);
    const refreshed = remainingGuestMs(expires, "2026-10-28T00:01:00Z", 500, 500);
    expect(refreshed).toBeLessThanOrEqual(first + 1);
    // A backwards monotonic reading (clock change) cannot add time.
    expect(remainingGuestMs(expires, server, 5_000, 1_000)).toBe(7_200_000);
  });

  it("fails closed on unparseable times", () => {
    expect(remainingGuestMs("nope", "2026-10-28T00:00:00Z", 0, 0)).toBe(0);
    expect(remainingGuestMs("2026-10-28T02:00:00Z", "", 0, 0)).toBe(0);
  });

  it("labels in whole minutes, rounded up", () => {
    expect(remainingLabel(84 * 60_000 - 1)).toBe("1 giờ 24 phút");
    expect(remainingLabel(60 * 60_000)).toBe("1 giờ");
    expect(remainingLabel(59_000)).toBe("1 phút");
    expect(remainingLabel(0)).toBe("dưới 1 phút");
  });
});
