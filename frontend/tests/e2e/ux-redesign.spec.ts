import { expect, test, type Page } from "@playwright/test";
import { app, baseSession, sessionWith } from "./ux-fixtures";

const pendingProposal = {
  id: "p-1",
  botId: "may",
  purpose: "memory",
  text: "Thích đi bộ buổi tối",
  status: "pending",
  version: 1,
  expiresAt: "2099-01-01T00:00:00Z",
};

test.describe("truthful consent recovery (F03)", () => {
  test("with AI processing off a pending proposal points to an explicit Send, not to Settings", async ({ page }) => {
    await app(page, sessionWith({ AI: false, MEM: false }), { "/proposals": () => ({ json: [pendingProposal] }) });
    await page.goto("/#/memory");
    const proposal = page.getByRole("article").filter({ hasText: "Thích đi bộ buổi tối" });
    await expect(proposal).toContainText("Quyền xử lý AI đang tắt nên chưa thể duyệt đề xuất này.");
    await expect(proposal.getByRole("link", { name: "Mở trợ lý" })).toHaveAttribute("href", "#/assistants");
    await expect(proposal.getByRole("link", { name: /quyền riêng tư/i })).toHaveCount(0);
    await expect(proposal.getByRole("button", { name: "Không lưu" })).toBeEnabled();
  });

  test("with approved memory off the page explains that approving a proposal is the way back", async ({ page }) => {
    await app(page, sessionWith({ AI: true, MEM: false }));
    await page.goto("/#/memory");
    await expect(page.getByText("Trợ lý chỉ dùng lại ghi nhớ sau khi bạn duyệt một đề xuất mới.", { exact: false })).toBeVisible();
    await expect(page.getByRole("link", { name: "Xem quyền ghi nhớ" })).toHaveCount(0);
  });

  test("with MATCH withdrawn, messages lead to reviewing and showing the matching profile", async ({ page }) => {
    await app(page, sessionWith({ MATCH: false }));
    await page.goto("/#/messages");
    await expect(page.getByRole("link", { name: "Mở hồ sơ tìm bạn" })).toHaveAttribute("href", "#/connect?tab=profile");
    await expect(page.getByText(/Hiển thị hồ sơ/)).toBeVisible();
    await expect(page.getByRole("link", { name: "Xem quyền tìm bạn" })).toHaveCount(0);
  });
});

test.describe("truthful blocking (F04)", () => {
  test("the chat block dialog states in-app irreversibility, focuses cancel and sends nothing on cancel", async ({ page }) => {
    const writes: string[] = [];
    page.on("request", (request) => {
      if (request.method() === "POST" && request.url().includes("/block")) writes.push(request.url());
    });
    await app(page, sessionWith({ AI: false }));
    await page.goto("/#/chat/room-1");
    await page.getByText("Chia sẻ và an toàn", { exact: true }).click();
    await page.getByRole("button", { name: "Chặn kết nối này", exact: true }).click();
    const dialog = page.getByRole("dialog", { name: "Chặn kết nối này?" });
    await expect(dialog).toContainText("Hai bạn sẽ không thể xem hoặc gửi tiếp tin nhắn trong kết nối này.");
    await expect(dialog).toContainText("Việc chặn không thể hoàn tác trong ứng dụng.");
    await expect(dialog).not.toContainText("Bỏ chặn");
    await expect(dialog.getByRole("button", { name: "Giữ kết nối" })).toBeFocused();
    await dialog.getByRole("button", { name: "Giữ kết nối" }).click();
    await expect(dialog).toHaveCount(0);
    expect(writes).toEqual([]);
  });
});

test.describe("service failures do not blame input (F11)", () => {
  test("a non-JSON 500 asks to retry instead of checking the content", async ({ page }) => {
    await app(page, baseSession, { "/session": () => ({ status: 500, body: "<html>proxy error</html>", contentType: "text/html" }) });
    await page.goto("/#/assistants");
    const alert = page.getByRole("alert");
    await expect(alert).toContainText("Chưa hoàn tất yêu cầu. Bạn hãy thử lại.");
    await expect(alert).not.toContainText("kiểm tra nội dung");
  });
});

test("resolved reports show a Vietnamese outcome instead of the raw enum", async ({ page }) => {
  const resolved = { id: "r1", status: "resolved", version: 3, reason: "Quấy rối", createdAt: "2026-10-23T07:00:00Z", subjectRef: "s-abcdef0123456789", reporterRef: "r-abcdef012345", evidence: [], priorActions: 1, resolution: "warned" };
  await app(page, sessionWith({}, { staff: "moderator", notices: [] }), {
    "/admin/reports": (request) => ({ json: new URL(request.url()).searchParams.get("status") === "resolved" ? [resolved, { ...resolved, id: "r2", resolution: "mystery" }] : [] }),
  });
  await page.goto("/#/admin/reports");
  await page.getByRole("button", { name: "Đã xử lý", exact: true }).click();
  await expect(page.getByText(/Kết quả: Đã cảnh báo/)).toBeVisible();
  await expect(page.getByText(/Kết quả: Đã xử lý/)).toBeVisible();
  await expect(page.getByText(/warned|mystery/)).toHaveCount(0);
});

test("the first AI send explains the consent it records, next to Send", async ({ page }) => {
  await app(page, sessionWith({ AI: false }));
  await page.goto("/#/assistants/may");
  await expect(page.getByText("Khi chọn Gửi, bạn đồng ý để dịch vụ AI xử lý tin nhắn này. Bạn có thể rút quyền trong Quyền riêng tư.", { exact: true })).toBeVisible();
});

