import { test, expect } from "./helpers/fixtures";
import { companionLive } from "./helpers/capabilities";
import {
  createCaseViaApi,
  createUser,
  login,
  removeUser,
} from "./helpers/local";

test("N-01 E-SCH-01: fourteen real routes fit all eight widths and school demo stays independent", async ({
  page,
}) => {
  // Eight widths times fourteen authenticated routes. A loaded machine needs more than three minutes.
  test.setTimeout(360000);
  const user = await createUser();
  try {
    const item = await createCaseViaApi(user.email);
    await login(page, user.email);
    await expect(page).toHaveURL(/\/home$/);
    const routes = [
      "/home",
      "/ai",
      "/ai/chat",
      "/cases",
      "/cases/new",
      `/cases/${item.id}/timeline`,
      `/cases/${item.id}/plan`,
      "/ai/roleplay/teacher",
      "/support/knowledge",
      "/knowledge/treu-dua-hay-bat-nat",
      "/support",
      "/support/prepare",
      "/support/urgent",
      "/demo/school",
    ];
    await page.emulateMedia({ reducedMotion: "reduce" });
    for (const width of [320, 360, 375, 390, 430, 768, 1024, 1440]) {
      await page.setViewportSize({ width, height: 900 });
      for (const path of routes) {
        await page.goto(path);
        await expect(page).toHaveURL(path);
        await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
        expect(
          await page.evaluate(() => document.documentElement.scrollWidth),
          `${path} at ${width}px`,
        ).toBeLessThanOrEqual(width);
      }
    }
    await expect(page.locator(".admin-table tbody tr")).toHaveCount(48);
    const writes: string[] = [];
    page.on("request", (request) => {
      if (
        request.url().startsWith(process.env.E2E_API_URL!) &&
        request.method() !== "GET"
      )
        writes.push(request.method());
    });
    await page
      .getByRole("link", { name: "SCHOOL-DEMO-001", exact: true })
      .click();
    await page.locator("#admin-status").selectOption("closed");
    await page.getByRole("button", { name: "Lưu trạng thái demo" }).click();
    await expect(
      page.getByText(
        "Đã cập nhật dữ liệu demo cục bộ. Chưa có ai được liên hệ.",
      ),
    ).toBeVisible();
    expect(writes).toEqual([]);
    await page.goto("/ai/chat");
    await expect(
      companionLive
        ? page.getByTestId("chat-live")
        : page.getByText(/AI mô phỏng/).first(),
    ).toBeVisible();
    await page
      .getByRole("textbox", { name: "Điều bạn muốn kể" })
      .fill("Một câu chuyện hoàn toàn hư cấu.");
    await page
      .getByRole("textbox", { name: "Điều bạn muốn kể" })
      .press("Enter");
    await expect(page.locator(".ai-message.ai")).toHaveCount(1);
    if (!companionLive) expect(writes).toEqual([]);
  } finally {
    await removeUser(user.email);
  }
});
