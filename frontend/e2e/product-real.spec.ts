import { test, expect } from "./helpers/fixtures";
import {
  apiJson,
  createCaseViaApi,
  createUser,
  login,
  removeUser,
  tokenFor,
} from "./helpers/local";

test("PC-UI: case context reaches chat and practice; live composer fits seven exact viewports", async ({
  page,
}) => {
  test.setTimeout(120000);
  const user = await createUser("Người chứng kiến tổng hợp");
  try {
    const { id: caseId } = await createCaseViaApi(user.email);
    await page.addInitScript(() =>
      localStorage.setItem("safevoice:ai-companion", "live"),
    );
    await login(page, user.email);
    await expect(page).toHaveURL(/\/home$/);
    await page.goto(`/cases/${caseId}`);
    await page
      .getByRole("link", { name: "Trao đổi về hồ sơ", exact: true })
      .click();
    await expect(page.getByLabel("Hồ sơ muốn trao đổi")).toHaveValue(caseId);
    await page.getByRole("button", { name: /Cuộc trò chuyện mới/ }).click();
    await expect(
      page.getByRole("link", { name: /Trở lại hồ sơ/ }),
    ).toHaveAttribute("href", `/cases/${caseId}`);
    const conversationId = new URL(page.url()).pathname.split("/").pop();
    const conversation = await apiJson(
      `/v1/conversations/${conversationId}`,
      await tokenFor(user.email),
    );
    expect((await conversation.json()).linkedCaseId).toBe(caseId);
    await page.reload();
    await expect(
      page.getByRole("link", { name: /Trở lại hồ sơ/ }),
    ).toBeVisible();
    const input = page.getByRole("textbox", { name: "Điều bạn muốn kể" });
    await input.fill("Mình muốn kể thêm về tình huống hư cấu này.");
    await input.press("Enter");
    await expect(page.getByTestId("live-assistant")).toHaveCount(1);
    for (const [width, height] of [
      [320, 720],
      [360, 800],
      [390, 844],
      [430, 932],
      [768, 1024],
      [1024, 768],
      [1440, 900],
    ]) {
      await page.setViewportSize({ width, height });
      expect(
        await page.evaluate(() => document.documentElement.scrollWidth),
      ).toBeLessThanOrEqual(width);
      const composer = await page.locator(".live-composer").boundingBox();
      expect(composer!.y + composer!.height).toBeLessThanOrEqual(height);
      await expect(
        page.getByRole("link", { name: "Tìm hỗ trợ ngay", exact: true }),
      ).toBeVisible();
    }
    await page.getByRole("link", { name: /Trở lại hồ sơ/ }).click();
    await page
      .getByRole("link", { name: "Luyện cách trình bày", exact: true })
      .click();
    await page.getByRole("radio").first().check();
    await expect(
      page.getByLabel(/Cho AI dùng tóm tắt hồ sơ/),
    ).not.toBeChecked();
    await page
      .getByRole("button", { name: "Bắt đầu diễn tập", exact: true })
      .click();
    await expect(
      page.getByRole("link", { name: "Trở lại hồ sơ", exact: true }),
    ).toHaveAttribute("href", `/cases/${caseId}`);
    await page
      .getByRole("button", { name: "Thoát, không cần phản hồi", exact: true })
      .click();
    await page
      .getByRole("button", { name: "Luyện một tình huống khác", exact: true })
      .click();
    await expect(
      page.getByLabel(/Cho AI dùng tóm tắt hồ sơ/),
    ).not.toBeChecked();
    await page.getByLabel(/Cho AI dùng tóm tắt hồ sơ/).check();
    await page
      .getByRole("button", { name: "Bắt đầu diễn tập", exact: true })
      .click();
    await expect(
      page.getByRole("link", { name: "Trở lại hồ sơ", exact: true }),
    ).toHaveAttribute("href", `/cases/${caseId}`);
    await page
      .getByRole("button", { name: "Thoát, không cần phản hồi", exact: true })
      .click();
    await page
      .getByRole("button", { name: "Luyện một tình huống khác", exact: true })
      .click();
    await expect(
      page.getByLabel(/Cho AI dùng tóm tắt hồ sơ/),
    ).not.toBeChecked();
  } finally {
    await page.close();
    await removeUser(user.email);
  }
});