test("an unavailable AI service is not sent to Settings for a fix that does not exist there", async ({ page }) => {
  await app(page, sessionWith({}, { features: { ai: false, aiStatus: "configuration_missing", matching: true, voice: false } }));
  await page.goto("/#/assistants/may?new=1");
  const notice = page.locator(".chat-readonly");
  await expect(notice).toContainText("Trợ lý chưa được kết nối với dịch vụ AI.");
  await expect(notice.getByRole("link")).toHaveCount(0);
});

const longBots = [
  { botId: "may", name: "Mây", role: "Lắng nghe & tâm sự", description: "Một khoảng nhỏ để được lắng nghe, không phán xét và không vội vàng.", starters: ["Hôm nay mình hơi mệt"], avatarKey: "may" },
  { botId: "guong", name: "Gương", role: "Nhìn lại bản thân", description: "Cùng nhìn lại một ngày đã qua bằng những câu hỏi nhẹ nhàng.", starters: ["Mình muốn nhìn lại hôm nay"], avatarKey: "guong" },
];
const WIDTHS = [320, 375, 390, 768, 1280, 1440];

test.describe("readable foundations (V-TOKENS / V-REFLOW)", () => {
  test("body text is 16px and persona descriptions are readable without truncation at every width", async ({ page }) => {
    await app(page, baseSession, { "/bots": () => ({ json: longBots }) });
    for (const width of WIDTHS) {
      await page.setViewportSize({ width, height: width < 768 ? 844 : 900 });
      await page.goto("/#/assistants");
      const row = page.getByRole("link", { name: /Gương/ }).first();
      await expect(row).toBeVisible();
      const metrics = await page.evaluate(() => {
        const body = parseFloat(getComputedStyle(document.body).fontSize);
        const description = document.querySelector<HTMLElement>(".bot-row-text p")!;
        const role = document.querySelector<HTMLElement>(".bot-row-text small")!;
        const style = getComputedStyle(description);
        return {
          body,
          description: parseFloat(style.fontSize),
          role: parseFloat(getComputedStyle(role).fontSize),
          ellipsis: style.textOverflow === "ellipsis" && style.whiteSpace === "nowrap",
          overflow: document.documentElement.scrollWidth - innerWidth,
        };
      });
      expect(metrics.body, `body at ${width}`).toBe(16);
      expect(metrics.description, `description at ${width}`).toBeGreaterThanOrEqual(14);
      expect(metrics.role, `role at ${width}`).toBeGreaterThanOrEqual(13);
      expect(metrics.ellipsis, `description truncated at ${width}`).toBe(false);
      expect(metrics.overflow, `horizontal overflow at ${width}`).toBeLessThanOrEqual(1);
    }
  });

  test("navigation labels are readable and ordinary targets are at least 44px", async ({ page }) => {
    await app(page, baseSession, { "/bots": () => ({ json: longBots }) });
    for (const width of [320, 1280]) {
      await page.setViewportSize({ width, height: 844 });
      await page.goto("/#/messages");
      const nav = page.getByRole("navigation", { name: "Điều hướng chính" });
      const sizes = await nav.getByRole("link").evaluateAll((links) =>
        links.map((link) => ({
          font: parseFloat(getComputedStyle(link).fontSize),
          height: link.getBoundingClientRect().height,
          width: link.getBoundingClientRect().width,
        })),
      );
      for (const size of sizes) {
        expect(size.font).toBeGreaterThanOrEqual(width < 768 ? 12 : 13);
        expect(size.height).toBeGreaterThanOrEqual(44);
        expect(size.width).toBeGreaterThanOrEqual(44);
      }
    }
  });

  test("chat text, starters and composer controls are readable and touch-sized on a phone", async ({ page }) => {
    await app(page, baseSession, { "/bots": () => ({ json: longBots }) });
    await page.setViewportSize({ width: 320, height: 700 });
    await page.goto("/#/assistants/may");
    await expect(page.getByRole("textbox", { name: "Tin nhắn cho Mây" })).toBeVisible();
    const metrics = await page.evaluate(() => {
      const box = (selector: string) => document.querySelector<HTMLElement>(selector)!.getBoundingClientRect();
      const font = (selector: string) => parseFloat(getComputedStyle(document.querySelector<HTMLElement>(selector)!).fontSize);
      return {
        starterFont: font(".quick-replies button"),
        starterHeight: box(".quick-replies button").height,
        composerFont: font(".bot-composer textarea"),
        sendHeight: box(".send-button").height,
        headerRole: font(".conversation-header p"),
        overflow: document.documentElement.scrollWidth - innerWidth,
      };
    });
    expect(metrics.starterFont).toBeGreaterThanOrEqual(14);
    expect(metrics.starterHeight).toBeGreaterThanOrEqual(44);
    expect(metrics.composerFont).toBe(16);
    expect(metrics.sendHeight).toBeGreaterThanOrEqual(44);
    expect(metrics.headerRole).toBeGreaterThanOrEqual(13);
    expect(metrics.overflow).toBeLessThanOrEqual(1);
  });
});

