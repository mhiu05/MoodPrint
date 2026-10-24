import { expect, test, type BrowserContext } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

async function syntheticSession(context: BrowserContext) {
  await context.addCookies([
    {
      name: "moodprint_session",
      value: "e2e-synthetic-session-6",
      url: "http://127.0.0.1:5174",
      httpOnly: true,
      sameSite: "Strict",
    },
    {
      name: "moodprint_csrf",
      value: "e2e-synthetic-csrf-6",
      url: "http://127.0.0.1:5174",
      sameSite: "Strict",
    },
  ]);
}

test("real saved history requires opt-in, resumes by URL, and stays manageable after AI/history withdrawal", async ({
  browser,
}) => {
  const context = await browser.newContext({
    baseURL: "http://127.0.0.1:5174",
    acceptDownloads: true,
    reducedMotion: "reduce",
    viewport: { width: 1440, height: 960 },
  });
  await syntheticSession(context);
  const page = await context.newPage();
  const consoleErrors: string[] = [];
  page.on("pageerror", (error) => consoleErrors.push(error.message));
  await page.goto("/#/settings");
  const history = page.getByRole("checkbox", {
    name: "Lưu lịch sử trò chuyện",
    exact: true,
  });
  const semantic = page.getByRole("checkbox", {
    name: "Tìm ghi nhớ theo ngữ nghĩa qua Voyage",
    exact: true,
  });
  await expect(history).not.toBeChecked();
  await expect(semantic).not.toBeChecked();
  await history.check();
  await expect(
    page.getByText("Đã cập nhật lựa chọn dữ liệu AI.", { exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Bật trò chuyện AI", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Tắt trò chuyện AI", exact: true }),
  ).toBeVisible();
  await page.goto("/#/assistants/may");
  await page
    .getByRole("textbox", { name: "Tin nhắn cho Mây", exact: true })
    .fill("Một buổi sáng tổng hợp để kiểm tra lịch sử");
  await page
    .getByRole("button", { name: "Gửi tin cho AI", exact: true })
    .click();
  await expect(
    page
      .getByRole("log")
      .getByText("Mây đã nhận được chia sẻ của bạn qua SDK.", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Dừng", exact: true }),
  ).toHaveCount(0);
  const selectedUrl = page.url();
  const conversationId = new URLSearchParams(selectedUrl.split("?")[1]).get(
    "conversation",
  )!;
  expect(conversationId).toMatch(/^[a-f0-9-]{36}$/);
  const stored = await context.request.get(
    `/api/v1/ai/conversations/${conversationId}`,
  );
  expect(stored.ok(), await stored.text()).toBe(true);
  expect((await stored.json()).persistent).toBe(true);
  await page.reload();
  await expect(
    page
      .getByRole("log")
      .getByText("Một buổi sáng tổng hợp để kiểm tra lịch sử", { exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Cuộc trò chuyện mới", exact: true })
    .click();
  await expect(
    page
      .getByRole("log")
      .getByText("Một buổi sáng tổng hợp để kiểm tra lịch sử", { exact: true }),
  ).toHaveCount(0);
  await page
    .getByRole("textbox", { name: "Tin nhắn cho Mây", exact: true })
    .fill("Một cuộc trò chuyện riêng thứ hai");
  await page
    .getByRole("button", { name: "Gửi tin cho AI", exact: true })
    .click();
  await expect(
    page
      .getByRole("log")
      .getByText("Mây đã nhận được chia sẻ của bạn qua SDK.", { exact: true }),
  ).toBeVisible();
  await page
    .getByRole("region", { name: "Lịch sử hội thoại", exact: true })
    .getByRole("link", { name: /Một buổi sáng tổng hợp/ })
    .click();
  await expect(
    page
      .getByRole("log")
      .getByText("Một buổi sáng tổng hợp để kiểm tra lịch sử", { exact: true }),
  ).toBeVisible();
  await expect(
    page
      .getByRole("log")
      .getByText("Một cuộc trò chuyện riêng thứ hai", { exact: true }),
  ).toHaveCount(0);
  await page.screenshot({
    path: "evidence/ai-chat-memory/history-desktop.png",
    fullPage: true,
  });
  await page.goto("/#/settings");
  await history.uncheck();
  await expect(
    page.getByText("Đã cập nhật lựa chọn dữ liệu AI.", { exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Tắt trò chuyện AI", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Bật trò chuyện AI", exact: true }),
  ).toBeVisible();
  await page.goto(selectedUrl);
  await expect(
    page
      .getByRole("log")
      .getByText("Một buổi sáng tổng hợp để kiểm tra lịch sử", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Gửi tin cho AI", exact: true }),
  ).toHaveCount(0);
  await page.setViewportSize({ width: 390, height: 844 });
  await page
    .getByRole("button", { name: "Mở lịch sử hội thoại", exact: true })
    .click();
  await expect(
    page
      .getByRole("dialog")
      .getByRole("link", { name: /Một buổi sáng tổng hợp/ }),
  ).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).toHaveCount(0);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  const accessibility = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
    .analyze();
  expect(accessibility.violations).toEqual([]);
  await page.screenshot({
    path: "evidence/ai-chat-memory/history-mobile.png",
    fullPage: true,
  });
  // Renaming is history management, so it works with AI and saving both off.
  await page.getByRole("button", { name: "Đổi tên", exact: true }).click();
  await page
    .getByRole("dialog", { name: "Đổi tên hội thoại" })
    .getByRole("textbox", { name: "Tên hội thoại", exact: true })
    .fill("Buổi sáng đã đặt tên");
  await page.getByRole("button", { name: "Lưu tên", exact: true }).click();
  await expect(
    page.getByText("Đã đổi tên hội thoại.", { exact: true }),
  ).toBeVisible();
  await page.reload();
  await page
    .getByRole("button", { name: "Mở lịch sử hội thoại", exact: true })
    .click();
  await expect(
    page
      .getByRole("dialog")
      .getByRole("link", { name: /Buổi sáng đã đặt tên/ }),
  ).toBeVisible();
  await page.keyboard.press("Escape");
  const downloaded = page.waitForEvent("download");
  await page
    .getByRole("button", { name: "Xuất hội thoại", exact: true })
    .click();
  expect((await downloaded).suggestedFilename()).toBe(
    `moodprint-conversation-${conversationId}.json`,
  );
  await page
    .getByRole("button", { name: "Xóa hội thoại", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Xác nhận xóa hội thoại", exact: true })
    .click();
  await expect(
    page
      .getByRole("log")
      .getByText("Một buổi sáng tổng hợp để kiểm tra lịch sử", { exact: true }),
  ).toHaveCount(0);
  // Deleted and unknown threads share the backend's not-found/expired contract.
  expect([404, 410]).toContain(
    (
      await context.request.get(`/api/v1/ai/conversations/${conversationId}`)
    ).status(),
  );
  expect(consoleErrors).toEqual([]);
  // Remove the second synthetic thread so subsequent accessibility journeys keep their baseline.
  for (const item of await (
    await context.request.get("/api/v1/ai/conversations")
  ).json()) {
    const result = await context.request.delete(
      `/api/v1/ai/conversations/${item.conversationId}`,
      {
        headers: {
          "X-CSRF-Token": "e2e-synthetic-csrf-6",
          "Idempotency-Key": crypto.randomUUID(),
        },
      },
    );
    expect(result.ok()).toBe(true);
  }
  await context.close();
});
