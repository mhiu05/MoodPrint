import { chromium } from "@playwright/test";
import { mkdir } from "node:fs/promises";
import { resolve } from "node:path";

const stage = process.argv[2] ?? "after";
if (!["before", "after"].includes(stage))
  throw new Error("Use before or after");
const destination = resolve(
  "../docs/prototype/screenshots/ui-refinement",
  stage,
);
await mkdir(destination, { recursive: true });
const browser = await chromium.launch({ headless: true });
for (const width of [390, 1440]) {
  const page = await browser.newPage({
    viewport: { width, height: 844 },
    reducedMotion: "reduce",
  });
  const capture = async (name) =>
    page.screenshot({
      path: resolve(destination, `${name}-${width}.png`),
      fullPage: true,
    });
  await page.goto("http://127.0.0.1:5179/");
  await page.getByRole("link", { name: "Bỏ qua" }).waitFor();
  await capture("welcome");
  await page.getByRole("link", { name: "Bỏ qua" }).click();
  await capture("auth");
  await page
    .getByRole("button", { name: "Vào thử với tài khoản demo" })
    .click();
  await page.getByRole("heading", { name: /Chào An/ }).waitFor();
  await capture("home");
  await page.goto("http://127.0.0.1:5179/ai");
  await page.getByRole("link", { name: /Bắt đầu kể/ }).waitFor();
  await capture("ai-hub");
  await page.goto("http://127.0.0.1:5179/ai/chat");
  await page.getByRole("textbox", { name: "Điều bạn muốn kể" }).waitFor();
  await capture("chat-empty");
  await page.locator(".ai-quick-reply button").first().click();
  await page.locator(".ai-message.ai").first().waitFor();
  await page.locator(".ai-stream").waitFor({ state: "detached" });
  await capture("chat-conversation");
  if (stage === "after") {
    await page.emulateMedia({ reducedMotion: "no-preference" });
    await page.locator(".ai-quick-reply button").click();
    await page.locator(".ai-stream").waitFor();
    await capture("chat-processing");
    await page.locator(".ai-stream").waitFor({ state: "detached" });
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.getByRole("button", { name: "Đính kèm dữ liệu mẫu" }).click();
    await page.getByRole("button", { name: /8 ảnh nhóm lớp/ }).click();
    await page.locator(".ai-evidence-row").first().waitFor();
    await page.goBack();
    await page.locator(".chat-attachment").scrollIntoViewIfNeeded();
    await capture("chat-inline-analysis");
  }
  await page.goto("http://127.0.0.1:5179/support");
  await page
    .getByRole("heading", { name: "Bạn có thể tìm một điểm tựa" })
    .waitFor();
  await capture("support");
  await page.close();
}
await browser.close();
console.log(
  `Saved ${stage === "after" ? 18 : 14} ${stage} screenshots to ${destination}`,
);
