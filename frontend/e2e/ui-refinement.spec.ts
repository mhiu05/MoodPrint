import { expect, test } from "./helpers/fixtures";
import { chatFixtures } from "../src/mocks/scenarios";

test("mock processing keeps the compact companion identity stable", async ({
  page,
}) => {
  await page.setViewportSize({ width: 320, height: 640 });
  await login(page);
  await page.emulateMedia({ reducedMotion: "no-preference" });
  await page.goto("/ai/chat");
  const before = await page.locator(".chat-topbar").boundingBox();
  await page.locator(".ai-quick-reply button").click();
  await page.locator(".ai-stream").waitFor();
  const during = await page.locator(".chat-topbar").boundingBox();
  expect(during!.height).toBe(before!.height);
  await expect(
    page.getByRole("heading", { name: "MoodPrint", exact: true }),
  ).toBeVisible();
});

test("active conversation and inline evidence fit every requested width", async ({
  page,
}) => {
  test.setTimeout(90000);
  await page.setViewportSize({ width: 390, height: 844 });
  await login(page);
  await page.goto("/ai/chat");
  await page.locator(".ai-quick-reply button").click();
  await expect(page.locator(".ai-stream")).toHaveCount(0);
  await page.getByRole("button", { name: "Đính kèm dữ liệu mẫu" }).click();
  await page.getByRole("button", { name: /8 ảnh nhóm lớp/ }).click();
  await expect(page.locator(".ai-evidence-row")).toHaveCount(8);
  await page.goBack();
  const card = page.locator(".chat-attachment");
  await expect(card).toContainText("0/8 nguồn bạn xác nhận");
  for (const width of [320, 360, 375, 390, 430, 768, 1024, 1440]) {
    await page.setViewportSize({ width, height: 640 });
    await card.scrollIntoViewIfNeeded();
    await expect(
      page.getByRole("link", { name: "Tìm hỗ trợ ngay", exact: true }),
    ).toBeVisible();
    expect(
      await page.evaluate(() => document.documentElement.scrollWidth),
    ).toBeLessThanOrEqual(width);
    const composer = await page.locator(".chat-composer").boundingBox();
    expect(composer!.y + composer!.height).toBeLessThanOrEqual(640);
    if (process.env.CAPTURE_SCREENSHOTS === "1")
      await page.screenshot({
        path: `../docs/prototype/screenshots/ui-refinement/after/inline-analysis-${width}.png`,
      });
  }
  await page.setViewportSize({ width: 320, height: 480 });
  await page.goto("/auth");
  // Authenticated /auth redirects to Home; entry controls are covered separately.
  await expect(page).toHaveURL("/home");
});

async function login(page: import("@playwright/test").Page) {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/auth");
  await page
    .getByRole("button", { name: "Vào thử với tài khoản demo" })
    .click();
  await expect(page).toHaveURL(/\/home$/);
}

test("single canvas, unclipped illustrations and reachable actions at all requested widths", async ({
  page,
}) => {
  // Eight widths × four welcome loads plus auth checks; same budget as the route sweep.
  test.setTimeout(180000);
  for (const width of [320, 360, 375, 390, 430, 768, 1024, 1440]) {
    await page.setViewportSize({ width, height: width < 500 ? 640 : 900 });
    for (const step of [1, 2, 3, 4]) {
      await page.goto(`/welcome/${step}`);
      await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
      const geometry = await page.locator(".welcome-art").evaluate((stage) => {
        const bounds = stage.getBoundingClientRect();
        return Array.from(
          stage.querySelectorAll(".petal, .flower-center"),
        ).every((part) => {
          const box = part.getBoundingClientRect();
          return (
            box.top >= bounds.top &&
            box.bottom <= bounds.bottom &&
            box.left >= bounds.left &&
            box.right <= bounds.right
          );
        });
      });
      expect(geometry, `flower fits at ${width}px, step ${step}`).toBe(true);
      await expect(page.getByRole("link", { name: "Bỏ qua" })).toBeVisible();
      await page
        .getByRole("link", {
          name: step === 4 ? "Bắt đầu" : "Tiếp tục",
          exact: true,
        })
        .scrollIntoViewIfNeeded();
      expect(
        await page.evaluate(() => document.documentElement.scrollWidth),
      ).toBeLessThanOrEqual(width);
    }
    await page.goto("/auth");
    await page
      .getByRole("button", { name: "Đăng ký demo", exact: true })
      .click();
    await expect(
      page.getByRole("textbox", { name: "Bí danh demo" }),
    ).toBeVisible();
    expect(
      await page.evaluate(() => document.documentElement.scrollWidth),
    ).toBeLessThanOrEqual(width);
  }
  await page.setViewportSize({ width: 320, height: 480 });
  await page.goto("/welcome/1");
  await page.getByRole("link", { name: "Tiếp tục", exact: true }).click();
  await expect(page).toHaveURL("/welcome/2");
  await page.getByRole("link", { name: "Quay lại", exact: true }).click();
  await expect(page).toHaveURL("/welcome/1");
});

