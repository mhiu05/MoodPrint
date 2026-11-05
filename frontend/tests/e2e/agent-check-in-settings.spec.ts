import { expect, test, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { baseSession } from "./ux-fixtures";

// Every endpoint is intercepted. These fixtures prove UI contracts, never provider delivery.
const agents = [
  { botId: "dieuphoi", name: "Điều phối", role: "Cùng bạn tìm hướng đi", description: "Trợ lý chủ quản", starters: [], avatarKey: "dieuphoi" },
  { botId: "nhatky", name: "Nhật ký", role: "Nhìn lại cảm xúc", description: "Lắng nghe mỗi ngày", starters: [], avatarKey: "nhatky" },
  { botId: "hoatdong", name: "Hoạt động", role: "Học hỏi và cùng chơi", description: "Thử một việc nhỏ", starters: [], avatarKey: "hoatdong" },
];
const legacyBots = [
  { botId: "nhip", name: "Nhịp", role: "Cảm xúc", description: "Lịch cũ", starters: [], avatarKey: "nhip" },
  { botId: "caunoi", name: "Cầu Nối", role: "Kết nối", description: "Lịch cũ", starters: [], avatarKey: "caunoi" },
];
type Schedule = {
  botId: string; slot: string; enabled: boolean; localTime: string; weekdays: number[];
  version: number; pausedUntil: string | null; autoPaused: boolean; nextDeliveryAt: string | null;
  eligibility: { allowed: boolean; reason: string | null }; legacy: boolean; migrateTo: string | null;
};
function fixture() {
  return {
    available: true,
    settings: { timezone: "Asia/Bangkok", quietStart: "22:00", quietEnd: "07:00", badgesEnabled: true, journalContextEnabled: true, version: 1, policyVersion: "proactive-v1" },
    schedules: [...agents, ...legacyBots].flatMap((bot) => ["morning", "evening"].map((slot): Schedule => ({
      botId: bot.botId, slot, enabled: bot.botId === "nhatky" || bot.botId === "hoatdong",
      localTime: slot === "morning" ? "07:30" : "20:00", weekdays: [1,2,3,4,5,6,7], version: 1,
      pausedUntil: bot.botId === "nhatky" && slot === "morning" ? "2026-11-05" : null,
      autoPaused: bot.botId === "nhatky" && slot === "evening",
      nextDeliveryAt: "2026-11-04T00:30:00Z", eligibility: { allowed: true, reason: null },
      legacy: ["nhip", "caunoi"].includes(bot.botId), migrateTo: bot.botId === "nhip" ? "nhatky" : null,
    }))),
    limits: { dailyCap: 4, enabledSlots: 4, windows: { morning: ["05:00", "11:30"], evening: ["17:00", "22:30"] }, stepMinutes: 15 },
  };
}

const CONV = "66666666-6666-4666-8666-666666666666";
async function mount(page: Page, options: { staleSettings?: boolean; view?: ReturnType<typeof fixture>; handoff?: boolean } = {}) {
  let view = options.view ?? fixture();
  const writes: { path: string; method: string; body: Record<string, unknown> }[] = [];
  let stale = options.staleSettings;
  await page.route("**/api/v1/**", async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname.replace("/api/v1", "");
    const method = request.method();
    const json = (body: unknown, status = 200) => route.fulfill({ status, json: body });
    if (method !== "GET") writes.push({ path, method, body: request.postDataJSON() });
    if (path === `/ai/conversations/${CONV}/read` && method === "PUT") return json({ conversationId: CONV, lastReadSequence: 2 });
    if (path === "/ai/proactive/settings" && method === "PUT") {
      if (stale) {
        stale = false;
        view = { ...view, settings: { ...view.settings, journalContextEnabled: false, version: 8 } };
        return json({ error: { code: "STALE_VERSION", message: "Changed in another tab" } }, 409);
      }
      const { expectedVersion, ...patch } = request.postDataJSON();
      if (expectedVersion !== view.settings.version) return json({ error: { code: "STALE_VERSION", message: "stale" } }, 409);
      view = { ...view, settings: { ...view.settings, ...patch, version: view.settings.version + 1 } };
      return json(view.settings);
    }
    const schedule = path.match(/^\/ai\/proactive\/schedules\/(\w+)\/(\w+)(\/migrate)?$/);
    if (schedule && method !== "GET") {
      const current = view.schedules.find((item) => item.botId === schedule[1] && item.slot === schedule[2])!;
      if (method === "DELETE") { current.enabled = false; current.version = 0; return json({ status: "ok" }); }
      if (schedule[3]) {
        const target = view.schedules.find((item) => item.botId === current.migrateTo && item.slot === current.slot)!;
        Object.assign(target, { enabled: true, localTime: current.localTime, weekdays: current.weekdays, version: target.version + 1 });
        current.enabled = false; current.version = 0;
        return json(target);
      }
      const { expectedVersion: _version, ...patch } = request.postDataJSON();
      Object.assign(current, patch, { version: current.version + 1 });
      if (patch.enabled === true) current.autoPaused = false;
      view.limits.enabledSlots = view.schedules.filter((item) => item.enabled && !item.legacy).length;
      return json(current);
    }
    const thread = { conversationId: CONV, botId: "dieuphoi", activeAgent: "hoatdong", version: 2, persistent: true, title: "Chọn hoạt động", expiresAt: "2026-12-01T00:00:00Z", createdAt: "2026-11-01T08:00:00Z", updatedAt: "2026-11-01T08:00:00Z", hasMoreMessages: false, activeRunId: null, activeRunVersion: null,
      messages: [{ id: "77777777-7777-4777-8777-777777777777", actor: "bot", text: "Thử đếm các âm thanh quanh bạn nhé.", speaker: "hoatdong", cards: [], createdAt: "2026-11-01T08:00:00Z", status: "completed", partIndex: 0, partCount: 1, origin: "user", proactiveSlot: null }] };
    const fixed: Record<string, unknown> = {
      "/public/experience": { guestAvailable: false, captchaSiteKey: null, authCaptchaRequired: false },
      "/session": { ...baseSession, features: { ...baseSession.features, proactive: true, threeAgents: true } },
      "/bots": agents, "/bots/legacy": legacyBots,
      "/ai/preferences": { historyEnabled: true, semanticMemoryEnabled: false, version: 1, policyVersion: "ai-data-v1", retentionDays: 30, historyAvailable: true, semanticMemoryAvailable: true },
      "/ai/proactive": view,
      "/ai/inbox": { badgesEnabled: true, unreadTotal: 0, bots: [] },
      "/ai/conversations": options.handoff ? [thread] : [], [`/ai/conversations/${CONV}`]: thread, "/proposals": [], "/memories": [],
      "/social/summary": { pendingIncomingRequests: 0, unreadConnections: 0, activityInvites: 0 },
      "/connections": [], "/connection-requests": [], "/activities/catalog": [], "/profiles/published/current": null,
    };
    if (method === "GET" && path in fixed) return json(fixed[path]);
    return json({ error: { code: "NOT_FOUND", message: `Missing fixture ${path}` } }, 404);
  });
  return { writes };
}
const open = (page: Page, bot = "dieuphoi") => page.goto(`/#/assistants/${bot}?panel=info&section=check-ins`);

