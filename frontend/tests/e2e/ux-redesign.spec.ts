import { expect, test, type Page } from "@playwright/test";
import { artifactPath } from "../artifacts";
import AxeBuilder from "@axe-core/playwright";
import { app, baseSession, room, sessionWith, type Routes } from "./ux-fixtures";

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
  test("a legacy disabled AI flag does not block approving a pending proposal", async ({ page }) => {
    await app(page, sessionWith({ AI: false, MEM: false }), { "/proposals": () => ({ json: [pendingProposal] }) });
    await page.goto("/#/memory");
    const proposal = page.getByRole("article").filter({ hasText: "Thích đi bộ buổi tối" });
    await expect(proposal.getByRole("button", { name: "Duyệt và lưu" })).toBeEnabled();
    await expect(proposal.getByRole("button", { name: "Không lưu" })).toBeEnabled();
    await expect(proposal.getByRole("link", { name: /quyền riêng tư/i })).toHaveCount(0);
  });

  test("with no approved memories the page explains that a proposal is how memory is saved", async ({ page }) => {
    await app(page, sessionWith({ AI: true, MEM: false }));
    await page.goto("/#/memory");
    await expect(page.getByText("Bạn chưa lưu ghi nhớ nào. Khi trò chuyện, bạn có thể nhờ trợ lý đề xuất điều cần nhớ rồi duyệt tại đây.", { exact: true })).toBeVisible();
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
    await page.getByRole("button", { name: "Chia sẻ và an toàn" }).click();
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

test("the AI composer has no consent hurdle for legacy disabled flags", async ({ page }) => {
  await app(page, sessionWith({ AI: false }));
  await page.goto("/#/assistants/may");
  await expect(page.getByText("Khi chọn Gửi, bạn đồng ý để dịch vụ AI xử lý tin nhắn này. Bạn có thể rút quyền trong Quyền riêng tư.", { exact: true })).toHaveCount(0);
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
        const name = document.querySelector<HTMLElement>(".bot-row-text strong")!;
        const role = document.querySelector<HTMLElement>(".bot-row-text small")!;
        const style = getComputedStyle(role);
        return {
          body,
          name: parseFloat(getComputedStyle(name).fontSize),
          role: parseFloat(style.fontSize),
          ellipsis: style.textOverflow === "ellipsis" && style.whiteSpace === "nowrap",
          overflow: document.documentElement.scrollWidth - innerWidth,
        };
      });
      expect(metrics.body, `body at ${width}`).toBe(16);
      expect(metrics.name, `name at ${width}`).toBeGreaterThanOrEqual(16);
      expect(metrics.role, `role at ${width}`).toBeGreaterThanOrEqual(13);
      expect(metrics.ellipsis, `role truncated at ${width}`).toBe(false);
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
  // The stored transcript records what the server accepted and produced, as a real server would.
  const thread = { conversationId: CONV, botId: "may", version: 1, persistent: false, expiresAt: "2026-10-24T08:00:00Z", messages: [] as unknown[], hasMoreMessages: false, activeRunId: null, activeRunVersion: null };
  const terminal = options.terminal ?? "completed";
  await app(page, baseSession, {
    "/ai/conversations": (request) => (request.method() === "GET" ? { json: [] } : { status: 201, json: thread }),
    [`/ai/conversations/${CONV}`]: () => { calls.transcript += 1; return { json: thread }; },
  });
  await page.route(`**/api/v1/ai/conversations/${CONV}/messages`, async (route) => {
    calls.messages += 1;
    await accept.promise;
    const sent = route.request().postDataJSON();
    thread.messages.push({ id: sent.clientMessageId, actor: "self", text: sent.text });
    await route.fulfill({ status: 202, json: { runId: RUN, conversationId: CONV, version: 2, runVersion: 1, eventsUrl: `/api/v1/ai/runs/${RUN}/events` } });
  });
  await page.route(`**/api/v1/ai/runs/${RUN}/events`, async (route) => {
    await finish.promise;
    if (terminal === "completed") thread.messages.push({ id: `${RUN}-bot`, actor: "bot", text: "Mình nghe bạn đây.", cards: [] });
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
  test("the composer switches its single action to stop even with an empty draft, preserving the next draft", async ({ page }) => {
    const run = await aiRun(page, { terminal: "cancelled" });
    await sendHello(page);
    const field = page.getByRole("textbox", { name: "Tin nhắn cho Mây" });
    const action = page.locator(".bot-composer .send-button");
    await expect(action).toBeDisabled();
    run.accept.open();
    await expect(field).toHaveValue("");
    await expect(action).toHaveAccessibleName("Dừng phản hồi");
    await expect(action).toBeEnabled();
    await expect(action).toBeFocused();
    await expect(page.getByRole("button", { name: "Dừng phản hồi", exact: true })).toHaveCount(1);
    await field.fill("Mình muốn nói thêm một chút");
    await action.click();
    await expect(action).toBeDisabled();
    await expect(status(page)).toHaveText("Đang yêu cầu dừng…");
    expect(run.calls.messages).toBe(1);
    expect(run.calls.cancels).toBe(1);
    run.cancelGate.open();
    run.finish.open();
    await expect(action).toHaveAccessibleName("Gửi tin cho AI");
    await expect(action).toBeEnabled();
    await expect(field).toHaveValue("Mình muốn nói thêm một chút");
  });

  test("a failed composer stop request restores the stop action without sending the next draft", async ({ page }) => {
    const run = await aiRun(page);
    await page.route(`**/api/v1/ai/runs/${RUN}/cancel`, (route) => route.fulfill({
      status: 503, json: { error: { code: "UNAVAILABLE", message: "Thử lại sau." } },
    }));
    await sendHello(page);
    run.accept.open();
    const action = page.locator(".bot-composer .send-button");
    await expect(action).toHaveAccessibleName("Dừng phản hồi");
    await page.getByRole("textbox", { name: "Tin nhắn cho Mây" }).fill("Tin tiếp theo");
    await action.click();
    await expect(page.getByRole("alert")).toBeVisible();
    await expect(action).toHaveAccessibleName("Dừng phản hồi");
    await expect(action).toBeEnabled();
    expect(run.calls.messages).toBe(1);
    run.finish.open();
    await expect(action).toHaveAccessibleName("Gửi tin cho AI");
    await expect(page.getByRole("textbox", { name: "Tin nhắn cho Mây" })).toHaveValue("Tin tiếp theo");
  });

  test("a read-only transition retains one stop action beside the inline status", async ({ page }) => {
    const run = await aiRun(page, { terminal: "cancelled" });
    await sendHello(page);
    run.accept.open();
    await expect(page.locator(".bot-composer .send-button")).toHaveAccessibleName("Dừng phản hồi");
    await page.route("**/api/v1/ai/preferences", (route) => route.fulfill({
      status: 503, json: { error: { code: "UNAVAILABLE", message: "Thử lại sau." } },
    }));
    await page.evaluate(() => window.dispatchEvent(new Event("focus")));
    await expect(page.locator(".bot-composer")).toHaveCount(0);
    const stop = page.getByRole("button", { name: "Dừng phản hồi", exact: true });
    await expect(stop).toHaveCount(1);
    await stop.click();
    await expect(status(page)).toHaveText("Đang yêu cầu dừng…");
    expect(run.calls.cancels).toBe(1);
    run.cancelGate.open();
    run.finish.open();
    await expect(status(page)).toHaveText("Đã dừng phản hồi.");
  });

  test("sending, accepted and final states are truthful and the orb runs only after acceptance", async ({ page }) => {
    await page.emulateMedia({ reducedMotion: "no-preference" });
    const run = await aiRun(page);
    await sendHello(page);
    await expect(status(page)).toHaveText("Đang gửi tin nhắn…");
    await expect(page.locator(".ai-status canvas")).toHaveCount(0);
    run.accept.open();
    await expect(status(page)).toHaveText("Đang trả lời…");
    await expect(page.locator("canvas")).toHaveCount(1);
    await expect(page.locator(".ai-status canvas")).toHaveAttribute("aria-hidden", "true");
    await expect(page.getByRole("button", { name: "Dừng phản hồi", exact: true })).toBeVisible();
    run.finish.open();
    // Settled means the stored transcript has replaced the streamed copy; the reply must survive that.
    await expect(page.getByRole("button", { name: "Dừng phản hồi", exact: true })).toHaveCount(0);
    expect(run.calls.transcript).toBe(1);
    await expect(page.locator(".from-bot .chat-bubble")).toContainText("Mình nghe bạn đây.");
    await expect(page.locator("canvas")).toHaveCount(0);
    await expect(status(page)).toHaveText("");
  });

  test("reduced motion keeps a static status and never mounts a canvas", async ({ page }) => {
    await page.emulateMedia({ reducedMotion: "reduce" });
    const run = await aiRun(page);
    await sendHello(page);
    run.accept.open();
    await expect(status(page)).toHaveText("Đang trả lời…");
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
    await expect(status(page)).toHaveText("Đang trả lời…");
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
    const stop = page.locator(".bot-composer .send-button");
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
    await page.getByRole("button", { name: "Dừng phản hồi", exact: true }).click();
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
  await expect(page.locator(".from-bot .chat-bubble").first()).toContainText("Một điều nhỏ");
}
const infoButton = (page: Page) => page.getByRole("button", { name: "Thông tin cuộc trò chuyện", exact: true });

test.describe("compact agent chat", () => {
  test("human chat keeps the application palette after visiting the redesigned AI chat", async ({ page }) => {
    await app(page, baseSession);
    await page.goto("/#/assistants/may?new=1");
    await expect(page.locator(".bot-composer")).toBeVisible();
    await page.goto(`/#/chat/${room.id}`);
    await expect(page.locator(".real-human-chat")).toBeVisible();
    const palette = await page.locator(".real-human-chat").evaluate((element) => {
      const root = getComputedStyle(document.documentElement);
      const human = getComputedStyle(element);
      return ["--color-bg", "--color-ink", "--control-min"].map(token => ({ root: root.getPropertyValue(token).trim(), human: human.getPropertyValue(token).trim() }));
    });
    for (const token of palette) expect(token.human).toBe(token.root);
  });

  for (const width of [360, 390, 666, 1440]) {
    test(`the inline activity and multiline composer remain usable at ${width}px`, async ({ page }) => {
      await page.setViewportSize({ width, height: width < 768 ? 844 : 900 });
      const finish = gate();
      const thread = savedThread({ messages: [
        { id: "visual-self", actor: "self", text: "Dạo này mình thấy hơi quá tải. Có cách nào để bắt đầu chậm lại không?", createdAt: "2026-10-30T01:00:00Z" },
        { id: "visual-bot", actor: "bot", text: "Mình nghe bạn. **Một điều nhỏ** cũng có thể là khởi đầu.\n\nBạn thử dành một phút để thở chậm, rồi chọn một việc có thể để sang ngày mai. Không cần giải quyết mọi thứ cùng một lúc.", cards: [{ kind: "navigate_bot", botId: "nhip" }], createdAt: "2026-10-30T01:01:00Z" },
      ] });
      await app(page, { ...baseSession, features: { ...baseSession.features, voice: true } }, {
        "/ai/preferences": () => ({ json: historyOn }),
        "/ai/conversations": () => ({ json: [thread] }),
        [`/ai/conversations/${CONV}`]: () => ({ json: thread }),
      });
      await page.route(`**/api/v1/ai/conversations/${CONV}/messages`, async (route) => {
        const sent = route.request().postDataJSON();
        thread.messages.push({ id: sent.clientMessageId, actor: "self", text: sent.text });
        await route.fulfill({ status: 202, json: { runId: RUN, conversationId: CONV, version: 3, runVersion: 1, eventsUrl: `/api/v1/ai/runs/${RUN}/events` } });
      });
      await page.route(`**/api/v1/ai/runs/${RUN}/events`, async (route) => {
        await finish.promise;
        await route.fulfill({ contentType: "text/event-stream", body: sse([{ type: "cancelled" }]) });
      });
      await page.route(`**/api/v1/ai/runs/${RUN}/cancel`, (route) => route.fulfill({ json: { runId: RUN, version: 2, status: "ended" } }));
      await page.goto("/#/assistants/may?new=1");
      const field = page.getByRole("textbox", { name: "Tin nhắn cho Mây" });
      await expect(field).toBeEditable();
      await expect(page.locator(".quick-replies button").first()).toBeEnabled();
      if (width === 390 || width === 1440) {
        await page.screenshot({ path: artifactPath(`agent-chat/empty-${width}.png`), fullPage: true });
      }
      await page.goto(`/#/assistants/may?conversation=${CONV}`);
      await expect(page.locator(".from-bot .chat-bubble")).toContainText("Không cần giải quyết mọi thứ");
      await expect(page.locator(".from-bot .ai-markdown strong")).toHaveText("Một điều nhỏ");
      await expect(page.locator(".chat-introduction")).toHaveCount(0);
      if (width === 390 || width === 1440) {
        await page.screenshot({ path: artifactPath(`agent-chat/conversation-${width}.png`), fullPage: true });
      }
      await field.fill("Mình muốn thử.\nBạn có thể cùng mình bắt đầu không?");
      await page.getByRole("button", { name: "Gửi tin cho AI", exact: true }).click();
      const action = page.locator(".bot-composer .send-button");
      await expect(action).toHaveAccessibleName("Dừng phản hồi");
      await expect(page.locator(".conversation-log .ai-status [role=status]")).toHaveText("Đang trả lời…");
      await field.fill("Mình sẽ viết thêm ở đây.\nMột chút thời gian cho bản thân.\nKhông cần phải vội.");
      await expect(status(page)).toBeInViewport({ ratio: 1 });
      const metrics = await page.evaluate(() => {
        const button = document.querySelector(".bot-composer .send-button")!.getBoundingClientRect();
        const textarea = document.querySelector(".bot-composer textarea")!.getBoundingClientRect();
        const activity = document.querySelector(".ai-status [role=status]")!.getBoundingClientRect();
        const log = document.querySelector(".conversation-log")!.getBoundingClientRect();
        return { overflow: document.documentElement.scrollWidth > innerWidth, left: textarea.left, right: button.right, bottom: button.bottom, width: button.width, height: button.height, viewportHeight: innerHeight, activityBottom: activity.bottom, logBottom: log.bottom };
      });
      expect(metrics.overflow).toBe(false);
      expect(metrics.left).toBeGreaterThanOrEqual(0);
      expect(metrics.right).toBeLessThanOrEqual(width);
      expect(metrics.bottom).toBeLessThanOrEqual(metrics.viewportHeight);
      expect(metrics.width).toBeGreaterThanOrEqual(44);
      expect(metrics.height).toBeGreaterThanOrEqual(44);
      expect(metrics.activityBottom, "growing the composer keeps the current activity in view").toBeLessThanOrEqual(metrics.logBottom);
      // Settle the sole 160ms entrance before recording visual evidence.
      await page.waitForTimeout(200);
      await page.screenshot({ path: artifactPath(`agent-chat/working-${width}.png`), fullPage: true });
      if (width === 390) {
        const results = await new AxeBuilder({ page }).include(".bot-conversation").withTags(["wcag2a", "wcag2aa"]).analyze();
        expect(results.violations).toEqual([]);
      }
      await action.click();
      await expect(action).toHaveAccessibleName("Đang yêu cầu dừng");
      await expect(action).toBeDisabled();
      finish.open();
      await expect(action).toHaveAccessibleName("Gửi tin cho AI");
      await expect(field).toHaveValue("Mình sẽ viết thêm ở đây.\nMột chút thời gian cho bản thân.\nKhông cần phải vội.");
    });
  }
});

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
    for (const name of ["Đổi tên", "Xóa cuộc trò chuyện"])
      await expect(panel.getByRole("button", { name, exact: true })).toBeVisible();
    await expect(panel.getByRole("button", { name: "Tải xuống cuộc trò chuyện", exact: true })).toHaveCount(0);
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
    await page.locator(".from-bot .chat-bubble").hover();
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
    await page.locator(".from-bot .chat-bubble").hover();
    await page.getByRole("button", { name: "Sao chép câu trả lời" }).click();
    await expect(page.getByText("Chưa sao chép được. Bạn có thể chọn và sao chép nội dung.", { exact: true })).toBeVisible();
    await expect(page.getByText("Đã sao chép câu trả lời.", { exact: true })).toHaveCount(0);
  });
});

test.describe("AI message dates and details", () => {
  const messages = [
    { id: "m1", actor: "self", text: "Hôm nay mình hơi mệt.", createdAt: "2026-10-30T01:00:00Z" },
    { id: "m2", actor: "bot", text: "Mình nghe bạn. **Một điều nhỏ** nào làm bạn mệt nhất?", cards: [], createdAt: "2026-10-30T01:01:00Z" },
  ];

  test.beforeEach(async ({ page }) => {
    await page.clock.setFixedTime(new Date("2026-10-30T02:00:00Z"));
  });

  test("hover reveals only the current message's time and icon without shifting messages", async ({ page }) => {
    await savedChat(page, { thread: { messages } });
    const self = page.locator(".from-self .message-content");
    const reply = page.locator(".from-bot .message-content");
    const copy = reply.getByRole("button", { name: "Sao chép câu trả lời", includeHidden: true });
    await expect(copy).toBeHidden();
    await expect(self.locator("time")).toBeHidden();
    await expect(reply.locator("time")).toBeHidden();
    const before = await reply.boundingBox();
    await reply.locator(".chat-bubble").hover();
    await expect(copy).toBeVisible();
    await expect(copy).toHaveText("");
    await expect(reply.locator("time")).toHaveText("08:01");
    await expect(reply.locator("time")).toBeVisible();
    await expect(self.locator("time")).toBeHidden();
    expect(await reply.boundingBox()).toEqual(before);
    await page.screenshot({ path: artifactPath("chat-message-details/desktop-hover.png"), fullPage: true });
    await self.locator(".chat-bubble").hover();
    await expect(self.locator("time")).toBeVisible();
    await expect(self.locator("time")).toHaveText("08:00");
    await expect(copy).toBeHidden();
    await page.getByRole("textbox", { name: "Tin nhắn cho Mây", exact: true }).hover();
    await expect(self.locator("time")).toBeHidden();
  });

  test("keyboard users can reveal details and reach the copy action", async ({ page }) => {
    await savedChat(page, { thread: { messages } });
    await page.getByRole("log").focus();
    await page.keyboard.press("Tab");
    await expect(page.locator(".from-self time")).toBeVisible();
    await page.keyboard.press("Tab");
    await expect(page.locator(".from-bot time")).toBeVisible();
    await page.keyboard.press("Tab");
    await expect(page.getByRole("button", { name: "Sao chép câu trả lời" })).toBeFocused();
  });

  test("day separators use account-local calendar days, include years, and tolerate legacy dates", async ({ page }) => {
    await savedChat(page, { thread: { messages: [
      { ...messages[0], id: "old-year", createdAt: "2025-12-31T16:59:00Z" },
      { ...messages[0], id: "old", createdAt: "2026-10-28T09:00:00Z" },
      { ...messages[0], id: "yesterday", createdAt: "2026-10-28T17:01:00Z" },
      { ...messages[1], id: "yesterday-reply", createdAt: "2026-10-29T16:59:00Z" },
      { ...messages[0], id: "today", createdAt: "2026-10-29T17:01:00Z" },
      { ...messages[1], id: "legacy", createdAt: null },
      { ...messages[1], id: "invalid", createdAt: "invalid" },
    ] } });
    await expect(page.locator(".message-date-separator")).toHaveText(["31/12/2025", "28/10/2026", "Yesterday", "Today"]);
    await expect(page.locator(".message-content time")).toHaveCount(5);
    await expect(page.getByRole("log")).not.toContainText("Invalid Date");
  });

  test.describe("touch", () => {
    test.use({ hasTouch: true, viewport: { width: 390, height: 844 } });

    test("tap toggles details, switches messages and dismisses outside the message", async ({ page, context }) => {
      await context.grantPermissions(["clipboard-read", "clipboard-write"]);
      await savedChat(page, { thread: { messages } });
      const self = page.locator(".from-self .message-content");
      const reply = page.locator(".from-bot .message-content");
      const copy = reply.getByRole("button", { name: "Sao chép câu trả lời", includeHidden: true });
      await expect(copy).toBeHidden();
      await expect(reply.locator("time")).toBeHidden();
      await reply.locator(".chat-bubble").tap();
      await expect(copy).toBeVisible();
      await expect(reply.locator("time")).toBeVisible();
      await page.screenshot({ path: artifactPath("chat-message-details/mobile-tap.png"), fullPage: true });
      await copy.tap();
      await expect(reply.getByRole("status")).toHaveText("Đã sao chép câu trả lời.");
      expect(await page.evaluate(() => navigator.clipboard.readText())).toBe("Mình nghe bạn. Một điều nhỏ nào làm bạn mệt nhất?");
      await reply.locator(".chat-bubble").tap();
      await expect(copy).toBeHidden();
      await reply.locator(".chat-bubble").tap();
      await self.locator(".chat-bubble").tap();
      await expect(self.locator("time")).toBeVisible();
      await expect(copy).toBeHidden();
      await page.getByRole("textbox", { name: "Tin nhắn cho Mây", exact: true }).tap();
      await expect(self.locator("time")).toBeHidden();
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    });
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
    await expect(status(page)).toHaveText("Đang trả lời…");
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
    await expect(status(page)).toHaveText("Đang trả lời…");
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
    await expect(status(page)).toHaveText("Đang trả lời…");
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
  await expect(status(page)).toHaveText("Đang trả lời…");
  const log = page.getByRole("log");
  await log.evaluate((element) => { element.scrollTop = 200; element.dispatchEvent(new Event("scroll")); });
  const top = await log.evaluate((element) => element.scrollTop);
  await page.getByRole("textbox", { name: "Tin nhắn cho Mây" }).fill("Nháp nhiều dòng\nĐang đọc tin cũ\nGiữ nguyên vị trí đọc");
  expect(await log.evaluate((element) => element.scrollTop)).toBe(top);
  finish.open();
  await expect(page.getByRole("button", { name: "Về tin mới" })).toBeVisible();
  expect(await log.evaluate((element) => element.scrollTop)).toBe(top);
  await page.getByRole("button", { name: "Về tin mới" }).click();
  await expect.poll(() => log.evaluate((element) => element.scrollHeight - element.scrollTop - element.clientHeight)).toBeLessThan(90);
  await expect(page.getByRole("button", { name: "Về tin mới" })).toHaveCount(0);
});

// ---- Privacy and memory comprehension (V-PRIVACY-COPY / V-MEMORY / V-DATA-DELETE) ----
test.describe("personal account and memory comprehension", () => {
  const prefs = { historyEnabled: false, semanticMemoryEnabled: false, version: 1, policyVersion: "ai-data-v1", retentionDays: 30, historyAvailable: true, semanticMemoryAvailable: true };

  test("personal settings replace privacy switches with account actions", async ({ page }) => {
    await app(page, sessionWith({ AI: true, MEM: false, MATCH: true, VOICE: false }), { "/ai/preferences": () => ({ json: prefs }) });
    await page.goto("/#/settings");
    await expect(page).toHaveURL(/#\/profile$/);
    await expect(page.getByRole("heading", { name: "Cá nhân", exact: true })).toBeVisible();
    await expect(page.getByRole("region", { name: "Tài khoản & hỗ trợ" })).toBeVisible();
    await expect(page.getByRole("button", { name: /Rút quyền/ })).toHaveCount(0);
    await expect(page.getByRole("checkbox", { name: "Lưu lịch sử trò chuyện" })).toHaveCount(0);
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
    await expect(waiting.getByRole("textbox", { name: "Nội dung sẽ lưu" })).toHaveValue("Thích trà buổi tối");
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
    await page.getByRole("button", { name: "Xóa ghi nhớ này", exact: true }).click();
    await expect(page.getByRole("alert")).toContainText("Dịch vụ tạm gián đoạn.");
    await expect(page.getByText("Thích đi bộ", { exact: true })).toBeVisible();
  });

  test("account deletion dialog focuses the keep action first", async ({ page }) => {
    await app(page, sessionWith({}), { "/ai/preferences": () => ({ json: prefs }) });
    await page.goto("/#/settings");
    await page.getByRole("button", { name: "Xóa tài khoản", exact: true }).click();
    await expect(page.getByRole("button", { name: "Giữ tài khoản", exact: true })).toBeFocused();
  });
});

// ---- Human chat continuity and safety access (V-CHAT-SCROLL / V-SAFETY) ----
test.describe("human chat continuity and safety", () => {
  const message = (seq: number, sender: "self" | "peer", text: string) => ({
    id: `msg-${seq}`, connectionId: room.id, clientMessageId: `c-${seq}`, seq: String(seq), sender, text, acceptedAt: new Date(Date.UTC(2026, 9, 23, 8, 0, seq)).toISOString(),
  });

  test("a peer message arriving while reading older messages keeps the place and is not marked read", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 700 });
    const messages = Array.from({ length: 40 }, (_, index) => message(index + 1, index % 2 ? "peer" : "self", `Tin số ${index + 1}. `.repeat(5)));
    const reads: number[] = [];
    await app(page, sessionWith({ AI: false }), {
      [`/connections/${room.id}/messages`]: (request) => {
        const after = BigInt(new URL(request.url()).searchParams.get("afterSeq") ?? "0");
        return { json: { messages: messages.filter((item) => BigInt(item.seq) > after), highWaterSeq: messages.at(-1)!.seq } };
      },
    });
    await page.route(`**/api/v1/connections/${room.id}/read`, (route) => { reads.push(Number(route.request().postDataJSON().seq)); return route.fulfill({ json: {} }); });
    await page.goto(`/#/chat/${room.id}`);
    const log = page.getByRole("log");
    await expect(log.getByText(/Tin số 40\./)).toBeVisible();
    await log.evaluate((element) => { element.scrollTop = 300; element.dispatchEvent(new Event("scroll")); });
    const top = await log.evaluate((element) => element.scrollTop);
    const before = reads.length ? Math.max(...reads) : 0;
    messages.push(message(41, "peer", "Một tin mới từ bạn kia."));
    await expect(page.getByRole("button", { name: "Về tin mới" })).toBeVisible({ timeout: 10_000 });
    expect(await log.evaluate((element) => element.scrollTop)).toBe(top);
    await page.waitForTimeout(1300);
    expect(reads.filter((seq) => seq >= 41)).toEqual([]);
    expect(before).toBeLessThan(41);
    await page.getByRole("button", { name: "Về tin mới" }).click();
    await expect.poll(() => reads.includes(41), { timeout: 5000 }).toBe(true);
  });

  test("safety actions open from the conversation header and stay away from Send", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await app(page, sessionWith({ AI: false }));
    await page.goto(`/#/chat/${room.id}`);
    await expect(page.getByRole("textbox", { name: "Nhắn tin cho người bạn kết nối" })).toBeEnabled();
    const composer = page.locator("form.bot-composer");
    await expect(composer.getByRole("button", { name: /Kết thúc|Chặn/ })).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Kết thúc kết nối" })).toHaveCount(0);
    const open = page.locator(".conversation-header").getByRole("button", { name: "Chia sẻ và an toàn" });
    await open.click();
    const dialog = page.getByRole("dialog", { name: "Chia sẻ và an toàn" });
    for (const name of ["Gửi báo cáo", "Chặn kết nối này", "Kết thúc kết nối"])
      await expect(dialog.getByRole("button", { name, exact: true })).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(dialog).toHaveCount(0);
    await expect(open).toBeFocused();
  });
});

