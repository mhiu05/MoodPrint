import { expect, test, type Page } from "@playwright/test";
import { app, guestSession, type Reply, type Routes } from "./ux-fixtures";

const MINUTE = 60_000;
const failure = (status: number, code: string, message = "Không thành công."): Reply => ({
  status,
  json: { error: { code, message } },
});
const endedHeading = (page: Page) => page.getByRole("heading", { name: "Lượt dùng thử đã kết thúc" });

/** A guest trial that ends `expiresInMs` from now; every API path that is hit is recorded. */
async function trial(page: Page, expiresInMs: number, routes: Routes = {}) {
  const calls: string[] = [];
  await app(page, guestSession(expiresInMs), {
    "/auth/guest/end": (request) => (request.method() === "POST" ? { status: 204 } : undefined),
    ...routes,
  });
  await page.route("**/api/v1/**", (route) => {
    const request = route.request();
    calls.push(`${request.method()} ${new URL(request.url()).pathname.replace("/api/v1", "")}`);
    return route.fallback();
  });
  return calls;
}

test("the deadline replaces the private tree and drops answers that arrive afterwards", async ({ page }) => {
  await page.clock.install();
  const calls = await trial(page, 10 * MINUTE);
  let release!: () => void;
  const gate = new Promise<void>((resolve) => (release = resolve));
  let held = 0;
  let late = 0;
  await page.route("**/api/v1/bots", async (route) => {
    held += 1;
    await gate;
    late += 1;
    await route
      .fulfill({
        json: [{ botId: "may", name: "BÍ-MẬT-MUỘN", role: "x", description: "x", starters: [], avatarKey: "may" }],
      })
      .catch(() => undefined); // the page aborted the request: nothing is left to answer
  });
  await page.goto("/#/assistants");
  await expect(page.getByTestId("guest-status")).toContainText("còn 10 phút");

  await page.clock.fastForward(11 * MINUTE);
  await expect(endedHeading(page)).toBeFocused();
  await expect(page.getByTestId("guest-status")).toHaveCount(0);

  const settled = calls.length;
  expect(held).toBeGreaterThan(0);
  release();
  await expect.poll(() => late).toBe(held);
  await page.waitForTimeout(300);
  await expect(page.getByText("BÍ-MẬT-MUỘN")).toHaveCount(0);
  expect(calls).toHaveLength(settled);
});

test("rewinding the device clock cannot extend a trial", async ({ page }) => {
  await page.clock.install();
  await trial(page, 10 * MINUTE);
  await page.goto("/#/assistants");
  await expect(page.getByTestId("guest-status")).toContainText("còn 10 phút");
  await page.clock.setSystemTime(new Date(Date.now() - 3 * 60 * MINUTE));
  await page.clock.fastForward(11 * MINUTE);
  await expect(endedHeading(page)).toBeVisible();
});

test("a pending focus refresh cannot extend the original monotonic deadline", async ({ page }) => {
  await page.clock.install();
  await trial(page, 10 * MINUTE);
  await page.goto("/#/assistants");
  await expect(page.getByTestId("guest-status")).toContainText("còn 10 phút");
  await page.clock.fastForward(9 * MINUTE);
  let release!: () => void;
  let pending = 0;
  const gate = new Promise<void>(resolve => { release = resolve; });
  await page.route("**/api/v1/session", async route => {
    pending += 1;
    await gate;
    await route.fulfill({ status: 401, json: { error: { code: "GUEST_EXPIRED", message: "Lượt dùng thử đã kết thúc." } } }).catch(() => undefined);
  });
  await page.evaluate(() => window.dispatchEvent(new Event("focus")));
  await page.clock.runFor(200);
  await expect.poll(() => pending).toBeGreaterThan(0);
  try {
    await page.clock.fastForward(2 * MINUTE);
    await expect(endedHeading(page)).toBeFocused();
  } finally { release(); }
});

test("a late SSE final cannot repopulate the private tree after expiry", async ({ page }) => {
  await page.clock.install();
  const conversationId = "33333333-3333-4333-8333-333333333333";
  const runId = "44444444-4444-4444-8444-444444444444";
  await app(page, guestSession(10 * MINUTE, {
    features: { ai: true, matching: false, voice: false, feedback: false },
    consents: { AI: { enabled: true, version: 1, policyVersion: "v1" }, MEM: { enabled: false, version: 1, policyVersion: "v1" }, MATCH: { enabled: false, version: 1, policyVersion: "v1" }, VOICE: { enabled: false, version: 1, policyVersion: "v1" } },
  }), {
    "/ai/conversations": request => request.method() === "POST" ? { status: 201, json: { conversationId, botId: "may", version: 1, messages: [], activeRunId: null } } : undefined,
    [`/ai/conversations/${conversationId}/messages`]: () => ({ status: 202, json: { runId, conversationId, version: 2, runVersion: 1, eventsUrl: `/api/v1/ai/runs/${runId}/events` } }),
  });
  let release!: () => void;
  let queued = false, answered = false;
  const gate = new Promise<void>(resolve => { release = resolve; });
  await page.route("**/api/v1/ai/runs/*/events", async route => {
    queued = true;
    await gate;
    await route.fulfill({ contentType: "text/event-stream", body: 'data: {"version":"ai-events-v1","seq":"1","type":"final","data":{"text":"LATE-SSE-PRIVATE","cards":[]}}\n\n' }).catch(() => undefined);
    answered = true;
  });
  await page.goto("/#/assistants/may");
  await page.getByRole("textbox", { name: "Tin nhắn cho Mây" }).fill("PRIVATE-DRAFT");
  await page.getByRole("button", { name: "Gửi tin cho AI", exact: true }).click();
  await expect.poll(() => queued).toBe(true);
  await page.clock.fastForward(11 * MINUTE);
  await expect(endedHeading(page)).toBeFocused();
  release();
  await expect.poll(() => answered).toBe(true);
  await expect(page.getByText("LATE-SSE-PRIVATE")).toHaveCount(0);
  await expect(page.getByText("PRIVATE-DRAFT")).toHaveCount(0);
});

