import { expect, test } from "@playwright/test";
import { app, baseSession } from "./ux-fixtures";

// Keep keyboard input between the React commit and the next animation frame. A
// deferred selection restore must never move the caret behind text already typed.
test.beforeEach(async ({ page }) => {
  const id = "88888888-8888-4888-8888-888888888888";
  await app(page, { ...baseSession, features: { ...baseSession.features, groupChat: true, threeAgentExperience: true } }, {
    [`/ai/groups/${id}`]: () => ({ json: {
      groupId: id, name: "Kế hoạch cuối tuần", version: 1, messages: [], activeTurnId: null,
      members: ["dieuphoi", "nhatky", "hoatdong"].map((botId) => ({ botId, status: "active", journalAccess: false, historyFromSequence: 0, version: 1 })),
    } }),
    [`/ai/groups/${id}/read`]: () => ({ json: {} }),
  });
  await page.goto(`/#/assistants/groups/${id}`);
  const composer = page.getByRole("textbox", { name: "Tin nhắn cho nhóm Kế hoạch cuối tuần" });
  await expect(composer).toBeVisible();
});

for (const method of ["Enter", "Tab", "mouse"] as const) {
test(`typing immediately after choosing a group mention with ${method} keeps every character in order`, async ({ page }) => {
  const composer = page.getByRole("textbox", { name: "Tin nhắn cho nhóm Kế hoạch cuối tuần" });
  await composer.pressSequentially("@nh");
  await expect(page.getByRole("option", { name: "Nhật ký", exact: true })).toBeVisible();
  await page.clock.install();
  await page.clock.pauseAt(new Date());
  if (method === "mouse") await page.getByRole("option", { name: "Nhật ký", exact: true }).click({ force: true });
  else await composer.press(method);
  await composer.pressSequentially("t");
  await page.clock.runFor(32);
  await composer.pressSequentially("uần này mình thế nào?");
  await expect(composer).toHaveValue("@Nhật ký tuần này mình thế nào?");
});
}

test("the mention button keeps the caret inside a draft while typing before the next frame", async ({ page }) => {
  const composer = page.getByRole("textbox", { name: "Tin nhắn cho nhóm Kế hoạch cuối tuần" });
  await composer.fill("trước sau");
  await composer.evaluate((field: HTMLTextAreaElement) => field.setSelectionRange(6, 6));
  await page.clock.install();
  await page.clock.pauseAt(new Date());
  await page.getByRole("button", { name: "Nhắc tên một trợ lý", exact: true }).click({ force: true });
  await composer.pressSequentially("n");
  await page.clock.runFor(32);
  await composer.pressSequentially("h");
  await expect(composer).toHaveValue("trước @nhsau");
  await expect(page.getByRole("option", { name: "Nhật ký", exact: true })).toBeVisible();
});
