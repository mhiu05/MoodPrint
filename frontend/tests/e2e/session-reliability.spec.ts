import { expect, test } from "@playwright/test";
import { app, baseSession } from "./ux-fixtures";

test("a transient session recheck keeps the open screen and an unsent draft", async ({ page }) => {
  let failed = false;
  await app(page, baseSession, {
    "/session": () =>
      failed
        ? { status: 503, json: { error: { code: "DATABASE_BUSY", message: "MoodPrint đang hơi đông. Bạn hãy thử lại sau ít giây.", retryable: true } } }
        : undefined,
  });
  await page.goto("/#/assistants/may");
  const composer = page.getByRole("textbox", { name: "Tin nhắn cho Mây" });
  await expect(composer).toBeVisible();
  await composer.fill("mình muốn giữ câu này");
  failed = true;
  await page.evaluate(() => window.dispatchEvent(new Event("focus")));
  await expect(page.getByTestId("connection-status")).toContainText("Kết nối đang gián đoạn");
  await expect(page.getByText("Mây").first()).toBeVisible();
  await expect(composer).toHaveValue("mình muốn giữ câu này");
  await expect(page.getByRole("heading", { name: "Chưa thể mở MoodPrint" })).toHaveCount(0);
});

test("the first visit does not show private content when the session cannot be checked", async ({ page }) => {
  await app(page, baseSession, {
    "/session": () => ({ status: 500, json: { error: { code: "INTERNAL_ERROR", message: "MoodPrint đang gặp chút gián đoạn. Bạn hãy thử lại.", retryable: true } } }),
  });
  await page.goto("/#/assistants");
  await expect(page.getByRole("heading", { name: "Chưa thể mở MoodPrint" })).toBeVisible();
  await expect(page.getByText("Mây")).toHaveCount(0);
});

test("an expired session leaves the private screen immediately", async ({ page }) => {
  let expired = false;
  await app(page, baseSession, {
    "/session": () => (expired ? { status: 401, json: { error: { code: "SESSION_EXPIRED", message: "Phiên đã kết thúc. Vui lòng đăng nhập lại.", retryable: false } } } : undefined),
  });
  await page.goto("/#/assistants");
  await expect(page.getByText("Mây").first()).toBeVisible();
  expired = true;
  await page.evaluate(() => window.dispatchEvent(new Event("focus")));
  await expect(page.getByRole("heading", { name: "Chào bạn trở lại" })).toBeVisible();
  await expect(page.getByText("Mây")).toHaveCount(0);
});

test("focus, visibility and online share one session read", async ({ page }) => {
  await app(page, baseSession);
  await page.goto("/#/assistants");
  await expect(page.getByText("Mây").first()).toBeVisible();
  let reads = 0;
  await page.route("**/api/v1/session", async (route) => {
    reads += 1;
    await route.fulfill({ json: baseSession });
  });
  await page.evaluate(() => {
    window.dispatchEvent(new Event("focus"));
    document.dispatchEvent(new Event("visibilitychange"));
    window.dispatchEvent(new Event("online"));
  });
  await page.waitForTimeout(400);
  expect(reads).toBe(1);
});

test("private content is cleared after the grace period and the draft is not kept", async ({ page }) => {
  await page.clock.install();
  let failed = false;
  await app(page, baseSession, {
    "/session": () =>
      failed
        ? { status: 503, json: { error: { code: "DATABASE_BUSY", message: "MoodPrint đang hơi đông. Bạn hãy thử lại sau ít giây.", retryable: true } } }
        : undefined,
  });
  await page.goto("/#/assistants/may");
  const composer = page.getByRole("textbox", { name: "Tin nhắn cho Mây" });
  await expect(composer).toBeVisible();
  await composer.fill("câu chưa gửi");
  await page.screenshot({ path: "evidence/session-ready-desktop.png" });
  failed = true;
  await page.evaluate(() => window.dispatchEvent(new Event("focus")));
  await page.clock.runFor(2_000);
  await expect(page.getByTestId("connection-status")).toBeVisible();
  await expect(composer).toHaveValue("câu chưa gửi");
  await page.screenshot({ path: "evidence/session-degraded-desktop.png" });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({ path: "evidence/session-degraded-mobile.png" });
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1);
  expect(overflow).toBe(false);
  await page.clock.fastForward(31_000);
  await expect(page.getByRole("heading", { name: "MoodPrint chưa thể kết nối" })).toBeVisible();
  await expect(page.getByText("câu chưa gửi")).toHaveCount(0);
  await expect(page.getByText("Mây")).toHaveCount(0);
});

test("a suspended account is not treated as a temporary outage", async ({ page }) => {
  await app(page, baseSession, {
    "/session": () => ({ status: 403, json: { error: { code: "ACCOUNT_SUSPENDED", message: "Tài khoản đang bị tạm khóa theo quy tắc cộng đồng.", retryable: false } } }),
  });
  await page.goto("/#/assistants");
  await expect(page.getByText("Tài khoản đang bị tạm khóa")).toBeVisible();
  await expect(page.getByText("Mây")).toHaveCount(0);
  await expect(page.getByTestId("connection-status")).toHaveCount(0);
});
