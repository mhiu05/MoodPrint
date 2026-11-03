import { useEffect, useRef, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { Dialog } from "../../../components/UI";

/** A child dialog escapes the compact info dialog, which stays mounted but closed. */
export function CheckInDialog(props: { title: string; children: ReactNode; onClose: () => void; destructive?: boolean }) {
  return createPortal(<Dialog {...props} />, document.body);
}

export function useCheckInDialog(onChildModalChange?: (open: boolean) => void) {
  const trigger = useRef<HTMLElement | null>(null);
  const isOpen = useRef(false);
  const notify = useRef(onChildModalChange);
  notify.current = onChildModalChange;
  useEffect(() => () => { if (isOpen.current) notify.current?.(false); }, []);
  return (open: boolean) => {
    isOpen.current = open;
    if (open) trigger.current = document.activeElement as HTMLElement;
    onChildModalChange?.(open);
    if (!open) requestAnimationFrame(() => {
      // Parent reopens the compact panel before returning to the exact child trigger.
      if (trigger.current?.isConnected) trigger.current.focus();
    });
  };
}
