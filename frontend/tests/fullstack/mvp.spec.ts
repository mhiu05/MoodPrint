import { artifactPath } from "../artifacts";
import { expect, test, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import {
  call,
  noHorizontalOverflow,
  session,
} from "./helpers";

// Real FastAPI + PostgreSQL MVP journeys (synthetic users 10-20 from tests/e2e_server.py).

const shots = artifactPath("mvp-validation/screens", "../docs/mvp-validation/screens");

function localDay(serverTime: string, offsetDays = 0) {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Bangkok",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date(new Date(serverTime).getTime() - offsetDays * 86_400_000));
  return parts;
}
const display = (day: string) => day.split("-").reverse().join("/");

async function axe(page: Page) {
  const result = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
    .analyze();
  expect(result.passes.length).toBeGreaterThan(0);
  expect(
    result.violations.map((v) => ({
      id: v.id,
      nodes: v.nodes.map((n) => n.target),
    })),
  ).toEqual([]);
}

test("Journey E: settings does not offer a download and moods stay on the owner session", async ({
  browser,
}) => {
  const context = await browser.newContext();
  await session(context, 13);
  const page = await context.newPage();
  const now = (await call(context, 13, "GET", "/session")).body.serverTime;
  await call(context, 13, "PUT", `/moods/${localDay(now)}`, {
    value: 4,
    note: "EXPORT_OWN_NOTE",
    timezone: "Asia/Bangkok",
    expectedVersion: 0,
  });
  await page.goto("/#/settings");
  await expect(
    page.getByRole("button", { name: "Tải bản sao dữ liệu", exact: true }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("heading", { name: "Tài khoản", exact: true }),
  ).toBeVisible();
  const moods = await call(context, 13, "GET", "/moods");
  expect(moods.body.map((item: { note: string }) => item.note)).toEqual([
    "EXPORT_OWN_NOTE",
  ]);
  await context.close();
});

test("Mood lifecycle: create, reload, edit, stale-tab conflict, insights and confirmed delete", async ({
  browser,
}) => {
  const context = await browser.newContext({
    viewport: { width: 1280, height: 900 },
  });
  await session(context, 10);
  const page = await context.newPage();
  const now = (await call(context, 10, "GET", "/session")).body.serverTime;
  const today = localDay(now);
  await page.goto("/#/self/daily");
  await expect(
    page.getByText("Chưa có ghi chép. Bạn có thể bắt đầu từ hôm nay."),
  ).toBeVisible();
  await expect(
    page.getByText(`Ghi chép mới cho ngày ${display(today)}`, { exact: false }),
  ).toBeVisible();
  await page.getByLabel("Tâm trạng", { exact: true }).selectOption("4");
  await page.getByLabel("Ghi chú", { exact: true }).fill("Ghi chép MVP");
  await page
    .getByRole("button", { name: "Lưu tâm trạng", exact: true })
    .click();
  await expect(
    page.getByText(/^Đã lưu cảm xúc ngày \d{2}\/\d{2}\/\d{4}\.$/),
  ).toBeVisible();
  await expect(
    page.getByText("Ghi chép MVP", { exact: true }).first(),
  ).toBeVisible();
  await expect(page.getByText(/Trung bình từ 1\/7 ngày có ghi/)).toBeVisible();
  await expect(
    page.getByText("Cần ghi tâm trạng ít nhất 3 ngày để xem phần nhìn lại."),
  ).toBeVisible();

  await page.reload();
  await expect(
    page.getByText(`Đang sửa ghi chép đã lưu của ngày ${display(today)}.`),
  ).toBeVisible();
  await expect(page.getByLabel("Ghi chú", { exact: true })).toHaveValue(
    "Ghi chép MVP",
  );
  await page.getByLabel("Tâm trạng", { exact: true }).selectOption("2");
  await page.getByLabel("Ghi chú", { exact: true }).fill("Đã sửa");
  await page
    .getByRole("button", { name: "Cập nhật tâm trạng", exact: true })
    .click();
  await expect(
    page.getByText(/^Đã cập nhật cảm xúc ngày \d{2}\/\d{2}\/\d{4}\.$/),
  ).toBeVisible();
  await expect(page.getByText(/2\/5 · /).first()).toBeVisible();
  const stored = (await call(context, 10, "GET", "/moods")).body;
  expect(
    stored.map((m: { version: number; note: string }) => [m.version, m.note]),
  ).toEqual([[2, "Đã sửa"]]);

  // A second tab changes the same day; the first tab gets a clear conflict and keeps its input.
  await call(context, 10, "PUT", `/moods/${today}`, {
    value: 5,
    note: "Từ tab khác",
    timezone: "Asia/Bangkok",
    expectedVersion: 2,
  });
  await page.getByLabel("Ghi chú", { exact: true }).fill("Bản nhập cần giữ");
  await page
    .getByRole("button", { name: "Cập nhật tâm trạng", exact: true })
    .click();
  await expect(page.getByRole("alert")).toContainText(
    "vừa được thay đổi ở nơi khác",
  );
  await expect(page.getByLabel("Ghi chú", { exact: true })).toHaveValue(
    "Bản nhập cần giữ",
  );
  await expect(
    page.getByText("Từ tab khác", { exact: true }).first(),
  ).toBeVisible();

  for (const [offset, value] of [
    [2, 3],
    [5, 1],
  ] as const)
    await call(context, 10, "PUT", `/moods/${localDay(now, offset)}`, {
      value,
      note: "",
      timezone: "Asia/Bangkok",
      expectedVersion: 0,
    });
  await page.reload();
  await expect(
    page.getByText(
      "Bạn đã ghi tâm trạng trong 3/7 ngày. Điểm bạn tự chọn từ 1 đến 5/5.",
    ),
  ).toBeVisible();
  await page.getByRole("button", { name: "30 ngày", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "30 ngày", exact: true }),
  ).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByText(/trong 3\/30 ngày/)).toBeVisible();
  await page.getByText("Xem từng ngày", { exact: true }).click();
  await expect(
    page.getByRole("row", { name: new RegExp(display(localDay(now, 1))) }),
  ).toContainText("Chưa ghi");
  await axe(page);
  await page.screenshot({ path: `${shots}/mood-1280.png`, fullPage: true });

  const remove = page.getByRole("button", {
    name: `Xóa tâm trạng ngày ${display(today)}`,
    exact: true,
  });
  await remove.click();
  const dialog = page.getByRole("dialog", { name: "Xóa ghi chép này?" });
  await expect(dialog).toBeVisible();
  await expect(dialog.getByRole("button", { name: "Giữ lại" })).toBeFocused();
  await page.keyboard.press("Tab");
  await page.keyboard.press("Tab");
  await page.keyboard.press("Tab");
  expect(
    await dialog.evaluate((node) => node.contains(document.activeElement)),
  ).toBe(true);
  await page.keyboard.press("Escape");
  await expect(dialog).toHaveCount(0);
  await expect(remove).toBeFocused();
  await remove.click();
  await dialog
    .getByRole("button", { name: "Xóa ghi chép", exact: true })
    .click();
  await expect(
    page.getByText(`Đã xóa tâm trạng ngày ${display(today)}.`),
  ).toBeVisible();
  await page.reload();
  await expect(page.locator("article.real-item")).toHaveCount(2);
  expect((await call(context, 10, "GET", "/moods")).body).toHaveLength(2);
  await context.close();
});

