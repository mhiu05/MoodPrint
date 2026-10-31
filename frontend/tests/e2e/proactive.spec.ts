import { test, expect, type Page, type Request } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { baseSession, guestSession } from "./ux-fixtures";

// P1-16/P1-17 check-ins. Synthetic fixtures only: every API call is intercepted, so this proves
// the UI contract, not real integration (that is the fullstack spec's job).
const CONV = "44444444-4444-4444-8444-444444444444";
const RUN = "55555555-5555-4555-8555-555555555555";
const session = { ...baseSession, features: { ...baseSession.features, proactive: true } };
const bots = [
  { botId: "nhip", name: "Nhịp", role: "Cảm xúc & thói quen", description: "Chậm một nhịp.", starters: [], avatarKey: "nhip" },
  { botId: "rure", name: "Rủ Rê", role: "Học hỏi & cùng chơi", description: "Chơi một chút.", starters: [], avatarKey: "rure" },
  { botId: "may", name: "Mây", role: "Lắng nghe & tâm sự", description: "Lắng nghe.", starters: [], avatarKey: "may" },
  { botId: "guong", name: "Gương", role: "Khám phá bản thân", description: "Khám phá.", starters: [], avatarKey: "guong" },
  { botId: "caunoi", name: "Cầu Nối", role: "Tìm bạn đồng điệu", description: "Kết nối.", starters: [], avatarKey: "caunoi" },
];
const prefs = { historyEnabled: true, semanticMemoryEnabled: false, version: 1, policyVersion: "ai-data-v1", retentionDays: 30, historyAvailable: true, semanticMemoryAvailable: true };

type Schedule = Record<string, unknown> & { botId: string; slot: string; enabled: boolean; version: number };

function proactiveView(overrides: { enabled?: [string, string][]; available?: boolean; caunoi?: string | null } = {}) {
  const enabled = new Set((overrides.enabled ?? [["nhip", "morning"]]).map(([b, s]) => `${b}/${s}`));
  const schedules: Schedule[] = [];
  for (const bot of ["nhip", "rure", "may", "guong", "caunoi"]) {
    for (const slot of ["morning", "evening"]) {
      const on = enabled.has(`${bot}/${slot}`);
      const reason = bot === "caunoi" ? (overrides.caunoi === undefined ? "social_not_enabled" : overrides.caunoi) : null;
      schedules.push({
        botId: bot, slot, enabled: on, localTime: slot === "morning" ? "07:30" : "20:00", weekdays: [1, 2, 3, 4, 5, 6, 7],
        pausedUntil: null, autoPaused: false, nextDeliveryAt: on ? "2026-11-01T00:30:00Z" : null, version: on ? 1 : 0,
        eligibility: { allowed: reason === null, reason },
      });
    }
  }
  return {
    available: overrides.available ?? true,
    settings: { timezone: "Asia/Ho_Chi_Minh", quietStart: "22:00", quietEnd: "07:00", badgesEnabled: true, journalContextEnabled: false, version: 1, policyVersion: "proactive-v1" },
    schedules,
    limits: { dailyCap: 4, enabledSlots: enabled.size, windows: { morning: ["05:00", "11:30"], evening: ["17:00", "22:30"] }, stepMinutes: 15 },
  };
}

const inbox = {
  badgesEnabled: true,
  unreadTotal: 2,
  bots: [
    { botId: "nhip", unread: 1, latest: { conversationId: CONV, runId: RUN, slot: "morning", deliveredAt: "2026-10-31T00:31:00Z", firstSequence: 2 } },
    { botId: "rure", unread: 1, latest: { conversationId: "66666666-6666-4666-8666-666666666666", runId: "77777777-7777-4777-8777-777777777777", slot: "morning", deliveredAt: "2026-10-31T00:45:00Z", firstSequence: 4 } },
  ],
};
const EMPTY_INBOX = { badgesEnabled: true, unreadTotal: 0, bots: [] };

const thread = {
  conversationId: CONV, botId: "nhip", version: 3, persistent: true, title: "Lời hỏi thăm buổi sáng 31/10",
  expiresAt: "2026-11-26T08:00:00Z", createdAt: "2026-10-31T00:31:00Z", updatedAt: "2026-10-31T00:31:00Z",
  hasMoreMessages: false, activeRunId: null, activeRunVersion: null,
  messages: [
    { id: "a0000000-0000-4000-8000-000000000001", actor: "bot", text: "Chào buổi sáng! Hôm qua bạn có ghi là thấy khá mệt.", cards: [], createdAt: "2026-10-31T00:31:00Z", runId: RUN, status: "completed", partIndex: 0, partCount: 2, origin: "proactive", proactiveSlot: "morning" },
    { id: "a0000000-0000-4000-8000-000000000002", actor: "bot", text: "Hôm nay thử nghỉ mắt 10 phút sau bữa trưa nhé.", cards: [], createdAt: "2026-10-31T00:31:00Z", runId: RUN, status: "completed", partIndex: 1, partCount: 2, origin: "proactive", proactiveSlot: "morning" },
  ],
};

