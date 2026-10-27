import { expect, test, type Page, type Request } from "@playwright/test";

// Synthetic fixtures only: no real accounts, conversations or provider calls.
type Reply = { status?: number; json?: unknown; body?: string; contentType?: string };
type Routes = Record<string, (request: Request) => Reply | undefined>;

const baseSession = {
  userId: "11111111-1111-4111-8111-111111111111",
  alias: "An",
  ageBand: "adult",
  eligible: true,
  csrfToken: "csrf-ux",
  timezone: "Asia/Bangkok",
  serverTime: "2026-10-23T08:00:00Z",
  features: { ai: true, matching: true, voice: false },
  consents: {
    AI: { enabled: true, version: 1, policyVersion: "v1" },
    MEM: { enabled: true, version: 1, policyVersion: "v1" },
    MATCH: { enabled: true, version: 1, policyVersion: "v1" },
    VOICE: { enabled: false, version: 1, policyVersion: "v1" },
  },
};

export function sessionWith(consents: Partial<Record<"AI" | "MEM" | "MATCH" | "VOICE", boolean>>, patch: Record<string, unknown> = {}) {
  const next = structuredClone(baseSession) as typeof baseSession & Record<string, unknown>;
  for (const [purpose, enabled] of Object.entries(consents))
    next.consents[purpose as keyof typeof next.consents].enabled = enabled;
  return { ...next, ...patch };
}

const bots = [
  { botId: "may", name: "Mây", role: "Lắng nghe & tâm sự", description: "Một khoảng nhỏ để được lắng nghe.", starters: ["Hôm nay mình hơi mệt"], avatarKey: "may" },
];
const room = { id: "room-1", alias: "Bạn đồng hành 3fa9c1", status: "open", version: 1, highWaterSeq: "0", unreadCount: 0 };

async function app(page: Page, session: unknown, routes: Routes = {}) {
  await page.route("**/api/v1/**", async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname.replace("/api/v1", "");
    const custom = routes[path]?.(request);
    if (custom)
      return custom.body !== undefined
        ? route.fulfill({ status: custom.status ?? 200, body: custom.body, contentType: custom.contentType ?? "text/plain" })
        : route.fulfill({ status: custom.status ?? 200, json: custom.json });
    const fixed: Record<string, unknown> = {
      "/session": session,
      "/bots": bots,
      "/ai/preferences": { historyEnabled: false, semanticMemoryEnabled: false, version: 1, policyVersion: "ai-data-v1", retentionDays: 30, historyAvailable: true, semanticMemoryAvailable: true },
      "/ai/conversations": [],
      "/social/summary": { pendingIncomingRequests: 0, unreadConnections: 0, activityInvites: 0 },
      "/proposals": [],
      "/memories": [],
      "/connections": [],
      "/connection-requests": [],
      "/activities/catalog": [],
      [`/connections/${room.id}`]: room,
      [`/connections/${room.id}/messages`]: { messages: [], highWaterSeq: "0" },
      [`/connections/${room.id}/activities`]: [],
      [`/connections/${room.id}/activities/current`]: null,
      [`/connections/${room.id}/reveal-requests`]: [],
      "/profiles/published/current": null,
    };
    if (request.method() === "GET" && path in fixed) return route.fulfill({ json: fixed[path] });
    return route.fulfill({ status: 404, json: { error: { code: "NOT_FOUND", message: "Missing fixture" } } });
  });
}

const pendingProposal = {
  id: "p-1",
  botId: "may",
  purpose: "memory",
  text: "Thích đi bộ buổi tối",
  status: "pending",
  version: 1,
  expiresAt: "2099-01-01T00:00:00Z",
};

test.describe("truthful consent recovery (F03)", () => {
  test("with AI processing off a pending proposal points to an explicit Send, not to Settings", async ({ page }) => {
    await app(page, sessionWith({ AI: false, MEM: false }), { "/proposals": () => ({ json: [pendingProposal] }) });
    await page.goto("/#/memory");
    const proposal = page.getByRole("article").filter({ hasText: "Thích đi bộ buổi tối" });
    await expect(proposal).toContainText("Quyền xử lý AI đang tắt nên chưa thể duyệt đề xuất này.");
    await expect(proposal.getByRole("link", { name: "Mở trợ lý" })).toHaveAttribute("href", "#/assistants");
    await expect(proposal.getByRole("link", { name: /quyền riêng tư/i })).toHaveCount(0);
    await expect(proposal.getByRole("button", { name: "Không lưu" })).toBeEnabled();
  });

  test("with approved memory off the page explains that approving a proposal is the way back", async ({ page }) => {
    await app(page, sessionWith({ AI: true, MEM: false }));
    await page.goto("/#/memory");
    await expect(page.getByText("Trợ lý chỉ dùng lại ghi nhớ sau khi bạn duyệt một đề xuất mới.", { exact: false })).toBeVisible();
    await expect(page.getByRole("link", { name: "Xem quyền ghi nhớ" })).toHaveCount(0);
  });

  test("with MATCH withdrawn, messages lead to reviewing and showing the matching profile", async ({ page }) => {
    await app(page, sessionWith({ MATCH: false }));
    await page.goto("/#/messages");
    await expect(page.getByRole("link", { name: "Mở hồ sơ tìm bạn" })).toHaveAttribute("href", "#/connect?tab=profile");
    await expect(page.getByText(/Hiển thị hồ sơ/)).toBeVisible();
    await expect(page.getByRole("link", { name: "Xem quyền tìm bạn" })).toHaveCount(0);
  });
});