test.describe("navigation and route focus (V-NAV / V-ROUTE-FOCUS)", () => {
  const moodRoutes = {
    "/moods": () => ({ json: [] }),
    "/moods/summary": () => ({ json: { from: "2026-10-17", to: "2026-10-23", count: 0, mean: null, min: null, max: null, insightAvailable: false, buckets: [] } }),
  };

  test("five primary destinations, with Cảm xúc opening the mood journal directly", async ({ page }) => {
    await app(page, baseSession, moodRoutes);
    for (const width of [320, 768, 1280]) {
      await page.setViewportSize({ width, height: 844 });
      await page.goto("/#/messages");
      const nav = page.getByRole("navigation", { name: "Điều hướng chính" });
      await expect(nav.getByRole("link")).toHaveText(["Trợ lý", "Cảm xúc", "Tìm bạn", "Tin nhắn", "Cá nhân"]);
      await nav.getByRole("link", { name: "Cảm xúc" }).click();
      await expect(page).toHaveURL(/#\/self$/);
      await expect(nav.getByRole("link", { name: "Cảm xúc" })).toHaveAttribute("aria-current", "page");
      expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(1);
    }
  });

  for (const width of [390, 1280]) {
    test(`choosing an assistant focuses the visible conversation heading at ${width}px`, async ({ page }) => {
      await page.setViewportSize({ width, height: 844 });
      await app(page, baseSession);
      await page.goto("/#/assistants");
      await page.getByRole("link", { name: /Mây/ }).first().click();
      await expect(page.getByRole("heading", { level: 1, name: /^Mây/ })).toBeVisible();
      await expect.poll(() => page.evaluate(() => {
        const active = document.activeElement as HTMLElement;
        return active?.tagName === "H1" && active.getClientRects().length > 0 ? active.textContent?.trim() : active?.tagName;
      })).toMatch(/^Mây/);
    });
  }

  test("route focus never moves focus away from a control the person already chose", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 900 });
    let release: () => void = () => {};
    const held = new Promise<void>((resolve) => { release = resolve; });
    await app(page, baseSession);
    await page.route("**/api/v1/bots", async (route) => { await held; await route.fulfill({ json: [{ botId: "may", name: "Mây", role: "Lắng nghe", description: "Lắng nghe.", starters: [], avatarKey: "may" }] }); });
    await page.goto("/#/assistants/may");
    await page.getByRole("textbox", { name: "Tìm trợ lý" }).focus();
    release();
    await expect(page.getByRole("heading", { level: 1, name: /^Mây/ })).toBeVisible();
    await page.waitForTimeout(300);
    await expect(page.getByRole("textbox", { name: "Tìm trợ lý" })).toBeFocused();
  });
});

// ---- AI activity status (V-AI-STATUS / V-MOTION-LIFECYCLE) ----
type Gate = { promise: Promise<void>; open: () => void };
function gate(): Gate {
  let open: () => void = () => {};
  const promise = new Promise<void>((resolve) => { open = resolve; });
  return { promise, open };
}
const RUN = "33333333-3333-4333-8333-333333333333";
const CONV = "22222222-2222-4222-8222-222222222222";
const sse = (events: { type: string; data?: unknown }[]) =>
  events.map((event, index) => `id: ${index + 1}\ndata: ${JSON.stringify({ version: "ai-events-v1", seq: String(index + 1), type: event.type, data: event.data ?? {} })}\n\n`).join("");

async function aiRun(page: Page, options: { terminal?: "completed" | "cancelled" } = {}) {
  const accept = gate(), finish = gate(), cancelGate = gate();
  const calls = { messages: 0, cancels: 0, transcript: 0 };
  const thread = { conversationId: CONV, botId: "may", version: 1, persistent: false, expiresAt: "2026-10-24T08:00:00Z", messages: [] as unknown[], hasMoreMessages: false, activeRunId: null, activeRunVersion: null };
  const terminal = options.terminal ?? "completed";
  await app(page, baseSession, {
    "/ai/conversations": (request) => (request.method() === "GET" ? { json: [] } : { status: 201, json: thread }),
    [`/ai/conversations/${CONV}`]: () => { calls.transcript += 1; return { json: thread }; },
  });
  await page.route(`**/api/v1/ai/conversations/${CONV}/messages`, async (route) => {
    calls.messages += 1;
    await accept.promise;
    await route.fulfill({ status: 202, json: { runId: RUN, conversationId: CONV, version: 2, runVersion: 1, eventsUrl: `/api/v1/ai/runs/${RUN}/events` } });
  });
  await page.route(`**/api/v1/ai/runs/${RUN}/events`, async (route) => {
    await finish.promise;
    const body = terminal === "completed"
      ? sse([{ type: "progress" }, { type: "final", data: { text: "Mình nghe bạn đây.", cards: [] } }, { type: "completed" }])
      : sse([{ type: "progress" }, { type: "cancelled" }]);
    await route.fulfill({ contentType: "text/event-stream", body });
  });
  await page.route(`**/api/v1/ai/runs/${RUN}/cancel`, async (route) => {
    calls.cancels += 1;
    await cancelGate.promise;
    await route.fulfill({ json: { runId: RUN, version: 2, status: "ended" } });
  });
  return { accept, finish, cancelGate, calls };
}

async function sendHello(page: Page) {
  await page.goto("/#/assistants/may?new=1");
  await page.getByRole("textbox", { name: "Tin nhắn cho Mây" }).fill("Xin chào");
  await page.getByRole("button", { name: "Gửi tin cho AI", exact: true }).click();
}
const status = (page: Page) => page.locator(".ai-status [role=status]");

