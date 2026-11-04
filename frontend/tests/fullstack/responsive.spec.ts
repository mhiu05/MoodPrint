import { artifactPath } from "../artifacts";
import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";
import { noHorizontalOverflow, session } from "./helpers";

// T-UX-02: journal and assistant screens at the 08 section 9 sizes, axe WCAG 2.1 AA, no sideways
// scroll; screenshots for review in docs/productization/screens/.
const VIEWPORTS = [
  [390, 844],
  [430, 932],
  [768, 1024],
  [1280, 900],
  [1440, 960],
] as const;

async function audit(page: Page, name: string, width: number, height: number) {
  await noHorizontalOverflow(page);
  const result = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
    .analyze();
  expect(result.passes.length).toBeGreaterThan(0);
  expect(
    result.violations.map((item) => ({
      id: item.id,
      nodes: item.nodes.map((node) => node.target),
    })),
    `${name} at ${width}x${height}`,
  ).toEqual([]);
  await page.screenshot({
    path: artifactPath(`productization/screens/${name}-${width}x${height}.png`, `../docs/productization/screens/${name}-${width}x${height}.png`),
    fullPage: true,
  });
}

test("journal and assistant screens are responsive and pass axe at every acceptance size", async ({ browser }) => {
  test.setTimeout(300_000);
  const context = await browser.newContext({ reducedMotion: "reduce" });
  const staff = await browser.newContext({ reducedMotion: "reduce" });
  await session(context, 38);
  await session(staff, 37);
  const page = await context.newPage();
  const admin = await staff.newPage();
  try {
    for (const [width, height] of VIEWPORTS) {
      await page.setViewportSize({ width, height });
      for (const [route, heading] of [["/self", "Nhật ký cảm xúc"], ["/assistants", "Chọn một trợ lý"], ["/assistants/may?new=1", "Mây AI"]]) {
        await page.goto(`/#${route}`);
        await expect(page.getByRole("heading", { level: 1, name: heading, exact: true })).toBeVisible();
        await expect(page.getByText(/^Đang tải/)).toHaveCount(0);
        await audit(page, route.startsWith("/self") ? "journal" : route.includes("may") ? "assistant-chat" : "assistants", width, height);
      }
      await admin.setViewportSize({ width, height });
      await admin.goto("/#/admin/reports");
      await expect(admin.getByRole("heading", { level: 1, name: "Kiểm duyệt báo cáo" })).toBeVisible();
      await expect(admin.getByText("Đang tải báo cáo…")).toHaveCount(0);
      await audit(admin, "admin", width, height);
    }
    await page.setViewportSize({ width: 390, height: 480 });
    await page.goto("/#/assistants/may?new=1");
    const composer = page.getByRole("textbox", { name: "Tin nhắn cho Mây" });
    await composer.focus();
    await expect(composer).toBeInViewport();
    await audit(page, "assistant-keyboard", 390, 480);
  } finally {
    await staff.close();
    await context.close();
  }
});
