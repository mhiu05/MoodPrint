import { describe, expect, it } from "vitest";
import { createMessageDateFormatter } from "./messageDates";

describe("AI message calendar labels", () => {
  it("uses calendar dates in the account timezone across the UTC date boundary", () => {
    const format = createMessageDateFormatter("Asia/Bangkok", new Date("2026-10-30T01:00:00Z"));
    expect(format("2026-10-29T17:01:00Z")).toEqual({ dayKey: "30/10/2026", dayLabel: "Hôm nay", time: "00:01" });
    expect(format("2026-10-29T16:59:00Z")).toEqual({ dayKey: "29/10/2026", dayLabel: "Hôm qua", time: "23:59" });
    expect(format("2026-10-28T16:59:00Z")).toEqual({ dayKey: "28/10/2026", dayLabel: "28/10/2026", time: "23:59" });
  });

  it("recognizes yesterday across a year boundary", () => {
    const format = createMessageDateFormatter("Asia/Bangkok", new Date("2026-01-01T01:00:00Z"));
    expect(format("2025-12-31T16:59:00Z")?.dayLabel).toBe("Hôm qua");
    expect(format("2025-12-30T16:59:00Z")?.dayLabel).toBe("30/12/2025");
  });

  it("recognizes yesterday across a 25-hour daylight-saving day", () => {
    const format = createMessageDateFormatter("America/New_York", new Date("2026-11-02T04:30:00Z"));
    expect(format("2026-11-01T03:30:00Z")).toEqual({ dayKey: "31/10/2026", dayLabel: "Hôm qua", time: "23:30" });
  });

  it("omits missing or invalid legacy timestamps", () => {
    const format = createMessageDateFormatter("Asia/Bangkok", new Date("2026-10-30T01:00:00Z"));
    for (const value of [undefined, null, "", "invalid"]) expect(format(value)).toBeUndefined();
  });
});
