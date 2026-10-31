import { test, expect, type Page, type Request } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { baseSession, guestSession } from "./ux-fixtures";

// P2-08 companion collaboration (E2E-17..19 UI contract). Synthetic fixtures only: every API
// call is intercepted. The real execution path is covered by the fullstack spec.
const CONV = "88888888-8888-4888-8888-888888888888";
const RUN = "99999999-9999-4999-8999-999999999999";
const NEW_RUN = "99999999-9999-4999-8999-99999999999a";
const LINE = {
  kind: "nhip_energy_for_rure",
  companions: ["nhip", "rure"],
  summary: "Nhịp đã gợi ý mức năng lượng phù hợp với bạn. Rủ Rê đã dựa vào đó để chọn hoạt động này.",
};
const session = { ...baseSession, features: { ...baseSession.features, proactive: true, collaboration: true } };
const bots = [
  { botId: "rure", name: "Rủ Rê", role: "Học hỏi & cùng chơi", description: "Chơi một chút.", starters: [], avatarKey: "rure" },
  { botId: "nhip", name: "Nhịp", role: "Cảm xúc & thói quen", description: "Chậm một nhịp.", starters: [], avatarKey: "nhip" },
  { botId: "may", name: "Mây", role: "Lắng nghe", description: "Lắng nghe.", starters: [], avatarKey: "may" },
  { botId: "guong", name: "Gương", role: "Khám phá", description: "Khám phá.", starters: [], avatarKey: "guong" },
  { botId: "caunoi", name: "Cầu Nối", role: "Kết nối", description: "Kết nối.", starters: [], avatarKey: "caunoi" },
];
const prefs = { historyEnabled: true, semanticMemoryEnabled: false, version: 1, policyVersion: "ai-data-v1", retentionDays: 30, historyAvailable: true, semanticMemoryAvailable: true };
const now = "2026-10-31T08:00:00Z";
const TECH = /agent|tool|handoff|delegation|\brun\b|model|digest|specialist|receipt/i;

type Message = Record<string, unknown>;
function bubble(id: string, text: string, index: number, count: number, collaboration: unknown = null, run = RUN): Message {
  return { id, actor: "bot", text, cards: [], createdAt: now, runId: run, status: "completed", partIndex: index, partCount: count, origin: "user", proactiveSlot: null, collaboration };
}
function thread(messages: Message[]) {
  return { conversationId: CONV, botId: "rure", version: messages.length + 1, persistent: true, title: "Chơi gì nhẹ nhàng", expiresAt: "2026-11-26T08:00:00Z", createdAt: now, updatedAt: now, messages, hasMoreMessages: false, activeRunId: null, activeRunVersion: null };
}
const history = () => thread([
  { id: "c0000000-0000-4000-8000-000000000001", actor: "self", text: "Gợi ý gì nhẹ nhàng hợp với mình hôm nay", cards: [], createdAt: now, runId: RUN, status: "completed", partIndex: 0, partCount: 1, origin: "user", proactiveSlot: null, collaboration: null },
  bubble("c0000000-0000-4000-8000-000000000002", "Thử nhắm mắt đếm xem nghe được mấy âm thanh trong 2 phút nhé.", 0, 2, LINE),
  bubble("c0000000-0000-4000-8000-000000000003", "Đếm được bao nhiêu thì kể mình nghe nhé!", 1, 2),
]);

function sse(events: { type: string; data?: unknown }[]) {
  return events.map((event, index) => `id: ${index + 1}\ndata: ${JSON.stringify({ version: "ai-events-v2", seq: String(index + 1), type: event.type, data: event.data ?? {} })}\n\n`).join("");
}

type Sharing = { edge: string; requester: string; specialist: string; enabled: boolean; version: number; requires: string[]; available: boolean; reason: string | null };
function sharingView(journal = false): { available: boolean; edges: Sharing[] } {
  return {
    available: true,
    edges: [
      { edge: "nhip_energy_for_rure", requester: "rure", specialist: "nhip", enabled: false, version: 0, requires: ["journal_context"], available: journal, reason: journal ? null : "journal_context_off" },
      { edge: "nhip_habit_for_may", requester: "may", specialist: "nhip", enabled: false, version: 0, requires: [], available: true, reason: null },
      { edge: "rure_activity_for_guong", requester: "guong", specialist: "rure", enabled: false, version: 0, requires: [], available: true, reason: null },
    ],
  };
}

