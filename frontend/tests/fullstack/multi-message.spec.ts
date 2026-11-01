import { expect, test } from "@playwright/test";
import { api, noHorizontalOverflow, session } from "./helpers";

// P1-07/G1a against the real backend (tests.e2e_server, AI_MULTI_MESSAGE_ENABLED on there)
// with the synthetic SDK model. User 51 is reserved for this journey.
const USER = 51;
// The harness can run the off path (E2E_MULTI_MESSAGE=0); bubbles exist only when it is on.
test.skip(process.env.E2E_MULTI_MESSAGE === "0", "multi-message flag is off for this run");
const MARKER = "[ba tin]";
const BUBBLES = [
  "Nghe như hôm nay bạn đã gồng khá nhiều.",
  "Mây ở đây nghe bạn.",
  "Tối nay thử nghỉ sớm hơn 15 phút xem sao?",
];

test("a real three-bubble reply persists, groups, survives reload and joins for v1", async ({ browser }) => {
  const context = await browser.newContext({ baseURL: "http://127.0.0.1:5174", reducedMotion: "reduce", viewport: { width: 1440, height: 960 } });
  await session(context, USER);
  const page = await context.newPage();
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("console", (message) => { if (message.type() === "error") errors.push(message.text()); });
  const eventRequests: string[] = [];
  page.on("request", (request) => { if (request.url().includes("/events")) eventRequests.push(new URL(request.url()).search); });

  await page.goto("/#/assistants/may");
  await page.getByRole("textbox", { name: "Tin nhắn cho Mây", exact: true }).fill(`Hôm nay mình hơi uể oải ${MARKER}`);
  await page.getByRole("button", { name: "Gửi tin cho AI", exact: true }).click();
  const group = page.getByRole("group", { name: "Tin nhắn từ Mây, 3 phần" });
  await expect(group.locator(".chat-bubble")).toHaveText(BUBBLES);
  expect(eventRequests).toContain("?protocol=2");

  // Persisted as three rows of one run, in order, with version == max(sequence).
  const conversationId = new URL(page.url().replace("/#", "")).searchParams.get("conversation");
  expect(conversationId).toBeTruthy();
  const stored = await page.request.get(`${api}/ai/conversations/${conversationId}`);
  const thread = await stored.json();
  const bot = thread.messages.filter((message: { actor: string }) => message.actor === "bot");
  expect(bot.map((message: { text: string }) => message.text)).toEqual(BUBBLES);
  expect(bot.map((message: { partIndex: number }) => message.partIndex)).toEqual([0, 1, 2]);
  expect(new Set(bot.map((message: { runId: string }) => message.runId)).size).toBe(1);
  expect(thread.version).toBe(thread.messages.length + 1);

  // An old client asking for v1 receives the joined reply.
  const runId = bot[0].runId;
  const v1 = await page.request.get(`${api}/ai/runs/${runId}/events`);
  expect(await v1.text()).toContain(JSON.stringify({ text: BUBBLES.join("\n\n"), cards: [] }).slice(1, -1));

  // Reload: the group is rebuilt from the server copy.
  await page.reload();
  await expect(page.getByRole("group", { name: "Tin nhắn từ Mây, 3 phần" }).locator(".chat-bubble")).toHaveText(BUBBLES);
  for (const width of [768, 390]) {
    await page.setViewportSize({ width, height: width === 390 ? 844 : 1024 });
    await expect(page.getByRole("group", { name: "Tin nhắn từ Mây, 3 phần" })).toBeVisible();
    await noHorizontalOverflow(page);
  }
  expect(errors).toEqual([]);
  await context.close();
});
