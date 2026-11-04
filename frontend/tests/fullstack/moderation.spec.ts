import { expect, test } from "@playwright/test";
import { call, origin, session } from "./helpers";

// Historical report -> staff queue -> restriction, without the retired human chat UI.
test("a seeded historical report reaches the staff queue and a restriction preserves personal tools", async ({ browser }) => {
  test.setTimeout(150_000);
  const reporter = await browser.newContext();
  const subject = await browser.newContext();
  const staff = await browser.newContext();
  try {
    await session(reporter, 35);
    await session(subject, 36);
    await session(staff, 37);
    const seeded = await reporter.request.post(`${origin}/__test/moderation/seed-report`);
    expect(seeded.status(), await seeded.text()).toBe(200);
    expect((await seeded.json()).id).toMatch(/^[0-9a-f-]{36}$/);
    const evidence = "LOI-LE-QUAY-ROI";
    // Retained backend capability: restriction must still deny old social clients.
    expect((await call(subject, 36, "PUT", "/consents/MATCH", {
      enabled: true, expectedVersion: 1, policyVersion: "v1",
    })).status).toBe(200);
    const denied = await call(reporter, 35, "GET", "/admin/reports");
    expect(denied.status).toBe(403);
    expect(denied.body.error.code).toBe("STAFF_REQUIRED");

    const queue = await staff.newPage();
    await queue.goto("/#/admin/reports");
    const card = queue.getByRole("article").filter({ hasText: evidence });
    await expect(card).toContainText("Quấy rối");
    expect(await card.innerText()).not.toMatch(/@|00000000-0000-4000-8000/);
    await card.getByRole("button", { name: "Nhận xử lý" }).click();
    await expect(queue.getByText("Bạn đang xem xét báo cáo này.")).toBeVisible();
    await card.getByRole("button", { name: "Hạn chế kết nối" }).click();
    const dialog = queue.getByRole("dialog", { name: "Xác nhận: Hạn chế kết nối" });
    await dialog.getByRole("spinbutton", { name: "Số ngày (1–90)" }).fill("7");
    await dialog.getByRole("textbox", { name: /Ghi chú xử lý/ }).fill("E2E restriction");
    await dialog.getByRole("button", { name: "Xác nhận" }).click();
    await expect(queue.getByText("Đã ghi nhận quyết định.")).toBeVisible();

    const blocked = await call(subject, 36, "GET", "/matching/candidates");
    expect(blocked.status).toBe(403);
    expect(blocked.body.error.code).toBe("SOCIAL_RESTRICTED");
    const page = await subject.newPage();
    await page.goto("/#/assistants/may?new=1");
    await expect(page.getByText(/Tài khoản của bạn đang bị hạn chế/)).toBeVisible();
    await expect(page.getByRole("textbox", { name: "Tin nhắn cho Mây" })).toBeEditable();
    await page.goto("/#/self");
    await expect(page.getByRole("heading", { name: "Nhật ký cảm xúc", exact: true })).toBeVisible();
    const resolved = await call(staff, 37, "GET", "/admin/reports?status=resolved");
    expect(resolved.body.some((item: { resolution: string }) => item.resolution === "restricted")).toBe(true);
  } finally {
    await reporter.close();
    await subject.close();
    await staff.close();
  }
});