type Seen = { writes: { method: string; path: string; body: unknown }[] };

async function mount(page: Page, options: { view?: ReturnType<typeof proactiveView>; inbox?: typeof inbox | typeof EMPTY_INBOX; scheduleError?: string; sess?: unknown } = {}) {
  const seen: Seen = { writes: [] };
  let view = options.view ?? proactiveView();
  let currentInbox: typeof inbox | typeof EMPTY_INBOX = options.inbox ?? EMPTY_INBOX;
  let failNext = options.scheduleError;
  await page.route("**/api/v1/**", async (route) => {
    const request: Request = route.request();
    const path = new URL(request.url()).pathname.replace("/api/v1", "");
    const method = request.method();
    const json = (body: unknown, status = 200) => route.fulfill({ status, json: body });
    if (method !== "GET") seen.writes.push({ method, path, body: request.postDataJSON() });
    const schedule = path.match(/^\/ai\/proactive\/schedules\/(\w+)\/(\w+)$/);
    if (schedule && method === "PUT") {
      if (failNext) {
        const code = failNext;
        failNext = undefined;
        return json({ error: { code, message: code } }, code === "STALE_VERSION" ? 409 : 422);
      }
      const body = request.postDataJSON();
      const current = view.schedules.find((s) => s.botId === schedule[1] && s.slot === schedule[2])!;
      const next = { ...current, ...body, version: current.version + 1, nextDeliveryAt: body.enabled ? "2026-11-01T00:30:00Z" : null };
      delete (next as Record<string, unknown>).expectedVersion;
      view = { ...view, schedules: view.schedules.map((s) => (s === current ? next : s)) };
      view.limits = { ...view.limits, enabledSlots: view.schedules.filter((s) => s.enabled).length };
      // Like the API: the first saved schedule creates the settings row.
      if (view.settings.version === 0) view = { ...view, settings: { ...view.settings, version: 1 } };
      return json(next);
    }
    if (path === "/ai/proactive/settings" && method === "PUT") {
      const { expectedVersion, ...body } = request.postDataJSON();
      if (expectedVersion !== view.settings.version) return json({ error: { code: "STALE_VERSION", message: "stale" } }, 409);
      view = { ...view, settings: { ...view.settings, ...body, version: view.settings.version + 1 } };
      return json(view.settings);
    }
    if (path === "/ai/inbox/read-all" && method === "POST") {
      currentInbox = EMPTY_INBOX;
      return json(currentInbox);
    }
    if (path === `/ai/conversations/${CONV}/read` && method === "PUT") {
      currentInbox = { ...inbox, unreadTotal: 1, bots: inbox.bots.filter((b) => b.botId !== "nhip") };
      return json({ conversationId: CONV, lastReadSequence: thread.version });
    }
    const fixed: Record<string, unknown> = {
      "/session": options.sess ?? session,
      "/bots": bots,
      "/ai/preferences": prefs,
      "/ai/proactive": view,
      "/ai/inbox": currentInbox,
      "/ai/conversations": [thread],
      [`/ai/conversations/${CONV}`]: thread,
      "/social/summary": { pendingIncomingRequests: 0, unreadConnections: 0, activityInvites: 0 },
      "/proposals": [], "/memories": [], "/connections": [], "/connection-requests": [], "/activities/catalog": [],
      "/profiles/published/current": null,
    };
    if (method === "GET" && path in fixed) return json(fixed[path]);
    return json({ error: { code: "NOT_FOUND", message: `Missing synthetic fixture ${path}` } }, 404);
  });
  return seen;
}

async function noHorizontalOverflow(page: Page) {
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow).toBeLessThanOrEqual(1);
}

