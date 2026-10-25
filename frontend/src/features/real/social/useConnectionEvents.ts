import { useEffect, useRef } from "react";

type Handlers = {
  /** New messages may exist: fetch them through the authorized HTTP read. */
  onMessages: () => void;
  /** The room's activity watermark moved: refetch the current activity. */
  onActivity: () => void;
  /** Access ended (block, end, consent, deletion): stop everything. */
  onRevoked: () => void;
  /** Called on stream errors; the caller falls back to polling. */
  onError: () => void;
  /** Resume cursor for reconnects. */
  afterSeq: () => string;
  /** True once the tab no longer has access; no reconnects then. */
  stopped: () => boolean;
};

/**
 * One SSE subscription per room (DR-01): `messages_available` and `activity_changed`
 * carry ids only. Reconnects with exponential backoff; `healthy` tells the caller
 * whether its slower safety-net polling is enough.
 */
export function useConnectionEvents(connectionId: string | undefined, handlers: Handlers) {
  const healthy = useRef(false);
  const latest = useRef(handlers);
  latest.current = handlers;
  useEffect(() => {
    if (!connectionId) return;
    let source: EventSource | undefined,
      retry: number | undefined,
      attempt = 0,
      stopped = false,
      lastActivity = -1;
    const connect = () => {
      if (stopped || latest.current.stopped()) return;
      source = new EventSource(
        `/api/v1/connections/${connectionId}/events?afterSeq=${latest.current.afterSeq()}`,
      );
      source.addEventListener("messages_available", () => {
        attempt = 0;
        healthy.current = true;
        latest.current.onMessages();
      });
      source.addEventListener("activity_changed", (event) => {
        attempt = 0;
        healthy.current = true;
        let seq = lastActivity + 1;
        try {
          seq = Number(JSON.parse((event as MessageEvent).data).activitySeq);
        } catch {
          // A malformed envelope still means "something changed": refetch.
        }
        if (seq <= lastActivity) return; // duplicate after a reconnect
        lastActivity = seq;
        latest.current.onActivity();
      });
      source.addEventListener("access_revoked", () => {
        source?.close();
        healthy.current = false;
        stopped = true;
        latest.current.onRevoked();
      });
      source.onerror = () => {
        source?.close();
        healthy.current = false;
        latest.current.onError();
        attempt += 1;
        retry = window.setTimeout(connect, Math.min(30_000, 1000 * 2 ** attempt));
      };
    };
    connect();
    return () => {
      stopped = true;
      healthy.current = false;
      window.clearTimeout(retry);
      source?.close();
    };
  }, [connectionId]);
  return healthy;
}
