import { expect, test, type Page } from "@playwright/test";
import { app, guestSession, type Reply } from "./ux-fixtures";

const READY = {
  guestAvailable: true,
  guestUnavailableReason: null,
  feedbackAvailable: false,
  productTourAvailable: false,
  captchaSiteKey: "public-site-key",
};
const THIS_YEAR = new Date().getFullYear();
const failure = (status: number, code: string, message = "Không thành công."): Reply => ({
  status,
  json: { error: { code, message } },
});

// Stands in for the third-party widget: no network, deterministic one-shot tokens.
const TURNSTILE_STUB = `
(() => {
  let seq = 0;
  const widgets = new Map();
  const solve = (id) => {
    const entry = widgets.get(id);
    if (!entry) return;
    entry.solves += 1;
    entry.el.dataset.solves = String(entry.solves);
    entry.options.callback("captcha-token-" + (++seq));
  };
  window.turnstile = {
    render(el, options) {
      const id = "w" + (widgets.size + 1);
      widgets.set(id, { el, options, solves: 0 });
      setTimeout(() => solve(id), 0);
      return id;
    },
    reset(id) { setTimeout(() => solve(id), 0); },
    remove(id) { widgets.delete(id); },
  };
})();`;

type Call = { method: string; path: string; headers: Record<string, string>; body: unknown };
type GuestReply = Reply | "ok";

/** The public entry flow: readiness, anonymous /session, intent, guest creation, then the app. */
async function entry(page: Page, replies: GuestReply[], options: { guestDelayMs?: number } = {}) {
  const calls: Call[] = [];
  let created = false;
  let guestPosts = 0;
  await page.route("https://challenges.cloudflare.com/**", (route) =>
    route.fulfill({ contentType: "application/javascript", body: TURNSTILE_STUB }),
  );
  await app(page, null, {
    "/public/experience": () => ({ json: READY }),
    "/session": () =>
      created ? { json: guestSession(7_200_000 - 5_000) } : failure(401, "AUTH_REQUIRED", "Cần đăng nhập"),
    "/auth/guest-intents": (request) => (request.method() === "POST" ? { status: 204 } : undefined),
    "/auth/guest": (request) => {
      if (request.method() !== "POST") return undefined;
      const reply = replies[Math.min(guestPosts++, replies.length - 1)];
      if (reply !== "ok") return reply;
      created = true;
      return { status: 201, json: guestSession(7_200_000 - 5_000) };
    },
  });
  // Registered last, so it sees every request first and then hands it to the fixture above.
  await page.route("**/api/v1/**", async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname.replace("/api/v1", "");
    const raw = request.postData();
    calls.push({ method: request.method(), path, headers: request.headers(), body: raw ? JSON.parse(raw) : null });
    if (path === "/auth/guest" && options.guestDelayMs)
      await new Promise((resolve) => setTimeout(resolve, options.guestDelayMs));
    return route.fallback();
  });
  return calls;
}

const posts = (calls: Call[], path: string) =>
  calls.filter((call) => call.method === "POST" && call.path === path);

async function openEntry(page: Page) {
  await page.goto("/");
  const start = page.getByRole("button", { name: "Dùng thử 2 giờ" }).first();
  await expect(start).toBeEnabled();
  await start.click();
  await expect(page.getByRole("dialog", { name: "Dùng thử 2 giờ, không cần email" })).toBeVisible();
  await expect(page.locator("[data-solves='1']")).toBeAttached();
}

async function fillEligible(page: Page, year = THIS_YEAR - 25) {
  await page.getByLabel("Năm sinh").fill(String(year));
  await page.getByLabel("Tôi xác nhận mình từ 16 tuổi trở lên.").check();
}

const submit = (page: Page) => page.getByRole("button", { name: /Bắt đầu dùng thử|Thử lại/ });

test("under 16 is stopped on the device: no intent, no identity request", async ({ page }) => {
  const calls = await entry(page, ["ok"]);
  await openEntry(page);
  await fillEligible(page, THIS_YEAR - 12);
  await submit(page).click();
  await expect(page.getByText("MoodPrint hiện dành cho người từ 16 tuổi.")).toBeVisible();
  expect(calls.filter((call) => call.method !== "GET")).toEqual([]);
});

test("an unconfirmed age attestation also never reaches the network", async ({ page }) => {
  const calls = await entry(page, ["ok"]);
  await openEntry(page);
  await page.getByLabel("Năm sinh").fill(String(THIS_YEAR - 30));
  await submit(page).click();
  await expect(page.getByText("MoodPrint hiện dành cho người từ 16 tuổi.")).toBeVisible();
  expect(calls.filter((call) => call.method !== "GET")).toEqual([]);
});

