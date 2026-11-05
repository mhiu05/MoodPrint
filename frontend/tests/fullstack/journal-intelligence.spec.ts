import { expect, test } from "@playwright/test";
import { call, origin, session } from "./helpers";

test("hybrid journal sources survive reload and disappear after entry deletion", async ({ browser }) => {
  const context = await browser.newContext({ baseURL: origin });
  await session(context, 68);
  const page = await context.newPage();
  expect((await call(context, 68, "PUT", "/consents/AI", { enabled: true, expectedVersion: 1, policyVersion: "v1" })).status).toBe(200);
  const state = (await call(context, 68, "GET", "/session")).body;
  const parts = new Intl.DateTimeFormat("en-CA", { timeZone: state.timezone, year: "numeric", month: "2-digit", day: "2-digit" }).formatToParts(new Date(state.serverTime));
  const day = ["year", "month", "day"].map(type => parts.find(part => part.type === type)!.value).join("-");
  const older = new Date(`${day}T12:00:00Z`);
  older.setUTCDate(older.getUTCDate()-5);
  let target = "";
  for (const [index, text] of ["mệt rã rời sau ca đêm", "đọc sách trong vườn", "sắp xếp ngăn tủ"].entries()) {
    const created = await call(context, 68, "POST", "/journal/entries", {
      localDate: index === 0 ? older.toISOString().slice(0, 10) : day, mood: 3, text, emotions: [], factors: [], status: "saved",
    });
    expect(created.status).toBe(201);
    if (index === 0) target = created.body.id;
  }
  expect((await call(context, 68, "GET", "/journal/ai-settings")).body.embeddingAvailable).toBe(true);
  await expect.poll(async () => (await call(context, 68, "GET", "/journal/ai-settings")).body.indexedEntries, { timeout: 45000 }).toBe(3);
  async function ask() {
    const created = await call(context, 68, "POST", "/ai/conversations", { botId: "nhatky" });
    expect(created.status).toBe(201);
    await page.goto(`/#/assistants/nhatky?conversation=${created.body.conversationId}`);
    await page.getByRole("textbox", { name: "Tin nhắn cho Nhật ký", exact: true }).fill("[journal-hybrid-e2e] kiệt sức");
    await page.getByRole("button", { name: "Gửi tin cho AI", exact: true }).click();
    await expect(page.getByRole("log", { name: "Cuộc trò chuyện với Nhật ký" })
      .getByText(/^JOURNAL-HYBRID-E2E Một ghi nhận/)).toBeVisible();
  }
  await ask();
  const source = page.locator(`a[href="#/self/entry/${target}"], a[href="/self/entry/${target}"]`);
  await expect(source).toBeVisible();
  await page.reload();
  await expect(source).toBeVisible();
  expect((await call(context, 68, "DELETE", `/journal/entries/${target}`, { expectedVersion: 1 })).status).toBe(200);
  expect((await call(context, 68, "GET", "/journal/ai-settings")).body.indexedEntries).toBe(2);
  await ask();
  await expect(source).toHaveCount(0);
  await context.close();
});
