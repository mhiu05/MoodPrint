import { expect, test, type Page } from "@playwright/test";
import { api, noHorizontalOverflow, session } from "./helpers";

// P1-18 against the real backend (tests.e2e_server) and the synthetic SDK model. There is no
// background worker in the harness: /__test/proactive/run makes schedules due and drains the
// queue, exactly what the `proactive` service does on its own clock. User 52 is reserved.
const USER = 52;
const USER_ID = `00000000-0000-4000-8000-${String(USER).padStart(12, "0")}`;
test.skip(process.env.E2E_PROACTIVE === "0", "check-ins are switched off for this run");

function yesterday() {
  const today = new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Bangkok" }).format(new Date());
  const [y, m, d] = today.split("-").map(Number);
  return new Date(Date.UTC(y, m - 1, d - 1)).toISOString().slice(0, 10);
}

async function toggle(page: Page, bot: string, slot: RegExp) {
  const card = page.getByRole("region", { name: bot });
  await card.getByRole("switch", { name: slot }).click();
  await expect(card.getByRole("status")).toHaveText("Đã lưu");
}

test("schedule, delivery, unread, provenance and read state work end to end", async ({ browser }) => {
  const context = await browser.newContext({ baseURL: "http://127.0.0.1:5174", reducedMotion: "reduce", viewport: { width: 1440, height: 960 } });
  await session(context, USER);
  const page = await context.newPage();
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("console", (message) => { if (message.type() === "error") errors.push(message.text()); });

  await page.goto("/#/check-ins");
  await expect(page.getByRole("heading", { level: 1, name: "Lời hỏi thăm từ trợ lý" })).toBeVisible();
  await toggle(page, "Mây", /Buổi tối/);
  await toggle(page, "Nhịp", /Buổi sáng/);
  const optIn = page.getByRole("checkbox", { name: "Dùng khoảnh khắc đã lưu hôm qua" });
  await optIn.click();
  await expect(optIn).toBeChecked();
  await expect(page.getByText("Đang dùng 2/4")).toBeVisible();

  // Reload: the saved state comes back from PostgreSQL.
  await page.reload();
  await expect(page.getByRole("region", { name: "Mây" }).getByRole("switch", { name: /Buổi tối/ })).toBeChecked();

  const run = await page.request.post("http://127.0.0.1:5174/__test/proactive/run", { data: { userId: USER_ID, journalYesterday: yesterday() } });
  expect(run.ok()).toBe(true);
  const jobs = (await run.json()).jobs as { bot: string; status: string }[];
  expect(jobs.map((job) => `${job.bot}:${job.status}`).sort()).toEqual(["may:delivered", "nhip:delivered"]);

  // A second run the same day never delivers twice.
  const again = await page.request.post("http://127.0.0.1:5174/__test/proactive/run", { data: { userId: USER_ID } });
  expect(((await again.json()).jobs as unknown[]).length).toBe(2);

  await page.goto("/#/assistants");
  await expect(page.getByRole("link", { name: "Trợ lý, 2 lời nhắn mới" })).toBeVisible();
  const inbox = page.getByRole("region", { name: "Lời nhắn mới" });
  await expect(inbox.getByRole("link")).toHaveCount(2);
  await inbox.getByRole("link", { name: /^Nhịp · Lời hỏi thăm buổi sáng/ }).click();

  const group = page.getByRole("group", { name: "Tin nhắn từ Nhịp, 2 phần" });
  await expect(group).toContainText("PROACTIVE-E2E Hôm qua bạn có ghi lại một khoảnh khắc.");
  await expect(page.getByText(/^Lời hỏi thăm buổi sáng · \d\d:\d\d$/)).toBeVisible();
  await expect(group.getByRole("link", { name: /\d\d\/\d\d\/\d{4}/ })).toHaveAttribute("href", /#\/self\/entry\//);
  await expect(page.getByRole("link", { name: "Trợ lý, 1 lời nhắn mới" })).toBeVisible({ timeout: 10_000 });

  // The persisted run: proactive origin, two bubbles, no user message.
  const conversationId = new URL(page.url().replace("/#", "")).searchParams.get("conversation");
  const thread = await (await page.request.get(`${api}/ai/conversations/${conversationId}`)).json();
  expect(thread.messages.map((m: { actor: string; origin: string; partIndex: number }) => `${m.actor}:${m.origin}:${m.partIndex}`))
    .toEqual(["bot:proactive:0", "bot:proactive:1"]);

  // A reply in the same thread works and counts as the user's own turn.
  await page.getByRole("textbox", { name: "Tin nhắn cho Nhịp", exact: true }).fill("Cảm ơn Nhịp");
  await page.getByRole("button", { name: "Gửi tin cho AI", exact: true }).click();
  await expect(page.locator(".chat-bubble").last()).not.toHaveText("");

  // Mobile: the back button shows Mây's unread check-in; no horizontal overflow.
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.getByRole("link", { name: "Về danh sách trợ lý, có 1 lời nhắn mới" })).toBeVisible();
  await noHorizontalOverflow(page);

  // A second tab hears about reads without reloading.
  const other = await context.newPage();
  await other.goto("/#/assistants");
  await expect(other.getByRole("link", { name: "Trợ lý, 1 lời nhắn mới" })).toBeVisible();
  await page.goto("/#/assistants");
  await page.getByRole("region", { name: "Lời nhắn mới" }).getByRole("button", { name: "Đánh dấu đã đọc tất cả" }).click();
  await expect(other.getByRole("link", { name: "Trợ lý" })).toBeVisible({ timeout: 10_000 });
  await expect(other.getByRole("region", { name: "Lời nhắn mới" })).toBeHidden();

  // Turning journal use off takes effect at once.
  await page.goto("/#/check-ins");
  await page.getByRole("checkbox", { name: "Dùng khoảnh khắc đã lưu hôm qua" }).click();
  await expect(page.getByRole("region", { name: "Nhịp" }).getByRole("status")).toHaveText("Đã lưu");
  expect(errors).toEqual([]);
  await context.close();
});

test("a guest has no check-in entry and the API refuses", async ({ browser }) => {
  const context = await browser.newContext({ baseURL: "http://127.0.0.1:5174" });
  const page = await context.newPage();
  const response = await page.request.get(`${api}/ai/proactive`);
  expect(response.status()).toBe(401);
  await context.close();
});