// ---- Auth orientation, personal profile, mood and voice (V-AUTH / V-MOOD / V-VOICE-DRAFT) ----
test.describe("personal journeys", () => {
  async function voiceChat(page: Page) {
    const writes: string[] = [];
    page.on("request", (request) => {
      if (request.method() !== "GET" && /ai\/conversations|consents/.test(request.url())) writes.push(request.url());
    });
    await page.addInitScript(() => {
      // A synthetic microphone: a quiet oscillator through the real AudioWorklet path.
      Object.defineProperty(navigator, "mediaDevices", {
        configurable: true,
        value: {
          getUserMedia: async () => {
            const context = new AudioContext();
            const oscillator = context.createOscillator();
            const destination = context.createMediaStreamDestination();
            oscillator.connect(destination);
            oscillator.start();
            return destination.stream;
          },
        },
      });
    });
    await app(page, sessionWith({ AI: true, VOICE: true }, { features: { ai: true, matching: true, voice: true } }), {
      "/voice/transcriptions": () => ({ json: { text: "Bản chép lời thử", durationSeconds: 1 } }),
    });
    await page.route("**/api/v1/voice/transcriptions", (route) => route.fulfill({ json: { text: "Bản chép lời thử", durationSeconds: 1 } }));
    await page.goto("/#/assistants/may?new=1");
    return writes;
  }
  async function transcribe(page: Page) {
    await page.getByRole("button", { name: "Ghi âm", exact: true }).click();
    await expect(page.getByText(/Đang ghi âm · [1-9]/)).toBeVisible();
    await page.getByRole("button", { name: "Dừng và chuyển thành văn bản" }).click();
    await expect(page.getByRole("textbox", { name: "Xem và sửa bản chép lời" })).toHaveValue("Bản chép lời thử");
  }

  test("a transcript fills an empty composer only when chosen, and never sends", async ({ page }) => {
    const writes = await voiceChat(page);
    const draft = page.getByRole("textbox", { name: "Tin nhắn cho Mây" });
    await transcribe(page);
    await page.getByRole("button", { name: "Đưa vào ô tin nhắn" }).click();
    await expect(draft).toHaveValue("Bản chép lời thử");
    await expect(draft).toBeFocused();
    expect(writes).toEqual([]);
  });

  test("with a draft already typed, the transcript is appended or replaces it only by explicit choice", async ({ page }) => {
    const writes = await voiceChat(page);
    const draft = page.getByRole("textbox", { name: "Tin nhắn cho Mây" });
    await draft.fill("Chào Mây.");
    await transcribe(page);
    await expect(page.getByRole("button", { name: "Đưa vào ô tin nhắn" })).toHaveCount(0);
    await page.getByRole("button", { name: "Thêm vào tin nhắn" }).click();
    await expect(draft).toHaveValue("Chào Mây. Bản chép lời thử");
    await transcribe(page);
    await page.getByRole("button", { name: "Giữ tin nhắn đang soạn" }).click();
    await expect(draft).toHaveValue("Chào Mây. Bản chép lời thử");
    await transcribe(page);
    await page.getByRole("button", { name: "Thay nội dung" }).click();
    await expect(draft).toHaveValue("Bản chép lời thử");
    expect(writes).toEqual([]);
  });

  test("stopping before any sound is captured says the recording is too short, without uploading", async ({ page }) => {
    // A microphone that has not delivered any audio yet: frames never reach the app.
    await page.addInitScript(() => {
      const Original = window.AudioWorkletNode;
      window.AudioWorkletNode = class extends Original {
        constructor(...args: ConstructorParameters<typeof AudioWorkletNode>) {
          super(...args);
          Object.defineProperty(this.port, "onmessage", { configurable: true, get: () => null, set: () => undefined });
        }
      };
    });
    await voiceChat(page);
    const uploads: string[] = [];
    page.on("request", (request) => { if (request.url().includes("/voice/transcriptions")) uploads.push(request.url()); });
    await page.getByRole("button", { name: "Ghi âm", exact: true }).click();
    await page.getByRole("button", { name: "Dừng và chuyển thành văn bản" }).click();
    await expect(page.getByRole("alert")).toContainText("Bản ghi quá ngắn");
    await expect(page.getByRole("alert")).not.toContainText("kết nối");
    expect(uploads).toEqual([]);
    await expect(page.getByRole("button", { name: "Ghi âm", exact: true })).toBeVisible();
  });

  test("first-time sign in explains what MoodPrint is in one sentence", async ({ page }) => {
    await page.route("**/api/v1/session", (route) => route.fulfill({ status: 401, json: { error: { code: "AUTH_REQUIRED", message: "Vui lòng đăng nhập." } } }));
    await page.goto("/#/");
    await expect(page.getByRole("heading", { name: "Chào bạn trở lại" })).toBeVisible();
    await expect(page.getByText(/MoodPrint là nơi/)).toBeVisible();
    await expect(page.getByRole("button", { name: "Đăng nhập", exact: true })).toBeInViewport();
  });

  test("the private profile field shows its remaining characters", async ({ page }) => {
    await app(page, baseSession, { "/profiles/private-items": () => ({ json: [] }), "/users/me/identity": () => ({ json: [] }) });
    await page.goto("/#/profile");
    const field = page.getByLabel("Điều bạn muốn ghi lại");
    await field.fill("Mình thích đi bộ");
    await expect(field).toHaveAccessibleDescription(/16\/120 ký tự/);
  });

  test("saving a mood confirms the exact day next to the form", async ({ page }) => {
    let saved: unknown;
    await app(page, baseSession, {
      "/moods": () => ({ json: saved ? [saved] : [] }),
      "/moods/summary": () => ({ json: { from: "2026-10-17", to: "2026-10-23", count: 0, mean: null, min: null, max: null, insightAvailable: false, buckets: [] } }),
    });
    await page.route("**/api/v1/moods/*", (route) => {
      if (route.request().method() !== "PUT") return route.fallback();
      const body = route.request().postDataJSON();
      saved = { localDate: "2026-10-23", value: body.value, note: body.note, version: 1 };
      return route.fulfill({ json: saved });
    });
    await page.goto("/#/self/daily");
    await page.getByLabel("Tâm trạng", { exact: true }).selectOption("4");
    await page.getByRole("button", { name: "Lưu tâm trạng", exact: true }).click();
    await expect(page.getByText("Đã lưu cảm xúc ngày 23/10/2026.", { exact: true })).toBeVisible();
  });
});