test("paused schedules show their actual state and can resume from the selector", async ({ page }) => {
  const seen = await mount(page);
  await open(page, "nhatky");
  const pause = page.getByRole("combobox", { name: "Tạm dừng", exact: true }).first();
  await expect(pause).toHaveValue("paused");
  await expect(pause.getByRole("option", { name: "Đang tạm dừng đến hết 05/11" })).toHaveAttribute("disabled", "");
  await pause.selectOption("");
  await expect.poll(() => seen.writes.filter((write) => write.path.endsWith("/nhatky/morning")).length).toBe(1);
  expect(seen.writes[0].body).toMatchObject({ pausedUntil: null, expectedVersion: 1 });
  await expect(page.getByText("Đang tạm dừng đến hết 05/11.")).toHaveCount(0);
  await expect(pause).toHaveValue("");
});

test("evening quiet-hour help opens the shared editor and returns keyboard focus", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await mount(page);
  await open(page, "nhatky");
  const help = page.getByRole("button", { name: "Muốn chọn muộn hơn? Đổi giờ yên lặng" });
  await help.focus();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("dialog", { name: "Dùng chung cho mọi trợ lý", exact: true })).toBeVisible();
  await expect(page.locator("dialog:modal")).toHaveCount(1);
  await page.keyboard.press("Escape");
  await expect(help).toBeFocused();
});

test("deep-linked schedule headings stay below the info header at desktop and enlarged text", async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  await page.emulateMedia({ reducedMotion: "reduce" });
  await mount(page);
  await open(page, "nhatky");
  const heading = page.getByRole("heading", { name: "Lời hỏi thăm của Nhật ký" });
  await expect(heading).toBeFocused();
  const clearance = () => heading.evaluate((element) => element.getBoundingClientRect().top - element.closest("dialog")!.querySelector(".conversation-info-header")!.getBoundingClientRect().bottom);
  await expect.poll(clearance).toBeGreaterThanOrEqual(0);
  await page.addStyleTag({ content: "html { font-size: 200% !important; }" });
  await heading.evaluate((element) => element.scrollIntoView({ block: "start" }));
  await expect.poll(clearance).toBeGreaterThanOrEqual(0);
  await page.screenshot({ path: testInfo.outputPath("agent-check-ins-200-percent.png"), fullPage: true });
});

