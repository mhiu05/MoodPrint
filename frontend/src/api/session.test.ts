import { describe, expect, it } from "vitest";
import type { SessionView } from "./contracts";
import { isGuest, validateSession } from "./session";

const consents = {
  AI: { enabled: false, version: 1, policyVersion: "v1" },
  MEM: { enabled: false, version: 1, policyVersion: "v1" },
  MATCH: { enabled: false, version: 1, policyVersion: "v1" },
  VOICE: { enabled: false, version: 1, policyVersion: "v1" },
};
const registered = {
  userId: "11111111-1111-4111-8111-111111111111",
  alias: "An",
  ageBand: "adult",
  eligible: true,
  csrfToken: "csrf",
  timezone: "Asia/Bangkok",
  serverTime: "2026-10-28T00:10:00Z",
  features: { ai: false, matching: true, voice: false, feedback: false },
  consents,
  accountKind: "registered",
  guestStartedAt: null,
  guestExpiresAt: null,
  guestQuota: null,
} as unknown as SessionView;
const guest = {
  ...registered,
  accountKind: "guest",
  guestStartedAt: "2026-10-28T00:00:00Z",
  guestExpiresAt: "2026-10-28T02:00:00Z",
  guestQuota: { aiTurnsRemaining: 25, voiceClipsRemaining: 6, voiceSecondsRemaining: 180 },
  features: { ai: false, matching: false, voice: false, feedback: false },
} as unknown as SessionView;

describe("validateSession", () => {
  it("accepts registered and guest projections", () => {
    expect(validateSession(registered)).toBe(registered);
    expect(validateSession(guest)).toBe(guest);
    expect(isGuest(guest)).toBe(true);
    expect(isGuest(registered)).toBe(false);
  });

  it("legacy sessions without account fields stay registered", () => {
    const legacy = { ...registered } as Record<string, unknown>;
    delete legacy.accountKind;
    delete legacy.guestStartedAt;
    delete legacy.guestExpiresAt;
    delete legacy.guestQuota;
    expect(() => validateSession(legacy as unknown as SessionView)).not.toThrow();
  });

  it("rejects inconsistent or forged guest projections", () => {
    const wrong = (patch: Record<string, unknown>) =>
      expect(() => validateSession({ ...guest, ...patch } as unknown as SessionView)).toThrow();
    wrong({ guestExpiresAt: "2026-10-28T02:00:01Z" }); // not exactly start + 7200 s
    wrong({ guestExpiresAt: "not a time" });
    wrong({ guestStartedAt: null });
    wrong({ staff: "admin" }); // forged staff claim
    wrong({ features: { ...guest.features, matching: true } }); // forged social capability
    wrong({ guestQuota: null });
    wrong({ serverTime: "NaN" });
    wrong({ accountKind: "visitor" });
    expect(() =>
      validateSession({ ...registered, guestExpiresAt: "2026-10-28T02:00:00Z" } as unknown as SessionView),
    ).toThrow();
  });
});
