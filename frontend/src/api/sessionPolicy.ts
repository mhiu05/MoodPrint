import { ApiError } from "./client";

export const SESSION_ATTEMPTS = 3;
export const SESSION_BUDGET_MS = 20_000;
export const SESSION_ATTEMPT_TIMEOUT_MS = 8_000;
export const SESSION_GRACE_MS = 30_000;

export type SessionFailureKind =
  | "unauthorized"
  | "forbidden"
  | "transient"
  | "invalid"
  | "cancelled";

export type SessionFailure = {
  kind: SessionFailureKind;
  retryAfterMs?: number;
};

function retryAfterMs(header: string | null, nowMs: number): number | undefined {
  if (!header) return undefined;
  const seconds = Number(header);
  if (Number.isFinite(seconds) && seconds >= 0 && header.trim() !== "")
    return Math.round(seconds * 1000);
  const parsed = Date.parse(header);
  if (Number.isFinite(parsed)) return Math.max(0, parsed - nowMs);
  return undefined;
}

export function classifySessionFailure(reason: unknown, nowMs: number): SessionFailure {
  if (reason instanceof DOMException && reason.name === "AbortError")
    return { kind: "cancelled" };
  if (reason instanceof TypeError) return { kind: "transient" };
  if (!(reason instanceof ApiError)) return { kind: "invalid" };
  if (reason.code === "INVALID_SESSION") return { kind: "invalid" };
  if (reason.code === "REQUEST_TIMEOUT" || reason.code === "NETWORK_UNAVAILABLE")
    return { kind: "transient" };
  if (reason.status === 401) return { kind: "unauthorized" };
  if (reason.status === 403) return { kind: "forbidden" };
  const retryAfter = retryAfterMs(reason.retryAfter, nowMs);
  if (reason.status === 429)
    return { kind: "transient", ...(retryAfter !== undefined ? { retryAfterMs: retryAfter } : {}) };
  if (reason.status === 502 || reason.status === 503 || reason.status === 504)
    return { kind: "transient", ...(retryAfter !== undefined ? { retryAfterMs: retryAfter } : {}) };
  if (reason.status >= 500 && reason.retryable !== false) return { kind: "transient" };
  if (reason.status === 0) return { kind: "transient" };
  return { kind: "invalid" };
}

/** Full jitter. Attempt 1 waits at most 500 ms; later attempts at most 1 s. */
export function sessionRetryDelayMs(attempt: number, random: number): number {
  const cap = attempt <= 1 ? 500 : 1000;
  const unit = Math.min(1, Math.max(0, random));
  return Math.floor(unit * cap);
}

export function attemptTimeoutMs(
  elapsedMs: number,
  budgetMs = SESSION_BUDGET_MS,
  capMs = SESSION_ATTEMPT_TIMEOUT_MS,
): number {
  const remaining = budgetMs - elapsedMs;
  if (remaining <= 0) return 0;
  return Math.min(capMs, remaining);
}

export function shouldContinueSessionRetry(input: {
  attempt: number;
  elapsedMs: number;
  delayMs: number;
  budgetMs?: number;
}): boolean {
  const budget = input.budgetMs ?? SESSION_BUDGET_MS;
  if (input.attempt >= SESSION_ATTEMPTS) return false;
  if (input.elapsedMs >= budget) return false;
  if (input.delayMs > budget - input.elapsedMs) return false;
  return true;
}

/** The first failure anchors the grace window. Later calls must not move it. */
export function rememberGraceStart(existing: number | null, nowMs: number): number {
  return existing ?? nowMs;
}

export function graceExpired(
  startMs: number | null,
  nowMs: number,
  graceMs = SESSION_GRACE_MS,
): boolean {
  return startMs !== null && nowMs - startMs >= graceMs;
}

export type RevalidateStatus = "ok" | "failed" | "stopped";

function wait(ms: number, signal: AbortSignal): Promise<void> {
  if (signal.aborted) return Promise.reject(new DOMException("Aborted", "AbortError"));
  if (ms <= 0) return Promise.resolve();
  return new Promise((resolve, reject) => {
    const timer = setTimeout(finish, ms);
    const onAbort = () => {
      clearTimeout(timer);
      signal.removeEventListener("abort", onAbort);
      reject(new DOMException("Aborted", "AbortError"));
    };
    signal.addEventListener("abort", onAbort, { once: true });
    function finish() {
      signal.removeEventListener("abort", onAbort);
      resolve();
    }
  });
}

/**
 * One session-read cycle. Callers keep a single in-flight cycle; this function
 * does not retry writes, login, or any other route.
 */
export async function revalidateSession(options: {
  request: (timeoutMs: number, signal: AbortSignal) => Promise<void>;
  signal: AbortSignal;
  isCurrent: () => boolean;
  onTransient: (error: unknown) => void;
  onSuccess: () => void;
  onUnauthorized: (error: ApiError) => void;
  onForbidden: (error: ApiError) => void;
  onInvalid: (error: unknown) => void;
  random?: () => number;
  now?: () => number;
  sleep?: (ms: number, signal: AbortSignal) => Promise<void>;
  clock?: () => number;
}): Promise<RevalidateStatus> {
  const now = options.now ?? (() => performance.now());
  const clock = options.clock ?? (() => Date.now());
  const random = options.random ?? Math.random;
  const sleep = options.sleep ?? wait;
  const started = now();
  let attempt = 0;
  while (options.isCurrent() && !options.signal.aborted) {
    attempt += 1;
    const timeoutMs = attemptTimeoutMs(now() - started);
    if (attempt > SESSION_ATTEMPTS || timeoutMs <= 0) return "failed";
    try {
      await options.request(timeoutMs, options.signal);
      if (!options.isCurrent() || options.signal.aborted) return "stopped";
      options.onSuccess();
      return "ok";
    } catch (reason) {
      if (!options.isCurrent() || options.signal.aborted) return "stopped";
      const failure = classifySessionFailure(reason, clock());
      if (failure.kind === "cancelled") return "stopped";
      if (failure.kind === "unauthorized" && reason instanceof ApiError) {
        options.onUnauthorized(reason);
        return "stopped";
      }
      if (failure.kind === "forbidden" && reason instanceof ApiError) {
        options.onForbidden(reason);
        return "stopped";
      }
      if (failure.kind === "invalid") {
        options.onInvalid(reason);
        return "stopped";
      }
      options.onTransient(reason);
      const delay = failure.retryAfterMs ?? sessionRetryDelayMs(attempt, random());
      if (
        !shouldContinueSessionRetry({
          attempt,
          elapsedMs: now() - started,
          delayMs: delay,
        })
      )
        return "failed";
      try {
        await sleep(delay, options.signal);
      } catch {
        return "stopped";
      }
    }
  }
  return "stopped";
}