test("each agent owns two slots before the first chat and only Nhật ký owns consent", async ({ page }) => {
  const seen = await mount(page);
  for (const agent of agents) {
    await open(page, agent.botId);
    const section = page.getByRole("region", { name: `Lời hỏi thăm của ${agent.name}` });
    await expect(section).toBeVisible();
    await expect(section.getByRole("switch")).toHaveCount(2);
    await expect(page.locator(".conversation-info")).toHaveAttribute("data-bot-id", agent.botId);
    await expect(section.getByRole("checkbox", { name: "Dùng khoảnh khắc đã lưu hôm qua" })).toHaveCount(agent.botId === "nhatky" ? 1 : 0);
    await expect(section).toContainText("Đang dùng 4/4 trên toàn tài khoản");
  }
  expect(seen.writes).toEqual([]);
});

test("a specialist speaker leaves schedule ownership with the route owner", async ({ page }) => {
  const seen = await mount(page, { handoff: true });
  await page.goto(`/#/assistants/dieuphoi?conversation=${CONV}&panel=info&section=check-ins`);
  const owner = page.getByRole("region", { name: "Lời hỏi thăm của Điều phối" });
  await expect(owner).toBeVisible();
  await expect(page.locator(".conversation-info")).toHaveAttribute("data-bot-id", "dieuphoi");
  await expect(owner.getByRole("switch")).toHaveCount(2);
  await expect(page.getByRole("region", { name: "Lời hỏi thăm của Hoạt động" })).toHaveCount(0);
  await page.getByRole("button", { name: "Đóng thông tin cuộc trò chuyện" }).click();
  await expect(page.getByText("Bạn đang trò chuyện trực tiếp với", { exact: false })).toBeVisible();
  await page.getByRole("link", { name: "Thông tin Hoạt động", exact: true }).click();
  await expect(page.getByRole("region", { name: "Lời hỏi thăm của Hoạt động" })).toBeVisible();
  expect(seen.writes.filter((write) => write.path.startsWith("/ai/proactive"))).toEqual([]);
});

test("settings fetch failures stay local and do not block writing a chat message", async ({ page }) => {
  const seen = await mount(page);
  await page.route("**/api/v1/ai/proactive", (route) => route.abort("failed"));
  await open(page);
  await expect(page.getByRole("region", { name: "Lời hỏi thăm của Điều phối" }).getByRole("alert")).toContainText("Chưa tải được lịch hỏi thăm");
  await page.getByRole("button", { name: "Đóng thông tin cuộc trò chuyện" }).click();
  await expect(page.getByRole("textbox", { name: "Tin nhắn cho Điều phối" })).toBeEditable();
  expect(seen.writes).toEqual([]);
});

for (const width of [320, 390, 768, 1099, 1100, 1280]) {
  test(`info check-ins are accessible without overflow at ${width}px`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width, height: 900 });
    await page.emulateMedia({ reducedMotion: "reduce" });
    await mount(page);
    await open(page, "nhatky");
    await expect(page.getByRole("heading", { name: "Lời hỏi thăm của Nhật ký" })).toBeVisible();
    await expect(page.getByText("Đang tạm dừng đến hết 05/11.")).toBeVisible();
    await expect(page.getByRole("button", { name: "Bật lại", exact: true })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(1);
    expect((await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze()).violations).toEqual([]);
    await page.screenshot({ path: testInfo.outputPath(`agent-check-ins-${width}.png`), fullPage: true });
  });
}

test("global editor keeps one modal and its draft/focus through resize then restores its trigger", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await mount(page);
  await open(page);
  const trigger = page.getByRole("button", { name: "Đổi múi giờ dùng cho tất cả trợ lý" });
  await trigger.click();
  const editor = page.getByRole("dialog", { name: "Dùng chung cho mọi trợ lý", exact: true });
  await expect(editor).toBeVisible();
  await expect(page.locator("dialog:modal")).toHaveCount(1);
  await editor.getByLabel("Tìm múi giờ").fill("Tokyo");
  const zone = editor.getByRole("combobox", { name: "Múi giờ", exact: true });
  await zone.selectOption("Asia/Tokyo");
  await zone.focus();
  await page.setViewportSize({ width: 1280, height: 900 });
  await expect(zone).toHaveValue("Asia/Tokyo");
  await expect(zone).toBeFocused();
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.locator("dialog:modal")).toHaveCount(1);
  await expect(zone).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(editor).toBeHidden();
  await expect(trigger).toBeFocused();
  await expect(page.getByRole("dialog", { name: "Thông tin cuộc trò chuyện" })).toBeVisible();
});

