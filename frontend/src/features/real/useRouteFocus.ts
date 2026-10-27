import { useEffect } from "react";

const visible = (element: HTMLElement) =>
  element.getClientRects().length > 0 && getComputedStyle(element).visibility !== "hidden";

/**
 * Focus the heading that names the content now on screen: a heading marked
 * data-route-heading wins (an open conversation), otherwise the first visible
 * h1 in main. Hidden headings, such as a roster behind a phone conversation,
 * are skipped.
 */
export function focusRouteHeading(): boolean {
  const main = document.getElementById("main");
  if (!main) return false;
  const target = [
    ...main.querySelectorAll<HTMLElement>("[data-route-heading]"),
    ...main.querySelectorAll<HTMLElement>("h1"),
  ].find(visible);
  if (!target) return false;
  if (!target.hasAttribute("tabindex")) target.tabIndex = -1;
  target.focus({ preventScroll: true });
  return true;
}

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
