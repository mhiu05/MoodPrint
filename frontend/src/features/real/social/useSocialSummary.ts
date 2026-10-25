import { useCallback, useEffect, useState } from "react";
import type { components } from "../../../api/generated/schema";
import { useSession } from "../RealApp";

type Summary = components["schemas"]["SocialSummaryView"];

export const EMPTY_SUMMARY: Summary = {
  pendingIncomingRequests: 0,
  unreadConnections: 0,
  activityInvites: 0,
};

/** Badge counts; polled every 15 s while visible and refreshed on focus/navigation. */
export function useSocialSummary(trigger?: unknown): Summary {
  const { api, session } = useSession();
  const enabled =
    session.features.matching &&
    session.ageBand === "adult" &&
    session.consents.MATCH.enabled;
  const [summary, setSummary] = useState<Summary>(EMPTY_SUMMARY);
  const refresh = useCallback(() => {
    // Badges are advisory: a failed poll keeps the last known counts.
    api
      .request<Summary>("/social/summary")
      .then(setSummary)
      .catch(() => undefined);
  }, [api]);
  useEffect(() => {
    if (!enabled) {
      setSummary(EMPTY_SUMMARY);
      return;
    }
    refresh();
    const visible = () => {
      if (document.visibilityState === "visible") refresh();
    };
    const timer = setInterval(visible, 15_000);
    window.addEventListener("focus", refresh);
    document.addEventListener("visibilitychange", visible);
    return () => {
      clearInterval(timer);
      window.removeEventListener("focus", refresh);
      document.removeEventListener("visibilitychange", visible);
    };
  }, [enabled, refresh, trigger]);
  return enabled ? summary : EMPTY_SUMMARY;
}

export function badgeText(count: number) {
  return count > 9 ? "9+" : String(count);
}