test("only chat is immersive; drafts survive back, reload, history and section changes", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await login(page);
  for (const path of ["/home", "/ai", "/cases", "/support", "/ai/roleplay"]) {
    await page.goto(path);
    await expect(page.locator(".topbar, .demo-strip")).toHaveCount(0);
    await expect(page.locator(".bottom-nav a")).toHaveCount(4);
  }
  await page.goto("/support");
  await page.getByRole("link", { name: "Cài đặt", exact: true }).click();
  await expect(page).toHaveURL("/settings");
  await page.goto("/ai/chat");
  await expect(
    page.locator(".bottom-nav, .app-sidebar, .topbar, .demo-strip"),
  ).toHaveCount(0);
  const input = page.getByRole("textbox", { name: "Điều bạn muốn kể" });
  await input.fill("Bản nháp trước khi sẵn sàng");
  const draftUrl = page.url();
  await page.getByRole("link", { name: "Quay lại không gian AI" }).click();
  await expect(page.locator(".bottom-nav a")).toHaveCount(4);
  await page.locator(".ai-recent-row").first().click();
  await expect(input).toHaveValue("Bản nháp trước khi sẵn sàng");
  await page.reload();
  await expect(input).toHaveValue("Bản nháp trước khi sẵn sàng");
  await page.getByRole("button", { name: "Tùy chọn cuộc trò chuyện" }).click();
  await expect(page.locator("#chat-scenario option")).toHaveCount(30);
  await page.getByRole("link", { name: "Luyện cách nói", exact: true }).click();
  await page.goto(draftUrl);
  await expect(input).toHaveValue("Bản nháp trước khi sẵn sàng");
  await page
    .getByRole("button", { name: "Lịch sử trò chuyện", exact: true })
    .click();
  await expect(
    page.getByRole("dialog", { name: "Lịch sử trò chuyện" }),
  ).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(
    page.getByRole("button", { name: "Lịch sử trò chuyện", exact: true }),
  ).toBeFocused();
  await input.press("Shift+Enter");
  await expect(page.locator(".ai-message.user")).toHaveCount(0);
  await input.fill("Câu tự do ngoài kịch bản");
  await input.press("Enter");
  await expect(page.locator(".ai-message.ai")).toContainText("không tự hiểu");
});

test("all twelve scripted flows still advance through three turns from the compact scenario menu", async ({
  page,
}) => {
  test.setTimeout(90000);
  await login(page);
  for (const fixture of chatFixtures) {
    await page.goto(`/ai/chat?scenario=${fixture.scenarioId}`);
    for (let turn = 0; turn < 3; turn++) {
      await page.locator(".ai-quick-reply button").click();
      await expect(page.locator(".ai-message.ai")).toHaveCount(turn + 1);
      await expect(page.locator(".ai-message.ai").last()).toContainText(
        fixture.messages[turn * 2 + 1].body,
      );
    }
    await expect(page.locator(".ai-findings")).toBeVisible();
  }
});

test("composer fits short and simulated keyboard viewports without page scrolling", async ({
  page,
}) => {
  await login(page);
  for (const width of [320, 360, 375, 390, 430, 768, 1024, 1440]) {
    await page.setViewportSize({ width, height: 480 });
    await page.goto("/ai/chat");
    await page
      .getByRole("textbox", { name: "Điều bạn muốn kể" })
      .fill("Dòng một\nDòng hai\nDòng ba");
    const box = await page.locator(".chat-composer").boundingBox();
    expect(box!.y).toBeGreaterThan(44);
    expect(box!.y + box!.height).toBeLessThanOrEqual(480);
    expect(
      await page.evaluate(() => document.documentElement.scrollHeight),
    ).toBeLessThanOrEqual(480);
  }
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/ai/chat");
  await page.getByRole("textbox").focus();
  await page.evaluate(() => {
    Object.defineProperty(window.visualViewport!, "height", {
      configurable: true,
      get: () => 420,
    });
    window.visualViewport!.dispatchEvent(new Event("resize"));
  });
  await expect(page.locator("html")).toHaveAttribute(
    "data-keyboard-open",
    "true",
  );
  await expect
    .poll(async () => {
      const box = await page.locator(".chat-composer").boundingBox();
      return box!.y + box!.height;
    })
    .toBeLessThanOrEqual(420);
  if (process.env.CAPTURE_SCREENSHOTS === "1")
    await page.screenshot({
      path: "../docs/prototype/screenshots/ui-refinement/after/chat-keyboard-390.png",
    });
});

test("manual reading position is respected while new messages arrive", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 640 });
  await login(page);
  await page.goto("/ai/chat");
  const input = page.getByRole("textbox", { name: "Điều bạn muốn kể" });
  for (let i = 0; i < 7; i++) {
    await input.fill(`Tin nhắn tự do ${i}`);
    await input.press("Enter");
    await expect(page.locator(".ai-message.ai")).toHaveCount(i + 1);
    await expect(page.locator(".ai-stream")).toHaveCount(0);
  }
  await page.emulateMedia({ reducedMotion: "no-preference" });
  await input.fill("Một lượt nữa");
  await input.press("Enter");
  await page.locator(".chat-transcript").evaluate((element) => {
    element.scrollTop = 0;
    element.dispatchEvent(new Event("scroll"));
  });
  await expect(page.locator(".ai-message.ai")).toHaveCount(8);
  await expect(page.locator(".ai-stream")).toHaveCount(0);
  expect(
    await page
      .locator(".chat-transcript")
      .evaluate((element) => element.scrollTop),
  ).toBe(0);
  await page.getByRole("button", { name: "Tin nhắn mới nhất" }).click();
  await expect
    .poll(() =>
      page
        .locator(".chat-transcript")
        .evaluate(
          (element) =>
            element.scrollHeight - element.clientHeight - element.scrollTop,
        ),
    )
    .toBeLessThan(5);
});
