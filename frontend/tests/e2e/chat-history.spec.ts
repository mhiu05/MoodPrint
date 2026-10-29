import { artifactPath } from "../artifacts";
import { test, expect, type Page } from "@playwright/test";

const id = "22222222-2222-4222-8222-222222222222";
const bot = {
  botId: "may",
  name: "Mây",
  role: "Lắng nghe",
  description: "Một khoảng riêng.",
  starters: [],
  avatarKey: "may",
};
const defaults = {
  historyEnabled: false,
  semanticMemoryEnabled: false,
  version: 1,
  policyVersion: "ai-data-v1",
  retentionDays: 30,
  historyAvailable: true,
  semanticMemoryAvailable: true,
};
async function fixture(page: Page, ai = true, options: {
  preferences?: Partial<typeof defaults>;
  preferencesReady?: Promise<void>;
  serviceStatus?: "disabled" | "configuration_missing" | "configuration_invalid";
} = {}) {
  let preferences = { ...defaults, ...options.preferences };
  let deleted = false;
  const writes: any[] = [];
  const header = {
    conversationId: id,
    botId: "may",
    version: 2,
    persistent: true,
    title: "Một buổi sáng",
    createdAt: "2026-10-24T08:00:00Z",
    updatedAt: "2026-10-24T09:00:00Z",
    expiresAt: "2026-11-23T08:00:00Z",
  };
  await page.route("**/api/v1/**", async (route) => {
    const request = route.request(),
      url = new URL(request.url()),
      path = url.pathname.replace("/api/v1", "");
    if (path === "/session")
      return route.fulfill({
        json: {
          userId: "11111111-1111-4111-8111-111111111111",
          alias: "An",
          eligible: true,
          ageBand: "adult",
          csrfToken: "synthetic-csrf",
          timezone: "Asia/Bangkok",
          serverTime: "2026-10-24T08:00:00Z",
          features: { ai: !options.serviceStatus, aiStatus: options.serviceStatus || "ready", voice: false, matching: false },
          consents: Object.fromEntries(
            ["AI", "MEM", "MATCH", "VOICE"].map((p) => [
              p,
              { enabled: p === "AI" && ai, version: 1, policyVersion: "v1" },
            ]),
          ),
        },
      });
    if (path === "/bots") return route.fulfill({ json: [bot] });
    if (path === "/ai/preferences") {
      await options.preferencesReady;
      if (request.method() === "PUT") {
        writes.push(request.postDataJSON());
        preferences = {
          ...preferences,
          ...request.postDataJSON(),
          version: preferences.version + 1,
        };
      }
      return route.fulfill({ json: preferences });
    }
    if (path === "/ai/conversations")
      return route.fulfill({ json: deleted ? [] : [header] });
    if (path === `/ai/conversations/${id}/export`)
      return route.fulfill({
        json: { conversation: header, messages: [{ text: "Tin đã lưu" }] },
      });
    if (path === `/ai/conversations/${id}`) {
      if (request.method() === "DELETE") {
        deleted = true;
        return route.fulfill({ status: 204 });
      }
      if (request.method() === "PATCH") {
        writes.push(request.postDataJSON());
        header.title = request.postDataJSON().title;
        return route.fulfill({ json: header });
      }
      return route.fulfill({
        json: {
          ...header,
          activeRunId: null,
          activeRunVersion: null,
          hasMoreMessages: !url.searchParams.has("before"),
          messages: [
            {
              id: url.searchParams.has("before")
                ? "old-message"
                : "new-message",
              actor: "self",
              text: url.searchParams.has("before")
                ? "Tin cũ hơn"
                : "Tin đã lưu",
            },
          ],
        },
      });
    }
    if (path.startsWith("/ai/conversations/") && request.method() === "POST")
      writes.push(request.postDataJSON());
    if (["/memories", "/proposals", "/users/me/identity"].includes(path))
      return route.fulfill({ json: [] });
    return route.fulfill({
      status: 503,
      json: {
        error: { code: "UNAVAILABLE", message: "Dịch vụ chưa sẵn sàng." },
      },
    });
  });
  return writes;
}

test("latest saved history waits for a late preference response after login", async ({ page }) => {
  let release!: () => void;
  const ready = new Promise<void>(resolve => { release = resolve; });
  await fixture(page, true, { preferences: { historyEnabled: true }, preferencesReady: ready });
  await page.goto("/#/assistants/may");
  // History status now lives in the conversation info surface.
  await page.getByRole("button", { name: "Thông tin cuộc trò chuyện", exact: true }).click();
  await expect(page.getByText("Đang kiểm tra lịch sử…", { exact: true })).toBeVisible();
  release();
  await expect(page.getByRole("log").getByText("Tin đã lưu", { exact: true })).toBeVisible();
});

test("history server availability and user opt-out have distinct actions", async ({ page }) => {
  await fixture(page, true, { preferences: { historyAvailable: false } });
  await page.goto("/#/assistants/may?new=1");
  await page.getByRole("button", { name: "Thông tin cuộc trò chuyện", exact: true }).click();
  await expect(page.getByText("Lưu lịch sử chưa sẵn sàng.", { exact: true })).toBeVisible();
  await expect(page.getByText("Lưu lịch sử đang tắt", { exact: true })).toHaveCount(0);
});

