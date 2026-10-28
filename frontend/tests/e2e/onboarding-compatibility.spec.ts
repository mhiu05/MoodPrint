/** Opt-in package spike, not evidence that a production spotlight was accepted. */
import { expect, test, type Page } from "@playwright/test";
import { readFileSync, existsSync } from "node:fs";
import path from "node:path";
import { app, guestSession } from "./ux-fixtures";

async function load(page: Page) {
  const fixture = process.env.MOODPRINT_TOUR_SPIKE_DIR;
  expect(fixture, "Inspected pinned package fixture is required; missing fixture is not a pass").toBeTruthy();
  const script = path.join(fixture!, "dist/driver.js.iife.js");
  const css = path.join(fixture!, "dist/driver.css");
  expect(existsSync(script) && existsSync(css), "Driver.js 1.10.2 bundle/CSS missing").toBe(true);
  const mutations: string[] = [];
  page.on("request", (request) => { if (["POST", "PUT", "PATCH", "DELETE"].includes(request.method())) mutations.push(request.url()); });
  await app(page, guestSession(7_000_000));
  await page.route("**/__tour_spike__/driver.js", (route) => route.fulfill({ contentType: "application/javascript", body: readFileSync(script) }));
  await page.route("**/__tour_spike__/driver.css", (route) => route.fulfill({ contentType: "text/css", body: readFileSync(css) }));
  const response = await page.goto("/#/assistants");
  await expect(page.locator("main h1")).toBeVisible();
  await page.addScriptTag({ url: "/__tour_spike__/driver.js" });
  await page.addStyleTag({ url: "/__tour_spike__/driver.css" });
  return { mutations, response };
}

async function start(page: Page) {
  await page.evaluate(() => {
    const scope = window as any;
    scope.__spike?.destroy();
    scope.__spike = scope.driver.js.driver({
      animate: false, smoothScroll: false, showProgress: true, allowClose: true,
      nextBtnText: "Tiếp", prevBtnText: "Quay lại", doneBtnText: "Hoàn tất", closeBtnLabel: "Bỏ qua",
      progressText: "Bước {{current}}/{{total}}",
      steps: [{ element: "main h1", popover: { title: "Trợ lý", description: "Chọn trợ lý hợp với điều bạn muốn làm hôm nay." } }],
    });
    scope.__spike.drive();
  });
}

test("one overlay after repeated setup/cleanup in the StrictMode app", async ({ page }) => {
  const { mutations } = await load(page);
  for (let index = 0; index < 3; index++) { await start(page); await expect(page.locator(".driver-popover")).toHaveCount(1); }
  await page.evaluate(() => (window as any).__spike.destroy());
  await expect(page.locator(".driver-popover")).toHaveCount(0);
  await expect(page.locator(".driver-overlay")).toHaveCount(0);
  expect(mutations).toEqual([]);
});

test("Escape and focus restoration", async ({ page }) => {
  await load(page);
  const launcher = page.getByRole("button", { name: "Kết thúc và xóa lượt dùng thử", exact: true });
  await launcher.focus();
  await start(page);
  await page.keyboard.press("Escape");
  await expect(page.locator(".driver-popover")).toHaveCount(0);
  await expect(launcher).toBeFocused();
});

test("native app dialog collision cleans overlay", async ({ page }) => {
  const { mutations } = await load(page);
  await start(page);
  await page.locator(".guest-end-link").evaluate((element: HTMLElement) => element.click());
  await expect(page.getByRole("dialog", { name: "Kết thúc và xóa lượt dùng thử?", exact: true })).toBeVisible();
  await expect(page.locator(".driver-popover")).toHaveCount(0);
  expect(mutations).toEqual([]);
});

test("reduced motion and narrow viewport", async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 700 });
  await page.emulateMedia({ reducedMotion: "reduce" });
  await load(page);
  await start(page);
  const box = await page.locator(".driver-popover").boundingBox();
  expect(box && box.x >= 0 && box.x + box.width <= 320 && box.y >= 0 && box.y + box.height <= 700).toBe(true);
  await page.keyboard.press("Escape");
  await expect(page.locator(".driver-popover")).toHaveCount(0);
});

test("real CSP serving-mode gate has no unproven header substitute", async ({ page }) => {
  const { response } = await load(page);
  expect(response?.headers()["content-security-policy"] || "", "Actual FastAPI AND Caddy CSP proof is required; Vite headers cannot certify it").toContain("script-src");
});