async function mount(page: Page, options: { conversation?: ReturnType<typeof thread>; sess?: unknown; live?: { collaboration: unknown; consulting: boolean }; sharing?: ReturnType<typeof sharingView>; sharingError?: string } = {}) {
  const seen = { writes: [] as { path: string; body: unknown }[] };
  let conversation = options.conversation ?? history();
  let sharing = options.sharing ?? sharingView();
  let failNext = options.sharingError;
  await page.route("**/api/v1/**", async (route) => {
    const request: Request = route.request();
    const url = new URL(request.url());
    const path = url.pathname.replace("/api/v1", "");
    const method = request.method();
    const json = (body: unknown, status = 200) => route.fulfill({ status, json: body });
    if (method !== "GET") seen.writes.push({ path, body: request.postDataJSON() });
    const edge = path.match(/^\/ai\/sharing\/(\w+)$/);
    if (edge && method === "PUT") {
      if (failNext) {
        const code = failNext;
        failNext = undefined;
        return json({ error: { code, message: code } }, 409);
      }
      const body = request.postDataJSON();
      sharing = { ...sharing, edges: sharing.edges.map((e) => (e.edge === edge[1] ? { ...e, enabled: body.enabled, version: e.version + 1 } : e)) };
      return json(sharing);
    }
    if (path === `/ai/conversations/${CONV}/messages` && method === "POST") {
      const body = request.postDataJSON();
      conversation = thread([...conversation.messages, { id: body.clientMessageId, actor: "self", text: body.text, cards: [], createdAt: now, runId: NEW_RUN, status: "completed", partIndex: 0, partCount: 1, origin: "user", proactiveSlot: null, collaboration: null }]);
      return json({ runId: NEW_RUN, conversationId: CONV, version: conversation.version, runVersion: 1, eventsUrl: `/api/v1/ai/runs/${NEW_RUN}/events` }, 202);
    }
    if (path === `/ai/runs/${NEW_RUN}/events` && options.live) {
      const ids = ["d0000000-0000-4000-8000-000000000001", "d0000000-0000-4000-8000-000000000002"];
      const texts = ["Sáng nay thử một thử thách nhỏ thôi nhé.", "Ngồi yên đếm âm thanh trong 2 phút."];
      conversation = thread([...conversation.messages, ...texts.map((text, index) => bubble(ids[index], text, index, 2, index === 0 ? options.live!.collaboration : null, NEW_RUN))]);
      const events = [
        { type: "progress" },
        ...(options.live.consulting ? [{ type: "progress", data: { activity: "consulting", companion: "nhip" } }, { type: "progress", data: { activity: "composing" } }] : []),
        { type: "final", data: { partCount: 2, messages: texts.map((text, index) => ({ messageId: ids[index], partIndex: index, text, cards: [] })), collaboration: options.live.collaboration } },
        { type: "completed" },
      ];
      return route.fulfill({ contentType: "text/event-stream", body: sse(events) }).catch(() => undefined);
    }
    const fixed: Record<string, unknown> = {
      "/session": options.sess ?? session,
      "/bots": bots,
      "/ai/preferences": prefs,
      "/ai/conversations": [conversation],
      [`/ai/conversations/${CONV}`]: conversation,
      "/ai/sharing": sharing,
      "/ai/inbox": { badgesEnabled: true, unreadTotal: 0, bots: [] },
      "/ai/proactive": { available: false, settings: { timezone: "Asia/Ho_Chi_Minh", quietStart: "22:00", quietEnd: "07:00", badgesEnabled: true, journalContextEnabled: false, version: 0, policyVersion: "proactive-v1" }, schedules: [], limits: { dailyCap: 4, enabledSlots: 0, windows: { morning: ["05:00", "11:30"], evening: ["17:00", "22:30"] }, stepMinutes: 15 } },
      "/social/summary": { pendingIncomingRequests: 0, unreadConnections: 0, activityInvites: 0 },
      "/proposals": [], "/memories": [], "/connections": [], "/connection-requests": [], "/activities/catalog": [],
      "/profiles/published/current": null,
    };
    if (method === "GET" && path in fixed) return json(fixed[path]);
    return json({ error: { code: "NOT_FOUND", message: `Missing synthetic fixture ${path}` } }, 404);
  });
  return seen;
}

