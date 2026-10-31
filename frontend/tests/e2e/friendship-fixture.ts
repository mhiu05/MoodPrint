import type { Page } from "@playwright/test";
import taxonomy from "../../../backend/app/modules/profiles/taxonomy_v2.json" with { type: "json" };

export { taxonomy as FRIENDSHIP_TAXONOMY };
export const LEGACY = {
  interests: [
    "reading",
    "music",
    "coffee",
    "walking",
    "running",
    "cycling",
    "yoga",
    "football",
    "badminton",
    "drawing",
  ],
  values: ["respect", "sincerity"],
  languages: ["vi", "en"],
  style: "direct",
  goal: "language-practice",
  activities: ["focus"],
  availability: ["weekday_evening"],
  strictGoal: true,
};
export async function friendshipFixture(
  page: Page,
  initial?: Record<string, unknown>,
  live = false,
) {
  const state = {
    profile: initial ?? {
      interests: [],
      values: [],
      languages: [],
      style: "balanced",
      goal: "friendship",
      activities: [],
      availability: [],
      strictGoal: false,
    },
    version: initial ? 2 : 0,
    publication: live ? 7 : 0,
    live,
    writes: [] as {
      path: string;
      body: Record<string, unknown>;
      key: string;
    }[],
    failSave: false,
    staleSave: false,
    expirePreview: false,
    candidates: [] as Record<string, unknown>[],
  };
  await page.route("**/api/v1/**", async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname.replace("/api/v1", "");
    const method = request.method();
    if (method !== "GET")
      state.writes.push({
        path,
        body: request.postData() ? request.postDataJSON() : {},
        key: request.headers()["idempotency-key"],
      });
    const error = (code: string, status = 409) =>
      route.fulfill({ status, json: { error: { code, message: code } } });
    if (path === "/session")
      return route.fulfill({
        json: {
          userId: "11111111-1111-4111-8111-111111111111",
          alias: "Private Name",
          accountKind: "registered",
          ageBand: "adult",
          eligible: true,
          csrfToken: "csrf",
          serverTime: "2026-10-31T08:00:00Z",
          timezone: "Asia/Bangkok",
          notices: [],
          staff: null,
          features: { ai: false, matching: true, voice: false },
          consents: Object.fromEntries(
            ["AI", "MEM", "MATCH", "VOICE"].map((p) => [
              p,
              {
                enabled: p === "MATCH" && state.live,
                version: 1,
                policyVersion: "v1",
              },
            ]),
          ),
        },
      });
    if (path === "/taxonomy") return route.fulfill({ json: taxonomy });
    if (path === "/profiles/matching-draft") {
      if (method === "PUT") {
        if (state.failSave) return error("NETWORK_ERROR", 503);
        if (state.staleSave) return error("STALE_VERSION");
        const { expectedVersion, ...profile } = request.postDataJSON();
        if (expectedVersion !== state.version) return error("STALE_VERSION");
        state.version++;
        state.profile = profile;
      }
      return route.fulfill({
        json: {
          profile: state.profile,
          version: state.version,
          publishedVersion: state.publication,
        },
      });
    }
    if (path === "/profiles/matching-draft/preview")
      return route.fulfill({
        json: {
          profile: state.profile,
          draftVersion: state.version,
          previewDigest: `token-${state.version}`,
        },
      });
    if (path === "/profiles/published" && method === "POST") {
      if (state.expirePreview) return error("PREVIEW_CHANGED");
      state.publication++;
      state.live = true;
      return route.fulfill({
        status: 201,
        json: {
          id: "public",
          profile: state.profile,
          version: state.publication,
          profileVersion: state.publication,
          state: "live",
        },
      });
    }
    if (path === "/profiles/published/current")
      return route.fulfill({
        json: state.live
          ? {
              id: "public",
              profile: initial ?? state.profile,
              version: state.publication,
              profileVersion: state.publication,
              state: "live",
            }
          : null,
      });
    if (path === "/matching/candidates")
      return route.fulfill({ json: { candidates: state.candidates } });
    if (path === "/social/summary")
      return route.fulfill({
        json: {
          pendingIncomingRequests: 0,
          unreadConnections: 0,
          activityInvites: 0,
        },
      });
    if (
      [
        "/connection-requests",
        "/connections",
        "/bots",
        "/ai/conversations",
        "/journal/entries",
      ].includes(path)
    )
      return route.fulfill({ json: [] });
    return route.fulfill({
      status: 404,
      json: { error: { code: "NOT_FOUND", message: "Missing fixture" } },
    });
  });
  return state;
}