test.describe("truthful blocking (F04)", () => {
  test("the chat block dialog states in-app irreversibility, focuses cancel and sends nothing on cancel", async ({ page }) => {
    const writes: string[] = [];
    page.on("request", (request) => {
      if (request.method() === "POST" && request.url().includes("/block")) writes.push(request.url());
    });
    await app(page, sessionWith({ AI: false }));
    await page.goto("/#/chat/room-1");
    await page.getByText("Chia sẻ và an toàn", { exact: true }).click();
    await page.getByRole("button", { name: "Chặn kết nối này", exact: true }).click();
    const dialog = page.getByRole("dialog", { name: "Chặn kết nối này?" });
    await expect(dialog).toContainText("Hai bạn sẽ không thể xem hoặc gửi tiếp tin nhắn trong kết nối này.");
    await expect(dialog).toContainText("Việc chặn không thể hoàn tác trong ứng dụng.");
    await expect(dialog).not.toContainText("Bỏ chặn");
    await expect(dialog.getByRole("button", { name: "Giữ kết nối" })).toBeFocused();
    await dialog.getByRole("button", { name: "Giữ kết nối" }).click();
    await expect(dialog).toHaveCount(0);
    expect(writes).toEqual([]);
  });
});

test.describe("service failures do not blame input (F11)", () => {
  test("a non-JSON 500 asks to retry instead of checking the content", async ({ page }) => {
    await app(page, baseSession, { "/session": () => ({ status: 500, body: "<html>proxy error</html>", contentType: "text/html" }) });
    await page.goto("/#/assistants");
    const alert = page.getByRole("alert");
    await expect(alert).toContainText("Chưa hoàn tất yêu cầu. Bạn hãy thử lại.");
    await expect(alert).not.toContainText("kiểm tra nội dung");
  });
});

test("resolved reports show a Vietnamese outcome instead of the raw enum", async ({ page }) => {
  const resolved = { id: "r1", status: "resolved", version: 3, reason: "Quấy rối", createdAt: "2026-10-23T07:00:00Z", subjectRef: "s-abcdef0123456789", reporterRef: "r-abcdef012345", evidence: [], priorActions: 1, resolution: "warned" };
  await app(page, sessionWith({}, { staff: "moderator", notices: [] }), {
    "/admin/reports": (request) => ({ json: new URL(request.url()).searchParams.get("status") === "resolved" ? [resolved, { ...resolved, id: "r2", resolution: "mystery" }] : [] }),
  });
  await page.goto("/#/admin/reports");
  await page.getByRole("button", { name: "Đã xử lý", exact: true }).click();
  await expect(page.getByText(/Kết quả: Đã cảnh báo/)).toBeVisible();
  await expect(page.getByText(/Kết quả: Đã xử lý/)).toBeVisible();
  await expect(page.getByText(/warned|mystery/)).toHaveCount(0);
});

test("the first AI send explains the consent it records, next to Send", async ({ page }) => {
  await app(page, sessionWith({ AI: false }));
  await page.goto("/#/assistants/may");
  await expect(page.getByText("Khi chọn Gửi, bạn đồng ý để dịch vụ AI xử lý tin nhắn này. Bạn có thể rút quyền trong Quyền riêng tư.", { exact: true })).toBeVisible();
});

test("an unavailable AI service is not sent to Settings for a fix that does not exist there", async ({ page }) => {
  await app(page, sessionWith({}, { features: { ai: false, aiStatus: "configuration_missing", matching: true, voice: false } }));
  await page.goto("/#/assistants/may?new=1");
  const notice = page.locator(".chat-readonly");
  await expect(notice).toContainText("Trợ lý chưa được kết nối với dịch vụ AI.");
  await expect(notice.getByRole("link")).toHaveCount(0);
});
