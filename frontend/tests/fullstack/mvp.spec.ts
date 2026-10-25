import { expect, test, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { readFile } from "node:fs/promises";
import {
  call,
  connectByApi,
  disable,
  enable,
  noHorizontalOverflow,
  pairAlias,
  publish,
  session,
} from "./helpers";

// Real FastAPI + PostgreSQL MVP journeys (synthetic users 10-20 from tests/e2e_server.py).

const shots = "../docs/mvp-validation/screens";

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

test("Journey E: export contains only the owner's own data and downloads once", async ({
  browser,
}) => {
  const context = await browser.newContext({ acceptDownloads: true });
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
  const download = page.waitForEvent("download");
  await page
    .getByRole("button", { name: "Xuất dữ liệu riêng", exact: true })
    .click();
  const file = await (await download).path();
  const data = JSON.parse(await readFile(file!, "utf-8"));
  expect(data.moods.map((m: { note: string }) => m.note)).toEqual([
    "EXPORT_OWN_NOTE",
  ]);
  expect(Object.keys(data).sort()).toEqual(
    [
      "account",
      "consents",
      "memories",
      "moods",
      "privateItems",
      "social",
    ].sort(),
  );
  expect(data.social.sentMessages).toEqual([]);
  await expect(
    page.getByText("Đã chuẩn bị tệp dữ liệu riêng của bạn.", { exact: true }),
  ).toBeVisible();
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
  await page.goto("/#/self");
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
    page.getByText("Đã lưu tâm trạng.", { exact: true }),
  ).toBeVisible();
  await expect(
    page.locator("article").getByText("Ghi chép MVP", { exact: true }),
  ).toBeVisible();
  await expect(page.getByText(/Trung bình từ 1\/7 ngày có ghi/)).toBeVisible();
  await expect(
    page.getByText("Cần ghi nhận ở ít nhất 3 ngày để xem xu hướng."),
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
    page.getByText("Đã cập nhật tâm trạng.", { exact: true }),
  ).toBeVisible();
  await expect(page.locator("article h3").first()).toContainText("2/5");
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
    "vừa thay đổi ở nơi khác",
  );
  await expect(page.getByLabel("Ghi chú", { exact: true })).toHaveValue(
    "Bản nhập cần giữ",
  );
  await expect(
    page.locator("article").getByText("Từ tab khác", { exact: true }),
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
      "Bạn đã dành thời gian cho mình trong 3/7 ngày. Mức tự ghi từ 1 đến 5/5.",
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
  await expect(page.locator("article")).toHaveCount(2);
  expect((await call(context, 10, "GET", "/moods")).body).toHaveLength(2);
  await context.close();
});

