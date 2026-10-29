export const WARNING_MS = 5 * 60 * 1000;

/**
 * Remaining trial time from the server's own clock reading plus *monotonic* elapsed time, so a
 * refresh, a wall-clock change or a sleeping laptop can never extend the trial. Never negative.
 */
export function remainingGuestMs(
  expiresAt: string,
  serverTime: string,
  observedMonotonicMs: number,
  currentMonotonicMs: number,
): number {
  const deadline = Date.parse(expiresAt);
  const server = Date.parse(serverTime);
  if (!Number.isFinite(deadline) || !Number.isFinite(server)) return 0;
  const elapsed = Math.max(0, currentMonotonicMs - observedMonotonicMs);
  return Math.max(0, deadline - server - elapsed);
}

/** Minutes only (rounded up): the screen reader is never fed a per-second countdown. */
export function remainingLabel(ms: number): string {
  const minutes = Math.max(0, Math.ceil(ms / 60_000));
  if (minutes <= 0) return "dưới 1 phút";
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  if (hours === 0) return `${rest} phút`;
  return rest === 0 ? `${hours} giờ` : `${hours} giờ ${rest} phút`;
}
