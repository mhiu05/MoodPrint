import { artifactPath } from "../artifacts";
import { expect, test, type Page } from "@playwright/test";

async function login(page: Page, number: 45 | 46) {
  await page.goto("/#/");
  await page
    .getByLabel("Email", { exact: true })
    .fill(`local-mvp-${number}@example.invalid`);
  await page
    .getByLabel("Mật khẩu", { exact: true })
    .fill("local-mvp-synthetic");
  await page.getByRole("button", { name: "Đăng nhập", exact: true }).click();
  await expect(page.getByLabel("Mật khẩu", { exact: true })).toHaveCount(0);
}

test("five assistants persist, recover after logout/login and deny a separately logged-in peer", async ({
  browser,
}) => {
  const one = await browser.newContext({
    viewport: { width: 1440, height: 960 },
  });
  const two = await browser.newContext({
    viewport: { width: 390, height: 844 },
  });
  const a = await one.newPage(),
    b = await two.newPage();
  const errors: string[] = [];
  a.on("pageerror", (error) => errors.push(error.message));
  b.on("pageerror", (error) => errors.push(error.message));
  try {
    await login(a, 45);
    await login(b, 46);
    await a.goto("/#/assistants/may");
    await expect(a.getByRole("textbox", { name: "Tin nhắn cho Mây", exact: true })).toBeVisible();
    await expect(a.getByText(/AI đang tắt hoặc chưa khả dụng/)).toHaveCount(0);
    const urls: string[] = [];
    for (const [bot, name] of [
      ["may", "Mây"],
      ["guong", "Gương"],
      ["nhip", "Nhịp"],
      ["rure", "Rủ Rê"],
      ["caunoi", "Cầu Nối"],
    ]) {
      await a.goto(`/#/assistants/${bot}`);
      await expect(a.getByRole("note").filter({ hasText: "model giả" })).toBeVisible();
      await a
        .getByRole("textbox", { name: `Tin nhắn cho ${name}`, exact: true })
        .fill(`LOCAL-MVP ${bot} synthetic history`);
      await a
        .getByRole("button", { name: "Gửi tin cho AI", exact: true })
        .click();
      await expect(
        a
          .getByRole("log")
          .getByText("Mây đã nhận được chia sẻ của bạn qua SDK.", {
            exact: true,
          }),
      ).toBeVisible();
      await expect(
        a.getByRole("button", { name: "Dừng", exact: true }),
      ).toHaveCount(0);
      urls.push(a.url());
      await a.reload();
      await expect(
        a
          .getByRole("log")
          .getByText(`LOCAL-MVP ${bot} synthetic history`, { exact: true }),
      ).toBeVisible();
      const id = new URLSearchParams(a.url().split("?")[1]).get("conversation");
      const foreign = await two.request.get(`/api/v1/ai/conversations/${id}`);
      expect(foreign.status()).toBe(404);
    }
    // Return through the assistant root after a NEW authenticated app session.
    // This must work without a conversation URL or browser transcript storage.
    await a.goto("/#/settings");
    await a.getByRole("button", { name: "Đăng xuất", exact: true }).click();
    await expect(a.getByLabel("Mật khẩu", { exact: true })).toBeVisible();
    await login(a, 45);
    await a.goto("/#/assistants/may");
    await expect(
      a
        .getByRole("log")
        .getByText("LOCAL-MVP may synthetic history", { exact: true }),
    ).toBeVisible();
    await a
      .getByRole("textbox", { name: "Tin nhắn cho Mây", exact: true })
      .fill("LOCAL-MVP continuation");
    await a
      .getByRole("button", { name: "Gửi tin cho AI", exact: true })
      .click();
    await expect(
      a
        .getByRole("log")
        .getByText("Mây đã nhận được chia sẻ của bạn qua SDK.", {
          exact: true,
        }),
    ).toHaveCount(2);
    await a.reload();
    await expect(
      a.getByRole("log").getByText("LOCAL-MVP continuation", { exact: true }),
    ).toBeVisible();
    await a.screenshot({
      path: artifactPath("local-mvp/history-desktop.png", ".cache/local-mvp/history-desktop.png"),
      fullPage: true,
    });
    await a.setViewportSize({ width: 390, height: 844 });
    await expect(
      a.getByRole("textbox", { name: "Tin nhắn cho Mây", exact: true }),
    ).toBeInViewport();
    await a.screenshot({
      path: artifactPath("local-mvp/history-mobile.png", ".cache/local-mvp/history-mobile.png"),
      fullPage: true,
    });
    expect(errors).toEqual([]);
    expect(urls).toHaveLength(5);
  } finally {
    await one.close();
    await two.close();
  }
});
