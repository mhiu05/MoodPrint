import { expect, test, type BrowserContext, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { api, noHorizontalOverflow, origin, session, userId } from "./helpers";

// P2-09 against the real backend (tests.e2e_server, AI_COLLABORATION_ENABLED on there) and the
// synthetic SDK model, which delays the specialist so the real `consulting` state is visible.
// Users 56-59 are reserved for these journeys.
test.skip(process.env.E2E_COLLABORATION === "0" || process.env.E2E_MULTI_MESSAGE === "0", "collaboration is off for this run");
const HABIT_LINE = "Nhịp đã gợi ý một thói quen nhỏ. Mây đã dựa vào đó để trả lời bạn.";
const ENERGY_LINE = "Nhịp đã gợi ý mức năng lượng phù hợp với bạn. Rủ Rê đã dựa vào đó để chọn hoạt động này.";

async function controls(page: Page, body: Record<string, unknown>) {
  const response = await page.request.post(`${origin}/__test/collaboration`, { data: body });
  expect(response.ok()).toBe(true);
}

async function open(context: BrowserContext, user: number, width = 1440) {
  await session(context, user);
  const page = await context.newPage();
  await page.setViewportSize({ width, height: width < 500 ? 844 : 960 });
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("console", (message) => { if (message.type() === "error") errors.push(message.text()); });
  return { page, errors };
}

async function enableEdge(page: Page, name: RegExp) {
  await page.goto("/#/companion-sharing");
  const toggle = page.getByRole("switch", { name });
  await toggle.click();
  await expect(toggle).toBeChecked();
  await expect(page.getByRole("status").filter({ hasText: "Đã bật." })).toBeVisible();
}

async function send(page: Page, bot: string, botName: string, text: string) {
  await page.goto(`/#/assistants/${bot}`);
  await page.getByRole("textbox", { name: `Tin nhắn cho ${botName}`, exact: true }).fill(text);
  await page.getByRole("button", { name: "Gửi tin cho AI", exact: true }).click();
}

test("E2E-17/18: a real consultation shows live progress, then a receipt-backed line that survives reload", async ({ browser }) => {
  const context = await browser.newContext({ baseURL: origin, viewport: { width: 1440, height: 960 } });
  const { page, errors } = await open(context, 56);
  await controls(page, { mode: "ok", delay: 2.5, enabled: true });
  await enableEdge(page, /Nhịp gợi ý thói quen nhỏ cho Mây/);

  await send(page, "may", "Mây", "Mấy hôm nay mình mất ngủ");
  // The status names both companions only while the server reports `consulting`.
  const status = page.locator(".ai-status [role=status]");
  await expect(status).toHaveText("Mây đang hỏi Nhịp một chút…");
  const group = page.getByRole("group", { name: "Tin nhắn từ Mây, 2 phần" });
  await expect(group.locator(".collaboration-line")).toContainText(HABIT_LINE);
  await expect(status).not.toHaveText(/đang hỏi/);
  await expect(group.locator(".chat-bubble").first()).toContainText("COLLAB-E2E");

  // The line comes from the database: same after a reload (S6), and in the conversation DTO.
  await page.reload();
  await expect(page.getByRole("group", { name: "Tin nhắn từ Mây, 2 phần" }).locator(".collaboration-line")).toContainText(HABIT_LINE);
  const conversationId = new URL(page.url().replace("/#", "")).searchParams.get("conversation");
  const thread = await (await page.request.get(`${api}/ai/conversations/${conversationId}`)).json();
  const bot = thread.messages.filter((m: { actor: string }) => m.actor === "bot");
  expect(bot[0].collaboration.summary).toBe(HABIT_LINE);
  expect(bot[1].collaboration).toBeNull();
  // The real v2 replay contains the two real progress events in order, v1 does not.
  const v2 = await (await page.request.get(`${api}/ai/runs/${bot[0].runId}/events?protocol=2`)).text();
  expect(v2.indexOf('"activity":"consulting"')).toBeGreaterThan(0);
  expect(v2.indexOf('"activity":"composing"')).toBeGreaterThan(v2.indexOf('"activity":"consulting"'));
  const v1 = await (await page.request.get(`${api}/ai/runs/${bot[0].runId}/events`)).text();
  expect(v1).not.toContain("consulting");
  expect(v1).not.toContain("collaboration");

  // Keyboard: open and close the explanation.
  const why = page.getByRole("button", { name: "Vì sao?" });
  await why.focus();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("dialog", { name: "Vì sao Mây gợi ý thói quen này?" })).toBeVisible();
  expect((await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze()).violations).toEqual([]);
  await page.keyboard.press("Escape");
  await expect(why).toBeFocused();

  for (const width of [768, 390, 360]) {
    await page.setViewportSize({ width, height: width < 500 ? 844 : 1024 });
    await expect(page.locator(".collaboration-line")).toBeVisible();
    await noHorizontalOverflow(page);
  }
  // Switching companions keeps each conversation's own state.
  await page.goto("/#/assistants/rure");
  await expect(page.locator(".collaboration-line")).toHaveCount(0);
  expect(errors).toEqual([]);
  await context.close();
});

