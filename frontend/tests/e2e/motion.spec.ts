import { expect, test, type Page } from "@playwright/test";
import { app, baseSession, sessionWith } from "./ux-fixtures";

// V-MOTION-TOKENS / V-MOTION-LIFECYCLE / V-REDUCED-MOTION. The dev server runs
// React StrictMode, so every mount here is also a mount→cleanup→mount check.

async function recordMainOpacity(page: Page) {
  await page.evaluate(() => {
    const samples: number[] = [];
    (window as any).mainOpacity = samples;
    const main = document.getElementById("main")!;
    const sample = () => {
      // Only animation-driven opacity counts (inline GSAP styles or running
      // CSS animations); static UA styling such as a disabled select does not.
      for (const element of main.querySelectorAll<HTMLElement>("*")) {
        const inline = element.style.opacity !== "" && parseFloat(element.style.opacity) < 1;
        const animated = element.getAnimations().length > 0 && parseFloat(getComputedStyle(element).opacity) < 1;
        if (inline || animated) { samples.push(parseFloat(getComputedStyle(element).opacity)); break; }
      }
    };
    new MutationObserver(sample).observe(main, { childList: true, subtree: true, attributes: true, attributeFilter: ["style"] });
  });
}

test("route changes swap content immediately without fading it in", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "no-preference" });
  await app(page, baseSession, {
    "/moods": () => ({ json: [] }),
    "/moods/summary": () => ({ json: { from: "2026-10-17", to: "2026-10-23", count: 0, mean: null, min: null, max: null, insightAvailable: false, buckets: [] } }),
  });
  await page.goto("/#/messages");
  await expect(page.getByRole("heading", { level: 1, name: "Tin nhắn" })).toBeVisible();
  await recordMainOpacity(page);
  await page.getByRole("navigation", { name: "Điều hướng chính" }).getByRole("link", { name: "Nhật ký" }).click();
  await expect(page).toHaveURL(/#\/self$/);
  await page.waitForTimeout(400);
  expect(await page.evaluate(() => (window as any).mainOpacity)).toEqual([]);
});

async function openRename(page: Page) {
  const conversation = {
    conversationId: "22222222-2222-4222-8222-222222222222", botId: "may", version: 2, persistent: true, title: "Một ngày dài",
    expiresAt: "2026-11-22T08:00:00Z", updatedAt: "2026-10-23T08:00:00Z", hasMoreMessages: false, activeRunId: null, activeRunVersion: null, messages: [],
  };
  await app(page, sessionWith({}), {
    "/ai/preferences": () => ({ json: { historyEnabled: true, semanticMemoryEnabled: false, version: 1, policyVersion: "ai-data-v1", retentionDays: 30, historyAvailable: true, semanticMemoryAvailable: false } }),
    "/ai/conversations": () => ({ json: [conversation] }),
    [`/ai/conversations/${conversation.conversationId}`]: () => ({ json: conversation }),
  });
  await page.goto(`/#/assistants/may?conversation=${conversation.conversationId}`);
}

async function openRenameDialog(page: Page) {
  // Rename lives in the conversation info surface once it exists.
  const info = page.getByRole("button", { name: "Thông tin cuộc trò chuyện", exact: true });
  if ((await info.getAttribute("aria-expanded")) !== "true") await info.click();
  await page.getByRole("button", { name: "Đổi tên", exact: true }).click();
}

async function dialogTransforms(page: Page) {
  await page.evaluate(() => {
    const transforms: string[] = [];
    (window as any).dialogTransforms = transforms;
    // The first sample is taken synchronously when the dialog opens, so the
    // starting offset is always captured regardless of frame timing.
    new MutationObserver(() => {
      const dialog = document.querySelector<HTMLElement>("dialog[open]");
      if (dialog) transforms.push(getComputedStyle(dialog).transform + "|" + getComputedStyle(dialog).opacity);
    }).observe(document.body, { subtree: true, attributes: true, attributeFilter: ["open"] });
    const tick = () => {
      const dialog = document.querySelector<HTMLElement>("dialog[open]");
      if (dialog) transforms.push(getComputedStyle(dialog).transform + "|" + getComputedStyle(dialog).opacity);
      requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  });
}

test("a dialog moves at most 8px, keeps text opaque and leaves no inline animation styles", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "no-preference" });
  await openRename(page);
  await dialogTransforms(page);
  await openRenameDialog(page);
  const dialog = page.getByRole("dialog", { name: /Đổi tên/ });
  await expect(dialog).toBeVisible();
  await page.waitForTimeout(450);
  const samples: string[] = await page.evaluate(() => (window as any).dialogTransforms);
  expect(samples.length).toBeGreaterThan(0);
  for (const sample of samples) {
    const [transform, opacity] = sample.split("|");
    expect(opacity).toBe("1");
    if (transform !== "none") {
      const values = transform.replace(/matrix\(|\)/g, "").split(",").map(Number);
      expect(Math.abs(values[5])).toBeLessThanOrEqual(8);
    }
  }
  expect(await dialog.evaluate((element) => (element as HTMLElement).style.cssText)).toBe("");
});

