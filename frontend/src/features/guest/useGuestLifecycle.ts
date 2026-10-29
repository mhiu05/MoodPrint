import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ApiError, type ApiClient } from "../../api/client";
import type { SessionView } from "../../api/contracts";
import { remainingGuestMs } from "./guestClock";
import { clearTourBlockers } from "../onboarding/tourActivity";

const CHANNEL = "moodprint-guest";

/**
 * Display and cleanup clock for one guest trial. It only ever shortens the trial: the deadline is
 * the server's, observed once and advanced by monotonic time; focus/visibility/online re-read
 * /session so an expiry the server already enforced is noticed immediately. A BroadcastChannel
 * carries content-free "ended" signals between tabs (no data, no identifiers).
 */
export function useGuestLifecycle({
  session,
  api,
  onExpired,
}: {
  session: SessionView;
  api: ApiClient;
  onExpired: (reason: "expired" | "ended") => void;
}) {
  const observed = useRef(performance.now());
  const lifecycle = useRef(session.userId);
  const deadline = useRef<number | null>(null);
  const [remainingMs, setRemaining] = useState(() =>
    remainingGuestMs(session.guestExpiresAt ?? "", session.serverTime, observed.current, observed.current),
  );
  const [epoch, setEpoch] = useState(0);
  const controller = useMemo(() => new AbortController(), [session.userId]);
  const done = useRef(false);
  const expire = useCallback(
    (reason: "expired" | "ended" = "expired") => {
      if (done.current) return;
      done.current = true;
      controller.abort();
      clearTourBlockers();
      setEpoch((value) => value + 1);
      setRemaining(0);
      try {
        new BroadcastChannel(CHANNEL).postMessage({ type: reason });
      } catch {
        /* no BroadcastChannel: the other tab finds out from its own clock/session read */
      }
      onExpired(reason);
    },
    [controller, onExpired],
  );

  useEffect(() => {
    if (lifecycle.current !== session.userId) {
      lifecycle.current = session.userId;
      deadline.current = null;
      done.current = false;
    }
    if (done.current) return;
    const now = performance.now();
    const candidate = now + remainingGuestMs(session.guestExpiresAt ?? "", session.serverTime, now, now);
    // Parent renders and delayed session replies can only shorten the original grant.
    // In particular, a focus-triggered revision must not reset an old server-time anchor.
    deadline.current = deadline.current === null ? candidate : Math.min(deadline.current, candidate);
    const tick = () => {
      const left = Math.max(0, deadline.current! - performance.now());
      setRemaining(left);
      if (left <= 0) expire("expired");
    };
    tick();
    // Minute display only; the hard stop is a one-shot timer at the deadline itself.
    const interval = window.setInterval(tick, 15_000);
    const left = Math.max(0, deadline.current - performance.now());
    const stop = window.setTimeout(() => expire("expired"), Math.max(0, left));
    return () => {
      window.clearInterval(interval);
      window.clearTimeout(stop);
    };
  }, [session.guestExpiresAt, session.serverTime, session.userId, expire]);

  useEffect(() => {
    let scheduled: number | undefined;
    const verify = () => {
      if (document.visibilityState !== "visible" || done.current) return;
      window.clearTimeout(scheduled);
      scheduled = window.setTimeout(() => {
        api
          .request<SessionView>("/session", { signal: controller.signal })
          .catch((reason) => {
            if (reason instanceof ApiError && reason.status === 401) expire("expired");
          });
      }, 100);
    };
    window.addEventListener("focus", verify);
    window.addEventListener("online", verify);
    document.addEventListener("visibilitychange", verify);
    let channel: BroadcastChannel | null = null;
    try {
      channel = new BroadcastChannel(CHANNEL);
      channel.onmessage = (event) => {
        if (event.data?.type === "expired" || event.data?.type === "ended")
          expire(event.data.type);
      };
    } catch {
      channel = null;
    }
    return () => {
      window.clearTimeout(scheduled);
      window.removeEventListener("focus", verify);
      window.removeEventListener("online", verify);
      document.removeEventListener("visibilitychange", verify);
      channel?.close();
    };
  }, [api, controller, expire]);

  return { remainingMs, epoch, signal: controller.signal, expire };
}
