import { test, expect, type Page } from "@playwright/test";

const session = {
  userId: "11111111-1111-4111-8111-111111111111",
  alias: "An",
  ageBand: "adult",
  eligible: true,
  csrfToken: "csrf-session-test",
  timezone: "Asia/Bangkok",
  serverTime: "2026-10-23T08:00:00Z",
  features: { ai: true, matching: false, voice: false },
  consents: Object.fromEntries(
    ["AI", "MEM", "MATCH", "VOICE"].map((purpose) => [
      purpose,
      { enabled: purpose === "AI", version: 1, policyVersion: "v1" },
    ]),
  ),
};
const bot = {
  botId: "may",
  name: "Mây",
  role: "Lắng nghe & tâm sự",
  description: "Một khoảng nhỏ để được lắng nghe.",
  starters: ["Hôm nay mình hơi mệt"],
  avatarKey: "may",
};
const conversation = {
  conversationId: "22222222-2222-4222-8222-222222222222",
  botId: "may",
  version: 1,
  expiresAt: "2026-10-24T08:00:00Z",
  messages: [],
  activeRunId: null,
  activeRunVersion: null,
};

async function api(page: Page, authenticated = true) {
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === "/api/v1/session")
      return route.fulfill({
        status: authenticated ? 200 : 401,
        json: authenticated
          ? session
          : {
              error: { code: "AUTH_REQUIRED", message: "Vui lòng đăng nhập." },
            },
      });
    if (path === "/api/v1/bots") return route.fulfill({ json: [bot] });
    if (path === "/api/v1/ai/preferences") return route.fulfill({ json: { historyEnabled: false, semanticMemoryEnabled: false, version: 1, policyVersion: "ai-data-v1", retentionDays: 30, historyAvailable: true, semanticMemoryAvailable: false } });
    if (path === "/api/v1/ai/conversations")
      return route.fulfill({
        json: route.request().method() === "GET" ? [] : conversation,
      });
    if (path === `/api/v1/ai/conversations/${conversation.conversationId}`)
      return route.fulfill({ json: conversation });
    if (path === "/api/v1/moods") return route.fulfill({ json: [] });
    if (path === "/api/v1/moods/summary")
      return route.fulfill({
        json: { from: "2026-10-17", to: "2026-10-23", count: 0, mean: null, min: null, max: null, insightAvailable: false, buckets: [] },
      });
    if (path === "/api/v1/profiles/private-items")
      return route.fulfill({ json: [] });
    if (path === "/api/v1/users/me/identity")
      return route.fulfill({ json: [] });
    return route.fulfill({
      status: 503,
      json: {
        error: {
          code: "UNAVAILABLE",
          message: "Chưa thể kết nối. Vui lòng thử lại.",
        },
      },
    });
  });
}

async function scopedNhip(page: Page, submitted: any[], fail = false) {
  await api(page);
  await page.route("**/api/v1/bots", route => route.fulfill({ json: [{ ...bot, botId: "nhip", name: "Nhịp", avatarKey: "nhip" }] }));
  await page.route("**/api/v1/ai/conversations", route => route.fulfill({ json: route.request().method() === "GET" ? [] : { ...conversation, botId: "nhip" } }));
  let version = 1;
  await page.route(`**/api/v1/ai/conversations/${conversation.conversationId}`, route => route.fulfill({ json: { ...conversation, botId: "nhip", version } }));
  await page.route(`**/api/v1/ai/conversations/${conversation.conversationId}/messages`, route => {
    submitted.push(route.request().postDataJSON());
    if (fail) return route.fulfill({ status: 503, json: { error: { code: "UNAVAILABLE", message: "Chưa gửi được. Thử lại nhé." } } });
    version += 2;
    return route.fulfill({ status: 202, json: { runId: "33333333-3333-4333-8333-333333333333", conversationId: conversation.conversationId, version: version - 1, runVersion: 1, eventsUrl: "/api/v1/ai/runs/33333333-3333-4333-8333-333333333333/events" } });
  });
  await page.route("**/api/v1/ai/runs/*/events", route => route.fulfill({ contentType: "text/event-stream", body: [
    { version: "ai-events-v1", seq: "1", type: "final", data: { text: "Đã phản hồi.", cards: [] } },
    { version: "ai-events-v1", seq: "2", type: "completed", data: {} },
  ].map(event => `id: ${event.seq}\ndata: ${JSON.stringify(event)}\n\n`).join("") }));
  await page.goto("/#/assistants/nhip");
  await page.getByText("Chia sẻ thống kê tâm trạng cho lượt này", { exact: true }).click();
}