test("with reduced motion a dialog never moves", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await openRename(page);
  await dialogTransforms(page);
  await openRenameDialog(page);
  await expect(page.getByRole("dialog", { name: /Đổi tên/ })).toBeVisible();
  await page.waitForTimeout(300);
  const samples: string[] = await page.evaluate(() => (window as any).dialogTransforms);
  expect(samples.every((sample) => sample.startsWith("none|1"))).toBe(true);
});

test("rapidly opening and closing a dialog leaves no open dialog, inert page or stuck style", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "no-preference" });
  await openRename(page);
  for (let index = 0; index < 10; index += 1) {
    await openRenameDialog(page);
    await expect(page.getByRole("dialog", { name: /Đổi tên/ })).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(page.getByRole("dialog", { name: /Đổi tên/ })).toHaveCount(0);
    const closeInfo = page.getByRole("button", { name: "Đóng thông tin cuộc trò chuyện" });
    if (await closeInfo.isVisible().catch(() => false)) await closeInfo.click();
  }
  await expect(page.locator("dialog[open]")).toHaveCount(0);
  const state = await page.evaluate(() => ({
    inert: [...document.querySelectorAll("[inert]")].length,
    styled: [...document.querySelectorAll<HTMLElement>("dialog")].map((dialog) => dialog.style.cssText).filter(Boolean),
  }));
  expect(state).toEqual({ inert: 0, styled: [] });
  await expect(page.getByRole("textbox", { name: "Tin nhắn cho Mây" })).toBeEditable();
});

test("the AI status wrapper moves only when an accepted run begins, never while sending or as the reply lands", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "no-preference" });
  const CONV = "22222222-2222-4222-8222-222222222222", RUN = "33333333-3333-4333-8333-333333333333";
  const thread = { conversationId: CONV, botId: "may", version: 1, persistent: false, messages: [] as unknown[], hasMoreMessages: false, activeRunId: null, activeRunVersion: null };
  let accept: () => void = () => {}, finish: () => void = () => {};
  const accepted = new Promise<void>((resolve) => { accept = resolve; });
  const finished = new Promise<void>((resolve) => { finish = resolve; });
  await app(page, baseSession, { "/ai/conversations": (request) => (request.method() === "GET" ? { json: [] } : { status: 201, json: thread }), [`/ai/conversations/${CONV}`]: () => ({ json: thread }) });
  await page.route(`**/api/v1/ai/conversations/${CONV}/messages`, async (route) => {
    await accepted;
    const sent = route.request().postDataJSON();
    thread.messages.push({ id: sent.clientMessageId, actor: "self", text: sent.text });
    await route.fulfill({ status: 202, json: { runId: RUN, conversationId: CONV, version: 2, runVersion: 1, eventsUrl: `/api/v1/ai/runs/${RUN}/events` } });
  });
  await page.route(`**/api/v1/ai/runs/${RUN}/events`, async (route) => {
    await finished;
    // The real backend records the reply before publishing completion.
    thread.messages.push({ id: `${RUN}-bot`, actor: "bot", text: "Xong.", cards: [] });
    await route.fulfill({ contentType: "text/event-stream", body: [{ type: "final", data: { text: "Xong.", cards: [] } }, { type: "completed", data: {} }].map((event, index) => `data: ${JSON.stringify({ version: "ai-events-v1", seq: String(index + 1), ...event })}\n\n`).join("") });
  });
  await page.goto("/#/assistants/may?new=1");
  await page.evaluate(() => {
    const samples: Record<string, string[]> = {};
    (window as any).statusSamples = samples;
    const read = () => {
      const wrapper = document.querySelector<HTMLElement>(".ai-status");
      const label = wrapper?.querySelector("[role=status]")?.textContent || "idle";
      const key = /gửi/.test(label) ? "sending" : /trả lời/.test(label) ? "accepted" : document.querySelector(".from-bot") ? "final" : "other";
      (samples[key] ||= []).push(wrapper ? getComputedStyle(wrapper).transform : "none");
    };
    new MutationObserver(read).observe(document.body, { subtree: true, childList: true, characterData: true, attributes: true });
    const tick = () => { read(); requestAnimationFrame(tick); };
    requestAnimationFrame(tick);
  });
  await page.getByRole("textbox", { name: "Tin nhắn cho Mây" }).fill("Xin chào");
  await page.getByRole("button", { name: "Gửi tin cho AI", exact: true }).click();
  await expect(page.locator(".ai-status [role=status]")).toHaveText("Đang gửi tin nhắn…");
  await page.waitForTimeout(250);
  accept();
  await expect(page.locator(".ai-status [role=status]")).toHaveText("Đang trả lời…");
  await page.waitForTimeout(300);
  finish();
  // The final reply must survive the authoritative transcript reconciliation.
  await expect(page.locator(".ai-status")).not.toHaveAttribute("aria-busy", "true");
  await expect(page.locator(".from-bot .chat-bubble")).toContainText("Xong.");
  await page.waitForTimeout(300);
  const samples: Record<string, string[]> = await page.evaluate(() => (window as any).statusSamples);
  expect(samples.sending.every((value) => value === "none")).toBe(true);
  expect((samples.final ?? []).every((value) => value === "none")).toBe(true);
  for (const value of samples.accepted) if (value !== "none") expect(Math.abs(Number(value.replace(/matrix\(|\)/g, "").split(",")[5]))).toBeLessThanOrEqual(4);
});
