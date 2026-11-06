import { expect, test } from "@playwright/test";
import { app, baseSession, guestSession } from "./ux-fixtures";

test("registered account keeps journal search and auto memory on without a settings section", async ({ page }) => {
  const requests: string[] = [];
  page.on("request", request => { if (request.url().includes("/journal/ai-settings")) requests.push(request.url()); });
  await app(page, baseSession);
  await page.goto("/#/profile");
  await expect(page.getByRole("heading", { name: "Tài khoản", exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Nhật ký và trợ lý AI" })).toHaveCount(0);
  await expect(page.getByText(/Voyage AI/)).toHaveCount(0);
  await expect(page.getByText(/Đã lập chỉ mục/)).toHaveCount(0);
  await expect(page.getByRole("checkbox", { name: "Tìm theo ý nghĩa trong nhật ký" })).toHaveCount(0);
  await expect(page.getByRole("checkbox", { name: "Tự ghi nhớ điều quan trọng từ nhật ký" })).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "Tài khoản & hỗ trợ" })).toBeVisible();
  expect(requests).toEqual([]);
});

test("guest account never requests journal derivation preferences", async ({ page }) => {
  const requests: string[] = [];
  page.on("request", request => { if (request.url().includes("/journal/ai-settings")) requests.push(request.url()); });
  await app(page, guestSession(7_000_000));
  await page.goto("/#/profile");
  await expect(page.getByRole("heading", { name: "Nhật ký và trợ lý AI" })).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "Tài khoản", exact: true })).toBeVisible();
  expect(requests).toEqual([]);
});