test("Journey B/C: two users match, request, accept and chat; stale tab loses access on MATCH withdrawal; C is denied", async ({
  browser,
}) => {
  const a = await browser.newContext(),
    b = await browser.newContext(),
    c = await browser.newContext();
  await session(a, 11);
  await session(b, 12);
  await session(c, 13);
  const one = await a.newPage(),
    two = await b.newPage();
  await publish(one);
  await publish(two);
  await one.reload(); // same hash route: reload so discovery sees B's new profile
  const card = one
    .locator("article")
    .filter({ has: one.getByRole("heading", { name: pairAlias(11, 12) }) });
  await expect(card).toBeVisible();
  await expect(card.getByText(/Cùng thích/).first()).toBeVisible();
  await card.getByRole("button", { name: "Gửi lời chào", exact: true }).click();
  await expect(one.getByText("Đã gửi lời mời.", { exact: true })).toBeVisible();
  await expect(
    one.getByText(`Lời chào gửi ${pairAlias(11, 12)}`),
  ).toBeVisible();

  await two.reload();
  const invite = two
    .locator("article")
    .filter({ hasText: `${pairAlias(11, 12)} muốn kết nối với bạn` });
  await invite
    .getByRole("button", { name: "Đồng ý kết nối", exact: true })
    .click();
  await expect(
    two.getByText("Đã kết nối. Bạn có thể bắt đầu trò chuyện."),
  ).toBeVisible();
  await two.getByRole("link", { name: "Mở cuộc trò chuyện" }).click();
  await expect(
    two.getByText("Hãy bắt đầu bằng một lời hỏi thăm."),
  ).toBeVisible();

  await one.goto("/#/messages");
  await one.locator('a[href^="#/chat/"]').first().click();
  const room = one.url().split("/chat/")[1];
  const composer = one.getByRole("textbox", {
    name: "Tin nhắn cho bạn kết nối",
  });
  await composer.fill("Xin chào từ 11");
  await one.getByRole("button", { name: "Gửi tin nhắn" }).dblclick();
  await expect(
    two.getByRole("log").getByText("Xin chào từ 11", { exact: true }),
  ).toBeVisible({ timeout: 15_000 });
  await two
    .getByRole("textbox", { name: "Tin nhắn cho bạn kết nối" })
    .fill("Chào 11, mình là 12");
  await two.getByRole("button", { name: "Gửi tin nhắn" }).click();
  await expect(
    one.getByRole("log").getByText("Chào 11, mình là 12", { exact: true }),
  ).toBeVisible({ timeout: 15_000 });
  const history = (await call(a, 11, "GET", `/connections/${room}/messages`))
    .body.messages;
  expect(history.map((m: { text: string }) => m.text)).toEqual([
    "Xin chào từ 11",
    "Chào 11, mình là 12",
  ]);

  await one.reload();
  await two.reload();
  await expect(one.getByRole("log").locator(".chat-bubble")).toHaveText([
    "Xin chào từ 11",
    "Chào 11, mình là 12",
  ]);
  await expect(two.getByRole("log").locator(".chat-bubble")).toHaveText([
    "Xin chào từ 11",
    "Chào 11, mình là 12",
  ]);

  for (const [method, path, data] of [
    ["GET", `/connections/${room}`, undefined],
    ["GET", `/connections/${room}/messages`, undefined],
    [
      "POST",
      `/connections/${room}/messages`,
      { text: "chen ngang", clientMessageId: crypto.randomUUID() },
    ],
  ] as const) {
    const denied = await call(c, 13, method, path, data);
    expect(denied.status).toBe(404);
    expect(denied.text).not.toContain("Xin chào từ 11");
  }

  // B withdraws MATCH from another page; A's open chat tab must lose access without reload.
  const settings = await b.newPage();
  await disable(settings, "tìm bạn");
  await expect(one.getByText(/không còn khả dụng/)).toBeVisible({
    timeout: 20_000,
  });
  await expect(composer).toBeDisabled();
  await expect(one.getByRole("log").locator(".chat-bubble")).toHaveCount(0);
  const stale = await call(a, 11, "POST", `/connections/${room}/messages`, {
    text: "tab cũ",
    clientMessageId: crypto.randomUUID(),
  });
  expect(stale.status).toBe(403);

  // Restoring consent never republishes the profile implicitly.
  await enable(settings, "tìm bạn");
  await settings.goto("/#/connect");
  await expect(
    settings.getByRole("heading", { name: "Hồ sơ đang tạm ẩn" }),
  ).toBeVisible();
  expect(
    (await call(b, 12, "GET", "/profiles/published/current")).body.state,
  ).toBe("needs_republish");
  const cards = (await call(a, 11, "GET", "/matching/candidates")).body
    .candidates;
  expect(cards.map((x: { alias: string }) => x.alias)).not.toContain(
    pairAlias(11, 12),
  );
  await a.close();
  await b.close();
  await c.close();
});

