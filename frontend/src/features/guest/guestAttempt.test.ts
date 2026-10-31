// @vitest-environment node
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, type ApiClient } from "../../api/client";
import { beginAttempt, beginOrResumeGuest, clearAttempt, loadAttempt } from "./guestAttempt";

type Call = { path: string; options: Record<string, unknown> };

function fakeApi(outcomes: unknown[]) {
  const calls: Call[] = [];
  const api = {
    request: vi.fn(async (path: string, options: Record<string, unknown>) => {
      calls.push({ path, options });
      const next = outcomes.shift();
      if (next instanceof Error) throw next;
      return next;
    }),
  };
  return { api: api as unknown as ApiClient, calls };
}

const body = {
  eligibility: {
    birthYear: 2000,
    confirmedMinimumAge: true,
    confirmedAdultAge: false,
    policyVersion: "self-declared-age-v2-18plus",
    expectedVersion: 0,
  },
  captchaToken: "synthetic",
  disclosureVersion: "guest-v1",
} as never;

beforeEach(() => {
  vi.stubGlobal("window", {
    get sessionStorage() {
      throw new Error("storage blocked");
    },
  });
  vi.stubGlobal("crypto", { randomUUID: () => "key-1" });
  clearAttempt();
});

describe("guest entry attempt", () => {
  it("publicGuestWriteKeepsExplicitKey", async () => {
    const { api, calls } = fakeApi([
      undefined, // intent
      new ApiError(409, "GUEST_ATTEMPT_PENDING", "đang xử lý", "2"), // ambiguous outcome
      { userId: "u", accountKind: "guest" }, // retry succeeds
    ]);
    const attempt = beginAttempt(1_000);
    const signal = new AbortController().signal;
    await expect(beginOrResumeGuest(api, body, attempt, signal)).rejects.toMatchObject({
      code: "GUEST_ATTEMPT_PENDING",
    });
    const retried = beginAttempt(2_000);
    expect(retried.key).toBe(attempt.key);
    await beginOrResumeGuest(api, body, retried, signal);
    const creates = calls.filter((c) => c.path === "/auth/guest");
    expect(creates).toHaveLength(2);
    expect(creates[0].options.idempotencyKey).toBe(creates[1].options.idempotencyKey);
    expect(calls.filter((c) => c.path === "/auth/guest-intents")).toHaveLength(1);
    expect(creates.every((c) => c.options.guestIntent === true && c.options.publicWrite === true)).toBe(true);
  });

  it("works without storage and expires after ten minutes", () => {
    const first = beginAttempt(0);
    expect(loadAttempt(599_000)?.key).toBe(first.key);
    expect(loadAttempt(600_001)).toBeNull();
  });

  it("never stores age, captcha or tokens", () => {
    const attempt = beginAttempt(0);
    expect(Object.keys(attempt).sort()).toEqual(["expiresAt", "intent", "key"]);
  });
});