test("Nhịp requires an explicit valid mood range and consumes permission after one accepted turn", async ({ page }) => {
  const submitted: any[] = [];
  await scopedNhip(page, submitted);
  await page.getByRole("checkbox", { name: "Cho Nhịp xem thống kê trong khoảng ngày đã chọn", exact: true }).check();
  await page.getByLabel("Thống kê từ ngày", { exact: true }).fill("2026-10-02");
  await page.getByLabel("Thống kê đến ngày", { exact: true }).fill("2026-10-01");
  await page.getByRole("textbox", { name: "Tin nhắn cho Nhịp" }).fill("Nhìn lại những ngày mình chọn");
  await expect(page.getByRole("button", { name: "Gửi tin cho AI", exact: true })).toBeDisabled();
  await page.getByRole("textbox", { name: "Tin nhắn cho Nhịp" }).press("Enter");
  expect(submitted).toHaveLength(0);
  await page.getByLabel("Thống kê từ ngày", { exact: true }).fill("2026-10-01");
  await page.getByLabel("Thống kê đến ngày", { exact: true }).fill("2026-10-02");
  await page.getByRole("button", { name: "Gửi tin cho AI", exact: true }).click();
  await expect.poll(() => submitted.length).toBe(1);
  expect(submitted[0].moodScope).toEqual({ fromDate: "2026-10-01", toDate: "2026-10-02" });
  await expect(page.getByRole("checkbox", { name: "Cho Nhịp xem thống kê trong khoảng ngày đã chọn", exact: true })).not.toBeChecked();
  await page.getByRole("textbox", { name: "Tin nhắn cho Nhịp" }).fill("Một lượt trò chuyện riêng");
  await page.getByRole("button", { name: "Gửi tin cho AI", exact: true }).click();
  await expect.poll(() => submitted.length).toBe(2);
  expect(submitted[1].moodScope).toBeUndefined();
  expect(submitted[1].clientMessageId).not.toBe(submitted[0].clientMessageId);
});

test("Nhịp retries preserve the exact range intent and changing dates creates a new intent", async ({ page }) => {
  const submitted: any[] = [];
  await scopedNhip(page, submitted, true);
  await page.getByRole("checkbox", { name: "Cho Nhịp xem thống kê trong khoảng ngày đã chọn", exact: true }).check();
  await page.getByLabel("Thống kê từ ngày", { exact: true }).fill("2026-10-01");
  await page.getByLabel("Thống kê đến ngày", { exact: true }).fill("2026-10-02");
  await page.getByRole("textbox", { name: "Tin nhắn cho Nhịp" }).fill("Cùng một lời nhắn");
  const send = page.getByRole("button", { name: "Gửi tin cho AI", exact: true });
  await send.click(); await expect.poll(() => submitted.length).toBe(1); await expect(send).toBeEnabled();
  await send.click(); await expect.poll(() => submitted.length).toBe(2); await expect(send).toBeEnabled();
  expect(submitted[1].clientMessageId).toBe(submitted[0].clientMessageId);
  expect(submitted[1].moodScope).toEqual(submitted[0].moodScope);
  await page.getByLabel("Thống kê đến ngày", { exact: true }).fill("2026-10-03");
  await send.click(); await expect.poll(() => submitted.length).toBe(3);
  expect(submitted[2].clientMessageId).not.toBe(submitted[1].clientMessageId);
  expect(submitted[2].moodScope).toEqual({ fromDate: "2026-10-01", toDate: "2026-10-03" });
  await expect(page.getByRole("textbox", { name: "Tin nhắn cho Nhịp" })).toHaveValue("Cùng một lời nhắn");
});

for (const width of [1280, 390]) {
  test(`Nhịp explicitly re-shares the previous range with keyboard at width ${width}`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    const submitted: any[] = [];
    const errors: string[] = [];
    page.on("pageerror", error => errors.push(error.message));
    await scopedNhip(page, submitted);
    await page.getByRole("checkbox", { name: "Cho Nhịp xem thống kê trong khoảng ngày đã chọn", exact: true }).check();
    await page.getByLabel("Thống kê từ ngày", { exact: true }).fill("2026-10-01");
    await page.getByLabel("Thống kê đến ngày", { exact: true }).fill("2026-10-02");
    const input = page.getByRole("textbox", { name: "Tin nhắn cho Nhịp" });
    await input.fill("Nhìn lại tuần");
    await page.getByRole("button", { name: "Gửi tin cho AI", exact: true }).click();
    const reshare = page.getByRole("button", { name: "Chia sẻ lại 2026-10-01 – 2026-10-02 cho lượt tiếp", exact: true });
    await expect(reshare).toBeEnabled();
    await reshare.focus();
    await page.keyboard.press("Enter");
    await expect(page.getByRole("checkbox", { name: "Cho Nhịp xem thống kê trong khoảng ngày đã chọn", exact: true })).toBeChecked();
    await expect(page.getByRole("status").filter({ hasText: "Nhịp chỉ đọc khi bạn gửi tin nhắn" })).toBeVisible();
    expect(submitted).toHaveLength(1);
    await input.fill("Bạn cứ nhận xét đi");
    await page.getByRole("button", { name: "Gửi tin cho AI", exact: true }).click();
    await expect.poll(() => submitted.length).toBe(2);
    expect(submitted[1].moodScope).toEqual(submitted[0].moodScope);
    await expect(page.getByRole("checkbox", { name: "Cho Nhịp xem thống kê trong khoảng ngày đã chọn", exact: true })).not.toBeChecked();
    expect(errors).toEqual([]);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  });
}