test("moving the device clock forward only reads the server's verdict, it does not end a live trial", async ({ page }) => {
  await page.clock.install();
  const calls = await trial(page, 60 * MINUTE);
  await page.goto("/#/assistants");
  await expect(page.getByTestId("guest-status")).toContainText("còn 1 giờ");
  await page.clock.setSystemTime(new Date(Date.now() + 3 * 60 * MINUTE));
  await page.clock.fastForward(MINUTE);
  await expect(page.getByTestId("guest-status")).toContainText(/còn (59|58) phút/);
  await expect(endedHeading(page)).toHaveCount(0);
  expect(calls.filter((call) => call.startsWith("POST"))).toEqual([]);
});

test("a server GUEST_EXPIRED answer ends the trial even before the local timer", async ({ page }) => {
  await trial(page, 60 * MINUTE, { "/bots": () => failure(401, "GUEST_EXPIRED", "Lượt dùng thử đã kết thúc.") });
  await page.goto("/#/assistants");
  await expect(endedHeading(page)).toBeVisible();
  await expect(page.getByRole("heading", { name: "Chào bạn trở lại" })).toHaveCount(0);
});

test("opening the app after expiry shows only the content-free end screen", async ({ page }) => {
  const calls = await trial(page, 60 * MINUTE, {
    "/session": () => failure(401, "GUEST_EXPIRED", "Lượt dùng thử đã kết thúc."),
  });
  await page.goto("/#/assistants");
  await expect(endedHeading(page)).toBeVisible();
  await page.waitForTimeout(300);
  expect(calls.filter((call) => call !== "GET /session")).toEqual([]);
});

test("coming back to the tab re-reads the session and notices an expiry the server enforced", async ({ page }) => {
  let expired = false;
  await trial(page, 60 * MINUTE, {
    "/session": () => (expired ? failure(401, "GUEST_EXPIRED", "Lượt dùng thử đã kết thúc.") : undefined),
  });
  await page.goto("/#/assistants");
  await expect(page.getByTestId("guest-status")).toBeVisible();
  expired = true;
  await page.evaluate(() => window.dispatchEvent(new Event("focus")));
  await expect(endedHeading(page)).toBeVisible();
});

test("multiple tabs: ending the trial in one tab ends it in the others, with no data in the signal", async ({ page }) => {
  await trial(page, 60 * MINUTE);
  const other = await page.context().newPage();
  await trial(other, 60 * MINUTE);
  await page.goto("/#/assistants");
  await other.goto("/#/assistants");
  await expect(page.getByTestId("guest-status")).toBeVisible();
  await expect(other.getByTestId("guest-status")).toBeVisible();

  await other.getByRole("button", { name: "Kết thúc và xóa lượt dùng thử" }).click();
  await other.getByRole("dialog").getByRole("button", { name: "Kết thúc và xóa", exact: true }).click();
  await expect(endedHeading(other)).toBeVisible();
  await expect(endedHeading(page)).toBeVisible();
});

test("after the end screen a new trial starts from the public page, and registering is explicit", async ({ page }) => {
  await trial(page, 60 * MINUTE, {
    "/session": () => failure(401, "GUEST_EXPIRED", "Lượt dùng thử đã kết thúc."),
    "/public/experience": () => ({
      json: {
        guestAvailable: true,
        guestUnavailableReason: null,
        feedbackAvailable: false,
        productTourAvailable: false,
        captchaSiteKey: "public-site-key",
      },
    }),
  });
  await page.goto("/#/assistants");
  await expect(endedHeading(page)).toBeVisible();
  await page.getByRole("button", { name: "Tạo tài khoản" }).click();
  await expect(endedHeading(page)).toHaveCount(0);
  await expect(page).toHaveURL(/#\/login\?mode=signup$/);

  await page.goto("/");
  await page.goto("/#/assistants");
  await expect(endedHeading(page)).toBeVisible();
  await page.getByRole("button", { name: "Bắt đầu lượt dùng thử mới" }).click();
  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByRole("heading", { name: "Bắt đầu với MoodPrint" })).toBeVisible();
});
