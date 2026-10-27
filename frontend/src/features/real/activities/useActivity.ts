import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError } from "../../../api/client";
import { useSession } from "../RealApp";
import { createClock, type Clock } from "./clock";
import { isOpen, type Definition, type Kind, type Session } from "./activityView";

const CHANGED = ["ACTIVITY_CHANGED", "ROUND_CHANGED", "ACTIVITY_IN_PROGRESS"];

/**
 * Server-authoritative activity state for one room. Refetches on `activity_changed`,
 * on tab focus and (while the event stream is down) every 3 s; nothing is stored in
 * browser storage. A 409 refreshes and shows a notice instead of an error.
 */
export function useActivity(
  connectionId: string | undefined,
  streamHealthy: { current: boolean },
  enabled: boolean,
) {
  const { api } = useSession();
  const [session, setSession] = useState<Session | null>(null);
  const [catalog, setCatalog] = useState<Definition[]>([]);
  // An empty catalog means activities are switched off; a failed read is not that.
  const [catalogStatus, setCatalogStatus] = useState<"loading" | "ready" | "empty" | "error">("loading");
  const [catalogError, setCatalogError] = useState<unknown>();
  const [catalogRevision, setCatalogRevision] = useState(0);
  const [inviteError, setInviteError] = useState<{ kind: Kind; error: unknown }>();
  const [error, setError] = useState<unknown>();
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [clock, setClock] = useState<Clock>(() => createClock(new Date().toISOString()));
  const [cooldown, setCooldown] = useState<Partial<Record<Kind, number>>>({});
  const loading = useRef(false);
  const lastRefresh = useRef(0);

  const receive = useCallback((value: Session | null) => {
    setSession(value);
    if (value) setClock(createClock(value.serverTime));
  }, []);

  const refresh = useCallback(async () => {
    if (!connectionId || !enabled || loading.current) return;
    loading.current = true;
    lastRefresh.current = Date.now();
    try {
      receive(
        await api.request<Session | null>(`/connections/${connectionId}/activities/current`),
      );
      setError(undefined);
    } catch (reason) {
      // A revoked room is handled by the chat itself; keep other errors visible.
      if (!(reason instanceof ApiError && [403, 404].includes(reason.status))) setError(reason);
    } finally {
      loading.current = false;
    }
  }, [api, connectionId, enabled, receive]);

  useEffect(() => {
    if (!enabled) return;
    const controller = new AbortController();
    setCatalogStatus("loading");
    setCatalogError(undefined);
    api
      .request<Definition[]>("/activities/catalog", { signal: controller.signal })
      .then((value) => {
        if (controller.signal.aborted) return;
        setCatalog(value);
        setCatalogStatus(value.length ? "ready" : "empty");
      })
      .catch((reason) => {
        if (controller.signal.aborted) return;
        setCatalogError(reason);
        setCatalogStatus("error");
      });
    return () => controller.abort();
  }, [api, enabled, catalogRevision]);
  const reloadCatalog = useCallback(() => setCatalogRevision((value) => value + 1), []);

  useEffect(() => {
    setSession(null);
    void refresh();
    const timer = setInterval(() => {
      if (document.visibilityState !== "visible" || streamHealthy.current) return;
      if (Date.now() - lastRefresh.current >= 2_900) void refresh();
    }, 3000);
    const visible = () => {
      if (document.visibilityState === "visible") void refresh();
    };
    document.addEventListener("visibilitychange", visible);
    return () => {
      clearInterval(timer);
      document.removeEventListener("visibilitychange", visible);
    };
  }, [refresh, streamHealthy]);

  async function send<T>(path: string, body: unknown): Promise<T | undefined> {
    if (busy) return undefined;
    setBusy(true);
    setError(undefined);
    setNotice("");
    try {
      return await api.request<T>(path, { method: "POST", body });
    } catch (reason) {
      if (reason instanceof ApiError && CHANGED.includes(reason.code)) {
        setNotice("Trạng thái vừa thay đổi, đã cập nhật.");
        await refresh();
      } else if (reason instanceof ApiError && reason.code === "ACTIVITY_COOLDOWN") {
        setNotice(reason.message);
      } else setError(reason);
      throw reason;
    } finally {
      setBusy(false);
    }
  }

  /** POST /activities/{id}/{op}; returns true when applied. */
  const act = async (op: string, body: Record<string, unknown> = {}) => {
    if (!session) return false;
    try {
      const result = await send<Session>(`/activities/${session.id}/${op}`, {
        expectedVersion: session.version,
        ...body,
      });
      if (result) receive(result);
      return Boolean(result);
    } catch {
      return false;
    }
  };

  const invite = async (kind: Kind, options?: Record<string, unknown>) => {
    if (!connectionId) return false;
    setInviteError(undefined);
    try {
      const result = await send<Session>(`/connections/${connectionId}/activities`, {
        kind,
        ...(options ? { options } : {}),
      });
      if (result) receive(result);
      return Boolean(result);
    } catch (reason) {
      if (reason instanceof ApiError && reason.code === "ACTIVITY_COOLDOWN") {
        const seconds = Number(reason.retryAfter || 600);
        setCooldown((value) => ({ ...value, [kind]: Date.now() + seconds * 1000 }));
      } else if (!(reason instanceof ApiError && CHANGED.includes(reason.code))) {
        // Shown inside the catalog next to the chosen activity, which stays open.
        setInviteError({ kind, error: reason });
        setError(undefined);
      }
      return false;
    }
  };

  const feedback = async (rating: string) => {
    if (!session) return false;
    try {
      await send(`/activities/${session.id}/feedback`, { rating });
      await refresh();
      return true;
    } catch {
      return false;
    }
  };

  return {
    session,
    open: isOpen(session),
    catalog,
    catalogStatus,
    catalogError,
    reloadCatalog,
    inviteError,
    clearInviteError: () => setInviteError(undefined),
    clock,
    cooldown,
    busy,
    error,
    notice,
    setNotice,
    refresh,
    act,
    invite,
    feedback,
    dismiss: () => setSession(null),
  };
}

export type ActivityState = ReturnType<typeof useActivity>;