test("Journey F: mood and AI chat stay usable at 390px and 430px with the composer in view", async ({
  browser,
}) => {
  const a = await browser.newContext({
      viewport: { width: 390, height: 844 },
      isMobile: true,
      hasTouch: true,
    }),
    b = await browser.newContext({
      viewport: { width: 430, height: 932 },
      isMobile: true,
      hasTouch: true,
    });
  await session(a, 18);
  await session(b, 19);
  const one = await a.newPage(),
    two = await b.newPage();
  await one.goto("/#/self/daily");
  await one.getByLabel("Ghi chú", { exact: true }).fill("Ghi trên điện thoại");
  await one.getByRole("button", { name: "Lưu tâm trạng", exact: true }).click();
  await expect(
    one.getByText(/^Đã lưu cảm xúc ngày \d{2}\/\d{2}\/\d{4}\.$/),
  ).toBeVisible();
  await expect(one.getByText(/Trung bình từ 1\/7 ngày có ghi/)).toBeVisible();
  await noHorizontalOverflow(one);
  await one.screenshot({ path: `${shots}/mood-390.png`, fullPage: true });
  for (const [page, width] of [[one, 390], [two, 430]] as const) {
    await page.goto("/#/assistants/may?new=1");
    await expect(page.getByRole("textbox", { name: "Tin nhắn cho Mây" })).toBeVisible();
    await noHorizontalOverflow(page);
    await page.screenshot({ path: `${shots}/chat-${width}.png` });
  }
  const composer = one.getByRole("textbox", { name: "Tin nhắn cho Mây" });
  await composer.tap();
  await composer.fill("Nhắn từ 390px");
  await one.getByRole("button", { name: "Gửi tin cho AI", exact: true }).tap();
  await expect(one.locator(".from-bot .chat-bubble")).toContainText("Mây đã nhận được chia sẻ của bạn qua SDK.");
  // Approximate an open on-screen keyboard by shrinking the visual viewport.
  await one.setViewportSize({ width: 390, height: 480 });
  await composer.focus();
  await composer.scrollIntoViewIfNeeded();
  const box = await composer.boundingBox();
  expect(box).not.toBeNull();
  expect(box!.y + box!.height).toBeLessThanOrEqual(480);
  // The newest message stays readable directly above the composer.
  const latest = await one.locator(".chat-bubble").last().boundingBox();
  expect(latest!.y).toBeGreaterThanOrEqual(0);
  expect(latest!.y + latest!.height).toBeLessThanOrEqual(box!.y);
  await expect(
    one.getByRole("navigation", { name: "Điều hướng chính" }),
  ).toBeHidden();
  const send = await one
    .getByRole("button", { name: "Gửi tin cho AI" })
    .boundingBox();
  expect(send!.width).toBeGreaterThanOrEqual(44);
  expect(send!.height).toBeGreaterThanOrEqual(44);
  await noHorizontalOverflow(one);
  await one.screenshot({ path: `${shots}/chat-keyboard-390.png` });
  await a.close();
  await b.close();
});