async function open(page: Page, reload = false) {
  await page.goto(`/#/assistants/rure?conversation=${CONV}`);
  // A hash-only navigation keeps the running app; re-mounted fixtures need a fresh document.
  if (reload) await page.reload();
  await expect(page.getByRole("textbox", { name: "Tin nhắn cho Rủ Rê" })).toBeVisible();
  await expect(page.getByText("Đang mở cuộc trò chuyện…")).toHaveCount(0);
}
const group = (page: Page) => page.getByRole("group", { name: "Tin nhắn từ Rủ Rê, 2 phần" });

async function noHorizontalOverflow(page: Page) {
  expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(1);
}

for (const width of [1440, 768, 390, 360]) {
  test(`history shows the receipt-backed line inside its reply group at ${width}px (S6)`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    await mount(page);
    await open(page);
    const line = group(page).locator(".collaboration-line");
    await expect(line).toHaveCount(1);
    await expect(line).toContainText(LINE.summary);
    // Read before the first bubble, inside the group, with decorative avatars hidden.
    const order = await group(page).evaluate((element) => Array.from(element.children).map((child) => child.className));
    expect(order[0]).toContain("collaboration-line");
    await expect(line.locator(".collaboration-avatars")).toHaveAttribute("aria-hidden", "true");
    const why = line.getByRole("button", { name: "Vì sao?" });
    const box = await why.boundingBox();
    expect(box!.height).toBeGreaterThanOrEqual(44);
    await noHorizontalOverflow(page);
    expect((await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze()).violations).toEqual([]);
  });
}

test("the why sheet opens and closes with the keyboard and explains only kinds of data", async ({ page }) => {
  await mount(page);
  await open(page);
  const why = group(page).getByRole("button", { name: "Vì sao?" });
  await why.focus();
  await page.keyboard.press("Enter");
  const dialog = page.getByRole("dialog", { name: "Vì sao Rủ Rê chọn hoạt động này?" });
  await expect(dialog).toBeVisible();
  await expect(dialog).toContainText("mức năng lượng");
  await expect(dialog).toContainText("không thấy nhật ký");
  // Never the shared values themselves (OD-10) and never technical vocabulary.
  expect(await dialog.innerText()).not.toMatch(/thấp, 5 phút|energy=|low/);
  expect(await dialog.innerText()).not.toMatch(TECH);
  await expect(dialog.getByRole("link", { name: "Đổi cài đặt phối hợp" })).toHaveAttribute("href", "#/companion-sharing");
  expect((await new AxeBuilder({ page }).include("dialog").withTags(["wcag2a", "wcag2aa"]).analyze()).violations).toEqual([]);
  await page.keyboard.press("Escape");
  await expect(dialog).toHaveCount(0);
  await expect(why).toBeFocused();
});

test("a turn without a receipt shows no line (S0) and the flag off hides stored lines", async ({ page }) => {
  const plain = thread([bubble("e0000000-0000-4000-8000-000000000001", "Chơi đố vui nhé!", 0, 1)]);
  await mount(page, { conversation: plain });
  await open(page);
  await expect(page.getByText("Chơi đố vui nhé!")).toBeVisible();
  await expect(page.locator(".collaboration-line")).toHaveCount(0);
  await page.unrouteAll({ behavior: "ignoreErrors" });
  await mount(page, { sess: { ...session, features: { ...session.features, collaboration: false } } });
  await open(page, true);
  await expect(group(page)).toBeVisible();
  await expect(page.locator(".collaboration-line")).toHaveCount(0);
});

test("a live collaborative turn adds the line only from the validated final (S1-S3)", async ({ page }) => {
  await mount(page, { conversation: thread([]), live: { collaboration: LINE, consulting: true } });
  await open(page);
  await page.getByRole("textbox", { name: "Tin nhắn cho Rủ Rê" }).fill("Gợi ý gì nhẹ nhàng hợp với mình hôm nay");
  await page.getByRole("button", { name: "Gửi tin cho AI", exact: true }).click();
  await expect(group(page).locator(".collaboration-line")).toContainText(LINE.summary);
  await expect(page.getByRole("status").filter({ hasText: "đang hỏi" })).toHaveCount(0);
});

