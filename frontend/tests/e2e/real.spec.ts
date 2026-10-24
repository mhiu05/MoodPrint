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
    if (path === "/api/v1/ai/conversations")
      return route.fulfill({
        json: route.request().method() === "GET" ? [] : conversation,
      });
    if (path === `/api/v1/ai/conversations/${conversation.conversationId}`)
      return route.fulfill({ json: conversation });
    if (path === "/api/v1/moods") return route.fulfill({ json: [] });
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
    page.getByRole("heading", { name: /Bạn muốn kể gì/ }),
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
    page.getByRole("heading", { name: "Trước khi bắt đầu" }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Xác nhận năm sinh", exact: true }),
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
    .getByRole("button", { name: "Xác nhận năm sinh", exact: true })
    .click();
  await expect(page.getByRole("alert")).toContainText("Chưa thể xác nhận");
  await expect(page.getByLabel("Năm sinh", { exact: true })).toHaveValue(
    "2007",
  );
  await page
    .getByRole("button", { name: "Xác nhận năm sinh", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Trước khi bắt đầu" }),
  ).toBeVisible();
  release();
  await expect(
    page.getByRole("heading", { name: /Bạn muốn kể gì/ }),
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
    page.getByRole("heading", { name: /Bạn muốn kể gì/ }),
  ).toHaveCount(0);
  available = true;
  await page.getByRole("button", { name: "Thử lại", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: /Bạn muốn kể gì/ }),
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
    .getByRole("button", { name: "Tắt trò chuyện AI", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Bật trò chuyện AI", exact: true }),
  ).toBeVisible();
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
  await page.route("**/api/v1/ai/conversations", (route) =>
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
  await expect(page.getByRole("alert")).toContainText("Chưa mở được lịch sử");
  await page
    .getByRole("textbox", { name: "Tin nhắn cho Mây" })
    .fill("Giữ bản nháp này");
  await expect(
    page.getByRole("button", { name: "Gửi tin cho AI", exact: true }),
  ).toBeDisabled();
});

test("returning to the app rechecks consent and removes the revoked conversation", async ({
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
    page.getByRole("heading", { name: "Trò chuyện AI đang tắt" }),
  ).toBeVisible();
  await expect(
    page.getByRole("textbox", { name: "Tin nhắn cho Mây" }),
  ).toHaveCount(0);
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
    page.getByText("Một ngày nhẹ nhàng", { exact: true }),
  ).toBeVisible();
  await page.reload();
  await expect(
    page.getByText("Một ngày nhẹ nhàng", { exact: true }),
  ).toBeVisible();
  await page.getByLabel("Ngày", { exact: true }).fill(date);
  await page
    .getByLabel("Ghi chú", { exact: true })
    .fill("Bản nháp cần giữ lại");
  await page
    .getByRole("button", { name: "Lưu tâm trạng", exact: true })
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