test("terminal AI failure restores text without regranting the consumed mood scope", async ({ page }) => {
  const submitted: any[] = [];
  await scopedNhip(page, submitted);
  await page.route("**/api/v1/ai/runs/*/events", route => route.fulfill({ contentType: "text/event-stream", body:
    `data: ${JSON.stringify({ version: "ai-events-v1", seq: "1", type: "failed", data: {} })}\n\n` }));
  const input = page.getByRole("textbox", { name: "Tin nhắn cho Nhịp" });
  await input.fill("Một lời nhắn cần thử lại");
  await page.getByRole("button", { name: "Gửi tin cho AI", exact: true }).click();
  await expect(page.getByRole("alert")).toBeVisible();
  await expect(input).toHaveValue("Một lời nhắn cần thử lại");
  await expect(page.getByRole("checkbox", { name: "Cho Nhịp xem thống kê trong khoảng ngày đã chọn", exact: true })).not.toBeChecked();
  expect(submitted).toHaveLength(1);
});

test("login failure retains credentials and never opens a sample session", async ({
  page,
}) => {
  await api(page, false);
  await page.goto("/");
  await page.getByLabel("Email", { exact: true }).fill("an@example.test");
  await page.getByLabel("Mật khẩu", { exact: true }).fill("private-passphrase");
  await page.getByRole("button", { name: "Đăng nhập", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("Chưa thể kết nối");
  await expect(page.getByLabel("Email", { exact: true })).toHaveValue(
    "an@example.test",
  );
  await expect(page.getByLabel("Mật khẩu", { exact: true })).toHaveValue(
    "private-passphrase",
  );
  await expect(
    page.getByRole("heading", { name: /Bạn muốn chia sẻ điều gì/ }),
  ).toHaveCount(0);
});

test("year onboarding requires confirmation and server success, retaining input after failure", async ({
  page,
}) => {
  await api(page);
  let updated = false;
  let attempts = 0;
  let release!: () => void;
  const receipt = new Promise<void>((resolve) => {
    release = resolve;
  });
  await page.route("**/api/v1/session", (route) =>
    route.fulfill({
      json: updated
        ? { ...session, birthYear: 2007, eligibilityVersion: 1 }
        : {
            ...session,
            ageBand: "unknown",
            eligible: false,
            birthYear: null,
            eligibilityVersion: 0,
          },
    }),
  );
  await page.route("**/api/v1/users/me/eligibility", async (route) => {
    const body = route.request().postDataJSON();
    expect(body.birthYear).toBe(2007);
    expect(body.confirmedMinimumAge).toBe(true);
    expect(body).not.toHaveProperty("ageBand");
    expect(route.request().headers()["x-csrf-token"]).toBe(session.csrfToken);
    if (++attempts === 1)
      return route.fulfill({
        status: 503,
        json: {
          error: {
            code: "UNAVAILABLE",
            message: "Chưa thể xác nhận. Vui lòng thử lại.",
            retryable: true,
          },
        },
      });
    await receipt;
    updated = true;
    return route.fulfill({
      json: { ...session, birthYear: 2007, eligibilityVersion: 1 },
    });
  });
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Xác nhận độ tuổi" }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Xác nhận và tiếp tục", exact: true }),
  ).toBeDisabled();
  await page.getByLabel("Năm sinh", { exact: true }).fill("2007");
  await page
    .getByRole("checkbox", {
      name: "Tôi xác nhận mình đã đủ 16 tuổi.",
      exact: true,
    })
    .check();
  await expect(page.getByRole("textbox", { name: /Tin nhắn/ })).toHaveCount(0);
  await page
    .getByRole("button", { name: "Xác nhận và tiếp tục", exact: true })
    .click();
  await expect(page.getByRole("alert")).toContainText("Chưa thể xác nhận");
  await expect(page.getByLabel("Năm sinh", { exact: true })).toHaveValue(
    "2007",
  );
  await page
    .getByRole("button", { name: "Xác nhận và tiếp tục", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Xác nhận độ tuổi" }),
  ).toBeVisible();
  release();
  await expect(
    page.getByRole("heading", { name: /Bạn muốn chia sẻ điều gì/ }),
  ).toBeVisible();
});

