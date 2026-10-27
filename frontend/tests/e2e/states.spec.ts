import { expect, test, type Page, type Route } from "@playwright/test";

const session = {
  userId: "11111111-1111-4111-8111-111111111111",
  alias: "An",
  ageBand: "adult",
  eligible: true,
  csrfToken: "test-csrf",
  serverTime: "2026-10-23T08:00:00Z",
  timezone: "Asia/Bangkok",
  features: { ai: false, matching: true, voice: false },
  staff: null,
  notices: [],
  consents: Object.fromEntries(
    ["AI", "MEM", "MATCH", "VOICE"].map((p) => [
      p,
      { enabled: p === "MATCH", version: 1, policyVersion: "v1" },
    ]),
  ),
};
const PROFILE = {
  interests: ["reading", "music", "walking"],
  values: ["respect", "sincerity"],
  style: "balanced",
  goal: "friendship",
  languages: ["vi"],
  activities: [],
  availability: [],
  strictGoal: false,
};
const room = {
  id: "room-1",
  alias: "Bạn đồng hành 3fa9c1",
  status: "open",
  version: 1,
  highWaterSeq: "0",
  unreadCount: 0,
  createdAt: "2026-10-23T07:00:00Z",
};

type Handler = (route: Route, path: string) => Promise<void | false> | void | false;

/** Baseline API with every screen's data; `override` may answer a path first. */
async function mock(page: Page, override: Handler = () => false) {
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname.replace("/api/v1", "");
    if ((await override(route, path)) !== false) return;
    const json: Record<string, unknown> = {
      "/session": session,
      "/social/summary": { pendingIncomingRequests: 0, unreadConnections: 0, activityInvites: 0 },
      "/taxonomy": {
        version: "v2",
        interests: { reading: "Đọc sách", music: "Âm nhạc", walking: "Đi bộ" },
        values: { respect: "Tôn trọng", sincerity: "Chân thành" },
        languages: { vi: "Tiếng Việt" },
        styles: { balanced: "Cân bằng" },
        goals: { friendship: "Tìm bạn trò chuyện" },
        activities: {},
        availability: {},
        categories: {},
        categoryLabels: {},
        limits: { interests: [3, 10], values: [2, 4], languages: [1, 2], activities: [0, 4], availability: [0, 6] },
      },
      "/profiles/matching-draft": { profile: PROFILE, version: 1, publishedVersion: 1 },
      "/profiles/published/current": { id: "p", profile: PROFILE, version: 1, state: "live", profileVersion: 1 },
      "/matching/candidates": { candidates: [] },
      "/connection-requests": [],
      "/connections": [room],
      "/connections/room-1": room,
      "/connections/room-1/messages": { messages: [], highWaterSeq: "0" },
      "/connections/room-1/activities": [],
      "/connections/room-1/activities/current": null,
      "/connections/room-1/reveal-requests": [],
      "/activities/catalog": [
        { kind: "icebreaker", definitionVersion: "icebreaker-v1", title: "Câu hỏi làm quen", description: "Ba câu hỏi.", estimatedMinutes: 5, rounds: 3 },
      ],
      "/bots": [],
      "/ai/conversations": [],
    };
    if (path in json) return route.fulfill({ json: json[path] });
    return route.fulfill({ status: 404, json: { error: { code: "NOT_FOUND", message: "Missing" } } });
  });
}

const failure = { status: 500, json: { error: { code: "INTERNAL_ERROR", message: "Chưa hoàn tất yêu cầu. Vui lòng thử lại.", retryable: true } } };