test("Every real screen passes axe and reflows at 1440, 1280, 430 and 390 with reduced motion", async ({
  browser,
}) => {
  const context = await browser.newContext({ reducedMotion: "reduce" });
  await session(context, 20);
  expect((await call(context, 20, "PUT", "/consents/MATCH", {
    enabled: true,
    expectedVersion: 1,
    policyVersion: "v1",
  })).status).toBe(200);
  const page = await context.newPage();
  const routes = [
    ["/assistants", "Chọn một trợ lý"],
    ["/self", "Nhật ký cảm xúc"],
    ["/profile", "Tài khoản"],
    ["/memory", ""],
    ["/settings", "Tài khoản"],
  ] as const;
  for (const width of [1440, 1280, 430, 390]) {
    await page.setViewportSize({ width, height: 900 });
    for (const [route, heading] of routes) {
      await page.goto(`/#${route}`);
      const h1 = page.getByRole("heading", { level: 1 });
      await expect(
        heading ? h1.filter({ hasText: heading }) : h1.first(),
      ).toBeVisible();
      await page.waitForLoadState("networkidle");
      await noHorizontalOverflow(page);
      await axe(page);
      if (width === 1440 || width === 390)
        await page.screenshot({
          path: `${shots}/${route.slice(1)}-${width}.png`,
          fullPage: true,
        });
    }
  }
  await context.close();
});
