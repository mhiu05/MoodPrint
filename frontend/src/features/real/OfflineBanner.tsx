import { useSyncExternalStore } from "react";
import { cx } from "../../components/UI";

function subscribe(notify: () => void) {
  window.addEventListener("online", notify);
  window.addEventListener("offline", notify);
  return () => {
    window.removeEventListener("online", notify);
    window.removeEventListener("offline", notify);
  };
}

/** Browser connectivity; writes are disabled while false (08 section 7). */
export function useOnline() {
  return useSyncExternalStore(subscribe, () => navigator.onLine, () => true);
}

/** One global banner in the shell; screens keep whatever the user was typing. */
export function OfflineBanner() {
  if (useOnline()) return null;
  return (
    <p className={cx.note} role="status">
      Mất kết nối mạng. Nội dung đang nhập vẫn được giữ.
    </p>
  );
}