test("Journey D: block keeps report-after-block possible, the peer's tab closes, and ending needs confirmation", async ({
  browser,
}) => {
  const a = await browser.newContext(),
    b = await browser.newContext();
  await session(a, 14);
  await session(b, 15);
  const room = await connectByApi(a, 14, b, 15, "friendship");
  await call(b, 15, "POST", `/connections/${room}/messages`, {
    text: "Tin nhắn cần báo cáo",
    clientMessageId: crypto.randomUUID(),
  });
  const one = await a.newPage(),
    two = await b.newPage();
  await one.goto(`/#/chat/${room}`);
  await two.goto(`/#/chat/${room}`);
  await expect(
    one.getByRole("log").getByText("Tin nhắn cần báo cáo"),
  ).toBeVisible();
  await one
    .locator("summary")
    .filter({ hasText: "Chia sẻ và an toàn" })
    .click();
  await one
    .getByRole("button", { name: "Chặn kết nối này", exact: true })
    .click();
  await one.getByRole("button", { name: "Xác nhận chặn", exact: true }).click();
  await expect(one.getByText("Bạn đã chặn kết nối này.")).toBeVisible();
  await expect(
    one.getByRole("textbox", { name: "Tin nhắn cho bạn kết nối" }),
  ).toBeDisabled();
  await one
    .getByRole("textbox", { name: "Lý do báo cáo", exact: true })
    .fill("Quấy rối sau khi chặn");
  await one
    .getByRole("checkbox", { name: "Tin nhắn cần báo cáo", exact: true })
    .check();
  await one.getByRole("button", { name: "Gửi báo cáo", exact: true }).click();
  await expect(
    one.getByText("Đã nhận báo cáo.", { exact: true }),
  ).toBeVisible();
  await expect(two.getByText(/không còn khả dụng/)).toBeVisible({
    timeout: 20_000,
  });
  await expect(
    two.getByRole("log").getByText("Tin nhắn cần báo cáo"),
  ).toHaveCount(0);
  expect(
    (
      await call(b, 15, "POST", `/connections/${room}/messages`, {
        text: "còn đó?",
        clientMessageId: crypto.randomUUID(),
      })
    ).status,
  ).toBe(403);
  const cards = (await call(b, 15, "GET", "/matching/candidates")).body
    .candidates;
  expect(cards.map((x: { alias: string }) => x.alias)).not.toContain(
    pairAlias(14, 15),
  );

  const c = await browser.newContext(),
    d = await browser.newContext();
  await session(c, 16);
  await session(d, 17);
  const ended = await connectByApi(c, 16, d, 17, "shared-interests");
  const three = await c.newPage();
  await three.goto(`/#/chat/${ended}`);
  const end = three.getByRole("button", {
    name: "Kết thúc kết nối",
    exact: true,
  });
  await end.click();
  await expect(
    three.getByRole("dialog", { name: "Kết thúc kết nối này?" }),
  ).toBeVisible();
  await three.keyboard.press("Escape");
  await expect(three.getByRole("dialog")).toHaveCount(0);
  await expect(end).toBeFocused();
  expect(
    (await call(d, 17, "GET", `/connections/${ended}/messages`)).status,
  ).toBe(200);
  await end.click();
  await three
    .getByRole("button", { name: "Xác nhận kết thúc", exact: true })
    .click();
  await expect(three.getByText("Bạn đã kết thúc kết nối này.")).toBeVisible();
  expect(
    (await call(d, 17, "GET", `/connections/${ended}/messages`)).status,
  ).toBe(403);
  for (const context of [a, b, c, d]) await context.close();
});

test("Journey F: mood, matching and chat stay usable at 390px and 430px with the composer in view", async ({
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
  await one.goto("/#/self");
  await one.getByLabel("Ghi chú", { exact: true }).fill("Ghi trên điện thoại");
  await one.getByRole("button", { name: "Lưu tâm trạng", exact: true }).click();
  await expect(
    one.getByText("Đã lưu tâm trạng.", { exact: true }),
  ).toBeVisible();
  await expect(one.getByText(/Trung bình từ 1\/7 ngày có ghi/)).toBeVisible();
  await noHorizontalOverflow(one);
  await one.screenshot({ path: `${shots}/mood-390.png`, fullPage: true });
  const room = await connectByApi(a, 18, b, 19, "friendship");
  for (const [page, width] of [
    [one, 390],
    [two, 430],
  ] as const) {
    await page.goto("/#/connect");
    await noHorizontalOverflow(page);
    await page.goto("/#/messages");
    await expect(
      page.getByRole("navigation", { name: "Điều hướng chính" }),
    ).toBeVisible();
    await noHorizontalOverflow(page);
    await page.goto(`/#/chat/${room}`);
    await expect(
      page
        .getByText("Hãy bắt đầu bằng một lời hỏi thăm.")
        .or(page.locator(".chat-bubble").first()),
    ).toBeVisible();
    await noHorizontalOverflow(page);
    await page.screenshot({ path: `${shots}/chat-${width}.png` });
  }
  const composer = one.getByRole("textbox", {
    name: "Tin nhắn cho bạn kết nối",
  });
  await composer.tap();
  await composer.fill("Nhắn từ 390px");
  await one.getByRole("button", { name: "Gửi tin nhắn" }).tap();
  await expect(two.getByRole("log").getByText("Nhắn từ 390px")).toBeVisible({
    timeout: 15_000,
  });
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
    .getByRole("button", { name: "Gửi tin nhắn" })
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
  const page = await context.newPage();
  await enable(page, "tìm bạn");
  const routes = [
    ["/assistants", "Bạn muốn kể gì"],
    ["/self", "Cảm xúc của bạn"],
    ["/profile", "Hồ sơ riêng"],
    ["/memory", ""],
    ["/settings", "Quyền riêng tư"],
    ["/connect", "Tìm bạn đồng điệu"],
    ["/messages", "Tin nhắn"],
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
