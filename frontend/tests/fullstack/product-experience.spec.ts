import { artifactPath } from "../artifacts";
import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";
import { noHorizontalOverflow, session } from "./helpers";

const SIZES = [
  [390, 844],
  [430, 932],
  [768, 1024],
  [1280, 900],
  [1440, 960],
  [390, 480],
] as const;

async function audit(page: Page, name: string, width: number, height: number) {
  await noHorizontalOverflow(page);
  const axe = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
    .analyze();
  expect(
    axe.violations.map(({ id, nodes }) => ({
      id,
      targets: nodes.map((node) => node.target),
    })),
  ).toEqual([]);
  await page.screenshot({
    path: artifactPath(`product-experience/${name}-${width}x${height}.png`, `.cache/product-experience/${name}-${width}x${height}.png`),
    fullPage: true,
  });
}

test("document branding and short pages stay at the top across all six sizes", async ({
  browser,
}) => {
  test.setTimeout(180_000);
  const context = await browser.newContext({ reducedMotion: "reduce" });
  await session(context, 44);
  const page = await context.newPage();
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  try {
    for (const [width, height] of SIZES) {
      await page.setViewportSize({ width, height });
      await page.goto("/#/assistants");
      const heading = page.getByRole("heading", { name: "Chọn một trợ lý", level: 1 });
      await expect(heading).toBeVisible();
      await expect(page).toHaveTitle(/^MoodPrint/);
      await expect(page.getByRole("main")).not.toContainText(/Me2We/i);
      await expect(
        page.getByRole("main").locator(".brand"),
      ).toHaveCount(0);
      expect((await heading.boundingBox())!.y).toBeLessThan(180);
      await audit(page, "assistants", width, height);
      await page.goto("/#/profile");
      await expect(
        page.getByRole("heading", { name: "Tài khoản", exact: true }),
      ).toBeVisible();
      await audit(page, "profile", width, height);
    }
    expect(errors).toEqual([]);
  } finally {
    await context.close();
  }
});

test("assistants link to remaining tools and retired social guides have no link", async ({
  browser,
}) => {
  test.setTimeout(180_000);
  const context = await browser.newContext({ reducedMotion: "reduce" });
  await session(context, 44);
  const page = await context.newPage();
  try {
    for (const [width, height] of [
      [390, 480],
      [1440, 960],
    ] as const) {
      await page.setViewportSize({ width, height });
      for (const [id, action, destination] of [
        ["may", "Ghi lại cảm xúc hôm nay", "/self"],
        ["guong", "Xem ghi nhớ AI", "/memory"],
        ["nhip", "Mở nhật ký cảm xúc", "/self"],
      ]) {
        await page.goto(`/#/assistants/${id}`);
        const link = page.getByRole("link", { name: action, exact: true });
        await expect(link).toHaveAttribute("href", `#${destination}`);
        await expect(
          page.getByText("Chỉ bạn xem được", { exact: true }),
        ).toBeVisible();
        await link.focus();
        await expect(link).toBeFocused();
        await audit(page, `assistant-${id}`, width, height);
        await link.press("Enter");
        await expect(page).toHaveURL(
          new RegExp(`#${destination.replace("?", "\\?")}$`),
        );
      }
      for (const [id, name] of [["rure", "Rủ Rê"], ["caunoi", "Cầu Nối"]]) {
        await page.goto(`/#/assistants/${id}`);
        await expect(page.getByRole("textbox", { name: `Tin nhắn cho ${name}` })).toBeVisible();
        await expect(page.locator(".assistant-guide a")).toHaveCount(0);
        await audit(page, `assistant-${id}`, width, height);
      }
    }
  } finally {
    await context.close();
  }
});
