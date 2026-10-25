import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";
import { call, noHorizontalOverflow, openRoom, session } from "./helpers";

// T-UX-02: the social screens at the 08 section 9 sizes, axe WCAG 2.1 AA, no sideways
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
    path: `../docs/productization/screens/${name}-${width}x${height}.png`,
    fullPage: true,
  });
}

test("social screens are responsive and pass axe at every acceptance size", async ({ browser }) => {
  test.setTimeout(300_000);
  const { one, two, pageA, room, close } = await openRoom(browser, 38, 39);
  const staff = await browser.newContext();
  try {
    const started = await call(one, 38, "POST", `/connections/${room}/activities`, {
      kind: "icebreaker",
    });
    expect(started.status, started.text).toBe(201);
    const accepted = await call(two, 39, "POST", `/activities/${started.body.id}/accept`, {
      expectedVersion: started.body.version,
    });
    expect(accepted.status, accepted.text).toBe(200);
    await session(staff, 37);
    const admin = await staff.newPage();
    for (const [width, height] of VIEWPORTS) {
      await pageA.setViewportSize({ width, height });
      await pageA.goto("/#/connect?tab=suggestions");
      await expect(pageA.getByRole("tab", { name: "Gợi ý" })).toHaveAttribute("aria-selected", "true");
      // Audit and capture the settled screen, not its loading state.
      await expect(pageA.getByText("Đang tìm điểm chung…")).toHaveCount(0);
      await audit(pageA, "connect", width, height);
      await pageA.goto("/#/messages");
      await expect(pageA.getByRole("heading", { level: 1, name: "Tin nhắn" })).toBeVisible();
      await expect(pageA.locator(`a[href="#/chat/${room}"]`)).toBeVisible();
      await expect(pageA.getByText("Đang tải kết nối…")).toHaveCount(0);
      await audit(pageA, "messages", width, height);
      await pageA.goto(`/#/chat/${room}`);
      const dock = pageA.getByRole("region", { name: "Hoạt động chung: Câu hỏi làm quen" });
      await expect(dock).toContainText("Câu 1/3");
      await expect(pageA.getByRole("textbox", { name: "Tin nhắn cho bạn kết nối" })).toBeInViewport();
      await audit(pageA, "chat-dock", width, height);
      await admin.setViewportSize({ width, height });
      await admin.goto("/#/admin/reports");
      await expect(admin.getByRole("heading", { level: 1, name: "Kiểm duyệt báo cáo" })).toBeVisible();
      await expect(admin.getByText("Đang tải báo cáo…")).toHaveCount(0);
      await audit(admin, "admin", width, height);
    }
    // Keyboard open on a phone: the composer stays reachable with the dock collapsed.
    await pageA.setViewportSize({ width: 390, height: 480 });
    await pageA.goto(`/#/chat/${room}`);
    const dock = pageA.getByRole("region", { name: "Hoạt động chung: Câu hỏi làm quen" });
    await dock.getByRole("button", { name: "Thu gọn hoạt động" }).click();
    const composer = pageA.getByRole("textbox", { name: "Tin nhắn cho bạn kết nối" });
    await composer.focus();
    await expect(composer).toBeInViewport();
    await audit(pageA, "chat-dock-collapsed", 390, 480);
  } finally {
    await staff.close();
    await close();
  }
});
