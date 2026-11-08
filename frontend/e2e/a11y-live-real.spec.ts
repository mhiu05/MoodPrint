// E-AG-13: the live Companion screens at the eight project widths, with axe, the keyboard and reduced
// motion. Real stack, deterministic model stand-in. Reports only what was exercised here.
import AxeBuilder from "@axe-core/playwright";
import type { Page } from "@playwright/test";
import { test, expect } from "./helpers/fixtures";
import {
  createCaseViaApi,
  createUser,
  login,
  removeUser,
} from "./helpers/local";
import { COLORS, solidPng, uploadImageEvidence } from "./helpers/phase3";

const WIDTHS = [320, 360, 375, 390, 430, 768, 1024, 1440];

async function serious(page: Page, label: string) {
  const result = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa"])
    .analyze();
  const bad = result.violations.filter((v) =>
    ["serious", "critical"].includes(v.impact ?? ""),
  );
  if (bad.length)
    console.log(
      `AXE ${label}:`,
      JSON.stringify(
        bad.map((v) => ({
          id: v.id,
          impact: v.impact,
          nodes: v.nodes.slice(0, 3).map((n) => ({
            target: n.target,
            summary: n.failureSummary?.slice(0, 220),
          })),
        })),
      ),
    );
  expect(bad, `axe serious/critical on ${label}`).toEqual([]);
}
async function say(page: Page, text: string) {
  // Typing while the previous run is still finishing is ignored by the UI; wait until it can send.
  await expect(page.getByRole("button", { name: "Gửi" })).toBeVisible();
  const box = page.getByRole("textbox", { name: "Điều bạn muốn kể" });
  await box.fill(text);
  await box.press("Enter");
}
async function noOverflow(page: Page, width: number, label: string) {
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth),
    `${label} at ${width}px`,
  ).toBeLessThanOrEqual(width);
}