// ---- Accessibility sweep (V-REFLOW / V-ROUTE-FOCUS / QA04 / QA15 automated part) ----
test.describe("accessibility sweep", () => {
  // axe samples colours as they are at that instant. A control enabled by a late
  // response is still in its disabled→enabled colour transition for a moment, so
  // each screen is measured once its loads and finite transitions have settled.
  const axe = async (page: Page) => {
    await expect(page.getByText(/^Đang tải/)).toHaveCount(0);
    await page.evaluate(() => Promise.all(document.getAnimations()
      .filter((animation) => animation.effect?.getComputedTiming().endTime !== Infinity)
      .map((animation) => animation.finished.catch(() => undefined))));
    return (await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"]).analyze()).violations
      .map((violation) => `${violation.id}: ${violation.nodes.map((node) => node.target.join(" ")).join(", ")}`);
  };

  for (const width of [390, 1280]) {
    test(`redesigned screens have no automated WCAG violations at ${width}px`, async ({ page }) => {
      await page.setViewportSize({ width, height: 844 });
      const thread = savedThread();
      await app(page, sessionWith({ AI: true, MEM: false }), {
        "/ai/preferences": () => ({ json: historyOn }),
        "/ai/conversations": () => ({ json: [thread] }),
        [`/ai/conversations/${CONV}`]: () => ({ json: thread }),
        "/moods": () => ({ json: [] }),
        "/moods/summary": () => ({ json: { from: "2026-10-17", to: "2026-10-23", count: 0, mean: null, min: null, max: null, insightAvailable: false, buckets: [] } }),
        "/connections": () => ({ json: [room] }),
      });
      const results: Record<string, string[]> = {};
      for (const [name, url, ready] of [
        ["assistants", "/#/assistants", "Chọn một trợ lý"],
        ["chat", `/#/assistants/may?conversation=${CONV}`, "Một điều nhỏ"],
        ["profile", "/#/profile", "Cá nhân"],
        ["memory", "/#/memory", "Đề xuất chờ duyệt"],
        ["messages", "/#/messages", "Tin nhắn"],
        ["mood", "/#/self/daily", "Tâm trạng"],
        ["human", `/#/chat/${room.id}`, "Bắt đầu cuộc trò chuyện"],
      ] as const) {
        await page.goto(url);
        await expect(page.getByText(ready).first()).toBeVisible();
        results[name] = await axe(page);
      }
      await page.goto(`/#/assistants/may?conversation=${CONV}`);
      await expect(page.getByText("Một điều nhỏ").first()).toBeVisible();
      await page.getByRole("button", { name: "Thông tin cuộc trò chuyện", exact: true }).click();
      await expect(page.getByRole("heading", { name: "Thông tin cuộc trò chuyện" })).toBeFocused();
      results["chat-info"] = await axe(page);
      expect(results).toEqual(Object.fromEntries(Object.keys(results).map((key) => [key, []])));
    });
  }

  test("resizing across 1100px while the info surface is open swaps modal and modeless cleanly", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 900 });
    await savedChat(page);
    await page.getByRole("button", { name: "Thông tin cuộc trò chuyện", exact: true }).click();
    await expect(page.getByRole("region", { name: "Thông tin cuộc trò chuyện" })).toBeVisible();
    await page.setViewportSize({ width: 900, height: 900 });
    const dialog = page.getByRole("dialog", { name: "Thông tin cuộc trò chuyện" });
    await expect(dialog).toBeVisible();
    await expect(page.locator(".conversation-info")).toHaveCount(1);
    await expect.poll(() => page.evaluate(() => document.querySelector("dialog.conversation-info")?.contains(document.activeElement))).toBe(true);
    await page.setViewportSize({ width: 1280, height: 900 });
    await expect(page.getByRole("region", { name: "Thông tin cuộc trò chuyện" })).toBeVisible();
    await expect(page.locator("dialog[open]")).toHaveCount(0);
    await page.keyboard.press("Escape");
    await expect(page.locator(".conversation-info")).toHaveCount(0);
    await expect(page.getByRole("textbox", { name: "Tin nhắn cho Mây" })).toBeEditable();
  });

  test("ordinary buttons on the redesigned chat, info and personal screens are at least 44px tall", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await savedChat(page);
    const small = async () => page.evaluate(() =>
      [...document.querySelectorAll<HTMLElement>("button")]
        .filter((button) => button.getClientRects().length && !button.closest("[inert]"))
        .map((button) => ({ name: button.getAttribute("aria-label") || button.textContent?.trim(), height: Math.round(button.getBoundingClientRect().height) }))
        .filter((item) => item.height < 44));
    expect(await small()).toEqual([]);
    await page.getByRole("button", { name: "Thông tin cuộc trò chuyện", exact: true }).click();
    expect(await small()).toEqual([]);
    await page.goto("/#/settings");
    await expect(page.getByRole("heading", { name: "Cá nhân", exact: true })).toBeVisible();
    expect(await small()).toEqual([]);
  });

  test("200% text keeps the chat and personal screens readable without sideways scrolling", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await savedChat(page);
    await page.addStyleTag({ content: "html { font-size: 200% !important; } body { font-size: 2rem !important; }" });
    await expect(page.getByRole("textbox", { name: "Tin nhắn cho Mây" })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(1);
    await page.getByRole("button", { name: "Thông tin cuộc trò chuyện", exact: true }).click();
    await expect(page.getByRole("button", { name: "Đóng thông tin cuộc trò chuyện" })).toBeInViewport();
    await page.keyboard.press("Escape");
    await page.goto("/#/settings");
    await page.addStyleTag({ content: "html { font-size: 200% !important; } body { font-size: 2rem !important; }" });
    await expect(page.getByRole("heading", { name: "Cá nhân", exact: true })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(1);
  });
});