test.describe("AI activity status", () => {
  test("sending, accepted and final states are truthful and the orb runs only after acceptance", async ({ page }) => {
    await page.emulateMedia({ reducedMotion: "no-preference" });
    const run = await aiRun(page);
    await sendHello(page);
    await expect(status(page)).toHaveText("Đang gửi tin nhắn…");
    await expect(page.locator(".ai-status canvas")).toHaveCount(0);
    run.accept.open();
    await expect(status(page)).toHaveText("Đang chuẩn bị câu trả lời…");
    await expect(page.locator("canvas")).toHaveCount(1);
    await expect(page.locator(".ai-status canvas")).toHaveAttribute("aria-hidden", "true");
    await expect(page.getByRole("button", { name: "Dừng", exact: true })).toBeVisible();
    run.finish.open();
    await expect(page.locator(".from-bot .chat-bubble")).toContainText("Mình nghe bạn đây.");
    await expect(page.locator("canvas")).toHaveCount(0);
    await expect(status(page)).toHaveText("");
    await expect(page.getByRole("button", { name: "Dừng", exact: true })).toHaveCount(0);
  });

  test("reduced motion keeps a static status and never mounts a canvas", async ({ page }) => {
    await page.emulateMedia({ reducedMotion: "reduce" });
    const run = await aiRun(page);
    await sendHello(page);
    run.accept.open();
    await expect(status(page)).toHaveText("Đang chuẩn bị câu trả lời…");
    await page.waitForTimeout(300);
    await expect(page.locator("canvas")).toHaveCount(0);
    await expect(page.locator(".ai-status-visual svg")).toHaveCount(1);
    await page.emulateMedia({ reducedMotion: "no-preference" });
    await expect(page.locator("canvas")).toHaveCount(1);
    await page.emulateMedia({ reducedMotion: "reduce" });
    await expect(page.locator("canvas")).toHaveCount(0);
    run.finish.open();
    await expect(page.locator(".from-bot .chat-bubble")).toContainText("Mình nghe bạn đây.");
  });

  test("a failed orb import keeps the static status and the reply still arrives", async ({ page }) => {
    await page.emulateMedia({ reducedMotion: "no-preference" });
    await page.route(/thinking-orbs|ThinkingOrbVisual/, (route) => route.abort());
    const run = await aiRun(page);
    await sendHello(page);
    run.accept.open();
    await expect(status(page)).toHaveText("Đang chuẩn bị câu trả lời…");
    await expect(page.locator(".ai-status-visual svg")).toHaveCount(1);
    await expect(page.locator("canvas")).toHaveCount(0);
    run.finish.open();
    await expect(page.locator(".from-bot .chat-bubble")).toContainText("Mình nghe bạn đây.");
    await expect(page.getByRole("alert")).toHaveCount(0);
  });

  test("a hidden page unmounts the loop and only an active run resumes it", async ({ page }) => {
    await page.emulateMedia({ reducedMotion: "no-preference" });
    const run = await aiRun(page);
    await sendHello(page);
    run.accept.open();
    await expect(page.locator("canvas")).toHaveCount(1);
    const setVisibility = (state: "hidden" | "visible") => page.evaluate((value) => {
      Object.defineProperty(document, "visibilityState", { configurable: true, get: () => value });
      document.dispatchEvent(new Event("visibilitychange"));
    }, state);
    await setVisibility("hidden");
    await expect(page.locator("canvas")).toHaveCount(0);
    await setVisibility("visible");
    await expect(page.locator("canvas")).toHaveCount(1);
    run.finish.open();
    await expect(page.locator(".from-bot .chat-bubble")).toContainText("Mình nghe bạn đây.");
    await setVisibility("hidden");
    await setVisibility("visible");
    await expect(page.locator("canvas")).toHaveCount(0);
  });

  test("Dừng waits for the confirmed terminal event before saying the reply stopped", async ({ page }) => {
    const run = await aiRun(page, { terminal: "cancelled" });
    await sendHello(page);
    run.accept.open();
    const stop = page.getByRole("button", { name: "Dừng", exact: true });
    await stop.click();
    await expect(status(page)).toHaveText("Đang yêu cầu dừng…");
    await expect(stop).toBeDisabled();
    await expect.poll(() => run.calls.cancels).toBe(1);
    run.cancelGate.open();
    await page.waitForTimeout(200);
    await expect(page.getByText("Đã dừng phản hồi.")).toHaveCount(0);
    run.finish.open();
    await expect(status(page)).toHaveText("Đã dừng phản hồi.");
    await expect(page.getByRole("alert")).toHaveCount(0);
    expect(run.calls.cancels).toBe(1);
    await expect(page.locator("canvas")).toHaveCount(0);
  });

  test("when the reply completes before the stop, it is shown and never labelled stopped", async ({ page }) => {
    const run = await aiRun(page, { terminal: "completed" });
    await sendHello(page);
    run.accept.open();
    await page.getByRole("button", { name: "Dừng", exact: true }).click();
    await expect.poll(() => run.calls.cancels).toBe(1);
    run.finish.open();
    await expect(page.locator(".from-bot .chat-bubble")).toContainText("Mình nghe bạn đây.");
    run.cancelGate.open();
    await page.waitForTimeout(300);
    await expect(page.getByText(/Đã dừng phản hồi/)).toHaveCount(0);
    await expect(page.getByRole("alert")).toHaveCount(0);
  });

  test("leaving for another assistant cannot carry the old run status or reply into the new view", async ({ page }) => {
    await page.emulateMedia({ reducedMotion: "no-preference" });
    const run = await aiRun(page);
    await page.route("**/api/v1/bots", (route) => route.fulfill({ json: [
      { botId: "may", name: "Mây", role: "Lắng nghe", description: "Lắng nghe.", starters: [], avatarKey: "may" },
      { botId: "guong", name: "Gương", role: "Nhìn lại", description: "Nhìn lại.", starters: [], avatarKey: "guong" },
    ] }));
    await sendHello(page);
    run.accept.open();
    await expect(page.locator("canvas")).toHaveCount(1);
    await page.goto("/#/assistants/guong?new=1");
    await expect(page.getByRole("textbox", { name: "Tin nhắn cho Gương" })).toBeVisible();
    run.finish.open();
    await page.waitForTimeout(400);
    await expect(page.locator("canvas")).toHaveCount(0);
    await expect(page.locator(".from-bot")).toHaveCount(0);
    await expect(status(page)).toHaveText("");
  });
});