test("global edits preview other agents and link to a quiet-hour conflict", async ({ page }) => {
  await mount(page);
  await open(page);
  await page.getByRole("button", { name: "Đổi múi giờ dùng cho tất cả trợ lý" }).click();
  const editor = page.getByRole("dialog", { name: "Dùng chung cho mọi trợ lý", exact: true });
  await expect(editor.getByText("Các lịch chịu ảnh hưởng")).toBeVisible();
  await editor.getByRole("combobox", { name: "Bắt đầu", exact: true }).selectOption("19:00");
  const conflict = editor.getByRole("alert");
  await expect(conflict.getByRole("link", { name: "Hoạt động · Buổi tối · 20:00" })).toHaveAttribute("href", "#/assistants/hoatdong?panel=info&section=check-ins");
  await expect(editor.getByRole("button", { name: "Lưu cài đặt chung" })).toBeDisabled();
});

test("a stale timezone update keeps journal consent revoked in another tab", async ({ page }) => {
  const seen = await mount(page, { staleSettings: true });
  await open(page);
  await page.getByRole("button", { name: "Đổi múi giờ dùng cho tất cả trợ lý" }).click();
  const editor = page.getByRole("dialog", { name: "Dùng chung cho mọi trợ lý", exact: true });
  await editor.getByLabel("Tìm múi giờ").fill("Tokyo");
  await editor.getByRole("combobox", { name: "Múi giờ", exact: true }).selectOption("Asia/Tokyo");
  await editor.getByRole("button", { name: "Lưu cài đặt chung" }).click();
  await expect(editor.getByRole("status")).toHaveText("Đã lưu");
  const puts = seen.writes.filter((write) => write.path === "/ai/proactive/settings");
  expect(puts).toHaveLength(2);
  expect(puts[1].body).toMatchObject({ timezone: "Asia/Tokyo", expectedVersion: 8, journalContextEnabled: false, policyVersion: "proactive-v1" });
  await page.keyboard.press("Escape");
  await open(page, "nhatky");
  await expect(page.getByRole("checkbox", { name: "Dùng khoảnh khắc đã lưu hôm qua" })).not.toBeChecked();
  await expect(page.getByText(/Múi giờ:.*Asia\/Tokyo/)).toBeVisible();
});

test("legacy migration is explicit and Cầu Nối exposes no enable control", async ({ page }) => {
  const view = fixture();
  view.schedules.find((schedule) => schedule.botId === "nhip" && schedule.slot === "morning")!.enabled = true;
  const seen = await mount(page, { view });
  await open(page, "nhatky");
  await page.getByText("Lịch cũ", { exact: true }).click();
  expect(seen.writes).toEqual([]);
  await page.getByRole("button", { name: "Chuyển sang Nhật ký" }).first().click();
  await expect.poll(() => seen.writes.filter((write) => write.path.endsWith("/migrate")).length).toBe(1);
  expect(seen.writes.find((write) => write.path.endsWith("/migrate"))).toMatchObject({ path: "/ai/proactive/schedules/nhip/morning/migrate", method: "POST", body: { expectedVersion: 1 } });
  await page.goto("/#/check-ins?bot=caunoi");
  await expect(page.getByRole("heading", { name: "Lời hỏi thăm của Cầu Nối" })).toBeVisible();
  await expect(page.getByRole("switch")).toHaveCount(0);
  await page.getByRole("button", { name: "Xóa lịch", exact: true }).click();
  await page.getByRole("dialog", { name: "Xóa lịch hỏi thăm của Cầu Nối?" }).getByRole("button", { name: "Xóa lịch", exact: true }).click();
  await expect.poll(() => seen.writes.filter((write) => write.method === "DELETE").length).toBe(2);
  expect(seen.writes.filter((write) => write.method === "DELETE").every((write) => write.path.includes("/caunoi/") && write.body.expectedVersion === 1)).toBe(true);
});

test("compact keyboard loop includes schedule selects and stays usable at 200 percent text", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await mount(page);
  await open(page, "nhatky");
  const panel = page.getByRole("dialog", { name: "Thông tin cuộc trò chuyện" });
  const select = panel.getByLabel("Lặp lại").last();
  await select.focus();
  await page.keyboard.press("Tab");
  await expect(panel.getByLabel("Tạm dừng").last()).toBeFocused();
  await page.addStyleTag({ content: "html { font-size: 200% !important; }" });
  expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(1);
  await panel.getByRole("button", { name: "Đóng thông tin cuộc trò chuyện" }).focus();
  await page.keyboard.press("Shift+Tab");
  await expect(panel.getByRole("button", { name: "Cuộc trò chuyện mới", exact: true })).toBeFocused();
});