for (const width of [1440, 768, 390, 360]) {
  test(`check-in schedule page is usable and accessible at ${width}px`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width, height: 900 });
    await mount(page);
    await page.goto("/#/check-ins");
    await expect(page.getByRole("heading", { level: 1, name: "Lời hỏi thăm từ trợ lý" })).toBeVisible();
    await expect(page.getByText("Đang dùng 1/4")).toBeVisible();
    await expect(page.getByText("Múi giờ: Việt Nam (GMT+7)")).toBeVisible();
    const morning = page.getByRole("region", { name: "Nhịp" }).getByRole("switch", { name: /Buổi sáng/ });
    await expect(morning).toBeChecked();
    await expect(page.getByText("Lần tới:", { exact: false }).first()).toBeVisible();
    await expect(page.getByRole("region", { name: "Cầu Nối" }).getByText("Cần bật tính năng kết nối để Cầu Nối hỏi thăm.")).toBeVisible();
    await noHorizontalOverflow(page);
    const box = await morning.boundingBox();
    expect(box!.width).toBeGreaterThanOrEqual(44);
    expect((await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze()).violations).toEqual([]);
    await page.screenshot({ path: testInfo.outputPath(`check-ins-${width}.png`), fullPage: true });
  });
}

test("turning a check-in on saves immediately and announces it", async ({ page }) => {
  const seen = await mount(page);
  await page.goto("/#/check-ins");
  await page.getByRole("region", { name: "Mây" }).getByRole("switch", { name: /Buổi tối/ }).click();
  await expect(page.getByRole("region", { name: "Mây" }).getByRole("status")).toHaveText("Đã lưu");
  const write = seen.writes.find((w) => w.path === "/ai/proactive/schedules/may/evening");
  expect(write?.body).toEqual({ enabled: true, localTime: "20:00", weekdays: [1, 2, 3, 4, 5, 6, 7], pausedUntil: null, expectedVersion: 0 });
  await expect(page.getByText("Đang dùng 2/4")).toBeVisible();
  // Times inside quiet hours are not offered.
  const times = await page.getByRole("region", { name: "Mây" }).getByLabel("Giờ nhắn").locator("option").allTextContents();
  expect(times).toContain("21:45");
  expect(times).not.toContain("22:00");
});

test("the fifth check-in is blocked with a clear reason", async ({ page }) => {
  await mount(page, { view: proactiveView({ enabled: [["nhip", "morning"], ["nhip", "evening"], ["may", "morning"], ["may", "evening"]] }) });
  await page.goto("/#/check-ins");
  const blocked = page.getByRole("region", { name: "Rủ Rê" }).getByRole("switch", { name: /Buổi sáng/ });
  await expect(blocked).toHaveAttribute("aria-disabled", "true");
  await expect(page.getByRole("region", { name: "Rủ Rê" }).getByText("Bạn đã dùng 4 lời hỏi thăm mỗi ngày. Tắt một lời khác để bật lời này.").first()).toBeVisible();
});

test("a stale schedule reloads and explains what happened", async ({ page }) => {
  await mount(page, { scheduleError: "STALE_VERSION" });
  await page.goto("/#/check-ins");
  await page.getByRole("region", { name: "Gương" }).getByRole("switch", { name: /Buổi sáng/ }).click();
  await expect(page.getByRole("region", { name: "Gương" }).getByRole("status")).toHaveText("Lịch vừa được thay đổi ở nơi khác. Mình đã tải lại để bạn xem.");
  // The optimistic switch went back to the server's state.
  await expect(page.getByRole("region", { name: "Gương" }).getByRole("switch", { name: /Buổi sáng/ })).not.toBeChecked();
});

test("journal use is opt-in and explained before it is enabled", async ({ page }) => {
  const seen = await mount(page);
  await page.goto("/#/check-ins");
  const optIn = page.getByRole("checkbox", { name: "Dùng khoảnh khắc đã lưu hôm qua" });
  await expect(optIn).not.toBeChecked();
  await page.getByRole("button", { name: "Tìm hiểu thêm" }).click();
  const dialog = page.getByRole("dialog", { name: "Nhịp dùng khoảnh khắc hôm qua như thế nào?" });
  await expect(dialog).toContainText("không đọc bản nháp");
  await page.keyboard.press("Escape");
  await expect(dialog).toBeHidden();
  await optIn.click();
  await expect(optIn).toBeChecked();
  const write = seen.writes.find((w) => w.path === "/ai/proactive/settings");
  expect(write?.body).toMatchObject({ journalContextEnabled: true, policyVersion: "proactive-v1", expectedVersion: 1 });
});

test("a closed feature and a guest get no settings", async ({ page }) => {
  await mount(page, { view: proactiveView({ available: false }) });
  await page.goto("/#/check-ins");
  await expect(page.getByRole("heading", { name: "Lời hỏi thăm chưa mở cho tài khoản của bạn." })).toBeVisible();
  await page.unrouteAll({ behavior: "ignoreErrors" });
  await mount(page, { sess: guestSession(3_600_000) });
  await page.goto("/#/check-ins");
  await expect(page.getByRole("switch")).toHaveCount(0);
});

