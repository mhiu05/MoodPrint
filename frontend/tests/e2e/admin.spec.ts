import { expect, test, type Page } from "@playwright/test";

function sessionFor(staff: string | null) {
  return {
    userId: "11111111-1111-4111-8111-111111111111",
    alias: "An",
    ageBand: "adult",
    eligible: true,
    csrfToken: "test-csrf",
    serverTime: "2026-10-23T08:00:00Z",
    timezone: "Asia/Bangkok",
    features: { ai: false, matching: true, voice: false },
    staff,
    notices: [],
    consents: Object.fromEntries(
      ["AI", "MEM", "MATCH", "VOICE"].map((p) => [
        p,
        { enabled: p === "MATCH", version: 1, policyVersion: "v1" },
      ]),
    ),
  };
}

const report = {
  id: "r1",
  status: "received",
  version: 1,
  reason: "Quấy rối",
  createdAt: "2026-10-23T07:00:00Z",
  subjectRef: "s-abcdef0123456789",
  reporterRef: "r-abcdef012345",
  evidence: [
    { kind: "message", text: "Tin nhắn quấy rối" },
    { kind: "activity", text: "Câu trả lời xúc phạm" },
  ],
  priorActions: 0,
};

async function mock(page: Page, staff: string | null, posts: { path: string; body: unknown }[], fail = false) {
  let current = { ...report };
  await page.route("**/api/v1/**", async (route) => {
    const request = route.request(),
      path = new URL(request.url()).pathname.replace("/api/v1", "");
    if (path === "/session") return route.fulfill({ json: sessionFor(staff) });
    if (path === "/social/summary")
      return route.fulfill({ json: { pendingIncomingRequests: 0, unreadConnections: 0, activityInvites: 0 } });
    if (path === "/admin/reports")
      return route.fulfill({ json: current.status === "resolved" ? [] : [current] });
    if (request.method() === "POST" && path.startsWith("/admin/reports/r1/")) {
      posts.push({ path, body: request.postDataJSON() });
      if (fail)
        return route.fulfill({
          status: 409,
          json: { error: { code: "REPORT_CHANGED", message: "Báo cáo vừa được người khác xử lý." } },
        });
      current = path.endsWith("/claim")
        ? { ...current, status: "in_review", version: 2 }
        : { ...current, status: "resolved", version: 3 };
      return route.fulfill({ json: current });
    }
    if (path === "/bots") return route.fulfill({ json: [] });
    return route.fulfill({ status: 404, json: { error: { code: "NOT_FOUND", message: "Missing" } } });
  });
}

test("non-staff sessions never see the moderation route", async ({ page }) => {
  await mock(page, null, []);
  await page.goto("/#/admin/reports");
  await expect(page).toHaveURL(/#\/assistants/);
  await expect(page.getByRole("heading", { name: "Kiểm duyệt báo cáo" })).toHaveCount(0);
});

test("staff claim and resolve a report after confirming", async ({ page }) => {
  const posts: { path: string; body: any }[] = [];
  await mock(page, "moderator", posts);
  await page.goto("/#/admin/reports");
  const card = page.getByRole("article", { name: /Báo cáo s-abcdef/ });
  await expect(card).toContainText("Tin nhắn quấy rối");
  await expect(card).toContainText("Câu trả lời hoạt động: Câu trả lời xúc phạm");
  await card.getByRole("button", { name: "Nhận xử lý" }).click();
  await expect(page.getByRole("status").filter({ hasText: "Bạn đang xem xét" })).toBeVisible();
  await card.getByRole("button", { name: "Hạn chế kết nối" }).click();
  const dialog = page.getByRole("dialog", { name: "Xác nhận: Hạn chế kết nối" });
  await dialog.getByRole("spinbutton", { name: "Số ngày (1–90)" }).fill("14");
  await dialog.getByRole("textbox", { name: /Ghi chú nội bộ/ }).fill("Lặp lại nhiều lần");
  await dialog.getByRole("button", { name: "Xác nhận" }).click();
  await expect(page.getByText("Hàng đợi đang trống.")).toBeVisible();
  expect(posts.at(-1)).toEqual({
    path: "/admin/reports/r1/resolve",
    body: { expectedVersion: 2, action: "restrict", note: "Lặp lại nhiều lần", days: 14 },
  });
});

test("a conflicting decision shows the server error", async ({ page }) => {
  await mock(page, "moderator", [], true);
  await page.goto("/#/admin/reports");
  await page.getByRole("button", { name: "Nhận xử lý" }).click();
  await expect(page.getByText("Báo cáo vừa được người khác xử lý.")).toBeVisible();
});
