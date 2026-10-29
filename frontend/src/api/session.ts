import { ApiError } from "./client";
import type { ConsentPurpose, SessionView } from "./contracts";

const GUEST_LIFETIME_MS = 7_200_000;

function invalid(): never {
  throw new ApiError(502, "INVALID_SESSION", "Chưa thể xác minh phiên. Vui lòng thử lại.");
}

function instant(value: unknown): number {
  const parsed = typeof value === "string" ? Date.parse(value) : NaN;
  if (!Number.isFinite(parsed)) invalid();
  return parsed;
}

/**
 * Structural check of a server session. The backend stays the authority; this only rejects
 * inconsistent or forged-looking projections (a guest with staff/matching claims, a deadline that
 * is not exactly start + 7200 s, non-finite times) before they reach the UI.
 */
export function validateSession(value: SessionView): SessionView {
  if (
    !value ||
    typeof value.userId !== "string" ||
    typeof value.alias !== "string" ||
    typeof value.eligible !== "boolean" ||
    typeof value.csrfToken !== "string" ||
    !value.csrfToken ||
    typeof value.timezone !== "string" ||
    !value.features ||
    !value.consents ||
    !["AI", "MEM", "MATCH", "VOICE"].every((purpose) => {
      const consent = value.consents[purpose as ConsentPurpose];
      return (
        consent &&
        typeof consent.enabled === "boolean" &&
        Number.isInteger(consent.version)
      );
    })
  )
    invalid();
  const kind = value.accountKind ?? "registered";
  if (kind !== "registered" && kind !== "guest") invalid();
  if (kind === "guest") {
    const started = instant(value.guestStartedAt);
    const expires = instant(value.guestExpiresAt);
    instant(value.serverTime);
    if (
      expires - started !== GUEST_LIFETIME_MS ||
      value.features.matching !== false ||
      value.staff ||
      !value.guestQuota
    )
      invalid();
  } else if (value.guestStartedAt || value.guestExpiresAt || value.guestQuota) {
    invalid();
  }
  return value;
}

export function isGuest(session: Pick<SessionView, "accountKind">): boolean {
  return session.accountKind === "guest";
}
