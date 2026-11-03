import { expect, test } from "@playwright/test";
import { field, openSearch, searchFixture, send, SOURCE } from "./search-fixtures";

test("manual Web keeps clickable provenance live and after reload", async ({ page }) => {
  const seen = await searchFixture(page);
  await openSearch(page);
  await page.getByRole("button", { name: "Thêm kỹ năng hoặc công cụ" }).click();
  await page.getByRole("button", { name: "Web Search Tìm kiếm công khai" }).click();
  await send(page, "Thông tin về Python");
  const link = page.getByRole("link", { name: "Nguồn: Thông tin công khai" });
  await expect(link).toHaveAttribute("href", SOURCE);
  await expect(link).toHaveAttribute("rel", "noopener noreferrer");
  await expect(link).toHaveAttribute("referrerpolicy", "no-referrer");
  expect(seen.sends[0].responseProtocol).toBe(3);
  await page.reload();
  await expect(link).toBeVisible();
});
test("auto fresh-info uses source response without a sticky option", async ({ page }) => {
  const seen = await searchFixture(page);
  await openSearch(page);
  await send(page, "Tin mới nhất về Python");
  await expect(page.getByRole("link", { name: "Nguồn: Thông tin công khai" })).toBeVisible();
  expect(seen.sends[0].promptOptions).toEqual({});
});

for (const outcome of ["empty", "timeout", "rate_limit", "budget"] as const) {
  test(`Web ${outcome} stays uncited across reload and permits a normal next turn`, async ({ page }) => {
    const seen = await searchFixture(page, { webOutcome: outcome });
    await openSearch(page);
    await page.getByRole("button", { name: "Thêm kỹ năng hoặc công cụ" }).click();
    await page.getByRole("button", { name: "Web Search Tìm kiếm công khai" }).click();
    await send(page, "Thông tin về Python");
    await expect(page.getByRole("log")).toContainText("chưa xác minh được");
    await expect(page.getByRole("link", { name: /^Nguồn:/ })).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Bỏ Web Search" })).toHaveCount(0);
    await page.reload();
    await expect(page.getByRole("log")).toContainText("chưa xác minh được");
    await expect(page.getByRole("link", { name: /^Nguồn:/ })).toHaveCount(0);
    expect(seen.sends).toHaveLength(1);
    await send(page, "Cảm ơn");
    expect(seen.sends[1].promptOptions).toEqual({});
  });
}

test("cancelling a Web turn publishes no source and keeps the next draft", async ({ page }) => {
  const seen = await searchFixture(page, { webOutcome: "cancel" });
  await openSearch(page);
  await page.getByRole("button", { name: "Thêm kỹ năng hoặc công cụ" }).click();
  await page.getByRole("button", { name: "Web Search Tìm kiếm công khai" }).click();
  await field(page).fill("Thông tin về Python");
  await page.getByRole("button", { name: "Gửi tin cho AI", exact: true }).click();
  await expect(field(page)).toHaveValue("");
  await field(page).fill("Mình muốn hỏi chuyện khác");
  await page.getByRole("button", { name: "Dừng phản hồi", exact: true }).click();
  await expect(page.getByRole("log")).toContainText("Đã dừng phản hồi.");
  await expect(field(page)).toHaveValue("Mình muốn hỏi chuyện khác");
  await expect(page.getByRole("link", { name: /^Nguồn:/ })).toHaveCount(0);
  expect(seen.cancels).toBe(1);
  expect(seen.sends).toHaveLength(1);
  await page.getByRole("button", { name: "Gửi tin cho AI", exact: true }).click();
  await expect(field(page)).toHaveValue("");
  expect(seen.sends[1].promptOptions).toEqual({});
});
