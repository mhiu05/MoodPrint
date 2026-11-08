import { expect, test } from "./helpers/fixtures";
import { mkdirSync } from "node:fs";
import { resolve } from "node:path";
const screenshotDir = resolve("..", "docs", "prototype", "screenshots");
test("responsive routes, reduced motion, console and local-only requests", async ({
  page,
  baseURL,
}) => {
  test.setTimeout(180000);
  if (process.env.CAPTURE_SCREENSHOTS === "1")
    mkdirSync(screenshotDir, { recursive: true });
  const errors: string[] = [];
  const external: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("console", (message) => {
    if (message.type() === "error") errors.push(message.text());
  });
  page.on("request", (request) => {
    if (
      !request.url().startsWith(baseURL!) &&
      !request.url().startsWith("data:") &&
      !request.url().startsWith("blob:")
    )
      external.push(request.url());
  });
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/auth");
  await page
    .getByRole("button", { name: "Vào thử với tài khoản demo" })
    .click();
  await expect(page).toHaveURL(/\/home$/);
  const routes = [
    "/home",
    "/ai",
    "/ai/chat",
    "/cases",
    "/cases/new",
    "/cases/CASE-AN-001/timeline",
    "/cases/CASE-AN-001/plan",
    "/ai/roleplay/teacher",
    "/support/knowledge",
    "/knowledge/treu-dua-hay-bat-nat",
    "/support",
    "/support/prepare",
    "/support/urgent",
    "/demo/school",
  ];
  for (const width of [320, 360, 375, 390, 430, 768, 1024, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    for (const route of routes) {
      await page.goto(route);
      await expect(page).toHaveURL(route);
      await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
      await expect(page.getByText("Trang demo cần được mở lại")).toHaveCount(0);
      const sizes = await page.evaluate(() => ({
        page: document.documentElement.scrollWidth,
        viewport: innerWidth,
      }));
      expect(sizes.page, `${route} at ${width}px`).toBeLessThanOrEqual(
        sizes.viewport,
      );
      if (
        (width === 390 || width === 1440) &&
        [
          "/home",
          "/ai/chat",
          "/cases/CASE-AN-001/plan",
          "/support/knowledge",
          "/ai/roleplay/teacher",
          "/support",
          "/demo/school",
        ].includes(route)
      ) {
        const name =
          route === "/home"
            ? "home"
            : route === "/ai/chat"
              ? "chat"
              : route.endsWith("/plan")
                ? "plan"
                : route.includes("knowledge")
                  ? "knowledge"
                  : route.includes("roleplay")
                    ? "roleplay"
                    : route.includes("school")
                      ? "school"
                      : "support";
        if (process.env.CAPTURE_SCREENSHOTS === "1")
          await page.screenshot({
            path: resolve(
              screenshotDir,
              `${name}-${width === 390 ? "mobile" : "desktop"}.png`,
            ),
            fullPage: true,
          });
      }
    }
  }
  await page.setViewportSize({ width: 390, height: 480 });
  await page.goto("/ai/chat");
  await page.getByRole("textbox", { name: "Điều bạn muốn kể" }).focus();
  const input = await page
    .getByRole("textbox", { name: "Điều bạn muốn kể" })
    .boundingBox();
  expect(input!.y + input!.height).toBeLessThanOrEqual(480);
  expect(errors).toEqual([]);
  expect(external).toEqual([]);
});
