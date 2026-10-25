import { expect, test } from "@playwright/test";
import { call, openRoom, pairAlias, session } from "./helpers";

// Report -> staff queue -> restriction, end to end (reporter 35, subject 36, staff 37).

test("a report reaches the staff queue and a restriction removes the subject from discovery", async ({
  browser,
}) => {
  test.setTimeout(150_000);
  const { one, two, pageA, pageB, room, close } = await openRoom(browser, 35, 36);
  const staff = await browser.newContext();
  try {
    const evidence = "LOI-LE-QUAY-ROI";
    await pageB.getByRole("textbox", { name: "Tin nhắn cho bạn kết nối" }).fill(evidence);
    await pageB.getByRole("button", { name: "Gửi tin nhắn" }).click();
    await expect(pageA.getByRole("log")).toContainText(evidence);

    // Non-staff cannot reach the queue.
    const denied = await call(one, 35, "GET", "/admin/reports");
    expect(denied.status).toBe(403);
    expect(denied.body.error.code).toBe("STAFF_REQUIRED");

    await pageA.getByText("Chia sẻ và an toàn").click();
    await pageA.getByLabel("Lý do báo cáo").fill("Quấy rối");
    await pageA.getByRole("checkbox", { name: evidence }).check();
    await pageA.getByRole("button", { name: "Gửi báo cáo" }).click();
    await expect(pageA.getByText("Đã nhận báo cáo.")).toBeVisible();

    await session(staff, 37);
    const queue = await staff.newPage();
    await queue.goto("/#/admin/reports");
    const card = queue.getByRole("article").filter({ hasText: evidence });
    await expect(card).toContainText("Quấy rối");
    // Opaque references only: no email or raw user id on the screen.
    expect(await card.innerText()).not.toMatch(/@|00000000-0000-4000-8000/);
    await card.getByRole("button", { name: "Nhận xử lý" }).click();
    await expect(queue.getByText("Bạn đang xem xét báo cáo này.")).toBeVisible();
    await card.getByRole("button", { name: "Hạn chế kết nối" }).click();
    const dialog = queue.getByRole("dialog", { name: "Xác nhận: Hạn chế kết nối" });
    await dialog.getByRole("spinbutton", { name: "Số ngày (1–90)" }).fill("7");
    await dialog.getByRole("textbox", { name: /Ghi chú nội bộ/ }).fill("E2E restriction");
    await dialog.getByRole("button", { name: "Xác nhận" }).click();
    await expect(queue.getByText("Đã ghi nhận quyết định.")).toBeVisible();

    // The subject is restricted: no discovery, a notice, and the room is closed.
    const blocked = await call(two, 36, "GET", "/matching/candidates");
    expect(blocked.status).toBe(403);
    expect(blocked.body.error.code).toBe("SOCIAL_RESTRICTED");
    // Notices come with the session, which a hash navigation does not refetch.
    await pageB.goto("/#/messages");
    await pageB.reload();
    await expect(pageB.getByText(/Tính năng kết nối của bạn đang tạm bị hạn chế/)).toBeVisible();
    const access = await call(one, 35, "GET", `/connections/${room}`);
    expect([403, 404, 410]).toContain(access.status);
    const cards = await call(one, 35, "GET", "/matching/candidates");
    expect(
      cards.body.candidates.map((item: { alias: string }) => item.alias),
    ).not.toContain(pairAlias(35, 36));
  } finally {
    await staff.close();
    await close();
  }
});
