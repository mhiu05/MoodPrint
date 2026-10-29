import { describe, expect, it, vi } from "vitest";
import { ApiError } from "./client";
import {
  classifySessionFailure,
  graceExpired,
  rememberGraceStart,
  revalidateSession,
  sessionRetryDelayMs,
  shouldContinueSessionRetry,
} from "./sessionPolicy";

const network = new TypeError("Failed to fetch");

describe("classifySessionFailure", () => {
  it("keeps authorization failures terminal and retries only transient session reads", () => {
    expect(classifySessionFailure(new ApiError(401, "SESSION_EXPIRED", "Phiên đã kết thúc."), 0).kind).toBe("unauthorized");
    expect(classifySessionFailure(new ApiError(403, "ACCOUNT_SUSPENDED", "Tài khoản đang bị tạm khóa."), 0).kind).toBe("forbidden");
    expect(classifySessionFailure(new ApiError(502, "INVALID_SESSION", "bad"), 0).kind).toBe("invalid");
    expect(classifySessionFailure(new ApiError(500, "INTERNAL_ERROR", "x", null, false), 0).kind).toBe("invalid");
    expect(classifySessionFailure(new ApiError(503, "DATABASE_BUSY", "đông", "2", true), 0)).toMatchObject({
      kind: "transient",
      retryAfterMs: 2000,
    });
    expect(classifySessionFailure(new ApiError(500, "INTERNAL_ERROR", "x", null, true), 0).kind).toBe("transient");
    expect(classifySessionFailure(network, 0).kind).toBe("transient");
    expect(classifySessionFailure(new DOMException("Aborted", "AbortError"), 0).kind).toBe("cancelled");
  });

  it("honors a Retry-After date and ignores a malformed header", () => {
    expect(classifySessionFailure(new ApiError(429, "RATE_LIMITED", "chờ", "not-a-date"), 1_000).retryAfterMs).toBeUndefined();
    const later = new Date(5_000).toUTCString();
    expect(classifySessionFailure(new ApiError(503, "DATABASE_UNAVAILABLE", "gián đoạn", later, true), 1_000).retryAfterMs).toBe(4000);
  });
});

describe("session retry budget", () => {
  it("uses full jitter and stops when the delay no longer fits", () => {
    expect(sessionRetryDelayMs(1, 0)).toBe(0);
    expect(sessionRetryDelayMs(1, 1)).toBe(500);
    expect(sessionRetryDelayMs(2, 1)).toBe(1000);
    expect(shouldContinueSessionRetry({ attempt: 3, elapsedMs: 10, delayMs: 0 })).toBe(false);
    expect(shouldContinueSessionRetry({ attempt: 1, elapsedMs: 19_000, delayMs: 2_000 })).toBe(false);
    expect(shouldContinueSessionRetry({ attempt: 1, elapsedMs: 100, delayMs: 200 })).toBe(true);
  });

  it("stops after three transient attempts and does not move the grace anchor", async () => {
    let calls = 0;
    const status = await revalidateSession({
      signal: new AbortController().signal,
      isCurrent: () => true,
      random: () => 0,
      now: () => 0,
      sleep: async () => undefined,
      request: async () => {
        calls += 1;
        throw new ApiError(503, "DATABASE_BUSY", "đông", null, true);
      },
      onTransient: () => undefined,
      onSuccess: () => undefined,
      onUnauthorized: () => undefined,
      onForbidden: () => undefined,
      onInvalid: () => undefined,
    });
    expect(status).toBe("failed");
    expect(calls).toBe(3);
    expect(rememberGraceStart(1_000, 9_000)).toBe(1_000);
    expect(graceExpired(1_000, 31_000)).toBe(true);
    expect(graceExpired(1_000, 30_999)).toBe(false);
  });

  it("does not retry a revoked session or a caller abort", async () => {
    let calls = 0;
    const unauthorized = await revalidateSession({
      signal: new AbortController().signal,
      isCurrent: () => true,
      request: async () => {
        calls += 1;
        throw new ApiError(401, "SESSION_EXPIRED", "Phiên đã kết thúc.");
      },
      onTransient: () => undefined,
      onSuccess: () => undefined,
      onUnauthorized: () => undefined,
      onForbidden: () => undefined,
      onInvalid: () => undefined,
    });
    expect(unauthorized).toBe("stopped");
    expect(calls).toBe(1);

    const controller = new AbortController();
    controller.abort();
    const cancelled = await revalidateSession({
      signal: controller.signal,
      isCurrent: () => true,
      request: async () => {
        throw new Error("should not run");
      },
      onTransient: () => undefined,
      onSuccess: () => undefined,
      onUnauthorized: () => undefined,
      onForbidden: () => undefined,
      onInvalid: () => undefined,
    });
    expect(cancelled).toBe("stopped");
  });

  it("retries a session read at most once per cycle when Retry-After exceeds the budget", async () => {
    const request = vi.fn(async () => {
      throw new ApiError(503, "DATABASE_BUSY", "đông", "30", true);
    });
    const status = await revalidateSession({
      signal: new AbortController().signal,
      isCurrent: () => true,
      clock: () => 0,
      now: () => 0,
      request,
      onTransient: () => undefined,
      onSuccess: () => undefined,
      onUnauthorized: () => undefined,
      onForbidden: () => undefined,
      onInvalid: () => undefined,
    });
    expect(status).toBe("failed");
    expect(request).toHaveBeenCalledTimes(1);
  });
});
