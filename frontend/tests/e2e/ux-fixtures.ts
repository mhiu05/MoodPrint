import type { Page, Request } from "@playwright/test";

// Synthetic fixtures only: no real accounts, conversations or provider calls.
export type Reply = { status?: number; json?: unknown; body?: string; contentType?: string };
export type Routes = Record<string, (request: Request) => Reply | undefined>;

export const baseSession = {
  userId: "11111111-1111-4111-8111-111111111111",
  alias: "An",
  ageBand: "adult",
  eligible: true,
  csrfToken: "csrf-ux",
  timezone: "Asia/Bangkok",
  serverTime: "2026-10-23T08:00:00Z",
  accountKind: "registered",
  guestStartedAt: null,
  guestExpiresAt: null,
  guestQuota: null,
  features: { ai: true, matching: true, voice: false, feedback: false },
  consents: {
    AI: { enabled: true, version: 1, policyVersion: "v1" },
    MEM: { enabled: true, version: 1, policyVersion: "v1" },
    MATCH: { enabled: true, version: 1, policyVersion: "v1" },
    VOICE: { enabled: false, version: 1, policyVersion: "v1" },
  },
};

export function sessionWith(consents: Partial<Record<"AI" | "MEM" | "MATCH" | "VOICE", boolean>>, patch: Record<string, unknown> = {}) {
  const next = structuredClone(baseSession) as typeof baseSession & Record<string, unknown>;
  for (const [purpose, enabled] of Object.entries(consents))
    next.consents[purpose as keyof typeof next.consents].enabled = enabled;
  return { ...next, ...patch };
}

export const bots = [
  { botId: "may", name: "Mây", role: "Lắng nghe & tâm sự", description: "Một khoảng nhỏ để được lắng nghe.", starters: ["Hôm nay mình hơi mệt"], avatarKey: "may" },
];
export const room = { id: "room-1", alias: "Bạn đồng hành 3fa9c1", status: "open", version: 1, highWaterSeq: "0", unreadCount: 0 };

export async function app(page: Page, session: unknown, routes: Routes = {}) {
  await page.route("**/api/v1/**", async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname.replace("/api/v1", "");
    const custom = routes[path]?.(request);
    if (custom)
      return custom.body !== undefined
        ? route.fulfill({ status: custom.status ?? 200, body: custom.body, contentType: custom.contentType ?? "text/plain" })
        : route.fulfill({ status: custom.status ?? 200, json: custom.json });
    const fixed: Record<string, unknown> = {
      "/session": session,
      "/bots": bots,
      "/ai/preferences": { historyEnabled: false, semanticMemoryEnabled: false, version: 1, policyVersion: "ai-data-v1", retentionDays: 30, historyAvailable: true, semanticMemoryAvailable: true },
      "/ai/conversations": [],
      "/social/summary": { pendingIncomingRequests: 0, unreadConnections: 0, activityInvites: 0 },
      "/proposals": [],
      "/memories": [],
      "/connections": [],
      "/connection-requests": [],
      "/activities/catalog": [],
      [`/connections/${room.id}`]: room,
      [`/connections/${room.id}/messages`]: { messages: [], highWaterSeq: "0" },
      [`/connections/${room.id}/activities`]: [],
      [`/connections/${room.id}/activities/current`]: null,
      [`/connections/${room.id}/reveal-requests`]: [],
      "/profiles/published/current": null,
    };
    if (request.method() === "GET" && path in fixed) return route.fulfill({ json: fixed[path] });
    return route.fulfill({ status: 404, json: { error: { code: "NOT_FOUND", message: "Missing fixture" } } });
  });
}
