import { expect, test } from "@playwright/test";
for (const width of [390, 1440]) {
  test(`full journey ${width}px: chat → eight screenshots → confirmed timeline → case → plan → roleplay → support`, async ({
    page,
  }) => {
    test.setTimeout(90000);
    await page.setViewportSize({ width, height: 900 });
    const errors: string[] = [];
    const external: string[] = [];
    page.on("pageerror", (error) => errors.push(error.message));
    page.on("request", (request) => {
      if (
        !request.url().startsWith("http://127.0.0.1:5178") &&
        !request.url().startsWith("data:") &&
        !request.url().startsWith("blob:")
      )
        external.push(request.url());
    });
    await page.goto("/welcome/1");
    await page.getByRole("link", { name: "Bỏ qua" }).click();
    await page.getByRole("button", { name: /M Minh/ }).click();
    await page
      .getByRole("button", { name: "Vào thử với tài khoản demo" })
      .click();
    await page.getByRole("link", { name: "Bắt đầu trò chuyện" }).click();
    await page.locator(".ai-quick-reply button").click();
    await expect(page.locator(".ai-message.ai")).toContainText("nhiều lần", {
      timeout: 10000,
    });
    await page.locator(".ai-quick-reply button").click();
    await expect(page.locator(".ai-message.ai").last()).toContainText(
      "ảnh hưởng",
      { timeout: 10000 },
    );
    await page.locator(".ai-quick-reply button").click();
    await expect(page.locator(".ai-findings")).toBeVisible({ timeout: 10000 });
    await page.getByRole("button", { name: "Đính kèm dữ liệu mẫu" }).click();
    await page.getByRole("button", { name: /8 ảnh nhóm lớp/ }).click();
    await expect(page.locator(".ai-evidence-row")).toHaveCount(8);
    await expect(
      page.getByRole("button", { name: "Tạo hồ sơ từ nội dung đã xác nhận" }),
    ).toHaveCount(0);
    await page.getByRole("button", { name: "Xem phân tích mô phỏng" }).click();
    await expect(
      page.getByRole("button", { name: "Tạo hồ sơ từ nội dung đã xác nhận" }),
    ).toBeDisabled();
    for (let i = 0; i < 6; i++)
      await page
        .locator(".ai-evidence-row")
        .nth(i)
        .getByRole("button", { name: "Xác nhận nội dung", exact: true })
        .click();
    await expect(page.locator(".ai-timeline li")).toHaveCount(6);
    await page.screenshot({
      path: `../docs/prototype/screenshots/analysis-${width}px.png`,
      fullPage: true,
    });
    await page
      .getByRole("button", { name: "Tạo hồ sơ từ nội dung đã xác nhận" })
      .click();
    await page
      .getByRole("button", { name: "Xác nhận và tạo hồ sơ", exact: true })
      .click();
    await expect(page).toHaveURL(/\/cases\/CASE-/);
    const caseUrl = page.url();
    await page
      .getByRole("link", { name: "Dòng thời gian", exact: true })
      .click();
    await expect(page.locator(".case-timeline li")).toHaveCount(6);
    await page
      .getByRole("link", { name: "Kế hoạch ứng phó", exact: true })
      .click();
    await page
      .getByRole("button", { name: "Chọn phương án này" })
      .first()
      .click();
    await page
      .getByRole("button", { name: "Lưu kế hoạch", exact: true })
      .filter({ visible: true })
      .first()
      .click();
    await expect(page.locator(".plan-save button")).toBeDisabled();
    await page
      .getByRole("button", { name: /^Hoàn tất:/ })
      .first()
      .click();
    await page.getByRole("button", { name: "Bỏ qua ghi chú" }).click();
    await page
      .getByRole("button", { name: "Lưu thay đổi", exact: true })
      .click();
    await page
      .getByRole("link", { name: "Luyện nói trước", exact: true })
      .click();
    await page.getByRole("button", { name: "Bắt đầu buổi luyện" }).click();
    for (let i = 0; i < 3; i++) {
      await page.getByRole("button", { name: "Dùng câu gợi ý" }).click();
      await page
        .getByRole("button", { name: "Nói câu này", exact: true })
        .click();
      await expect(page.locator(".ai-turn-status")).toHaveCount(0);
    }
    await page.getByRole("link", { name: "Xem gợi ý sau buổi tập" }).click();
    await expect(
      page.getByRole("heading", { name: "Điều đã luyện rõ" }),
    ).toBeVisible();
    await page.locator(".ai-transcript-choice input").first().check();
    await page
      .getByRole("button", { name: /Chuẩn bị lời nhắn từ 1 đoạn/ })
      .click();
    await expect(page).toHaveURL(/\/support\/prepare/);
    await expect(page.locator("#support-preview")).not.toHaveValue("");
    await page
      .getByRole("button", { name: "Lưu báo cáo demo", exact: true })
      .click();
    await page
      .getByRole("checkbox", { name: /Tôi hiểu đây chỉ là mô phỏng/ })
      .check();
    await page.getByRole("button", { name: "Xác nhận lưu mô phỏng" }).click();
    await expect(
      page.locator(".support-preview").getByText(/Đã lưu mô phỏng, chưa gửi/),
    ).toBeVisible();
    await page.screenshot({
      path: `../docs/prototype/screenshots/support-message-${width}px.png`,
      fullPage: true,
    });
    await page.reload();
    await page.goto(caseUrl + "/timeline");
    await expect(page.locator(".case-timeline li")).toHaveCount(6);
    expect(errors).toEqual([]);
    expect(external).toEqual([]);
  });
}
