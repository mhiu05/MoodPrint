import { useSyncExternalStore } from "react";
const subscribe = (callback: () => void) => {
  const query = matchMedia("(prefers-reduced-motion: reduce)");
  query.addEventListener("change", callback);
  return () => query.removeEventListener("change", callback);
};
export function useReducedMotion() {
  return useSyncExternalStore(
    subscribe,
    () => matchMedia("(prefers-reduced-motion: reduce)").matches,
    () => true,
  );
}