// ---- Conversation info, copy and confirmed stop/new (V-INFO-PANEL / V-RUN-EXIT / V-CHAT-SCROLL) ----
const savedThread = (patch: Record<string, unknown> = {}) => ({
  conversationId: CONV, botId: "may", version: 3, persistent: true, title: "Một buổi sáng",
  expiresAt: "2026-11-23T08:00:00Z", updatedAt: "2026-10-23T08:00:00Z", hasMoreMessages: false, activeRunId: null, activeRunVersion: null,
  messages: [
    { id: "m1", actor: "self", text: "Hôm nay mình hơi mệt." },
    { id: "m2", actor: "bot", text: "Mình nghe bạn. **Một điều nhỏ** nào làm bạn mệt nhất?", cards: [] },
  ],
  ...patch,
});
const historyOn = { historyEnabled: true, semanticMemoryEnabled: false, version: 1, policyVersion: "ai-data-v1", retentionDays: 30, historyAvailable: true, semanticMemoryAvailable: false };

async function savedChat(page: Page, options: { session?: unknown; thread?: Record<string, unknown> } = {}) {
  const thread = savedThread(options.thread);
  // A fresh document per fixture: re-visiting the same hash URL would not remount.
  await page.goto("about:blank");
  await app(page, options.session ?? baseSession, {
    "/ai/preferences": () => ({ json: historyOn }),
    "/ai/conversations": () => ({ json: [thread] }),
    [`/ai/conversations/${CONV}`]: () => ({ json: thread }),
  });
  await page.goto(`/#/assistants/may?conversation=${CONV}`);
  await expect(page.locator(".from-bot .chat-bubble")).toContainText("Một điều nhỏ");
}
const infoButton = (page: Page) => page.getByRole("button", { name: "Thông tin cuộc trò chuyện", exact: true });

test.describe("conversation info surface", () => {
  test("desktop opens a modeless 320px overlay without moving the transcript", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 900 });
    await savedChat(page);
    const log = page.getByRole("log");
    const before = await log.evaluate((element) => ({ ...element.getBoundingClientRect().toJSON(), top: element.scrollTop }));
    await expect(infoButton(page)).toHaveAttribute("aria-expanded", "false");
    await infoButton(page).click();
    await expect(infoButton(page)).toHaveAttribute("aria-expanded", "true");
    const panel = page.getByRole("region", { name: "Thông tin cuộc trò chuyện" });
    await expect(panel).toBeVisible();
    await expect(panel.getByRole("heading", { name: "Thông tin cuộc trò chuyện" })).toBeFocused();
    expect(Math.round((await panel.boundingBox())!.width)).toBe(320);
    const after = await log.evaluate((element) => ({ ...element.getBoundingClientRect().toJSON(), top: element.scrollTop }));
    expect(after).toEqual(before);
    expect(await page.evaluate(() => document.querySelectorAll("[inert],[aria-modal=true]").length)).toBe(0);
    // Not a trap: Tab eventually leaves the panel.
    let left = false;
    for (let index = 0; index < 25 && !left; index += 1) {
      await page.keyboard.press("Tab");
      left = await panel.evaluate((element) => !element.contains(document.activeElement));
    }
    expect(left).toBe(true);
    await panel.getByRole("heading", { name: "Thông tin cuộc trò chuyện" }).focus();
    await page.keyboard.press("Escape");
    await expect(panel).toHaveCount(0);
    await expect(infoButton(page)).toBeFocused();
  });

  test("tablet uses a 420px modal and phones a full-width modal sheet", async ({ page }) => {
    for (const [width, expected] of [[900, 420], [390, 390]] as const) {
      await page.setViewportSize({ width, height: 844 });
      await savedChat(page);
      await infoButton(page).click();
      const dialog = page.getByRole("dialog", { name: "Thông tin cuộc trò chuyện" });
      await expect(dialog).toBeVisible();
      expect(Math.round((await dialog.boundingBox())!.width)).toBe(expected);
      await expect(dialog.getByRole("button", { name: "Đóng thông tin cuộc trò chuyện" })).toBeVisible();
      await page.keyboard.press("Escape");
      await expect(dialog).toHaveCount(0);
      await expect(infoButton(page)).toBeFocused();
      expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(1);
      await page.unrouteAll({ behavior: "ignoreErrors" });
    }
  });

  test("management actions exist only for saved threads, including when AI is off", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 900 });
    await savedChat(page, { session: sessionWith({ AI: false }, { features: { ai: false, aiStatus: "disabled", matching: true, voice: false } }) });
    await infoButton(page).click();
    const panel = page.getByRole("region", { name: "Thông tin cuộc trò chuyện" });
    for (const name of ["Đổi tên", "Tải xuống cuộc trò chuyện", "Xóa cuộc trò chuyện"])
      await expect(panel.getByRole("button", { name, exact: true })).toBeVisible();
    await expect(panel).toContainText("Đã lưu");
    await page.unrouteAll({ behavior: "ignoreErrors" });
    await savedChat(page, { thread: { persistent: false, title: null } });
    await infoButton(page).click();
    const temporary = page.getByRole("region", { name: "Thông tin cuộc trò chuyện" });
    await expect(temporary).toContainText("Không lưu vào lịch sử.");
    for (const name of ["Đổi tên", "Tải xuống cuộc trò chuyện", "Xóa cuộc trò chuyện"])
      await expect(temporary.getByRole("button", { name, exact: true })).toHaveCount(0);
  });

  test("rename from the panel focuses the field and Escape returns to the panel action", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 900 });
    await savedChat(page);
    await infoButton(page).click();
    const rename = page.getByRole("region", { name: "Thông tin cuộc trò chuyện" }).getByRole("button", { name: "Đổi tên", exact: true });
    await rename.click();
    const field = page.getByRole("dialog", { name: "Đổi tên cuộc trò chuyện" }).getByRole("textbox", { name: "Tên cuộc trò chuyện" });
    await expect(field).toBeFocused();
    await page.keyboard.press("Escape");
    await expect(page.getByRole("dialog", { name: "Đổi tên cuộc trò chuyện" })).toHaveCount(0);
    await expect(rename).toBeFocused();
  });

  test("history opens from the panel on a phone", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await savedChat(page);
    await infoButton(page).click();
    await page.getByRole("button", { name: "Mở lịch sử trò chuyện" }).click();
    await expect(page.getByRole("dialog", { name: "Lịch sử trò chuyện" }).getByRole("link", { name: /Một buổi sáng/ })).toBeVisible();
  });
});

