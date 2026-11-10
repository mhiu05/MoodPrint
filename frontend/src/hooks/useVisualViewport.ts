import { useEffect } from "react";
export function useVisualViewport() {
  useEffect(() => {
    const viewport = window.visualViewport;
    if (!viewport) return;
    const update = () => {
      const editing = document.activeElement?.matches("input, textarea");
      const inset = Math.max(
        0,
        window.innerHeight - viewport.height - viewport.offsetTop,
      );
      document.documentElement.style.setProperty(
        "--keyboard-inset",
        `${editing ? inset : 0}px`,
      );
      document.documentElement.dataset.keyboardOpen = String(
        !!editing && inset > 100,
      );
      document.documentElement.style.setProperty(
        "--visual-viewport-height",
        `${viewport.height}px`,
      );
      document.documentElement.style.setProperty(
        "--visual-viewport-top",
        `${viewport.offsetTop}px`,
      );
    };
    viewport.addEventListener("resize", update);
    viewport.addEventListener("scroll", update);
    document.addEventListener("focusin", update);
    document.addEventListener("focusout", update);
    update();
    return () => {
      viewport.removeEventListener("resize", update);
      viewport.removeEventListener("scroll", update);
      document.removeEventListener("focusin", update);
      document.removeEventListener("focusout", update);
      document.documentElement.style.removeProperty("--visual-viewport-height");
      document.documentElement.style.removeProperty("--visual-viewport-top");
    };
  }, []);
}
