import { expect, test } from "./helpers/fixtures";
test("onboarding and mock account lead to four working tabs", async ({
  page,
}) => {
  const external: string[] = [];
  page.on("request", (r) => {
    if (
      !r.url().startsWith("http://127.0.0.1:5178") &&
      !r.url().startsWith("data:")
    )
      external.push(r.url());
  });
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toContainText(
    "khó để nói",
  );
  for (let i = 0; i < 3; i++)
    await page.getByRole("link", { name: "Tiếp tục" }).click();
  await page.getByRole("link", { name: "Bắt đầu", exact: true }).click();
  await expect(page).toHaveURL(/\/auth$/);
  await page
    .getByRole("button", { name: "Vào thử với tài khoản demo" })
    .click();
  await expect(page.getByRole("heading", { level: 1 })).toContainText(
    "Chào An",
  );
  for (const [name, url] of [
    ["AI", "/ai"],
    ["Hồ sơ", "/cases"],
    ["Support", "/support"],
    ["Home", "/home"],
  ]) {
    await page
      .locator(".app-sidebar nav")
      .getByRole("link", { name, exact: true })
      .click();
    await expect(page).toHaveURL(new RegExp(`${url}$`));
  }
  expect(external).toEqual([]);
});
test("account guard preserves deep link and urgent support stays public", async ({
  page,
}) => {
  await page.goto("/cases/CASE-AN-001/plan");
  await expect(page).toHaveURL(/\/auth$/);
  await page
    .getByRole("button", { name: "Vào thử với tài khoản demo" })
    .click();
  await expect(page).toHaveURL(/\/cases\/CASE-AN-001\/plan$/);
  await page.evaluate(() => localStorage.clear());
  await page.goto("/support/urgent");
  await expect(page.locator('a[href="tel:111"]')).toBeVisible();
  await expect(page).toHaveURL(/\/support\/urgent$/);
});
test("school filters use independent dataset and status update stays local", async ({
  page,
}) => {
  await page.goto("/demo/school");
  await expect(page.locator(".admin-kpi").first()).toContainText("48");
  await expect(page.locator(".admin-table tbody tr")).toHaveCount(48);
  await expect(page.locator(".bottom-nav")).toHaveCount(0);
  await page.locator("#category").selectOption("online");
  await expect(page.locator(".admin-kpi").first()).toContainText("15");
  await expect(page.locator(".admin-table tbody tr")).toHaveCount(15);
  await page
    .getByRole("link", { name: "SCHOOL-DEMO-001", exact: true })
    .click();
  await page.locator("#admin-status").selectOption("closed");
  await page.locator("#admin-notes").fill("Ghi chú riêng của báo cáo 001");
  await page.getByRole("button", { name: "Lưu trạng thái demo" }).click();
  await expect(
    page.getByText("Đã cập nhật dữ liệu demo cục bộ. Chưa có ai được liên hệ."),
  ).toBeVisible();
  await page.getByRole("link", { name: "Quay lại", exact: true }).click();
  await page
    .getByRole("link", { name: "SCHOOL-DEMO-002", exact: true })
    .click();
  await expect(page.locator("#admin-notes")).toHaveValue("");
  await page.goto("/auth");
  await page
    .getByRole("button", { name: "Vào thử với tài khoản demo" })
    .click();
  await expect(page.getByRole("heading", { name: /Chào An/ })).toBeVisible();
  await expect(page.getByText("SCHOOL-DEMO-001")).toHaveCount(0);
});
