/** Visible, stable for two frames, bounded readiness. Never reads target text/private values. */
export function waitForTourTarget(
  selector: string,
  signal: AbortSignal,
  timeoutMs = 3000,
): Promise<HTMLElement | null> {
  if (signal.aborted) return Promise.resolve(null);
  return new Promise((resolve) => {
    let done = false,
      pending = false,
      first = 0,
      second = 0;
    let resize: ResizeObserver | undefined;
    const visible = (node: HTMLElement) => {
      const rect = node.getBoundingClientRect();
      if (!node.isConnected || rect.width <= 0 || rect.height <= 0)
        return false;
      for (
        let current: HTMLElement | null = node;
        current;
        current = current.parentElement
      ) {
        const style = getComputedStyle(current);
        if (
          current.hidden ||
          current.inert ||
          style.display === "none" ||
          style.visibility === "hidden" ||
          style.visibility === "collapse" ||
          Number(style.opacity) === 0
        )
          return false;
      }
      return true;
    };
    const finish = (node: HTMLElement | null) => {
      if (done) return;
      done = true;
      observer.disconnect();
      resize?.disconnect();
      clearTimeout(timer);
      cancelAnimationFrame(first);
      cancelAnimationFrame(second);
      signal.removeEventListener("abort", abort);
      resolve(node);
    };
    const abort = () => finish(null);
    const inspect = () => {
      if (done || pending) return;
      const node = document.querySelector<HTMLElement>(selector);
      if (!node || !visible(node)) return;
      pending = true;
      resize?.disconnect();
      resize?.observe(node);
      first = requestAnimationFrame(() => {
        const before = node.getBoundingClientRect();
        second = requestAnimationFrame(() => {
          pending = false;
          if (done || signal.aborted) return;
          const after = node.getBoundingClientRect();
          if (
            visible(node) &&
            Math.abs(before.x - after.x) < 0.5 &&
            Math.abs(before.y - after.y) < 0.5 &&
            Math.abs(before.width - after.width) < 0.5 &&
            Math.abs(before.height - after.height) < 0.5
          )
            finish(node);
          else inspect();
        });
      });
    };
    const observer = new MutationObserver(inspect);
    if (typeof ResizeObserver !== "undefined")
      resize = new ResizeObserver(inspect);
    const timer = window.setTimeout(
      () => finish(null),
      Math.min(3000, Math.max(0, timeoutMs)),
    );
    signal.addEventListener("abort", abort, { once: true });
    observer.observe(document.body, {
      childList: true,
      subtree: true,
      attributes: true,
      attributeFilter: ["hidden", "inert", "class", "style"],
    });
    inspect();
  });
}
