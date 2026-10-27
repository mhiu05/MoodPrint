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