test.describe("copying a reply", () => {
  test("copies the validated reply as plain text and confirms only after success", async ({ page, context }) => {
    await context.grantPermissions(["clipboard-read", "clipboard-write"]);
    await savedChat(page);
    await expect(page.locator(".from-bot .ai-markdown strong")).toHaveText("Một điều nhỏ");
    await page.getByRole("button", { name: "Sao chép câu trả lời" }).click();
    await expect(page.getByText("Đã sao chép câu trả lời.", { exact: true })).toBeVisible();
    const copied = await page.evaluate(() => navigator.clipboard.readText());
    expect(copied).toBe("Mình nghe bạn. Một điều nhỏ nào làm bạn mệt nhất?");
  });

  test("a refused clipboard explains how to copy manually", async ({ page }) => {
    await page.addInitScript(() => {
      Object.defineProperty(navigator, "clipboard", { configurable: true, value: { writeText: () => Promise.reject(new Error("denied")) } });
    });
    await savedChat(page);
    await page.getByRole("button", { name: "Sao chép câu trả lời" }).click();
    await expect(page.getByText("Chưa sao chép được. Bạn có thể chọn và sao chép nội dung.", { exact: true })).toBeVisible();
    await expect(page.getByText("Đã sao chép câu trả lời.", { exact: true })).toHaveCount(0);
  });
});

