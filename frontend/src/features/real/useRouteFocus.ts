import { useEffect } from "react";
import { focusRouteHeading } from "../../components/focusHeading";

export { focusRouteHeading };

/**
 * After a route change, move focus once to the destination heading as soon as it
 * renders. Stops if the person moves focus themselves, so late data never steals it.
 */
export function useRouteFocus(key: string) {
  useEffect(() => {
    const main = document.getElementById("main");
    if (!main) return;
    const start = document.activeElement;
    let done = false;
    const stop = () => {
      done = true;
      observer.disconnect();
      window.clearTimeout(timer);
    };
    const attempt = () => {
      if (done) return;
      const active = document.activeElement;
      const moved = active && active !== start && active !== document.body && active !== main;
      if (moved || focusRouteHeading()) stop();
    };
    const observer = new MutationObserver(attempt);
    const timer = window.setTimeout(stop, 4000);
    observer.observe(main, { childList: true, subtree: true, attributes: true, attributeFilter: ["class", "hidden"] });
    attempt();
    return stop;
  }, [key]);
}