test("E-AG-13a: chat, approval dialog, analysis and roleplay fit every width and pass axe; the dialog is keyboard-safe", async ({
  page,
}) => {
  test.setTimeout(420000);
  const user = await createUser();
  try {
    await createCaseViaApi(user.email);
    await page.addInitScript(() =>
      localStorage.setItem("moodprint:ai-companion", "live"),
    );
    await page.emulateMedia({ reducedMotion: "reduce" });
    await login(page, user.email);
    await expect(page).toHaveURL(/\/home$/);
    await uploadImageEvidence(page, solidPng(COLORS.ok, 71));

    // -- chat with a pending approval --
    await page.goto("/ai/chat");
    await page.getByRole("button", { name: /Cuộc trò chuyện mới/ }).click();
    await expect(page.getByTestId("chat-live")).toBeVisible();
    await expect(page.getByText(/Bạn muốn kể điều gì/)).toBeVisible();
    await say(page, "Giúp mình ghi mốc bạn A chế giễu hôm 3/11");
    await expect(page.getByText(/CHƯA LƯU/)).toBeVisible();
    await say(page, "Ok, lưu mốc đó vào hồ sơ");
    const dialog = page.getByRole("dialog");
    await expect(dialog).toBeVisible();
    await serious(page, "approval dialog");

    // Keyboard: focus is inside the dialog, Tab cannot leave it, Esc defers without deciding.
    // A native modal dialog makes everything behind it inert: Tab cycles inside it (or leaves to the
    // browser chrome, where the active element is the body) and never reaches the page behind.
    const focusContained = () =>
      page.evaluate(
        () =>
          !!document.activeElement?.closest("dialog") ||
          document.activeElement === document.body,
      );
    expect(
      await page.evaluate(() => !!document.activeElement?.closest("dialog")),
    ).toBe(true); // initial focus is inside the dialog
    for (let i = 0; i < 8; i++) {
      await page.keyboard.press("Tab");
      expect(await focusContained(), `Tab ${i + 1} stays contained`).toBe(true);
    }
    await page.keyboard.press("Escape");
    await expect(dialog).toHaveCount(0);
    await expect(
      page.getByText(/đề xuất đang chờ bạn quyết định/),
    ).toBeVisible(); // deferred, not decided
    await serious(page, "chat with a deferred proposal");

    // -- every width: chat (with the notice and the dialog trigger), analysis, roleplay --
    const chatUrl = page.url();
    for (const width of WIDTHS) {
      await page.setViewportSize({ width, height: 900 });
      await page.goto(chatUrl);
      await expect(page.getByTestId("chat-live")).toBeVisible();
      // A reload restores the pending proposal and opens it again.
      await expect(page.getByRole("dialog")).toBeVisible();
      await noOverflow(page, width, "approval dialog");
      await page.keyboard.press("Escape");
      await noOverflow(page, width, "chat");
      await page.goto("/ai/analysis/new");
      await expect(page.getByTestId("analysis-live")).toBeVisible();
      await page.getByRole("radio", { name: /anh-tong-hop\.png/ }).check();
      await noOverflow(page, width, "analysis");
      await page.goto("/ai/roleplay");
      await expect(page.getByTestId("roleplay-live")).toBeVisible();
      await noOverflow(page, width, "roleplay picker");
    }
    await page.setViewportSize({ width: 1280, height: 900 });

    // -- analysis result and roleplay session --
    await page.goto("/ai/analysis/new");
    await page.getByRole("radio", { name: /anh-tong-hop\.png/ }).check();
    await serious(page, "analysis consent step");
    await page.getByRole("checkbox", { name: /Tôi đồng ý gửi ảnh/ }).check();
    await page.getByRole("button", { name: "Phân tích ảnh" }).click();
    await expect(page.getByTestId("analysis-result")).toBeVisible();
    await serious(page, "analysis result");

    await page.goto("/ai/roleplay");
    await page.getByRole("radio").first().check();
    await page.getByRole("button", { name: "Bắt đầu diễn tập" }).click();
    await expect(page.getByText(/Bạn muốn kể điều gì/)).toBeVisible();
    await say(page, "Em chào cô ạ.");
    await expect(page.getByText(/nghe .* đây \(lượt 1\)/)).toBeVisible();
    await serious(page, "roleplay session");
    await page
      .getByRole("button", { name: /Kết thúc & nhận phản hồi/ })
      .click();
    await expect(page.getByTestId("roleplay-feedback")).toBeVisible();
    await serious(page, "roleplay feedback");

    // Leave nothing pending (an account with a waiting approval cannot be deleted): decline it.
    await page.goto(chatUrl);
    await page
      .getByRole("dialog")
      .getByRole("button", { name: "Không lưu" })
      .click();
    await expect(page.getByRole("dialog")).toHaveCount(0);
    // The run finishes after the decision; only then can the account be removed.
    await expect(page.getByRole("button", { name: "Gửi" })).toBeVisible();
  } finally {
    await page.close();
    await removeUser(user.email);
  }
});

test("E-AG-13b: new messages are announced politely and reduced motion removes the working animation", async ({
  page,
}) => {
  test.setTimeout(120000);
  const user = await createUser();
  try {
    await page.addInitScript(() =>
      localStorage.setItem("moodprint:ai-companion", "live"),
    );
    await page.emulateMedia({ reducedMotion: "reduce" });
    await login(page, user.email);
    await expect(page).toHaveURL(/\/home$/);
    await page.goto("/ai/chat");
    await page.getByRole("button", { name: /Cuộc trò chuyện mới/ }).click();
    await expect(page.getByText(/Bạn muốn kể điều gì/)).toBeVisible();
    // The transcript is a polite live region; urgent content is not hidden inside an assertive loop.
    const log = page.getByRole("log", { name: "Tin nhắn" });
    await expect(log).toHaveAttribute("aria-live", "polite");
    await say(page, "Hãy trả lời chậm giúp mình nhé");
    await expect(page.getByRole("button", { name: "Dừng" })).toBeVisible();
    // With reduced motion nothing inside the chat keeps an infinite animation running.
    const animated = await page.evaluate(() =>
      [...document.querySelectorAll("[data-testid=chat-live] *")]
        .filter((el) => {
          const s = getComputedStyle(el);
          return (
            s.animationName !== "none" &&
            s.animationIterationCount === "infinite" &&
            parseFloat(s.animationDuration) > 0
          );
        })
        .map((el) => el.className),
    );
    expect(animated).toEqual([]);
    await page.getByRole("button", { name: "Dừng" }).click();
    await expect(page.getByRole("button", { name: "Gửi" })).toBeVisible({
      timeout: 20000,
    });
  } finally {
    await page.close();
    await removeUser(user.email);
  }
});