test.describe("new conversation while a reply is pending", () => {
  async function openNewFromInfo(page: Page) {
    if ((await infoButton(page).getAttribute("aria-expanded")) !== "true") await infoButton(page).click();
    return page.getByRole("button", { name: "Cuộc trò chuyện mới", exact: true });
  }

  test("is unavailable until the send outcome is known", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 900 });
    await aiRun(page);
    await sendHello(page);
    await expect(status(page)).toHaveText("Đang gửi tin nhắn…");
    const next = await openNewFromInfo(page);
    await expect(next).toBeDisabled();
    await expect(page.getByText("Đang xác nhận tin nhắn vừa gửi.", { exact: true })).toBeVisible();
  });

  test("stop-and-new switches only after the confirmed cancellation", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 900 });
    const run = await aiRun(page, { terminal: "cancelled" });
    await sendHello(page);
    run.accept.open();
    await expect(status(page)).toHaveText("Đang chuẩn bị câu trả lời…");
    await (await openNewFromInfo(page)).click();
    const confirm = page.getByRole("dialog", { name: "Dừng phản hồi và mở cuộc trò chuyện mới?" });
    await confirm.getByRole("button", { name: "Tiếp tục trò chuyện" }).click();
    await expect(confirm).toHaveCount(0);
    expect(run.calls.cancels).toBe(0);
    await (await openNewFromInfo(page)).click();
    await page.getByRole("button", { name: "Dừng và mở mới", exact: true }).click();
    await expect.poll(() => run.calls.cancels).toBe(1);
    run.cancelGate.open();
    await page.waitForTimeout(200);
    await expect(page).not.toHaveURL(/new=/);
    await expect(page.locator(".from-self .chat-bubble")).toContainText("Xin chào");
    run.finish.open();
    await expect(page).toHaveURL(/new=/);
    await expect(page.getByText("Đã dừng phản hồi và mở cuộc trò chuyện mới.", { exact: true })).toBeVisible();
    await expect(page.locator(".from-self")).toHaveCount(0);
    expect(run.calls.messages).toBe(1);
  });

  test("a reply that completes first is kept and never called cancelled", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 900 });
    const run = await aiRun(page, { terminal: "completed" });
    await sendHello(page);
    run.accept.open();
    await expect(status(page)).toHaveText("Đang chuẩn bị câu trả lời…");
    await (await openNewFromInfo(page)).click();
    await page.getByRole("button", { name: "Dừng và mở mới", exact: true }).click();
    run.finish.open();
    await expect(page.getByText("Câu trả lời vừa hoàn tất trước khi dừng. Đã mở cuộc trò chuyện mới.", { exact: true })).toBeVisible();
    await expect(page.getByRole("link", { name: "Xem cuộc trò chuyện trước" })).toHaveAttribute("href", new RegExp(`conversation=${CONV}`));
    run.cancelGate.open();
    await page.waitForTimeout(300);
    await expect(page.getByText(/Đã dừng phản hồi/)).toHaveCount(0);
    expect(run.calls.messages).toBe(1);
  });

  test("a failed stop request keeps the current conversation and its reply flow", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 900 });
    const run = await aiRun(page, { terminal: "completed" });
    await page.unroute(`**/api/v1/ai/runs/${RUN}/cancel`);
    await page.route(`**/api/v1/ai/runs/${RUN}/cancel`, (route) => route.fulfill({ status: 503, json: { error: { code: "UNAVAILABLE", message: "Dịch vụ tạm gián đoạn." } } }));
    await sendHello(page);
    run.accept.open();
    await expect(status(page)).toHaveText("Đang chuẩn bị câu trả lời…");
    await (await openNewFromInfo(page)).click();
    await page.getByRole("button", { name: "Dừng và mở mới", exact: true }).click();
    await expect(page.getByText("Chưa xác nhận được trạng thái. Kiểm tra lại cuộc trò chuyện.", { exact: true })).toBeVisible();
    await expect(page).not.toHaveURL(/new=/);
    await expect(page.locator(".from-self .chat-bubble")).toContainText("Xin chào");
    run.finish.open();
    await expect(page.locator(".from-bot .chat-bubble")).toContainText("Mình nghe bạn đây.");
    await expect(page).not.toHaveURL(/new=/);
  });
});

test("a reply arriving while someone reads older messages does not move them, and Về tin mới returns", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 700 });
  const accept = gate(), finish = gate();
  const messages = Array.from({ length: 30 }, (_, index) => ({ id: `m${index}`, actor: index % 2 ? "bot" : "self", text: `Tin nhắn số ${index}. `.repeat(6), cards: [] }));
  const thread = savedThread({ messages });
  await app(page, baseSession, {
    "/ai/preferences": () => ({ json: historyOn }),
    "/ai/conversations": () => ({ json: [thread] }),
    [`/ai/conversations/${CONV}`]: () => ({ json: thread }),
  });
  await page.route(`**/api/v1/ai/conversations/${CONV}/messages`, async (route) => { await accept.promise; await route.fulfill({ status: 202, json: { runId: RUN, conversationId: CONV, version: 4, runVersion: 1, eventsUrl: `/api/v1/ai/runs/${RUN}/events` } }); });
  await page.route(`**/api/v1/ai/runs/${RUN}/events`, async (route) => { await finish.promise; await route.fulfill({ contentType: "text/event-stream", body: sse([{ type: "final", data: { text: "Câu trả lời mới.", cards: [] } }, { type: "completed" }]) }); });
  await page.goto(`/#/assistants/may?conversation=${CONV}`);
  await page.getByRole("textbox", { name: "Tin nhắn cho Mây" }).fill("Một câu hỏi");
  await page.getByRole("button", { name: "Gửi tin cho AI", exact: true }).click();
  accept.open();
  await expect(status(page)).toHaveText("Đang chuẩn bị câu trả lời…");
  const log = page.getByRole("log");
  await log.evaluate((element) => { element.scrollTop = 200; element.dispatchEvent(new Event("scroll")); });
  const top = await log.evaluate((element) => element.scrollTop);
  finish.open();
  await expect(page.getByRole("button", { name: "Về tin mới" })).toBeVisible();
  expect(await log.evaluate((element) => element.scrollTop)).toBe(top);
  await page.getByRole("button", { name: "Về tin mới" }).click();
  await expect.poll(() => log.evaluate((element) => element.scrollHeight - element.scrollTop - element.clientHeight)).toBeLessThan(90);
  await expect(page.getByRole("button", { name: "Về tin mới" })).toHaveCount(0);
});