test("unread check-ins badge the assistants tab and list without previews", async ({ page }) => {
  const seen = await mount(page, { inbox });
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/#/assistants");
  await expect(page.getByRole("link", { name: "Trợ lý, 2 lời nhắn mới" })).toBeVisible();
  const section = page.getByRole("region", { name: "Lời nhắn mới" });
  await expect(section.getByRole("link", { name: "Nhịp · Lời hỏi thăm buổi sáng · 07:31" })).toBeVisible();
  await expect(section).not.toContainText("khá mệt");
  await expect(page.getByRole("link", { name: "Nhịp, AI, Cảm xúc & thói quen, 1 lời nhắn mới" })).toBeVisible();
  await section.getByRole("button", { name: "Đánh dấu đã đọc tất cả" }).click();
  await expect(section).toBeHidden();
  expect(seen.writes.some((w) => w.path === "/ai/inbox/read-all")).toBe(true);
});

test("a check-in in chat is labelled, links to its schedule and is marked read", async ({ page }) => {
  const seen = await mount(page, { inbox });
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto(`/#/assistants/nhip?conversation=${CONV}`);
  await expect(page.getByText("Lời hỏi thăm buổi sáng · 07:31")).toBeVisible();
  await expect(page.getByText("Lời hỏi thăm buổi sáng từ Nhịp lúc 07:31")).toBeAttached();
  await expect(page.getByRole("group", { name: "Tin nhắn từ Nhịp, 2 phần" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Đổi hoặc tắt lời hỏi thăm này" })).toHaveAttribute("href", "#/check-ins?bot=nhip");
  await expect.poll(() => seen.writes.find((w) => w.path === `/ai/conversations/${CONV}/read`)?.body).toEqual({ lastReadSequence: 3 });
  await expect(page.getByRole("link", { name: "Trợ lý, 1 lời nhắn mới" })).toBeAttached();
});

test("on a phone the back button signals check-ins from other companions", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await mount(page, { inbox });
  await page.goto(`/#/assistants/nhip?conversation=${CONV}`);
  await expect(page.getByRole("link", { name: "Về danh sách trợ lý, có 1 lời nhắn mới" })).toBeVisible();
  await noHorizontalOverflow(page);
});

test("the account page links to the schedule", async ({ page }) => {
  await mount(page);
  await page.goto("/#/profile");
  await expect(page.getByRole("heading", { name: "Lời hỏi thăm từ trợ lý" })).toBeVisible();
  await expect(page.getByText("1 lời hỏi thăm mỗi ngày, vào giờ bạn chọn.")).toBeVisible();
  await page.getByRole("link", { name: "Chỉnh lịch hỏi thăm" }).click();
  await expect(page).toHaveURL(/#\/check-ins$/);
});

test("the first schedule creates settings and the next settings change still saves", async ({ page }) => {
  const fresh = proactiveView({ enabled: [] });
  fresh.settings.version = 0;
  const seen = await mount(page, { view: fresh });
  await page.goto("/#/check-ins");
  await page.getByRole("region", { name: "Nhịp" }).getByRole("switch", { name: /Buổi sáng/ }).click();
  await expect(page.getByRole("region", { name: "Nhịp" }).getByRole("status")).toHaveText("Đã lưu");
  const optIn = page.getByRole("checkbox", { name: "Dùng khoảnh khắc đã lưu hôm qua" });
  await optIn.click();
  await expect(page.getByRole("region", { name: "Nhịp" }).getByRole("status")).toHaveText("Đã lưu");
  await expect(optIn).toBeChecked();
  const write = seen.writes.filter((w) => w.path === "/ai/proactive/settings").at(-1);
  expect(write?.body).toMatchObject({ journalContextEnabled: true, expectedVersion: 1 });
});

test("keyboard focus stays on a control after it saves", async ({ page }) => {
  await mount(page);
  await page.goto("/#/check-ins");
  const evening = page.getByRole("region", { name: "Mây" }).getByRole("switch", { name: /Buổi tối/ });
  await evening.focus();
  await page.keyboard.press("Space");
  await expect(page.getByRole("region", { name: "Mây" }).getByRole("status")).toHaveText("Đã lưu");
  await expect(evening).toBeFocused();
  const time = page.getByRole("region", { name: "Mây" }).getByLabel("Giờ nhắn");
  await time.focus();
  await time.selectOption("21:00");
  await expect(page.getByRole("region", { name: "Mây" }).getByRole("status")).toHaveText("Đã lưu");
  await expect(time).toBeFocused();
});