test("missing provider is distinct from missing consent", async ({ page }) => {
  await fixture(page, true, { serviceStatus: "configuration_missing" });
  await page.goto("/#/assistants/may?new=1");
  await expect(page.getByText("Trợ lý chưa được kết nối với dịch vụ AI. Bạn có thể quay lại sau.", { exact: true })).toBeVisible();
  await expect(page.getByRole("link", { name: "Bật quyền trò chuyện AI", exact: true })).toHaveCount(0);
});

test("legacy history opt-out does not require a settings switch", async ({ page }) => {
  const writes = await fixture(page);
  await page.goto(`/#/assistants/may?conversation=${id}`);
  await expect(page.getByRole("button", { name: "Gửi tin cho AI", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Thông tin cuộc trò chuyện", exact: true }).click();
  await expect(page.getByRole("link", { name: "Cài đặt lưu lịch sử", exact: true })).toHaveCount(0);
  expect(writes).toEqual([]);
});

test("saved history stays usable with a legacy disabled AI flag", async ({
  page,
}) => {
  await fixture(page, false);
  await page.goto(`/#/assistants/may?conversation=${id}`);
  await expect(
    page.getByRole("log").getByText("Tin đã lưu", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Gửi tin cho AI" }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Tải tin nhắn cũ hơn", exact: true })
    .click();
  await expect(
    page.getByRole("log").getByText("Tin cũ hơn", { exact: true }),
  ).toBeVisible();
  await page.reload();
  await expect(
    page.getByRole("log").getByText("Tin đã lưu", { exact: true }),
  ).toBeVisible();
  await page.screenshot({
    path: artifactPath("ai-chat-memory/mock-history-desktop.png", "evidence/ai-chat-memory/mock-history-desktop.png"),
    fullPage: true,
  });
  await page.getByRole("button", { name: "Thông tin cuộc trò chuyện", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Tải xuống cuộc trò chuyện", exact: true }),
  ).toHaveCount(0);
  await page
    .getByRole("button", { name: "Xóa cuộc trò chuyện", exact: true })
    .click();
  await page
    .getByRole("dialog", { name: "Xóa cuộc trò chuyện này?" })
    .getByRole("button", { name: "Xóa cuộc trò chuyện", exact: true })
    .click();
  await expect(
    page.getByRole("log").getByText("Tin đã lưu", { exact: true }),
  ).toHaveCount(0);
});

test("legacy history opt-out keeps saved threads writable and mobile history reachable", async ({
  page,
}) => {
  const writes = await fixture(page);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(`/#/assistants/may?conversation=${id}`);
  await expect(
    page.getByRole("log").getByText("Tin đã lưu", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Gửi tin cho AI" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Thông tin cuộc trò chuyện", exact: true }).click();
  await page
    .getByRole("button", { name: "Mở lịch sử trò chuyện", exact: true })
    .click();
  await expect(
    page.getByRole("dialog").getByRole("link", { name: /Một buổi sáng/ }),
  ).toBeVisible();
  await page.screenshot({
    path: artifactPath("ai-chat-memory/mock-history-mobile-dialog.png", "evidence/ai-chat-memory/mock-history-mobile-dialog.png"),
    fullPage: true,
  });
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).toHaveCount(0);
  expect(writes).toEqual([]);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: artifactPath("ai-chat-memory/mock-history-mobile.png", "evidence/ai-chat-memory/mock-history-mobile.png"),
    fullPage: true,
  });
});

test("expired proposals explain expiry and cannot be approved", async ({
  page,
}) => {
  await fixture(page);
  await page.route("**/api/v1/proposals", (route) =>
    route.fulfill({
      json: [
        {
          id: "expired-proposal",
          text: "",
          botId: "may",
          purpose: "memory",
          version: 2,
          status: "expired",
          expiresAt: "2020-01-01T00:00:00Z",
        },
      ],
    }),
  );
  await page.goto("/#/memory");
  await expect(
    page.getByText(
      "Đề xuất đã hết hạn. Bạn có thể nhờ trợ lý tạo đề xuất mới.",
      { exact: true },
    ),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Duyệt và lưu", exact: true }),
  ).toHaveCount(0);
});

test("returning to the page keeps history writable despite a legacy opt-out", async ({
  page,
}) => {
  const writes = await fixture(page);
  let enabled = true;
  await page.route("**/api/v1/ai/preferences", (route) =>
    route.fulfill({ json: { ...defaults, historyEnabled: enabled } }),
  );
  await page.goto(`/#/assistants/may?conversation=${id}`);
  await expect(
    page.getByRole("button", { name: "Gửi tin cho AI", exact: true }),
  ).toBeVisible();
  enabled = false;
  await page.evaluate(() => window.dispatchEvent(new Event("focus")));
  await expect(
    page.getByRole("button", { name: "Gửi tin cho AI", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("log").getByText("Tin đã lưu", { exact: true }),
  ).toBeVisible();
  expect(writes).toEqual([]);
});

test("retrying a history read preserves the draft and a new chat is saved", async ({
  page,
}) => {
  await fixture(page);
  let unavailable = true;
  const created: any[] = [];
  await page.route("**/api/v1/ai/conversations?*", (route) =>
    unavailable
      ? route.fulfill({
          status: 503,
          json: {
            error: { code: "UNAVAILABLE", message: "Lịch sử chưa tải được." },
          },
        })
      : route.fulfill({ json: [] }),
  );
  await page.route("**/api/v1/ai/conversations", (route) => {
    created.push(route.request().postDataJSON());
    return route.fulfill({
      json: {
        conversationId: id,
        botId: "may",
        version: 1,
        persistent: false,
        title: "Tạm thời",
        expiresAt: "2026-11-23T08:00:00Z",
      },
    });
  });
  await page.goto("/#/assistants/may");
  await expect(page.getByRole("log").getByRole("alert")).toContainText(
    "Lịch sử chưa tải được.",
  );
  const draft = page.getByRole("textbox", {
    name: "Tin nhắn cho Mây",
    exact: true,
  });
  await draft.fill("Giữ lại lời nhắn khi tải lại");
  unavailable = false;
  await page
    .getByRole("log")
    .getByRole("button", { name: "Thử lại", exact: true })
    .click();
  await expect(draft).toHaveValue("Giữ lại lời nhắn khi tải lại");
  await page
    .getByRole("button", { name: "Gửi tin cho AI", exact: true })
    .click();
  await expect.poll(() => created.length).toBe(1);
  expect(created[0]).toEqual({ botId: "may", persistent: true });
});

test("a saved thread can be renamed and history is grouped by assistant", async ({
  page,
}) => {
  const writes = await fixture(page);
  await page.goto(`/#/assistants/may?conversation=${id}`);
  await expect(
    page.getByRole("log").getByText("Tin đã lưu", { exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Thông tin cuộc trò chuyện", exact: true }).click();
  await page.getByRole("button", { name: "Đổi tên", exact: true }).click();
  const dialog = page.getByRole("dialog", { name: "Đổi tên cuộc trò chuyện" });
  const title = dialog.getByRole("textbox", { name: "Tên cuộc trò chuyện" });
  await expect(title).toHaveValue("Một buổi sáng");
  await title.fill("Kế hoạch tuần");
  await dialog.getByRole("button", { name: "Lưu tên", exact: true }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(
    page.getByText("Đã đổi tên cuộc trò chuyện.", { exact: true }),
  ).toBeVisible();
  expect(writes).toContainEqual({ title: "Kế hoạch tuần" });
  await page.goto("/#/assistants");
  const group = page.getByRole("list", { name: "Mây" });
  await expect(
    group.getByRole("link", { name: /Kế hoạch tuần/ }),
  ).toBeVisible();
});

test("pending proposals are linked from chat and memory deletion needs confirmation", async ({
  page,
}) => {
  await fixture(page);
  const deletes: string[] = [];
  let memories = [
    { id: "memory-1", botId: "may", text: "Thích đi bộ", version: 1 },
  ];
  await page.route("**/api/v1/proposals", (route) =>
    route.fulfill({
      json: [
        {
          id: "pending-proposal",
          text: "Mình thích trà",
          botId: "may",
          purpose: "memory",
          version: 1,
          status: "pending",
          expiresAt: "2999-01-01T00:00:00Z",
        },
      ],
    }),
  );
  await page.route("**/api/v1/memories**", (route) => {
    if (route.request().method() === "DELETE") {
      deletes.push(route.request().url());
      memories = [];
      return route.fulfill({
        json: {
          actionId: "a",
          status: "succeeded",
          resourceId: "memory-1",
          resourceVersion: 2,
        },
      });
    }
    return route.fulfill({ json: memories });
  });
  await page.goto(`/#/assistants/may?conversation=${id}`);
  const notice = page
    .getByRole("log")
    .getByText(/Có 1 đề xuất đang chờ bạn duyệt/);
  await expect(notice).toBeVisible();
  await notice.getByRole("link", { name: "Xem đề xuất" }).click();
  await expect(
    page.getByRole("textbox", { name: "Nội dung sẽ lưu" }),
  ).toHaveValue("Mình thích trà");
  await expect(
    page.getByText("Không có đề xuất đang chờ.", { exact: true }),
  ).toHaveCount(0);
  await page.getByRole("button", { name: "Xóa ghi nhớ", exact: true }).click();
  expect(deletes).toEqual([]);
  await page.getByRole("button", { name: "Giữ lại", exact: true }).click();
  await expect(page.getByText("Thích đi bộ", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Xóa ghi nhớ", exact: true }).click();
  await page
    .getByRole("button", { name: "Xóa ghi nhớ này", exact: true })
    .click();
  await expect.poll(() => deletes.length).toBe(1);
  await expect(
    page.getByText("Bạn chưa lưu ghi nhớ nào. Khi trò chuyện, bạn có thể nhờ trợ lý đề xuất điều cần nhớ rồi duyệt tại đây.", { exact: true }),
  ).toBeVisible();
});