// ---- Privacy and memory comprehension (V-PRIVACY-COPY / V-MEMORY / V-DATA-DELETE) ----
test.describe("privacy and memory comprehension", () => {
  const prefs = { historyEnabled: false, semanticMemoryEnabled: false, version: 1, policyVersion: "ai-data-v1", retentionDays: 30, historyAvailable: true, semanticMemoryAvailable: true };

  test("privacy is five named sections, each with its own withdrawal and real way back", async ({ page }) => {
    await app(page, sessionWith({ AI: true, MEM: false, MATCH: true, VOICE: false }), { "/ai/preferences": () => ({ json: prefs }) });
    await page.goto("/#/settings");
    await expect(page.getByRole("heading", { level: 2 })).toContainText([
      "Tin nhắn AI", "Lịch sử trò chuyện", "Thông tin AI ghi nhớ", "Hồ sơ và kết nối", "Xuất hoặc xóa dữ liệu",
    ]);
    const ai = page.getByRole("region", { name: "Tin nhắn AI" });
    await expect(ai.getByRole("button", { name: "Rút quyền trò chuyện AI" })).toBeVisible();
    const memory = page.getByRole("region", { name: "Thông tin AI ghi nhớ" });
    // MEM is off: no enable toggle is invented, the real path is approving a proposal.
    await expect(memory).toContainText("duyệt một đề xuất mới");
    await expect(memory.getByRole("button", { name: /Bật/ })).toHaveCount(0);
    await expect(page.getByRole("region", { name: "Hồ sơ và kết nối" }).getByRole("button", { name: "Rút quyền tìm bạn" })).toBeVisible();
  });

  test("with AI withdrawn the section explains that sending a message is how to resume", async ({ page }) => {
    await app(page, sessionWith({ AI: false, MEM: false }), { "/ai/preferences": () => ({ json: prefs }) });
    await page.goto("/#/settings");
    const ai = page.getByRole("region", { name: "Tin nhắn AI" });
    await expect(ai).toContainText("chọn Gửi");
    await expect(ai.getByRole("link", { name: "Mở trợ lý" })).toHaveAttribute("href", "#/assistants");
    await expect(ai.getByRole("button")).toHaveCount(0);
  });

  test("external memory lookup uses a plain label and discloses Voyage and its data scope on request", async ({ page }) => {
    await app(page, sessionWith({ AI: true, MEM: true }), { "/ai/preferences": () => ({ json: prefs }) });
    await page.goto("/#/settings");
    const toggle = page.getByRole("checkbox", { name: "Giúp trợ lý tìm lại ghi nhớ liên quan" });
    await expect(toggle).toBeVisible();
    await expect(toggle).not.toBeChecked();
    await page.getByText("Xem cách dữ liệu được xử lý", { exact: true }).click();
    const disclosure = page.locator("details", { hasText: "Xem cách dữ liệu được xử lý" });
    await expect(disclosure).toContainText("Voyage");
    await expect(disclosure).toContainText("ghi nhớ bạn đã duyệt");
    await expect(disclosure).toContainText("không được gửi tới Voyage");
    await expect(page.getByText(/ngữ nghĩa|dẫn xuất/)).toHaveCount(0);
  });

  test("memory separates proposals waiting for review from approved items", async ({ page }) => {
    await app(page, sessionWith({ AI: true, MEM: true }), {
      "/proposals": () => ({ json: [
        { id: "p-1", botId: "may", purpose: "memory", text: "Thích trà buổi tối", status: "pending", version: 1, expiresAt: "2099-01-01T00:00:00Z" },
        { id: "p-2", botId: "may", purpose: "memory", text: "", status: "rejected", version: 2, expiresAt: "2020-01-01T00:00:00Z" },
      ] }),
      "/memories": () => ({ json: [{ id: "m-1", botId: "may", text: "Thích đi bộ", version: 1 }] }),
    });
    await page.goto("/#/memory");
    await expect(page.getByRole("heading", { level: 1 })).toHaveText("Thông tin AI ghi nhớ");
    const waiting = page.getByRole("region", { name: "Đề xuất chờ duyệt" });
    await expect(waiting.getByRole("textbox", { name: "Nội dung bạn muốn duyệt" })).toHaveValue("Thích trà buổi tối");
    await expect(waiting).toContainText("Chưa lưu");
    await expect(waiting).not.toContainText("Bạn đã chọn không lưu đề xuất này.");
    await expect(page.getByRole("region", { name: "Đã duyệt" })).toContainText("Thích đi bộ");
  });

  test("a failed memory deletion keeps the item and explains the failure", async ({ page }) => {
    await app(page, sessionWith({ AI: true, MEM: true }), {
      "/memories": () => ({ json: [{ id: "m-1", botId: "may", text: "Thích đi bộ", version: 1 }] }),
    });
    await page.route("**/api/v1/memories/m-1", (route) => route.fulfill({ status: 503, json: { error: { code: "UNAVAILABLE", message: "Dịch vụ tạm gián đoạn." } } }));
    await page.goto("/#/memory");
    await page.getByRole("button", { name: "Xóa ghi nhớ", exact: true }).click();
    await page.getByRole("button", { name: "Xác nhận xóa ghi nhớ", exact: true }).click();
    await expect(page.getByRole("alert")).toContainText("Dịch vụ tạm gián đoạn.");
    await expect(page.getByText("Thích đi bộ", { exact: true })).toBeVisible();
  });

  test("data deletion dialogs focus the keep action first", async ({ page }) => {
    await app(page, sessionWith({}), { "/ai/preferences": () => ({ json: prefs }) });
    await page.goto("/#/settings");
    await page.getByRole("button", { name: "Xóa dữ liệu đã chọn", exact: true }).click();
    await expect(page.getByRole("button", { name: "Giữ dữ liệu", exact: true })).toBeFocused();
    await page.keyboard.press("Escape");
    await page.getByRole("button", { name: "Xóa tài khoản", exact: true }).click();
    await expect(page.getByRole("button", { name: "Giữ tài khoản", exact: true })).toBeFocused();
  });
});
