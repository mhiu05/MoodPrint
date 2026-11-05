import { expect, test } from "@playwright/test";
import { field, openSearch, searchFixture, send } from "./search-fixtures";

test("weekly review uses its capability name and clears after one accepted turn", async ({ page }) => {
  const seen = await searchFixture(page, { skillsOnly: true, botId: "nhatky" });
  await openSearch(page, "nhatky");
  await page.getByRole("button", { name: "Thêm kỹ năng hoặc công cụ" }).click();
  await page.getByRole("button", { name: /^Kỹ năng / }).click();
  await page.getByRole("button", { name: /^Nhìn lại tuần / }).click();
  await expect(page.locator(".prompt-chips").getByText("Nhìn lại tuần", { exact: true })).toBeVisible();
  await send(page, "Nhìn lại tuần này", "nhatky");
  await expect(page.getByRole("button", { name: "Bỏ kỹ năng" })).toHaveCount(0);
  expect(seen.sends[0].promptOptions.skillId).toBe("weekly-review");
  await send(page, "Cảm ơn", "nhatky");
  expect(seen.sends[1].promptOptions).toEqual({});
});

test("journal skills are disabled with a reason for the activity agent", async ({ page }) => {
  await searchFixture(page, { skillsOnly: true });
  await openSearch(page);
  await page.getByRole("button", { name: "Thêm kỹ năng hoặc công cụ" }).click();
  await page.getByRole("button", { name: /^Kỹ năng / }).click();
  const weekly = page.getByRole("button", { name: /^Nhìn lại tuần / });
  await expect(weekly).toBeDisabled();
  await expect(weekly).toHaveAttribute("title", "Kỹ năng này dành cho trợ lý Nhật ký.");
});

for (const width of [320, 390, 768, 1280]) {
  test(`manual skill is one-turn, keyboard focus and no overflow at ${width}`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    const seen = await searchFixture(page, { skillsOnly: true });
    await openSearch(page);
    const plus = page.getByRole("button", { name: "Thêm kỹ năng hoặc công cụ" });
    await plus.focus(); await page.keyboard.press("Enter");
    await expect(page.getByRole("group", { name: "Kỹ năng và công cụ" })).toBeVisible();
    await page.keyboard.press("Escape"); await expect(plus).toBeFocused();
    await plus.click();
    await page.getByRole("button", { name: /^Kỹ năng / }).click();
    await page.getByRole("button", { name: /Học điều mới Thử một điều mới/ }).click();
    await expect(field(page)).toBeFocused();
    await expect(page.getByRole("button", { name: "Bỏ kỹ năng" })).toBeVisible();
    await send(page, "Có 10 phút muốn học điều mới");
    await expect(page.getByRole("button", { name: "Bỏ kỹ năng" })).toHaveCount(0);
    expect(seen.sends[0].promptOptions.skillId).toBe("learn-new-thing");
    await send(page, "Cảm ơn");
    expect(seen.sends[1].promptOptions).toEqual({});
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  });
}
test("rejected unknown send keeps text, selection and id for explicit retry", async ({ page }) => {
  const seen = await searchFixture(page, { failFirst: true });
  await openSearch(page);
  await page.getByRole("button", { name: "Thêm kỹ năng hoặc công cụ" }).click();
  await page.getByRole("button", { name: /^Kỹ năng / }).click();
  await page.getByRole("button", { name: /Đi chơi Gợi ý hoạt động/ }).click();
  await field(page).fill("Gợi ý đi chơi");
  await page.getByRole("button", { name: "Gửi tin cho AI", exact: true }).click();
  await expect(field(page)).toHaveValue("Gợi ý đi chơi");
  await expect(page.getByRole("button", { name: "Bỏ kỹ năng" })).toBeVisible();
  await page.getByRole("button", { name: "Gửi tin cho AI", exact: true }).click();
  await expect(field(page)).toHaveValue("");
  expect(seen.sends[1].clientMessageId).toBe(seen.sends[0].clientMessageId);
  expect(seen.sends[1].promptOptions).toEqual(seen.sends[0].promptOptions);
});
