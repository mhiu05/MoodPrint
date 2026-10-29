import { expect, test } from "@playwright/test";
import { call, session } from "./helpers";

test("real journal HTTP/DB preserves two moments and old mood through reload, edit and delete", async ({
  browser,
}) => {
  const owner = await browser.newContext(),
    other = await browser.newContext();
  await session(owner, 41);
  await session(other, 42);
  const page = await owner.newPage();
  const state = (await call(owner, 41, "GET", "/session")).body;
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: state.timezone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(new Date(state.serverTime));
  const today = ["year", "month", "day"]
    .map((type) => parts.find((part) => part.type === type)!.value)
    .join("-");
  const legacy = await call(owner, 41, "PUT", `/moods/${today}`, {
    value: 2,
    note: "PRIVATE_LEGACY_NOTE",
    timezone: state.timezone,
    expectedVersion: 0,
  });
  expect(legacy.status).toBe(200);
  await page.goto("/#/self");
  await page
    .getByLabel("Khoảnh khắc của bạn", { exact: true })
    .fill("Một buổi sáng bình yên REAL_JOURNAL");
  await page
    .getByRole("button", { name: "Lưu khoảnh khắc", exact: true })
    .click();
  await expect(
    page.getByRole("status").filter({ hasText: "Đã lưu khoảnh khắc" }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Viết khoảnh khắc mới", exact: true })
    .click();
  await page
    .getByLabel("Khoảnh khắc của bạn", { exact: true })
    .fill("Buổi chiều cần nghỉ một chút REAL_JOURNAL");
  await page
    .getByRole("button", { name: "Lưu khoảnh khắc", exact: true })
    .click();
  await expect(
    page.getByRole("status").filter({ hasText: "Đã lưu khoảnh khắc" }),
  ).toBeVisible();
  const rows = (await call(owner, 41, "GET", "/journal/entries")).body;
  expect(rows.total).toBe(2);
  expect(rows.items[0].id).not.toBe(rows.items[1].id);
  expect(
    (await call(other, 42, "GET", `/journal/entries/${rows.items[0].id}`))
      .status,
  ).toBe(404);
  expect((await call(owner, 41, "GET", "/moods")).body[0].note).toBe(
    "PRIVATE_LEGACY_NOTE",
  );
  await page.reload();
  await page.getByRole("link", { name: "Lịch nhật ký", exact: true }).click();
  await expect(page.locator(".journal-calendar-entries")).toContainText(
    "2 khoảnh khắc",
  );
  await page
    .getByRole("link", { name: "Khoảnh khắc của bạn", exact: true })
    .click();
  await page.getByLabel("Tìm trong nhật ký", { exact: true }).fill("buổi sáng");
  await page.getByRole("button", { name: "Tìm kiếm", exact: true }).click();
  await expect(
    page.getByText("Một buổi sáng bình yên REAL_JOURNAL", { exact: true }),
  ).toBeVisible();
  await page.getByRole("link", { name: /Mở khoảnh khắc ngày/ }).click();
  await page
    .getByRole("button", { name: "Chỉnh sửa khoảnh khắc", exact: true })
    .click();
  await page
    .getByLabel("Khoảnh khắc của bạn", { exact: true })
    .fill("Đã sửa REAL_JOURNAL");
  await page
    .getByRole("button", { name: "Lưu khoảnh khắc", exact: true })
    .click();
  await expect(
    page.getByRole("status").filter({ hasText: "Đã lưu khoảnh khắc" }),
  ).toBeVisible();
  await page.reload();
  await expect(
    page.getByText("Đã sửa REAL_JOURNAL", { exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Xóa khoảnh khắc", exact: true })
    .click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await page
    .getByRole("button", { name: "Xóa vĩnh viễn", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Khoảnh khắc của bạn", exact: true }),
  ).toBeVisible();
  expect((await call(owner, 41, "GET", "/journal/entries")).body.total).toBe(1);
  await owner.close();
  await other.close();
});
