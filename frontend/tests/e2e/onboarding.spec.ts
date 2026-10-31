import { expect, test, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { app, baseSession, guestSession } from "./ux-fixtures";

async function setup(page: Page, value: unknown = baseSession, enabled = true) {
  const mutations: string[] = [];
  await app(page, value, {
    "/public/experience": () => ({ json: { guestAvailable: false, guestUnavailableReason: "disabled", feedbackAvailable: false, productTourAvailable: enabled, captchaSiteKey: null } }),
    "/moods": () => ({ json: [] }),
    "/moods/summary": () => ({ json: { buckets: [], mean: null, min: null, max: null, count: 0, from: "2026-10-17", to: "2026-10-23", timezone: "Asia/Bangkok" } }),
  });
  page.on("request", (request) => { if (["POST", "PUT", "PATCH", "DELETE"].includes(request.method())) mutations.push(request.url()); });
  return mutations;
}

async function open(page: Page) {
  await page.goto("/#/settings");
  await page.getByRole("button", { name: "Xem hướng dẫn", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Hướng dẫn nhanh", exact: true })).toBeVisible();
}

test("Next Back Skip Finish Escape and replay are keyboard accessible and mutation-free", async ({ page }) => {
  const mutations = await setup(page);
  await open(page);
  await page.getByRole("button", { name: "Bắt đầu hướng dẫn", exact: true }).click();
  await expect(page.getByText("Bước 1/4", { exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Chọn trợ lý", exact: true })).toBeFocused();
  await expect(page.getByRole("button", { name: "Tiếp", exact: true })).toBeEnabled();
  const next = page.getByRole("button", { name: "Tiếp", exact: true });
  await next.focus();
  await expect(next).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.getByText("Bước 2/4", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Quay lại", exact: true }).click();
  await expect(page.getByText("Bước 1/4", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Bỏ qua", exact: true }).click();
  await expect(page.getByText("Bạn có thể xem lại hướng dẫn bất cứ lúc nào.", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Xem lại hướng dẫn", exact: true }).click();
  for (let index = 0; index < 3; index++) await page.getByRole("button", { name: "Tiếp", exact: true }).click();
  await page.getByRole("button", { name: "Hoàn tất", exact: true }).click();
  await expect(page.getByText("Bạn đã xem xong hướng dẫn.", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Xem lại hướng dẫn", exact: true }).click();
  await page.keyboard.press("Escape");
  await expect(page.locator(".onboarding-target")).toHaveCount(0);
  expect(mutations).toEqual([]);
});

test("missing first target resolves within three seconds without late highlighting", async ({ page }) => {
  await setup(page);
  await open(page);
  await page.addStyleTag({ content: "[data-tour='assistants-list'] { display: none !important; }" });
  await page.getByRole("button", { name: "Bắt đầu hướng dẫn", exact: true }).click();
  await expect(page.getByText("Chưa thể mở hướng dẫn ở màn hình này. Thử lại sau.", { exact: true })).toBeVisible({ timeout: 4500 });
  await expect(page.locator(".onboarding-target")).toHaveCount(0);
});

test("transparent first target is not treated as visible geometry", async ({ page }) => {
  await setup(page);
  await open(page);
  await page.addStyleTag({ content: "[data-tour='assistants-list'] { opacity: 0 !important; }" });
  await page.getByRole("button", { name: "Bắt đầu hướng dẫn", exact: true }).click();
  await expect(page.getByText("Chưa thể mở hướng dẫn ở màn hình này. Thử lại sau.", { exact: true })).toBeVisible({ timeout: 4500 });
  await expect(page.locator(".onboarding-target")).toHaveCount(0);
});

test("closing during readiness aborts observers and cannot highlight a later target", async ({ page }) => {
  await page.clock.install({ time: new Date() });
  await setup(page);
  await open(page);
  const style = await page.addStyleTag({ content: "[data-tour='assistants-list'] { display: none !important; }" });
  await page.getByRole("button", { name: "Bắt đầu hướng dẫn", exact: true }).click();
  await expect(page.getByText("Đang tìm vị trí hướng dẫn…", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Đóng hướng dẫn", exact: true }).click();
  await style.evaluate((element) => (element as HTMLElement).remove());
  await page.clock.fastForward(4000);
  await expect(page.locator(".onboarding-guide, .onboarding-target")).toHaveCount(0);
});

test("browser Back cancels instead of forcing navigation", async ({ page }) => {
  await setup(page);
  await open(page);
  await page.getByRole("button", { name: "Bắt đầu hướng dẫn", exact: true }).click();
  await expect(page.getByText("Bước 1/4", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Tiếp", exact: true }).click();
  await expect(page.getByText("Bước 2/4", { exact: true })).toBeVisible();
  await page.goBack();
  await expect(page.locator(".onboarding-target")).toHaveCount(0);
  await expect(page.getByText("Hướng dẫn đã dừng khi bạn chuyển màn hình.", { exact: true })).toBeVisible();
});

test("browser Back stops guidance before a delayed router observes the history event", async ({ page }) => {
  // Model a delayed router transition without delaying the browser's actual Back.
  // The guide must release its target even while React still shows the old route.
  await page.addInitScript(() => {
    const original = window.addEventListener.bind(window);
    const remove = window.removeEventListener.bind(window);
    const listeners = new Map<EventListenerOrEventListenerObject, EventListener>();
    const state = window as typeof window & {
      registerGuide?: boolean; holdRouter?: boolean; historyCallbacks?: (() => void)[];
    };
    state.historyCallbacks = [];
    window.addEventListener = ((type: string, listener: EventListenerOrEventListenerObject, options?: boolean | AddEventListenerOptions) => {
      if (type !== "popstate" || state.registerGuide) return original(type, listener, options);
      const wrapped: EventListener = event => {
        const invoke = () => typeof listener === "function" ? listener.call(window, event) : listener.handleEvent(event);
        if (state.holdRouter) state.historyCallbacks!.push(invoke);
        else invoke();
      };
      listeners.set(listener, wrapped);
      original(type, wrapped, options);
    }) as typeof window.addEventListener;
    window.removeEventListener = ((type: string, listener: EventListenerOrEventListenerObject, options?: boolean | EventListenerOptions) => {
      remove(type, type === "popstate" ? listeners.get(listener) || listener : listener, options);
    }) as typeof window.removeEventListener;
  });
  const mutations = await setup(page);
  await page.goto("/#/settings");
  await expect(page.getByRole("button", { name: "Xem hướng dẫn", exact: true })).toBeVisible();
  await page.evaluate(() => { (window as typeof window & { registerGuide?: boolean }).registerGuide = true; });
  await page.getByRole("button", { name: "Xem hướng dẫn", exact: true }).click();
  await page.getByRole("button", { name: "Bắt đầu hướng dẫn", exact: true }).click();
  await page.getByRole("button", { name: "Tiếp", exact: true }).click();
  await expect(page.getByRole("button", { name: "Tiếp", exact: true })).toBeEnabled();
  await expect(page).toHaveURL(/#\/self$/);
  await page.evaluate(() => { (window as typeof window & { holdRouter?: boolean }).holdRouter = true; });
  try {
    await page.goBack();
    await expect(page).toHaveURL(/#\/assistants$/);
    expect(await page.evaluate(() => (window as typeof window & { historyCallbacks?: (() => void)[] }).historyCallbacks!.length)).toBeGreaterThan(0);
    await expect(page.getByText("Hướng dẫn đã dừng khi bạn chuyển màn hình.", { exact: true })).toBeVisible();
    await expect(page.locator(".onboarding-target")).toHaveCount(0);
  } finally {
    await page.evaluate(() => {
      const state = window as typeof window & { holdRouter?: boolean; historyCallbacks?: (() => void)[] };
      state.holdRouter = false;
      state.historyCallbacks?.splice(0).forEach(invoke => invoke());
    });
  }
  await expect(page).toHaveURL(/#\/assistants$/);
  await expect(page.locator(".onboarding-target")).toHaveCount(0);
  expect(mutations).toEqual([]);
});

test("guest expiry destroys active guidance and never persists a guest key", async ({ page }) => {
  await page.clock.install({ time: new Date() });
  await setup(page, guestSession(60_000));
  await open(page);
  await page.getByRole("button", { name: "Bắt đầu hướng dẫn", exact: true }).click();
  await expect(page.getByText("Bước 1/4", { exact: true })).toBeVisible();
  await page.clock.fastForward(61_000);
  await expect(page.getByRole("heading", { name: "Lượt dùng thử đã kết thúc" })).toBeVisible();
  await expect(page.locator(".onboarding-guide, .onboarding-target")).toHaveCount(0);
  expect(await page.evaluate(() => Object.keys(localStorage))).not.toContain("moodprint:tour:tour-v1:registered:22222222-2222-4222-8222-222222222222");
});

test("expiry while target readiness is waiting never publishes late guidance", async ({ page }) => {
  await page.clock.install({ time: new Date() });
  await setup(page, guestSession(10_000));
  await open(page);
  const style = await page.addStyleTag({ content: "[data-tour='assistants-list'] { display: none !important; }" });
  await page.getByRole("button", { name: "Bắt đầu hướng dẫn", exact: true }).click();
  await expect(page.getByText("Đang tìm vị trí hướng dẫn…", { exact: true })).toBeVisible();
  await page.clock.fastForward(11_000);
  await style.evaluate((element) => (element as HTMLElement).remove());
  await expect(page.getByRole("heading", { name: "Lượt dùng thử đã kết thúc" })).toBeVisible();
  await expect(page.locator(".onboarding-guide, .onboarding-target")).toHaveCount(0);
});

test("native app dialog suspends guidance before taking focus", async ({ page }) => {
  await setup(page, guestSession(7_000_000));
  await open(page);
  await page.getByRole("button", { name: "Bắt đầu hướng dẫn", exact: true }).click();
  await expect(page.getByText("Bước 1/4", { exact: true })).toBeVisible();
  await page.getByTestId("guest-status").getByRole("button", { name: "Kết thúc và xóa lượt dùng thử", exact: true }).click();
  await expect(page.getByRole("dialog", { name: "Kết thúc và xóa lượt dùng thử?", exact: true })).toBeVisible();
  await expect(page.locator(".onboarding-target")).toHaveCount(0);
});

test("flag off keeps a simple four-step inline guide without an overlay", async ({ page }) => {
  await setup(page, guestSession(7_000_000), false);
  await open(page);
  await expect(page.getByRole("list", { name: "Các bước hướng dẫn" }).getByRole("listitem")).toHaveCount(4);
  await expect(page.getByRole("button", { name: "Bắt đầu hướng dẫn", exact: true })).toHaveCount(0);
  await expect(page.locator(".driver-popover, .driver-overlay")).toHaveCount(0);
});

test("draft start refuses navigation and keeps the real mood draft", async ({ page }) => {
  const mutations = await setup(page);
  await open(page);
  await page.getByRole("link", { name: "Nhật ký", exact: true }).click();
  const note = page.locator("#journal-text");
  await note.fill("private-draft-stays-here");
  await page.getByRole("button", { name: "Bắt đầu hướng dẫn", exact: true }).click();
  await expect(page.getByText("Hãy hoàn tất hoặc đóng thao tác hiện tại rồi mở hướng dẫn.", { exact: true })).toBeVisible();
  await expect(page).toHaveURL(/#\/self/);
  await expect(note).toHaveValue("private-draft-stays-here");
  expect(mutations).toEqual([]);
});

async function chatWithGuide(page: Page) {
  await open(page);
  await page.getByRole("link", { name: "Trợ lý", exact: true }).click();
  await page.locator('a[href="#/assistants/may"]').first().click();
  await expect(page.getByRole("textbox", { name: "Tin nhắn cho Mây", exact: true })).toBeVisible();
}

test("active AI request refuses guidance without changing route or cancelling the request", async ({ page }) => {
  const mutations = await setup(page);
  const conversation = "66666666-6666-4666-8666-666666666666";
  let accepted = 0;
  let release: () => void = () => {};
  const held = new Promise<void>((resolve) => { release = resolve; });
  await page.route("**/api/v1/ai/conversations", (route) => route.request().method() === "POST"
    ? route.fulfill({ json: { conversationId: conversation, botId: "may", version: 1, persistent: false, title: "Mây", messages: [] } })
    : route.fallback());
  await page.route(`**/api/v1/ai/conversations/${conversation}/messages`, (route) => {
    accepted++;
    return route.fulfill({ status: 202, json: { runId: "77777777-7777-4777-8777-777777777777", version: 2, runVersion: 1, eventsUrl: "/api/v1/ai/runs/77777777-7777-4777-8777-777777777777/events" } });
  });
  await page.route("**/api/v1/ai/runs/*/events", async (route) => { await held; await route.fulfill({ contentType: "text/event-stream", body: "" }).catch(() => {}); });
  await chatWithGuide(page);
  await page.getByRole("textbox", { name: "Tin nhắn cho Mây", exact: true }).fill("Một lượt tổng hợp đang chờ");
  await page.getByRole("button", { name: "Gửi tin cho AI", exact: true }).click();
  await expect.poll(() => accepted).toBe(1);
  const beforeGuide = [...mutations];
  await page.getByRole("button", { name: "Bắt đầu hướng dẫn", exact: true }).click();
  await expect(page.getByText("Hãy hoàn tất hoặc đóng thao tác hiện tại rồi mở hướng dẫn.", { exact: true })).toBeVisible();
  await expect(page).toHaveURL(/#\/assistants\/may/);
  expect(accepted).toBe(1);
  expect(mutations).toEqual(beforeGuide);
  release();
});

test("pending microphone permission refuses guidance without requesting transcription", async ({ page }) => {
  await page.addInitScript(() => {
    Object.defineProperty(navigator, "mediaDevices", { configurable: true, value: { getUserMedia: () => new Promise(() => {}) } });
  });
  const mutations = await setup(page, { ...baseSession, features: { ...baseSession.features, voice: true }, consents: { ...baseSession.consents, VOICE: { enabled: true, version: 1, policyVersion: "v1" } } });
  await chatWithGuide(page);
  await page.getByRole("button", { name: "Ghi âm", exact: true }).click();
  await expect(page.getByText("Đang chờ quyền dùng micro…", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Bắt đầu hướng dẫn", exact: true }).click();
  await expect(page.getByText("Hãy hoàn tất hoặc đóng thao tác hiện tại rồi mở hướng dẫn.", { exact: true })).toBeVisible();
  await expect(page).toHaveURL(/#\/assistants\/may/);
  expect(mutations).toEqual([]);
});

test("loading saved journal metadata never invents an unsaved draft blocker", async ({ page }) => {
  await setup(page);
  await page.route("**/api/v1/moods", (route) => route.fulfill({ json: [{ localDate: "2026-10-23", value: 5, note: "saved-private-canary", timezone: "Asia/Bangkok", version: 1 }] }));
  await open(page);
  await page.getByRole("button", { name: "Bắt đầu hướng dẫn", exact: true }).click();
  await page.getByRole("button", { name: "Tiếp", exact: true }).click();
  await expect(page.locator("#journal-text")).toHaveValue("");
  await expect(page.getByText("Bước 2/4", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Tiếp", exact: true })).toBeEnabled();
  await expect(page.getByText("Hãy hoàn tất hoặc đóng thao tác hiện tại rồi mở hướng dẫn.", { exact: true })).toHaveCount(0);
});

test("missing later target skips once and unregistering a wait leaves no late highlight", async ({ page }) => {
  await setup(page);
  await open(page);
  await page.addStyleTag({ content: "[data-tour='memory-intro'] { display: none !important; }" });
  await page.getByRole("button", { name: "Bắt đầu hướng dẫn", exact: true }).click();
  await page.getByRole("button", { name: "Tiếp", exact: true }).click();
  await page.getByRole("button", { name: "Tiếp", exact: true }).click();
  await expect(page.getByText("Bước 4/4", { exact: true })).toBeVisible({ timeout: 4500 });
  await page.getByRole("button", { name: "Đóng hướng dẫn", exact: true }).click();
  await expect(page.locator(".onboarding-guide, .onboarding-target")).toHaveCount(0);
});

for (const width of [320, 390, 768, 1440]) {
  test(`inline tour fits ${width}px with reduced motion and 200% text`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width, height: 800 });
    await page.emulateMedia({ reducedMotion: "reduce" });
    const mutations = await setup(page);
    await open(page);
    await page.getByRole("button", { name: "Bắt đầu hướng dẫn", exact: true }).click();
    await expect(page.getByText("Bước 1/4", { exact: true })).toBeVisible();
    await page.addStyleTag({ content: "html { font-size: 200% !important; }" });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    expect((await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze()).violations).toEqual([]);
    expect(mutations).toEqual([]);
    await page.screenshot({ path: testInfo.outputPath(`onboarding-${width}.png`), fullPage: true });
  });
}
