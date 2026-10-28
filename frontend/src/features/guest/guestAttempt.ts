import type { ApiClient } from "../../api/client";
import type { SessionView } from "../../api/contracts";
import type { components } from "../../api/generated/schema";

export type GuestInput = components["schemas"]["GuestInput"];

const STORAGE_KEY = "moodprint.guestAttempt";
const TTL_MS = 10 * 60 * 1000;

/** Only a random, non-secret retry key and flags: never the age, CAPTCHA, a token or a user. */
export type Attempt = { key: string; expiresAt: number; intent: boolean };

let memory: Attempt | null = null;

function store(): Storage | null {
  try {
    return window.sessionStorage;
  } catch {
    return null;
  }
}

function write(attempt: Attempt | null) {
  memory = attempt;
  const target = store();
  try {
    if (!target) return;
    if (attempt) target.setItem(STORAGE_KEY, JSON.stringify(attempt));
    else target.removeItem(STORAGE_KEY);
  } catch {
    /* storage may be blocked: the in-memory copy still serves this page */
  }
}

export function loadAttempt(now = Date.now()): Attempt | null {
  let found = memory;
  if (!found) {
    try {
      const raw = store()?.getItem(STORAGE_KEY);
      const parsed = raw ? (JSON.parse(raw) as Partial<Attempt>) : null;
      if (
        parsed &&
        typeof parsed.key === "string" &&
        typeof parsed.expiresAt === "number" &&
        typeof parsed.intent === "boolean"
      )
        found = { key: parsed.key, expiresAt: parsed.expiresAt, intent: parsed.intent };
    } catch {
      found = null;
    }
  }
  if (found && found.expiresAt <= now) {
    write(null);
    return null;
  }
  return found;
}

/** An explicit CTA starts (or resumes within ten minutes) one attempt with a stable key. */
export function beginAttempt(now = Date.now()): Attempt {
  return loadAttempt(now) ?? persist({ key: crypto.randomUUID(), expiresAt: now + TTL_MS, intent: false });
}

function persist(attempt: Attempt): Attempt {
  write(attempt);
  return attempt;
}

export function clearAttempt() {
  write(null);
}

/**
 * Creates the owned intent only once per attempt (never on a retry), then asks for the trial with
 * the SAME key every time. A definitive 4xx never silently picks a new key or a new intent: the
 * visitor starts again explicitly.
 */
export async function beginOrResumeGuest(
  api: ApiClient,
  body: GuestInput,
  attempt: Attempt,
  signal: AbortSignal,
): Promise<SessionView> {
  if (!attempt.intent) {
    await api.request<void>("/auth/guest-intents", {
      method: "POST",
      body: {},
      publicWrite: true,
      guestIntent: true,
      signal,
    });
    attempt = persist({ ...attempt, intent: true });
  }
  return api.request<SessionView>("/auth/guest", {
    method: "POST",
    body,
    publicWrite: true,
    guestIntent: true,
    idempotencyKey: attempt.key,
    signal,
  });
}
