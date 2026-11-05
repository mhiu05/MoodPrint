/**
 * Server-anchored clock: countdowns use server time, never the device clock alone.
 * offset = serverTime - local receive time; re-created on every fetch or event.
 */
export type Clock = { offset: number; now(): number };

export function createClock(serverTime: string, receivedAt = Date.now()): Clock {
  const offset = Date.parse(serverTime) - receivedAt;
  return { offset, now: () => Date.now() + offset };
}

export function remainingMs(endsAt: string, clock: Clock) {
  return Math.max(0, Date.parse(endsAt) - clock.now());
}

export function formatCountdown(ms: number) {
  const total = Math.ceil(ms / 1000);
  const minutes = Math.floor(total / 60);
  const seconds = total % 60;
  return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
}