test("a failed consultation shows the ordinary reply without any collaboration hint (S4)", async ({ page }) => {
  await mount(page, { conversation: thread([]), live: { collaboration: null, consulting: true } });
  await open(page);
  await page.getByRole("textbox", { name: "Tin nhắn cho Rủ Rê" }).fill("Gợi ý gì nhẹ nhàng hợp với mình hôm nay");
  await page.getByRole("button", { name: "Gửi tin cho AI", exact: true }).click();
  await expect(group(page)).toBeVisible();
  await expect(page.locator(".collaboration-line")).toHaveCount(0);
  await expect(page.getByText(/lỗi phối hợp|Nhịp không/)).toHaveCount(0);
});

for (const width of [1440, 768, 390, 360]) {
  test(`sharing settings: three default-off switches, plain words, accessible at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    await mount(page);
    await page.goto("/#/companion-sharing");
    await expect(page.getByRole("heading", { level: 1, name: "Trợ lý phối hợp với nhau" })).toBeVisible();
    const switches = page.getByRole("switch");
    await expect(switches).toHaveCount(3);
    for (const index of [0, 1, 2]) await expect(switches.nth(index)).not.toBeChecked();
    await expect(page.getByText("Cầu Nối không nhận thông tin từ trợ lý khác.")).toBeVisible();
    const energy = page.getByRole("switch", { name: "Nhịp gợi ý mức năng lượng cho Rủ Rê" });
    await expect(energy).toHaveAttribute("aria-disabled", "true");
    await expect(page.getByRole("link", { name: "Mở Lịch hỏi thăm" })).toBeVisible();
    expect(await page.locator("main").innerText()).not.toMatch(TECH);
    await noHorizontalOverflow(page);
    expect((await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze()).violations).toEqual([]);
  });
}

test("turning an edge on saves just that edge and keeps keyboard focus", async ({ page }) => {
  const seen = await mount(page);
  await page.goto("/#/companion-sharing");
  const habit = page.getByRole("switch", { name: "Nhịp gợi ý thói quen nhỏ cho Mây" });
  await habit.focus();
  await page.keyboard.press("Space");
  await expect(habit).toBeChecked();
  await expect(page.getByRole("status").filter({ hasText: "Đã bật." })).toBeVisible();
  await expect(habit).toBeFocused();
  expect(seen.writes).toEqual([{ path: "/ai/sharing/nhip_habit_for_may", body: { enabled: true, expectedVersion: 0, policyVersion: "sharing-v1" } }]);
  const energy = page.getByRole("switch", { name: "Nhịp gợi ý mức năng lượng cho Rủ Rê" });
  await energy.click({ force: true });
  await expect(energy).not.toBeChecked();
  expect(seen.writes).toHaveLength(1);
});

test("a stale save reloads and explains, and the switch matches the server", async ({ page }) => {
  await mount(page, { sharingError: "STALE_VERSION" });
  await page.goto("/#/companion-sharing");
  const habit = page.getByRole("switch", { name: "Nhịp gợi ý thói quen nhỏ cho Mây" });
  await habit.click();
  await expect(page.getByText("Cài đặt vừa thay đổi ở nơi khác.", { exact: false })).toBeVisible();
  await expect(habit).not.toBeChecked();
});

test("account page links to the sharing settings only when the feature is open", async ({ page }) => {
  await mount(page);
  await page.goto("/#/profile");
  await expect(page.getByRole("link", { name: "Cài đặt phối hợp" })).toHaveAttribute("href", "#/companion-sharing");
  await page.unrouteAll({ behavior: "ignoreErrors" });
  await mount(page, { sess: baseSession });
  await page.goto("/#/profile");
  await page.reload();
  await expect(page.getByRole("heading", { level: 1, name: "Tài khoản" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Cài đặt phối hợp" })).toHaveCount(0);
});

test("guests never reach the sharing page", async ({ page }) => {
  await mount(page, { sess: guestSession(3_600_000) });
  await page.goto("/#/companion-sharing");
  await expect(page.getByRole("switch")).toHaveCount(0);
});

test("reduced motion renders the line statically", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await mount(page);
  await open(page);
  const line = group(page).locator(".collaboration-line");
  await expect(line).toBeVisible();
  const animations = await line.evaluate((element) => element.getAnimations({ subtree: true }).length);
  expect(animations).toBe(0);
});
