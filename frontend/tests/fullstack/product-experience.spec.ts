import { artifactPath } from "../artifacts";
import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";
import { call, noHorizontalOverflow, openRoom, session } from "./helpers";

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

test("MoodPrint identity and short pages stay at the top across all six sizes", async ({
  browser,
}) => {
  test.setTimeout(180_000);
  const context = await browser.newContext({ reducedMotion: "reduce" });
  await session(context, 44);
  const state = await call(context, 44, "GET", "/session");
  expect(
    (
      await call(context, 44, "PUT", "/consents/MATCH", {
        enabled: true,
        expectedVersion: state.body.consents.MATCH.version,
        policyVersion: "v1",
      })
    ).status,
  ).toBe(200);
  const page = await context.newPage();
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  try {
    for (const [width, height] of SIZES) {
      await page.setViewportSize({ width, height });
      await page.goto("/#/messages");
      const heading = page.getByRole("heading", { name: "Tin nhắn", level: 1 });
      await expect(heading).toBeVisible();
      await expect(page).toHaveTitle(/^MoodPrint/);
      await expect(page.getByRole("main")).not.toContainText(/Me2We/i);
      await expect(
        page.getByRole("main").getByText("MoodPrint", { exact: false }).first(),
      ).toBeVisible();
      expect((await heading.boundingBox())!.y).toBeLessThan(180);
      await audit(page, "messages", width, height);
      await page.goto("/#/profile");
      await expect(
        page.getByRole("heading", { name: "Cá nhân", exact: true }),
      ).toBeVisible();
      await audit(page, "profile", width, height);
    }
    expect(errors).toEqual([]);
  } finally {
    await context.close();
  }
});

test("all five assistants explain their purpose and link to the related real feature", async ({
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
        ["guong", "Xem hồ sơ riêng", "/profile"],
        ["nhip", "Mở nhật ký cảm xúc", "/self"],
        ["rure", "Xem tin nhắn và hoạt động chung", "/messages"],
        ["caunoi", "Xem hồ sơ tìm bạn", "/connect?tab=profile"],
      ]) {
        await page.goto(`/#/assistants/${id}`);
        const link = page.getByRole("link", { name: action, exact: true });
        await expect(link).toHaveAttribute("href", `#${destination}`);
        await expect(
          page.getByText("Không chia sẻ với bạn kết nối", { exact: true }),
        ).toBeVisible();
        await link.focus();
        await expect(link).toBeFocused();
        await audit(page, `assistant-${id}`, width, height);
        await link.press("Enter");
        await expect(page).toHaveURL(
          new RegExp(`#${destination.replace("?", "\\?")}$`),
        );
      }
    }
  } finally {
    await context.close();
  }
});

test("a conversation starter stays editable and reaches the other account only after Send", async ({
  browser,
}) => {
  const { pageA, pageB, two, room, close } = await openRoom(browser, 42, 43);
  try {
    await pageA.setViewportSize({ width: 390, height: 480 });
    const starter = pageA.getByRole("button", {
      name: "Khi rảnh bạn thích làm gì nhất?",
      exact: true,
    });
    await starter.click();
    const composer = pageA.getByRole("textbox", {
      name: "Nhắn tin cho người bạn kết nối",
    });
    await expect(composer).toHaveValue("Khi rảnh bạn thích làm gì nhất?");
    await expect(composer).toBeFocused();
    await expect(composer).toBeInViewport();
    // The peer has the same starter buttons inside its empty log. Wait for that
    // screen, then check persisted messages instead of mistaking a button for a send.
    await expect(pageB.getByRole("group", { name: "Lời mở đầu" })).toBeVisible();
    await expect(pageB.getByRole("log").locator(".message-row")).toHaveCount(0);
    const beforeSend = await call(two, 43, "GET", `/connections/${room}/messages`);
    expect(beforeSend.status).toBe(200);
    expect(beforeSend.body.messages).toEqual([]);
    await composer.fill("Chào bạn, mình rất vui được làm quen!");
    await pageA
      .getByRole("button", { name: "Gửi tin nhắn", exact: true })
      .click();
    await expect(pageB.getByRole("log")).toContainText(
      "Chào bạn, mình rất vui được làm quen!",
    );
    await pageA.reload();
    await expect(pageA.getByRole("log")).toContainText(
      "Chào bạn, mình rất vui được làm quen!",
    );
    await expect(pageA.getByRole("log").getByText("Chào bạn, mình rất vui được làm quen!", { exact: true })).toBeInViewport();
    await pageA.getByRole("log").focus();
    await expect(pageA.getByRole("log")).toBeFocused();
    await audit(pageA, "human-chat", 390, 480);
    await pageA
      .getByRole("button", { name: "Cùng làm gì đó?", exact: true })
      .click();
    const catalog = pageA.getByRole("dialog", { name: "Cùng làm gì đó?" });
    await expect(catalog).toContainText("Mỗi người trả lời riêng");
    await expect(catalog).toContainText("Năm vòng đố vui cùng một đội");
    await expect(catalog).toContainText(
      "Một người tạm dừng sẽ dừng đồng hồ của cả hai",
    );
    await audit(pageA, "activity-catalog", 390, 480);
    await expect(catalog).toBeVisible();
  } finally {
    await close();
  }
});