test("the 18th-birthday attestation appears only at the exact boundary year", async ({ page }) => {
  await entry(page, ["ok"]);
  await openEntry(page);
  const adult = page.getByLabel("Tôi đã đủ 18 tuổi (chỉ cần khi tạo tài khoản sau này).");
  await page.getByLabel("Năm sinh").fill(String(THIS_YEAR - 18));
  await expect(adult).toBeVisible();
  await page.getByLabel("Năm sinh").fill(String(THIS_YEAR - 25));
  await expect(adult).toHaveCount(0);
});

test("a started trial opens the app with the countdown and stores no secret", async ({ page }) => {
  const calls = await entry(page, ["ok"]);
  await openEntry(page);
  await fillEligible(page);
  await submit(page).click();
  await expect(page.getByTestId("guest-status")).toContainText("Đang dùng thử · còn 2 giờ");
  await expect(page).toHaveURL(/#\/assistants$/);

  expect(posts(calls, "/auth/guest-intents")).toHaveLength(1);
  const [guest] = posts(calls, "/auth/guest");
  expect(guest.body).toMatchObject({
    disclosureVersion: "guest-v1",
    eligibility: { birthYear: THIS_YEAR - 25, confirmedMinimumAge: true, confirmedAdultAge: false },
  });
  expect(guest.headers["x-guest-intent"]).toBe("1");
  expect(guest.headers["idempotency-key"]).toMatch(/^[0-9a-f-]{36}$/);

  const stored = await page.evaluate(() =>
    JSON.stringify({ local: { ...localStorage }, session: { ...sessionStorage } }),
  );
  expect(stored).not.toContain("captcha-token");
  expect(stored).not.toContain("csrf");
  expect(stored).not.toContain("moodprint.guestAttempt");
});

test("a failed attempt retries with the same key and creates no second intent", async ({ page }) => {
  const calls = await entry(page, [failure(503, "SERVICE_UNAVAILABLE", "Tạm thời chưa thể xử lý."), "ok"]);
  await openEntry(page);
  await fillEligible(page);
  await submit(page).click();
  await expect(page.getByRole("button", { name: "Bắt đầu dùng thử" })).toBeEnabled();
  await submit(page).click();
  await expect(page.getByTestId("guest-status")).toBeVisible();

  expect(posts(calls, "/auth/guest-intents")).toHaveLength(1);
  const attempts = posts(calls, "/auth/guest");
  expect(attempts).toHaveLength(2);
  expect(attempts[0].headers["idempotency-key"]).toBeTruthy();
  expect(attempts[1].headers["idempotency-key"]).toBe(attempts[0].headers["idempotency-key"]);
  expect(attempts[1].body).toEqual(attempts[0].body);
});

test("an unknown outcome is explained and resumed with the same request, never a new identity", async ({ page }) => {
  const calls = await entry(page, [
    failure(409, "GUEST_ATTEMPT_PENDING", "Yêu cầu trước vẫn đang được xử lý."),
    "ok",
  ]);
  await openEntry(page);
  await fillEligible(page);
  await submit(page).click();
  await expect(page.getByText("Đang xử lý lượt dùng thử của bạn.")).toBeVisible();
  await page.getByRole("button", { name: "Thử lại" }).click();
  await expect(page.getByTestId("guest-status")).toBeVisible();

  expect(posts(calls, "/auth/guest-intents")).toHaveLength(1);
  const attempts = posts(calls, "/auth/guest");
  expect(attempts.map((call) => call.headers["idempotency-key"])).toHaveLength(2);
  expect(attempts[1].headers["idempotency-key"]).toBe(attempts[0].headers["idempotency-key"]);
});

test("a definitive rejection needs a fresh challenge token, a fresh key and a fresh intent", async ({ page }) => {
  const calls = await entry(page, [failure(422, "CAPTCHA_FAILED", "Bước kiểm tra chưa hợp lệ."), "ok"]);
  await openEntry(page);
  await fillEligible(page);
  await expect(page.locator('script[src^="https://challenges.cloudflare.com/turnstile/"]')).toHaveCount(1);
  await submit(page).click();
  await expect(page.getByText("Bước kiểm tra chưa hợp lệ.")).toBeVisible();
  await expect(page.locator("[data-solves='2']")).toBeAttached();
  await submit(page).click();
  await expect(page.getByTestId("guest-status")).toBeVisible();

  const attempts = posts(calls, "/auth/guest");
  expect(attempts).toHaveLength(2);
  expect(attempts[1].headers["idempotency-key"]).not.toBe(attempts[0].headers["idempotency-key"]);
  expect((attempts[1].body as { captchaToken: string }).captchaToken).not.toBe(
    (attempts[0].body as { captchaToken: string }).captchaToken,
  );
  expect(posts(calls, "/auth/guest-intents")).toHaveLength(2);
});

test("a double click makes exactly one intent and one creation request", async ({ page }) => {
  const calls = await entry(page, ["ok"], { guestDelayMs: 400 });
  await openEntry(page);
  await fillEligible(page);
  await submit(page).dblclick();
  await expect(page.getByTestId("guest-status")).toBeVisible();
  expect(posts(calls, "/auth/guest-intents")).toHaveLength(1);
  expect(posts(calls, "/auth/guest")).toHaveLength(1);
});

test("the dialog can be dismissed without creating anything", async ({ page }) => {
  const calls = await entry(page, ["ok"]);
  await openEntry(page);
  await page.getByRole("button", { name: "Để sau" }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  expect(calls.filter((call) => call.method !== "GET")).toEqual([]);
});

test("guest settings ends a trial only after explicit confirmation", async ({ page }) => {
  const calls: string[] = [];
  await app(page, guestSession(7_000_000), {
    "/auth/guest/end": request => { calls.push(request.method()); return { status: 204 }; },
  });
  await page.goto("/#/settings");
  await expect(page.getByRole("button", { name: "Đăng xuất", exact: true })).toHaveCount(0);
  await page.getByRole("region", { name: "Phiên đăng nhập" }).getByRole("button", { name: "Kết thúc lượt dùng thử", exact: true }).click();
  await expect(page.getByRole("dialog", { name: "Kết thúc và xóa lượt dùng thử?", exact: true })).toBeVisible();
  expect(calls).toEqual([]);
  await page.getByRole("button", { name: "Giữ lượt dùng thử" }).click();
  await expect(page.getByTestId("guest-status")).toBeVisible();
  expect(calls).toEqual([]);
});

test("failed end is reported and never claims deletion was accepted", async ({ page }) => {
  let ended = false;
  await app(page, guestSession(7_000_000), {
    "/auth/guest/end": () => ended ? { status: 204 } : failure(503, "GUEST_END_UNAVAILABLE", "Chưa thể kết thúc lượt dùng thử."),
  });
  await page.goto("/#/assistants");
  await page.getByTestId("guest-status").getByRole("button", { name: "Kết thúc và xóa lượt dùng thử" }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Kết thúc và xóa", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("Chưa thể kết thúc lượt dùng thử.");
  await expect(page.getByRole("heading", { name: "Lượt dùng thử đã kết thúc" })).toHaveCount(0);
  await expect(page.getByTestId("guest-status")).toBeVisible();
  ended = true;
  await page.getByRole("dialog").getByRole("button", { name: "Kết thúc và xóa", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Lượt dùng thử đã kết thúc" })).toBeVisible();
});

test.describe("inside a trial", () => {
  async function inTrial(page: Page, hash: string) {
    const calls: Call[] = [];
    await app(page, guestSession(3_600_000), {
      "/auth/guest/end": (request) => (request.method() === "POST" ? { status: 204 } : undefined),
    });
    await page.route("**/api/v1/**", (route) => {
      const request = route.request();
      calls.push({
        method: request.method(),
        path: new URL(request.url()).pathname.replace("/api/v1", ""),
        headers: request.headers(),
        body: null,
      });
      return route.fallback();
    });
    await page.goto(hash);
    return calls;
  }

  test("people-matching and messaging are explained without any social request", async ({ page }) => {
    const calls = await inTrial(page, "/#/connect");
    await expect(page.getByText("Tạo tài khoản để tìm bạn và nhắn tin.")).toBeVisible();
    for (const hash of ["/#/messages", "/#/connect"]) {
      await page.goto(hash);
      await page.reload();
      await expect(page.getByText("Tạo tài khoản để tìm bạn và nhắn tin.")).toBeVisible();
    }
    const social = calls.filter((call) =>
      /^\/(social|connections?|connection-requests|proposals|activities|profiles\/published)/.test(call.path),
    );
    expect(social).toEqual([]);
  });

  test("ending the trial asks first, then clears the private tree", async ({ page }) => {
    const calls = await inTrial(page, "/#/assistants");
    await page.getByRole("button", { name: "Kết thúc và xóa lượt dùng thử" }).click();
    const dialog = page.getByRole("dialog", { name: "Kết thúc và xóa lượt dùng thử?" });
    await dialog.getByRole("button", { name: "Giữ lượt dùng thử" }).click();
    await expect(dialog).toHaveCount(0);
    expect(posts(calls, "/auth/guest/end")).toHaveLength(0);

    await page.getByRole("button", { name: "Kết thúc và xóa lượt dùng thử" }).click();
    await page.getByRole("dialog").getByRole("button", { name: "Kết thúc và xóa", exact: true }).click();
    await expect(page.getByRole("heading", { name: "Lượt dùng thử đã kết thúc" })).toBeFocused();
    expect(posts(calls, "/auth/guest/end")).toHaveLength(1);
    await expect(page.getByTestId("guest-status")).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Bắt đầu lượt dùng thử mới" })).toBeVisible();
  });
});
