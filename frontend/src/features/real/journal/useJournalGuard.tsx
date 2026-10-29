import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button, Dialog } from "../../../components/UI";

/** HashRouter has no data-router blocker: guard links before dispatch and native history before Router. */
export function useJournalGuard(active: boolean) {
  const navigate = useNavigate();
  const [pending, setPending] = useState<(() => void) | null>(null);
  const activeRef = useRef(active);
  activeRef.current = active;
  useEffect(() => {
    const current = location.href;
    const unload = (event: BeforeUnloadEvent) => {
      if (activeRef.current) {
        event.preventDefault();
        event.returnValue = "";
      }
    };
    const click = (event: MouseEvent) => {
      if (
        !activeRef.current ||
        event.defaultPrevented ||
        event.button !== 0 ||
        event.metaKey ||
        event.ctrlKey ||
        event.shiftKey ||
        event.altKey
      )
        return;
      const anchor = (event.target as Element)?.closest<HTMLAnchorElement>(
        "a[href]",
      );
      if (
        !anchor ||
        anchor.target === "_blank" ||
        anchor.href === location.href ||
        !anchor.hash.startsWith("#/")
      )
        return;
      event.preventDefault();
      event.stopPropagation();
      setPending(() => () => navigate(anchor.hash.slice(1)));
    };
    const historyChange = (event: PopStateEvent) => {
      if (!activeRef.current || location.href === current) return;
      const target = location.hash.slice(1);
      event.stopImmediatePropagation();
      history.replaceState(null, "", current);
      setPending(() => () => navigate(target));
    };
    window.addEventListener("beforeunload", unload);
    document.addEventListener("click", click, true);
    window.addEventListener("popstate", historyChange, true);
    return () => {
      window.removeEventListener("beforeunload", unload);
      document.removeEventListener("click", click, true);
      window.removeEventListener("popstate", historyChange, true);
    };
  }, [navigate]);
  return {
    guard: (action: () => void) => {
      if (activeRef.current) setPending(() => action);
      else action();
    },
    dialog: pending ? (
      <Dialog title="Rời bản đang viết?" onClose={() => setPending(null)}>
        <p>
          Những thay đổi chưa lưu và tệp chưa tải lên sẽ bị bỏ. Bạn có thể tiếp
          tục viết để lưu bản nháp trước khi rời đi.
        </p>
        <div className="actions">
          <Button variant="secondary" onClick={() => setPending(null)}>
            Tiếp tục viết
          </Button>
          <Button
            variant="danger"
            onClick={() => {
              activeRef.current = false;
              const action = pending;
              setPending(null);
              action();
            }}
          >
            Bỏ thay đổi và rời đi
          </Button>
        </div>
      </Dialog>
    ) : null,
  };
}
