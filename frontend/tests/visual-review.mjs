import { chromium, expect } from "@playwright/test";
import { mkdirSync, writeFileSync } from "node:fs";
const round = process.argv[2] || "1";
const base = process.env.DEMO_BASE || "http://127.0.0.1:5173";
const browser = await chromium.launch({
  headless: true,
  executablePath:
    process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH ||
    "C:/Users/minhh/AppData/Local/ms-playwright/chromium-1243/chrome-win64/chrome.exe",
});
const dir = `evidence/me2we/round-${round}`;
mkdirSync(dir, { recursive: true });
const manifest = [];
try {
  const page = await browser.newPage({
    viewport: { width: 390, height: 844 },
    reducedMotion: "reduce",
  });
  await page.goto(base);
  await page.waitForLoadState("networkidle");
  await page.getByRole("button", { name: "Đóng giới thiệu bản mẫu" }).click();
  const route = async (path) => {
    await page.evaluate((p) => {
      location.hash = p;
    }, path);
    await page.waitForTimeout(150);
  };
  const capture = async (name) => {
    const dismiss = page.getByRole("button", {
      name: "Đóng thông báo",
      exact: true,
    });
    if (await dismiss.isVisible()) await dismiss.click();
    await page.mouse.move(0, 0);
    const path = `${dir}/${name}.png`;
    await page.screenshot({ path, fullPage: false });
    manifest.push(path);
  };
  await capture("roster-390");
  await route("/assistants/may");
  await page
    .getByRole("button", { name: "Hôm nay mình hơi mệt", exact: true })
    .click();
  await expect(page.getByRole("log")).toContainText("Một ngày dài à?");
  await capture("ai-chat-390");
  await route("/assistants/nhip");
  await capture("mood-390");
  await page
    .getByRole("button", { name: "2 Hơi khó chịu", exact: true })
    .click();
  await page.getByRole("button", { name: "Xem xu hướng", exact: true }).click();
  await expect(page.getByRole("log")).toContainText("Nhịp cảm xúc của bạn");
  await capture("insight-390");
  await route("/assistants/guong");
  await page
    .getByRole("button", { name: "Mình thích đọc sách", exact: true })
    .click();
  await expect(page.getByRole("log")).toContainText("Khi đọc sách");
  await page
    .getByRole("button", {
      name: "Mình thích khoảng yên tĩnh khi đọc sách",
      exact: true,
    })
    .click();
  await expect(
    page.getByRole("button", { name: "Lưu vào hồ sơ", exact: true }),
  ).toBeVisible();
  await capture("profile-suggestion-390");
  await route("/connect");
  await expect(page.getByRole("article")).toHaveCount(4);
  await capture("discover-390");
  await page
    .getByRole("article")
    .filter({ has: page.getByRole("heading", { name: "Lá Non", exact: true }) })
    .getByRole("button", { name: "Làm quen" })
    .click();
  await page.getByRole("button", { name: "Đồng ý", exact: true }).click();
  await page.getByRole("link", { name: "Mở trò chuyện" }).click();
  await capture("human-chat-390");
  await page
    .getByRole("button", { name: "Cùng làm gì đó?", exact: false })
    .click();
  await capture("activities-390");
  await page
    .getByRole("button", { name: "Mời cùng tham gia", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Đồng ý hoạt động", exact: true })
    .click();
  await capture("icebreaker-390");
  await page.getByRole("button", { name: "Dừng ở đây", exact: true }).click();
  await page
    .getByRole("button", { name: "Dừng hoạt động", exact: true })
    .click();
  await route("/profile");
  await capture("profile-390");
  await page.setViewportSize({ width: 1440, height: 960 });
  await route("/assistants");
  await capture("roster-desktop-1440");
  await route("/assistants/may");
  await capture("chat-desktop-1440");
  writeFileSync(`${dir}/manifest.json`, JSON.stringify(manifest, null, 2));
  console.log(`Saved ${manifest.length} screenshots to ${dir}`);
} finally {
  await browser.close();
}