test("the skip link stays hidden until focused, then appears and moves focus to main", async ({ page }) => {
  await app(page, baseSession);
  await page.goto("/#/messages");
  const skip = page.getByRole("link", { name: "Đến nội dung chính" });
  await expect(skip).not.toBeInViewport();
  await skip.focus();
  await expect(skip).toBeInViewport();
  await skip.press("Enter");
  await expect(page.locator("#main")).toBeFocused();
});

// ---- Final review regressions ----
test.describe("final review regressions", () => {
  const paged = () => {
    const recent = Array.from({ length: 4 }, (_, index) => ({ id: `new-${index}`, actor: index % 2 ? "bot" : "self", text: `Tin gần đây ${index}`, cards: [] }));
    const older = [{ id: "old-1", actor: "self", text: "Một tin cũ hơn", cards: [] }];
    return { recent, older };
  };
  async function pagedChat(page: Page, url: string, extra: Routes = {}) {
    const { recent, older } = paged();
    const thread = savedThread({ messages: recent, hasMoreMessages: true });
    await app(page, baseSession, {
      "/ai/preferences": () => ({ json: historyOn }),
      "/ai/conversations": () => ({ json: [thread] }),
      [`/ai/conversations/${CONV}`]: (request) => ({ json: new URL(request.url()).searchParams.has("before") ? { ...thread, messages: older, hasMoreMessages: false } : thread }),
      ...extra,
    });
    await page.goto(url);
    await expect(page.getByText("Tin gần đây 3")).toBeVisible();
    await page.getByRole("button", { name: "Tải tin nhắn cũ hơn" }).click();
    await expect(page.getByText("Một tin cũ hơn")).toBeVisible();
  }

  test("returning to the tab on the default chat URL keeps loaded history and an in-flight send", async ({ page }) => {
    await pagedChat(page, "/#/assistants/may");
    const posted: unknown[] = [];
    let release: () => void = () => {};
    const held = new Promise<void>((resolve) => { release = resolve; });
    await page.route(`**/api/v1/ai/conversations/${CONV}/messages`, async (route) => { posted.push(route.request().postDataJSON()); await held; await route.fulfill({ status: 503, json: { error: { code: "UNAVAILABLE", message: "Chưa gửi được." } } }); });
    await page.getByRole("textbox", { name: "Tin nhắn cho Mây" }).fill("Một câu hỏi");
    await page.getByRole("button", { name: "Gửi tin cho AI", exact: true }).click();
    await expect.poll(() => posted.length).toBe(1);
    await page.evaluate(() => window.dispatchEvent(new Event("focus")));
    await page.waitForTimeout(500);
    release();
    await expect(page.getByRole("alert").filter({ hasText: "Chưa gửi được." })).toBeVisible();
    await expect(page.getByText("Một tin cũ hơn")).toBeVisible();
    await expect(page.getByRole("textbox", { name: "Tin nhắn cho Mây" })).toHaveValue("Một câu hỏi");
  });

  test("a completed reply keeps older messages the reader loaded", async ({ page }) => {
    await pagedChat(page, `/#/assistants/may?conversation=${CONV}`);
    await page.route(`**/api/v1/ai/conversations/${CONV}/messages`, (route) => route.fulfill({ status: 202, json: { runId: RUN, conversationId: CONV, version: 4, runVersion: 1, eventsUrl: `/api/v1/ai/runs/${RUN}/events` } }));
    await page.route(`**/api/v1/ai/runs/${RUN}/events`, (route) => route.fulfill({ contentType: "text/event-stream", body: sse([{ type: "final", data: { text: "Câu trả lời mới.", cards: [] } }, { type: "completed" }]) }));
    await page.getByRole("textbox", { name: "Tin nhắn cho Mây" }).fill("Một câu hỏi");
    await page.getByRole("button", { name: "Gửi tin cho AI", exact: true }).click();
    await expect(status(page)).toHaveText("");
    await expect(page.getByText("Một tin cũ hơn")).toBeVisible();
    await expect(page.getByText("Tin gần đây 3")).toBeVisible();
  });

  test("a consent the server recorded stays in the session when the send is abandoned", async ({ page }) => {
    let held: () => void = () => {};
    const hold = new Promise<void>((resolve) => { held = resolve; });
    const granted = sessionWith({ AI: true });
    granted.consents.AI.version = 2;
    await app(page, sessionWith({ AI: false }), {
      "/ai/conversations": (request) => (request.method() === "GET" ? { json: [] } : { status: 201, json: savedThread({ persistent: false, messages: [] }) }),
      "/ai/preferences": () => ({ json: historyOn }),
    });
    await page.route("**/api/v1/consents/AI", (route) => route.fulfill({ json: granted }));
    await page.route(`**/api/v1/ai/conversations/${CONV}/messages`, async (route) => { await hold; await route.fulfill({ status: 503, json: { error: { code: "UNAVAILABLE", message: "x" } } }); });
    await page.goto("/#/assistants/may?new=1");
    await page.getByRole("textbox", { name: "Tin nhắn cho Mây" }).fill("Xin chào");
    await page.getByRole("button", { name: "Gửi tin cho AI", exact: true }).click();
    await expect(status(page)).toHaveText("Đang gửi tin nhắn…");
    await page.waitForTimeout(300);
    await page.getByRole("navigation", { name: "Điều hướng chính" }).getByRole("link", { name: "Cá nhân" }).click();
    held();
    await expect(page.getByRole("heading", { name: "Cá nhân", exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "Đăng xuất", exact: true })).toBeVisible();
  });

  for (const action of ["Đổi tên", "Mở lịch sử trò chuyện"]) {
    test(`on a phone, closing ${action} from the info sheet returns focus to its trigger`, async ({ page }) => {
      await page.setViewportSize({ width: 390, height: 844 });
      await savedChat(page);
      await page.getByRole("button", { name: "Thông tin cuộc trò chuyện", exact: true }).click();
      await page.getByRole("button", { name: action, exact: true }).click();
      await expect(page.getByRole("dialog")).toHaveCount(1);
      await page.keyboard.press("Escape");
      await expect(page.getByRole("dialog")).toHaveCount(0);
      await expect(page.getByRole("button", { name: "Thông tin cuộc trò chuyện", exact: true })).toBeFocused();
    });
  }

  test("narrowing the window while a rename dialog is open keeps that dialog in charge", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 900 });
    await savedChat(page);
    await page.getByRole("button", { name: "Thông tin cuộc trò chuyện", exact: true }).click();
    await page.getByRole("region", { name: "Thông tin cuộc trò chuyện" }).getByRole("button", { name: "Đổi tên", exact: true }).click();
    const field = page.getByRole("dialog", { name: "Đổi tên cuộc trò chuyện" }).getByRole("textbox", { name: "Tên cuộc trò chuyện" });
    await field.fill("Tên chưa lưu");
    await page.setViewportSize({ width: 900, height: 900 });
    await page.waitForTimeout(300);
    await expect(page.locator("dialog[open]")).toHaveCount(1);
    await expect(field).toBeFocused();
    await expect(field).toHaveValue("Tên chưa lưu");
  });
});