test("offline shows one banner, disables sending and keeps the draft", async ({ page, context }) => {
  await mock(page);
  await page.goto("/#/chat/room-1");
  const composer = page.getByRole("textbox", { name: "Nhắn tin cho người bạn kết nối" });
  await composer.fill("mình đây");
  const send = page.getByRole("button", { name: "Gửi tin nhắn" });
  await expect(send).toBeEnabled();
  await context.setOffline(true);
  const banner = page.getByRole("status").filter({ hasText: "Bạn đang mất kết nối mạng. Nội dung đang nhập được giữ trên màn hình này." });
  await expect(banner).toHaveCount(1);
  await expect(send).toBeDisabled();
  await expect(send).toHaveAttribute("title", "Đang mất kết nối mạng");
  await expect(composer).toHaveValue("mình đây");
  await context.setOffline(false);
  await expect(banner).toHaveCount(0);
  await expect(send).toBeEnabled();
});

test("a failed list shows retry, and coming back online retries by itself", async ({ page, context }) => {
  let fail = true;
  await mock(page, (route, path) => (path === "/connections" && fail ? route.fulfill(failure) : false));
  await page.goto("/#/messages");
  const alert = page.getByRole("alert");
  await expect(alert).toContainText("Chưa hoàn tất yêu cầu");
  await alert.getByRole("button", { name: "Thử lại" }).click();
  await expect(alert).toContainText("Chưa hoàn tất yêu cầu");
  fail = false;
  const offlineBanner = page
    .getByRole("status")
    .filter({ hasText: "Bạn đang mất kết nối mạng. Nội dung đang nhập được giữ trên màn hình này." });
  await context.setOffline(true);
  await expect(offlineBanner).toBeVisible();
  await context.setOffline(false);
  await expect(offlineBanner).toHaveCount(0);
  await expect(page.getByRole("link", { name: /Bạn đồng hành 3fa9c1/ })).toBeVisible();
  await expect(page.getByRole("alert")).toHaveCount(0);
});

test("loading lists announce themselves", async ({ page }) => {
  let release!: () => void;
  const gate = new Promise<void>((resolve) => (release = resolve));
  await mock(page, async (route, path) => {
    if (path !== "/connections") return false;
    await gate;
    await route.fulfill({ json: [room] });
  });
  await page.goto("/#/messages");
  await expect(page.getByRole("status").filter({ hasText: "Đang tải kết nối…" })).toBeVisible();
  release();
  await expect(page.getByRole("link", { name: /Bạn đồng hành 3fa9c1/ })).toBeVisible();
});

test("empty screens say so honestly and offer one next step", async ({ page }) => {
  await mock(page, (route, path) => (path === "/connections" ? route.fulfill({ json: [] }) : false));
  await page.goto("/#/messages");
  await expect(page.getByText("Chưa có cuộc trò chuyện.")).toBeVisible();
  await expect(page.getByRole("link", { name: "Tìm người cùng điểm chung" })).toHaveAttribute(
    "href",
    "#/connect?tab=suggestions",
  );
  await page.goto("/#/connect?tab=requests");
  await expect(page.getByText("Bạn chưa có lời mời nào.")).toBeVisible();
  await page.getByRole("button", { name: "Xem gợi ý" }).click();
  await expect(page.getByRole("tab", { name: "Gợi ý" })).toHaveAttribute("aria-selected", "true");
  await expect(page.getByText("Chưa có gợi ý kết nối.", { exact: true })).toBeVisible();
  await expect(page.getByText(/Có thể hiện chưa có người cùng điểm chung/)).toBeVisible();
  await page.getByRole("button", { name: "Mở rộng hồ sơ tìm bạn" }).click();
  await expect(page.getByRole("tab", { name: "Hồ sơ tìm bạn" })).toHaveAttribute("aria-selected", "true");
});

test("with activities switched off the chat has no activity entry", async ({ page }) => {
  await mock(page, (route, path) => (path === "/activities/catalog" ? route.fulfill({ json: [] }) : false));
  await page.goto("/#/chat/room-1");
  await expect(page.getByRole("textbox", { name: "Nhắn tin cho người bạn kết nối" })).toBeEnabled();
  await expect(page.getByRole("button", { name: "Cùng làm gì đó?" })).toHaveCount(0);
});
