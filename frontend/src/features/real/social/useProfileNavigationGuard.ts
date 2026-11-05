import { useCallback, useEffect, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";

export type LeaveRequest = (destination: () => void) => void;
// PopState targets Window itself: registration order matters even for capture.
// This module is loaded before RealApp renders HashRouter. Register one early
// dispatcher; only the mounted profile editor owns a handler/private callback.
let profilePopHandler: ((event: PopStateEvent) => void) | null = null;
if (typeof window !== "undefined")
  window.addEventListener(
    "popstate",
    (event) => profilePopHandler?.(event),
    true,
  );
/** Scoped HashRouter guard. Undo a POP with history.go, then replay it once approved.
 * Never replace the destination entry or discard React Router's idx/key/usr state.
 */
export function useProfileNavigationGuard(active: boolean, busy: boolean) {
  const navigate = useNavigate();
  const location = useLocation();
  const [pending, setPending] = useState<(() => void) | null>(null);
  const activeRef = useRef(active);
  const busyRef = useRef(busy);
  activeRef.current = active;
  busyRef.current = busy;
  const pendingRef = useRef<(() => void) | null>(null);
  const current = useRef({
    href: window.location.href,
    idx: window.history.state?.idx as number | undefined,
  });
  const restoring = useRef(false);
  const replaying = useRef(false);
  useEffect(() => {
    if (!restoring.current)
      current.current = {
        href: window.location.href,
        idx: window.history.state?.idx,
      };
  }, [location]);
  const requestLeave = useCallback<LeaveRequest>((destination) => {
    if (!activeRef.current && !busyRef.current) {
      destination();
      return;
    }
    if (pendingRef.current) return;
    pendingRef.current = destination;
    setPending(() => destination);
  }, []);
  useEffect(() => {
    const unload = (event: BeforeUnloadEvent) => {
      if (!activeRef.current) return;
      event.preventDefault();
      event.returnValue = "";
    };
    const click = (event: MouseEvent) => {
      if (
        (!activeRef.current && !busyRef.current) ||
        event.defaultPrevented ||
        event.button !== 0 ||
        event.ctrlKey ||
        event.metaKey ||
        event.altKey ||
        event.shiftKey
      )
        return;
      const anchor = (event.target as Element)?.closest<HTMLAnchorElement>(
        "a[href]",
      );
      if (
        !anchor ||
        anchor.target === "_blank" ||
        anchor.hasAttribute("download") ||
        anchor.origin !== window.location.origin ||
        !anchor.hash.startsWith("#/") ||
        anchor.href === window.location.href
      )
        return;
      event.preventDefault();
      event.stopPropagation();
      requestLeave(() => navigate(anchor.hash.slice(1)));
    };
    const pop = (event: PopStateEvent) => {
      const targetIdx: number | undefined = event.state?.idx;
      if (replaying.current) {
        replaying.current = false;
        return;
      }
      if (restoring.current && targetIdx === current.current.idx) {
        event.stopImmediatePropagation();
        restoring.current = false;
        // Only expose confirmation once the URL and native history are restored.
        if (pendingRef.current) setPending(() => pendingRef.current);
        return;
      }
      if (
        (!activeRef.current && !busyRef.current) ||
        window.location.href === current.current.href
      )
        return;
      if (
        typeof targetIdx !== "number" ||
        typeof current.current.idx !== "number"
      )
        return;
      event.stopImmediatePropagation();
      const delta = targetIdx - current.current.idx;
      if (!delta) return;
      if (!pendingRef.current)
        pendingRef.current = () => {
          replaying.current = true;
          window.history.go(delta);
        };
      restoring.current = true;
      window.history.go(-delta);
    };
    window.addEventListener("beforeunload", unload);
    document.addEventListener("click", click, true);
    profilePopHandler = pop;
    return () => {
      window.removeEventListener("beforeunload", unload);
      document.removeEventListener("click", click, true);
      if (profilePopHandler === pop) profilePopHandler = null;
      pendingRef.current = null;
    };
  }, [navigate, requestLeave]);
  return {
    requestLeave,
    pending: Boolean(pending),
    cancel: () => {
      pendingRef.current = null;
      setPending(null);
    },
    proceed: () => {
      if (restoring.current) return;
      const destination = pendingRef.current;
      pendingRef.current = null;
      setPending(null);
      activeRef.current = false;
      destination?.();
    },
  };
}
