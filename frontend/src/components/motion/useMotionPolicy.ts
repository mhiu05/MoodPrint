import { useEffect, useState } from "react";

const REDUCED = "(prefers-reduced-motion: reduce)";

/** Motion is decoration: it runs only when allowed and actually visible. */
export function resolveMotionPolicy(reduced: boolean, visible: boolean): { animate: boolean } {
  return { animate: !reduced && visible };
}

function readReduced() {
  return typeof window !== "undefined" && typeof window.matchMedia === "function"
    ? window.matchMedia(REDUCED).matches
    : false;
}

function readVisible() {
  return typeof document === "undefined" || document.visibilityState === "visible";
}

/**
 * Reduced-motion and page-visibility state, read before the first render and
 * kept current. Never infers devices or tasks; callers decide what to animate.
 */
export function useMotionPolicy(): { reduced: boolean; visible: boolean; animate: boolean } {
  const [reduced, setReduced] = useState(readReduced);
  const [visible, setVisible] = useState(readVisible);
  useEffect(() => {
    const media = window.matchMedia(REDUCED);
    const mediaChange = () => setReduced(media.matches);
    const visibility = () => setVisible(readVisible());
    mediaChange();
    visibility();
    media.addEventListener("change", mediaChange);
    document.addEventListener("visibilitychange", visibility);
    return () => {
      media.removeEventListener("change", mediaChange);
      document.removeEventListener("visibilitychange", visibility);
    };
  }, []);
  return { reduced, visible, ...resolveMotionPolicy(reduced, visible) };
}