test("E2E-19: turning the edge off from another tab stops the turn and leaves no line", async ({ browser }) => {
  const context = await browser.newContext({ baseURL: origin, viewport: { width: 1440, height: 960 } });
  const { page } = await open(context, 57);
  await controls(page, { mode: "ok", delay: 6, enabled: true });
  await enableEdge(page, /Nhịp gợi ý thói quen nhỏ cho Mây/);
  await send(page, "may", "Mây", "Dạo này áp lực deadline quá");
  await expect(page.locator(".ai-status [role=status]")).toHaveText("Mây đang hỏi Nhịp một chút…");

  const other = await context.newPage();
  await other.goto("/#/companion-sharing");
  const toggle = other.getByRole("switch", { name: /Nhịp gợi ý thói quen nhỏ cho Mây/ });
  await toggle.click();
  await expect(toggle).not.toBeChecked();
  await expect(other.getByRole("status").filter({ hasText: "Đã tắt." })).toBeVisible();

  await expect(page.getByText("Đã dừng phản hồi.").first()).toBeVisible({ timeout: 15000 });
  await expect(page.locator(".collaboration-line")).toHaveCount(0);
  await controls(page, { delay: 2.5 });
  await context.close();
});

test("timeout and invalid specialist output fall back to an ordinary reply without a line", async ({ browser }) => {
  const context = await browser.newContext({ baseURL: origin, viewport: { width: 390, height: 844 } });
  const { page, errors } = await open(context, 58, 390);
  await enableEdge(page, /Nhịp gợi ý thói quen nhỏ cho Mây/);
  for (const mode of ["invalid", "timeout"]) {
    await controls(page, { mode, delay: 0.5, enabled: true });
    await send(page, "may", "Mây", mode === "invalid" ? "Mình mất ngủ" : "Mình căng thẳng quá");
    await expect(page.locator(".chat-bubble").filter({ hasText: "Mây đã nhận được chia sẻ" }).last()).toBeVisible({ timeout: 25000 });
    await expect(page.locator(".collaboration-line")).toHaveCount(0);
    await expect(page.getByText(/lỗi phối hợp/)).toHaveCount(0);
  }
  await controls(page, { mode: "ok", delay: 2.5 });
  await noHorizontalOverflow(page);
  expect(errors).toEqual([]);
  await context.close();
});

test("R1 reads only an authorized saved moment, and the flag off restores Phase 1 behaviour", async ({ browser }) => {
  const context = await browser.newContext({ baseURL: origin, viewport: { width: 768, height: 1024 } });
  const { page, errors } = await open(context, 59, 768);
  await controls(page, { mode: "ok", delay: 0.5, enabled: true });
  // Without the journal opt-in the energy edge cannot be enabled.
  await page.goto("/#/companion-sharing");
  await expect(page.getByRole("switch", { name: /Nhịp gợi ý mức năng lượng cho Rủ Rê/ })).toHaveAttribute("aria-disabled", "true");
  await page.goto("/#/check-ins");
  const optIn = page.getByRole("checkbox", { name: "Dùng khoảnh khắc đã lưu hôm qua" });
  await optIn.click();
  await expect(optIn).toBeChecked();
  await enableEdge(page, /Nhịp gợi ý mức năng lượng cho Rủ Rê/);
  // No saved moment yet: Rủ Rê answers alone.
  await send(page, "rure", "Rủ Rê", "Gợi ý gì nhẹ nhàng hợp với mình hôm nay");
  await expect(page.locator(".chat-bubble").last()).toBeVisible();
  await expect(page.locator(".collaboration-line")).toHaveCount(0);
  const today = new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Ho_Chi_Minh" }).format(new Date());
  await controls(page, { journalToday: userId(59), day: today });
  await send(page, "rure", "Rủ Rê", "Hôm nay mình đang mệt, chơi gì đây?");
  await expect(page.locator(".collaboration-line").last()).toContainText(ENERGY_LINE);
  // Flag off: no line, no progress, ordinary replies; the stored opt-in can still be turned off.
  await controls(page, { enabled: false });
  await page.reload();
  await expect(page.locator(".collaboration-line")).toHaveCount(0);
  await send(page, "rure", "Rủ Rê", "Hôm nay mình đang mệt, chơi gì đây?");
  await expect(page.locator(".chat-bubble").last()).toBeVisible();
  await expect(page.locator(".collaboration-line")).toHaveCount(0);
  await controls(page, { enabled: true });
  expect(errors).toEqual([]);
  await context.close();
});