test("an unavailable session remains an explicit error until retry succeeds", async ({
  page,
}) => {
  await api(page);
  let available = false;
  await page.route("**/api/v1/session", (route) =>
    route.fulfill(
      available
        ? { json: session }
        : {
            status: 503,
            json: {
              error: {
                code: "SERVICE_UNAVAILABLE",
                message: "Dịch vụ chưa sẵn sàng. Vui lòng thử lại.",
              },
            },
          },
    ),
  );
  await page.goto("/");
  await expect(page.getByRole("alert")).toContainText("Dịch vụ chưa sẵn sàng");
  await expect(
    page.getByRole("heading", { name: /Bạn muốn chia sẻ điều gì/ }),
  ).toHaveCount(0);
  available = true;
  await page.getByRole("button", { name: "Thử lại", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: /Bạn muốn chia sẻ điều gì/ }),
  ).toBeVisible();
});

test("consent changes wait for the server receipt and include session protection", async ({
  page,
}) => {
  await api(page);
  await page.route("**/api/v1/consents/AI", async (route) => {
    const request = route.request();
    expect(request.headers()["x-csrf-token"]).toBe("csrf-session-test");
    expect(request.headers()["idempotency-key"]).toBeTruthy();
    expect(request.postDataJSON()).toEqual({
      enabled: false,
      expectedVersion: 1,
      policyVersion: "v1",
    });
    await route.fulfill({
      json: {
        ...session,
        consents: {
          ...session.consents,
          AI: { enabled: false, version: 2, policyVersion: "v1" },
        },
      },
    });
  });
  await page.goto("/#/settings");
  await page
    .getByRole("button", { name: "Rút quyền trò chuyện AI", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Rút quyền trò chuyện AI", exact: true }),
  ).toHaveCount(0);
});

test("failed AI requests preserve the draft without creating a fake reply", async ({
  page,
}) => {
  await api(page);
  await page.goto("/#/assistants/may");
  const draft = page.getByRole("textbox", { name: "Tin nhắn cho Mây" });
  await draft.fill("Hôm nay mình cần được lắng nghe");
  await page
    .getByRole("button", { name: "Gửi tin cho AI", exact: true })
    .click();
  await expect(page.getByRole("alert")).toContainText("Chưa thể kết nối");
  await expect(draft).toHaveValue("Hôm nay mình cần được lắng nghe");
  await expect(page.locator(".from-bot .chat-bubble")).toHaveCount(0);
});

test("failed conversation history blocks new sends until the history can be checked", async ({
  page,
}) => {
  await api(page);
  await page.route("**/api/v1/ai/conversations?*", (route) =>
    route.fulfill({
      status: 503,
      json: {
        error: {
          code: "UNAVAILABLE",
          message: "Chưa mở được lịch sử trò chuyện.",
        },
      },
    }),
  );
  await page.goto("/#/assistants/may");
  await expect(page.getByRole("alert").filter({ hasText: "Chưa mở được lịch sử" }).first()).toBeVisible();
  await page
    .getByRole("textbox", { name: "Tin nhắn cho Mây" })
    .fill("Giữ bản nháp này");
  await expect(
    page.getByRole("button", { name: "Gửi tin cho AI", exact: true }),
  ).toBeDisabled();
});

test("returning to the app rechecks consent and keeps chat accessible", async ({
  page,
}) => {
  await api(page);
  let allowed = true;
  await page.route("**/api/v1/session", (route) =>
    route.fulfill({
      json: {
        ...session,
        consents: {
          ...session.consents,
          AI: {
            enabled: allowed,
            version: allowed ? 1 : 2,
            policyVersion: "v1",
          },
        },
      },
    }),
  );
  await page.goto("/#/assistants/may");
  await expect(
    page.getByRole("textbox", { name: "Tin nhắn cho Mây" }),
  ).toBeVisible();
  allowed = false;
  await page.evaluate(() => window.dispatchEvent(new Event("focus")));
  await expect(
    page.getByText("Khi chọn Gửi, bạn đồng ý để dịch vụ AI xử lý tin nhắn này. Bạn có thể rút quyền trong Quyền riêng tư.", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("textbox", { name: "Tin nhắn cho Mây" }),
  ).toBeVisible();
});

test("chat grants processing only when the user sends a message", async ({ page }) => {
  await api(page);
  const calls: string[] = [];
  let granted = false;
  await page.route("**/api/v1/session", route => route.fulfill({ json: {
    ...session, consents: { ...session.consents,
      AI: { enabled: granted, version: granted ? 2 : 1, policyVersion: "v1" } },
  } }));
  await page.route("**/api/v1/consents/AI", route => {
    calls.push("consent");
    expect(route.request().postDataJSON()).toEqual({
      enabled: true, expectedVersion: 1, policyVersion: "v1",
    });
    granted = true;
    return route.fulfill({ json: { ...session, consents: { ...session.consents,
      AI: { enabled: true, version: 2, policyVersion: "v1" } } } });
  });
  await page.route("**/api/v1/ai/conversations", route => {
    if (route.request().method() === "GET") return route.fulfill({ json: [] });
    calls.push("conversation");
    return route.fulfill({ json: conversation });
  });
  await page.goto("/#/assistants/may");
  await expect(page.getByRole("textbox", { name: "Tin nhắn cho Mây" })).toBeVisible();
  expect(calls).toEqual([]);
  await page.getByRole("textbox", { name: "Tin nhắn cho Mây" }).fill("Xin chào");
  await page.getByRole("button", { name: "Gửi tin cho AI" }).click();
  await expect.poll(() => calls).toEqual(["consent", "conversation"]);
});

test("privacy controls remain readable on mobile and desktop", async ({ page }) => {
  await api(page);
  await page.route("**/api/v1/profiles/published/current", route => route.fulfill({ json: null }));
  for (const width of [390, 768, 1280]) {
    await page.setViewportSize({ width, height: 844 });
    await page.goto("/#/settings");
    await expect(page.getByRole("heading", { name: "Tin nhắn AI" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Hồ sơ và kết nối" })).toBeVisible();
    await expect(page.getByRole("checkbox", { name: "Lưu lịch sử trò chuyện" })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
  }
});

test("voice waits for a click and handles microphone denial", async ({ page }) => {
  await api(page);
  await page.addInitScript(() => {
    (window as any).__microphoneCalls = 0;
    Object.defineProperty(navigator, "mediaDevices", {
      configurable: true,
      value: { getUserMedia: async () => {
        (window as any).__microphoneCalls += 1;
        throw new DOMException("Permission denied", "NotAllowedError");
      } },
    });
  });
  await page.route("**/api/v1/session", route => route.fulfill({ json: {
    ...session, features: { ...session.features, voice: true },
  } }));
  await page.route("**/api/v1/consents/VOICE", route => route.fulfill({ json: {
    ...session, features: { ...session.features, voice: true },
    consents: { ...session.consents, VOICE: { enabled: true, version: 2, policyVersion: "v1" } },
  } }));
  await page.goto("/#/assistants/may");
  await expect(page.getByRole("button", { name: "Ghi âm tối đa 30 giây" })).toBeVisible();
  expect(await page.evaluate(() => (window as any).__microphoneCalls)).toBe(0);
  await page.getByRole("button", { name: "Ghi âm tối đa 30 giây" }).click();
  await expect.poll(() => page.evaluate(() => (window as any).__microphoneCalls)).toBe(1);
  await expect(page.getByRole("alert").first()).toBeVisible();
  await expect(page.getByRole("button", { name: "Ghi âm tối đa 30 giây" })).toBeVisible();
});

test("AI presents the validated final and rejects raw stream deltas", async ({
  page,
}) => {
  await api(page);
  await page.route(
    `**/api/v1/ai/conversations/${conversation.conversationId}`,
    (route) =>
      route.fulfill({
        json: {
          ...conversation,
          version: 3,
          messages: [
            { id: "stored-self", actor: "self", text: "Xin chào" },
            {
              id: "stored-final",
              actor: "bot",
              text: "Mình đang lắng nghe bạn.",
            },
          ],
        },
      }),
  );
  await page.route(
    `**/api/v1/ai/conversations/${conversation.conversationId}/messages`,
    (route) =>
      route.fulfill({
        status: 202,
        json: {
          runId: "33333333-3333-4333-8333-333333333333",
          conversationId: conversation.conversationId,
          version: 2,
          runVersion: 1,
          eventsUrl:
            "/api/v1/ai/runs/33333333-3333-4333-8333-333333333333/events",
        },
      }),
  );
  await page.route("**/api/v1/ai/runs/*/events", (route) =>
    route.fulfill({
      contentType: "text/event-stream",
      body: [
        {
          version: "ai-events-v1",
          seq: "1",
          type: "progress",
          data: { text: "RAW_SECRET_DELTA" },
        },
        {
          version: "ai-events-v1",
          seq: "2",
          type: "final",
          data: { text: "Mình đang lắng nghe bạn.", cards: [] },
        },
        { version: "ai-events-v1", seq: "3", type: "completed", data: {} },
      ]
        .map((event) => `id: ${event.seq}\ndata: ${JSON.stringify(event)}\n\n`)
        .join(""),
    }),
  );
  await page.goto("/#/assistants/may");
  await page
    .getByRole("textbox", { name: "Tin nhắn cho Mây" })
    .fill("Xin chào");
  await page
    .getByRole("button", { name: "Gửi tin cho AI", exact: true })
    .click();
  await expect(page.locator(".from-bot .chat-bubble")).toHaveText(
    "Mình đang lắng nghe bạn.",
  );
  await expect(page.getByText("RAW_SECRET_DELTA")).toHaveCount(0);
});

test("bot Markdown renders emphasis and lists without HTML, active links or remote images", async ({ page }) => {
  await api(page);
  const text = "**Một bước nhỏ**\n\n- Mở sổ\n- Vẽ một nét\n\n[Liên kết](https://example.test)\n\n![Ảnh](https://example.test/pixel.png)\n\n<script>window.syntheticLeak = true</script>";
  await page.route("**/api/v1/ai/conversations", route => route.fulfill({ json: [conversation] }));
  await page.route(`**/api/v1/ai/conversations/${conversation.conversationId}`, route => route.fulfill({ json: { ...conversation, messages: [{ id: "synthetic-markdown", actor: "bot", text, cards: [] }] } }));
  await page.goto(`/#/assistants/may?conversation=${conversation.conversationId}`);
  const bubble = page.locator(".from-bot .chat-bubble");
  await expect(bubble.locator("strong")).toHaveText("Một bước nhỏ");
  await expect(bubble.getByRole("listitem")).toHaveCount(2);
  await expect(bubble.locator("a, img, script")).toHaveCount(0);
  expect(await page.evaluate(() => "syntheticLeak" in window)).toBe(false);
});

test("the next AI send uses the version persisted after final completion", async ({
  page,
}) => {
  await api(page);
  const versions: number[] = [];
  await page.route(
    `**/api/v1/ai/conversations/${conversation.conversationId}`,
    (route) =>
      route.fulfill({
        json: {
          ...conversation,
          version: 3,
          messages: [
            { id: "stored-self", actor: "self", text: "Xin chào" },
            {
              id: "stored-final",
              actor: "bot",
              text: "Mình đang lắng nghe bạn.",
            },
          ],
        },
      }),
  );
  await page.route(
    `**/api/v1/ai/conversations/${conversation.conversationId}/messages`,
    async (route) => {
      versions.push(route.request().postDataJSON().expectedConversationVersion);
      await route.fulfill(
        versions.length === 1
          ? {
              status: 202,
              json: {
                runId: "33333333-3333-4333-8333-333333333333",
                conversationId: conversation.conversationId,
                version: 2,
                runVersion: 1,
                eventsUrl:
                  "/api/v1/ai/runs/33333333-3333-4333-8333-333333333333/events",
              },
            }
          : {
              status: 503,
              json: { error: { code: "UNAVAILABLE", message: "Thử lại sau." } },
            },
      );
    },
  );
  await page.route("**/api/v1/ai/runs/*/events", (route) =>
    route.fulfill({
      contentType: "text/event-stream",
      body: 'data: {"version":"ai-events-v1","seq":"1","type":"final","data":{"text":"Mình đang lắng nghe bạn.","cards":[]}}\n\ndata: {"version":"ai-events-v1","seq":"2","type":"completed","data":{}}\n\n',
    }),
  );
  await page.goto("/#/assistants/may");
  await page
    .getByRole("textbox", { name: "Tin nhắn cho Mây" })
    .fill("Xin chào");
  await page
    .getByRole("button", { name: "Gửi tin cho AI", exact: true })
    .click();
  await expect(page.locator(".from-bot .chat-bubble")).toHaveText(
    "Mình đang lắng nghe bạn.",
  );
  await page
    .getByRole("textbox", { name: "Tin nhắn cho Mây" })
    .fill("Mình muốn kể thêm");
  await page
    .getByRole("button", { name: "Gửi tin cho AI", exact: true })
    .click();
  await expect.poll(() => versions).toEqual([1, 3]);
});

test("an invalid AI final fails visibly without rendering provider JSON", async ({
  page,
}) => {
  await api(page);
  await page.route(
    `**/api/v1/ai/conversations/${conversation.conversationId}/messages`,
    (route) =>
      route.fulfill({
        status: 202,
        json: {
          runId: "33333333-3333-4333-8333-333333333333",
          conversationId: conversation.conversationId,
          version: 2,
          runVersion: 1,
          eventsUrl:
            "/api/v1/ai/runs/33333333-3333-4333-8333-333333333333/events",
        },
      }),
  );
  await page.route("**/api/v1/ai/runs/*/events", (route) =>
    route.fulfill({
      contentType: "text/event-stream",
      body: 'data: {"version":"ai-events-v1","seq":"1","type":"final","data":{"raw":"PROVIDER_JSON_SECRET"}}\n\n',
    }),
  );
  await page.goto("/#/assistants/may");
  await page
    .getByRole("textbox", { name: "Tin nhắn cho Mây" })
    .fill("Xin chào");
  await page
    .getByRole("button", { name: "Gửi tin cho AI", exact: true })
    .click();
  await expect(page.getByRole("alert")).toBeVisible();
  await expect(page.locator(".from-bot .chat-bubble")).toHaveCount(0);
  await expect(page.getByText("PROVIDER_JSON_SECRET")).toHaveCount(0);
});

test("failed private profile writes retain the entry without a success receipt", async ({
  page,
}) => {
  await api(page);
  await page.route("**/api/v1/profiles/private-items", (route) =>
    route.fulfill(
      route.request().method() === "GET"
        ? { json: [] }
        : {
            status: 503,
            json: {
              error: {
                code: "UNAVAILABLE",
                message: "Chưa lưu được mục này. Vui lòng thử lại.",
              },
            },
          },
    ),
  );
  await page.goto("/#/profile");
  await page
    .getByRole("textbox", { name: "Điều bạn muốn ghi lại" })
    .fill("Mình thích đọc sách");
  await page
    .getByRole("button", { name: "Lưu vào hồ sơ riêng", exact: true })
    .click();
  await expect(page.getByRole("alert")).toContainText("Chưa lưu được mục này");
  await expect(
    page.getByRole("textbox", { name: "Điều bạn muốn ghi lại" }),
  ).toHaveValue("Mình thích đọc sách");
  await expect(page.getByRole("button", { name: /Xóa mục/ })).toHaveCount(0);
});

test("a saved mood reloads from the API while a failed edit keeps its note", async ({
  page,
}) => {
  await api(page);
  const date = "2026-10-23";
  const saved = {
    id: "44444444-4444-4444-8444-444444444444",
    localDate: date,
    value: 4,
    note: "Một ngày nhẹ nhàng",
    timezone: "Asia/Bangkok",
    version: 1,
  };
  await page.route("**/api/v1/moods", (route) =>
    route.fulfill({ json: [saved] }),
  );
  await page.goto("/#/self");
  await expect(
    page.locator("article").getByText("Một ngày nhẹ nhàng", { exact: true }),
  ).toBeVisible();
  await page.reload();
  await expect(
    page.locator("article").getByText("Một ngày nhẹ nhàng", { exact: true }),
  ).toBeVisible();
  await page.getByLabel("Ngày", { exact: true }).fill(date);
  await expect(page.getByLabel("Ghi chú", { exact: true })).toHaveValue(
    "Một ngày nhẹ nhàng",
  );
  await page
    .getByLabel("Ghi chú", { exact: true })
    .fill("Bản nháp cần giữ lại");
  await page
    .getByRole("button", { name: "Cập nhật tâm trạng", exact: true })
    .click();
  await expect(page.getByRole("alert")).toContainText("Chưa thể kết nối");
  await expect(page.getByLabel("Ghi chú", { exact: true })).toHaveValue(
    "Bản nháp cần giữ lại",
  );
});

test("validated AI cards navigate to existing tools without claiming a saved action", async ({
  page,
}) => {
  await api(page);
  await page.route(
    `**/api/v1/ai/conversations/${conversation.conversationId}`,
    (route) =>
      route.fulfill({
        json: {
          ...conversation,
          version: 3,
          messages: [
            {
              id: "stored-final",
              actor: "bot",
              text: "Bạn có thể ghi cảm xúc hôm nay.",
              cards: [
                { kind: "mood_form" },
                { kind: "navigate_bot", botId: "guong" },
                { kind: "discovery" },
              ],
            },
          ],
        },
      }),
  );
  await page.route(
    `**/api/v1/ai/conversations/${conversation.conversationId}/messages`,
    (route) =>
      route.fulfill({
        status: 202,
        json: {
          runId: "33333333-3333-4333-8333-333333333333",
          conversationId: conversation.conversationId,
          version: 2,
          runVersion: 1,
          eventsUrl:
            "/api/v1/ai/runs/33333333-3333-4333-8333-333333333333/events",
        },
      }),
  );
  await page.route("**/api/v1/ai/runs/*/events", (route) =>
    route.fulfill({
      contentType: "text/event-stream",
      body: 'data: {"version":"ai-events-v1","seq":"1","type":"final","data":{"text":"Bạn có thể ghi cảm xúc hôm nay.","cards":[{"kind":"mood_form"},{"kind":"navigate_bot","botId":"guong"},{"kind":"discovery"}]}}\n\ndata: {"version":"ai-events-v1","seq":"2","type":"completed","data":{}}\n\n',
    }),
  );
  await page.goto("/#/assistants/may");
  await page
    .getByRole("textbox", { name: "Tin nhắn cho Mây" })
    .fill("Xin chào");
  await page
    .getByRole("button", { name: "Gửi tin cho AI", exact: true })
    .click();
  await expect(
    page
      .locator(".inline-card")
      .getByRole("link", { name: "Ghi lại cảm xúc", exact: true }),
  ).toHaveAttribute("href", "#/self");
  await expect(
    page
      .locator(".inline-card")
      .getByRole("link", { name: "Trò chuyện với Gương", exact: true }),
  ).toHaveAttribute("href", "#/assistants/guong");
  await expect(
    page
      .locator(".inline-card")
      .getByRole("link", { name: "Tìm bạn đồng điệu", exact: true }),
  ).toHaveAttribute("href", "#/connect");
  await expect(page.getByText("Đã lưu", { exact: true })).toHaveCount(0);
});

async function starterFixture(page: Page, aiEnabled: boolean) {
  await api(page);
  const writes: string[] = [];
  await page.route("**/api/v1/session", route => route.fulfill({ json: {
    ...session, consents: { ...session.consents,
      AI: { enabled: aiEnabled, version: 1, policyVersion: "v1" } },
  } }));
  page.on("request", request => {
    if (request.method() !== "GET" && request.url().includes("/api/v1/")) writes.push(`${request.method()} ${new URL(request.url()).pathname}`);
  });
  await page.goto("/#/assistants/may");
  const draft = page.getByRole("textbox", { name: "Tin nhắn cho Mây" });
  await expect(draft).toBeVisible();
  return { writes, draft };
}

test("AI starter prepares an editable draft without any consent or message write", async ({ page }) => {
  const { writes, draft } = await starterFixture(page, false);
  await page.getByRole("button", { name: "Hôm nay mình hơi mệt", exact: true }).click();
  await expect(draft).toHaveValue("Hôm nay mình hơi mệt");
  await expect(draft).toBeFocused();
  await expect(page.getByText("Đã thêm gợi ý vào ô nhắn.", { exact: true })).toBeVisible();
  await draft.press("End");
  await draft.pressSequentially(" quá");
  await expect(draft).toHaveValue("Hôm nay mình hơi mệt quá");
  // Give any accidental side effect time to reach the network before asserting none happened.
  await page.waitForTimeout(300);
  expect(writes).toEqual([]);
});

test("a starter is inserted at the caret of a nonempty draft instead of replacing it", async ({ page }) => {
  const { writes, draft } = await starterFixture(page, true);
  await draft.fill("Chào Mây.");
  await draft.press("End");
  await page.getByRole("button", { name: "Hôm nay mình hơi mệt", exact: true }).click();
  await expect(draft).toHaveValue("Chào Mây. Hôm nay mình hơi mệt");
  await page.waitForTimeout(300);
  expect(writes).toEqual([]);
});

test("a starter that would exceed 500 characters keeps the draft and asks to shorten it", async ({ page }) => {
  const { writes, draft } = await starterFixture(page, true);
  const long = "a".repeat(490);
  await draft.fill(long);
  await page.getByRole("button", { name: "Hôm nay mình hơi mệt", exact: true }).click();
  await expect(draft).toHaveValue(long);
  await expect(page.getByText("Gợi ý này sẽ làm tin nhắn dài hơn 500 ký tự. Hãy rút gọn trước khi thêm.", { exact: true })).toBeVisible();
  expect(writes).toEqual([]);
});

test("only explicit Send submits: Shift+Enter, IME Enter and double activation create one intent", async ({ page }) => {
  const { draft } = await starterFixture(page, true);
  const posted: any[] = [];
  let release: () => void = () => {};
  const held = new Promise<void>(resolve => { release = resolve; });
  await page.route(`**/api/v1/ai/conversations/${conversation.conversationId}/messages`, async route => {
    posted.push(route.request().postDataJSON());
    await held;
    return route.fulfill({ status: 503, json: { error: { code: "UNAVAILABLE", message: "Chưa gửi được." } } });
  });
  await page.getByRole("button", { name: "Hôm nay mình hơi mệt", exact: true }).click();
  await draft.press("Shift+Enter");
  await draft.pressSequentially("dòng hai");
  await expect(draft).toHaveValue("Hôm nay mình hơi mệt\ndòng hai");
  await draft.evaluate((element) => element.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", isComposing: true, bubbles: true, cancelable: true })));
  await page.waitForTimeout(200);
  expect(posted).toHaveLength(0);
  const send = page.getByRole("button", { name: "Gửi tin cho AI", exact: true });
  await send.click();
  await expect.poll(() => posted.length).toBe(1);
  await draft.press("Enter");
  await send.click({ force: true }).catch(() => undefined);
  await page.waitForTimeout(200);
  expect(posted).toHaveLength(1);
  release();
  await expect(page.getByRole("alert").filter({ hasText: "Chưa gửi được." })).toBeVisible();
  await expect(draft).toHaveValue("Hôm nay mình hơi mệt\ndòng hai");
});
