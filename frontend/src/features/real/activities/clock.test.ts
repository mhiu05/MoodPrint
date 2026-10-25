import { afterEach, describe, expect, it, vi } from "vitest";
import { createClock, formatCountdown, remainingMs } from "./clock";

describe("server-anchored clock", () => {
  afterEach(() => vi.useRealTimers());

  it("follows the server when it is ahead of the device", () => {
    vi.useFakeTimers();
    vi.setSystemTime(Date.parse("2026-10-25T09:00:00Z"));
    const clock = createClock("2026-10-25T09:00:30Z");
    expect(clock.offset).toBe(30_000);
    expect(remainingMs("2026-10-25T09:01:00Z", clock)).toBe(30_000);
    vi.advanceTimersByTime(10_000);
    expect(remainingMs("2026-10-25T09:01:00Z", clock)).toBe(20_000);
  });

  it("follows the server when it is behind and never goes below zero", () => {
    vi.useFakeTimers();
    vi.setSystemTime(Date.parse("2026-10-25T09:00:00Z"));
    const clock = createClock("2026-10-25T08:59:00Z");
    expect(remainingMs("2026-10-25T09:00:00Z", clock)).toBe(60_000);
    expect(remainingMs("2026-10-25T08:58:00Z", clock)).toBe(0);
  });

  it("formats minutes and seconds", () => {
    expect(formatCountdown(25 * 60_000)).toBe("25:00");
    expect(formatCountdown(61_000)).toBe("01:01");
    expect(formatCountdown(400)).toBe("00:01");
    expect(formatCountdown(0)).toBe("00:00");
  });
});
