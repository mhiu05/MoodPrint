import { expect, test } from "@playwright/test";

test("matching publishes the reviewed profile only after a committed receipt", async ({
  page,
}) => {
  let draft: unknown;
  let published = false;
  const session = {
    userId: "11111111-1111-4111-8111-111111111111",
    alias: "An",
    ageBand: "adult",
    eligible: true,
    csrfToken: "test-csrf",
    serverTime: "2026-10-23T08:00:00Z",
    timezone: "Asia/Bangkok",
    features: { ai: false, matching: true, voice: false },
    consents: Object.fromEntries(
      ["AI", "MEM", "MATCH", "VOICE"].map((p) => [
        p,
        { enabled: p === "MATCH", version: 1, policyVersion: "v1" },
      ]),
    ),
  };
  await page.route("**/api/v1/**", async (route) => {
    const request = route.request(),
      path = new URL(request.url()).pathname;
    if (path.endsWith("/session")) return route.fulfill({ json: session });
    if (path.endsWith("/taxonomy"))
      return route.fulfill({
        json: {
          version: "v1",
          interests: {
            reading: "Đọc sách",
            music: "Âm nhạc",
            walking: "Đi bộ",
          },
          values: { respect: "Tôn trọng", sincerity: "Chân thành" },
          languages: { vi: "Tiếng Việt" },
          styles: { balanced: "Cân bằng" },
          goals: { friendship: "Tìm bạn trò chuyện" },
        },
      });
    if (path.endsWith("/matching/candidates"))
      return route.fulfill({ json: { candidates: [] } });
    if (path.endsWith("/connection-requests") || path.endsWith("/connections"))
      return route.fulfill({ json: [] });
    if (path.endsWith("/matching-draft/preview"))
      return route.fulfill({
        json: {
          profile: draft,
          draftVersion: 1,
          previewDigest: "reviewed-preview",
        },
      });
    if (path.endsWith("/matching-draft")) {
      if (request.method() === "GET")
        return route.fulfill({
          json: {
            profile: {
              interests: [],
              values: [],
              style: "balanced",
              goal: "friendship",
              languages: [],
            },
            version: 0,
          },
        });
      expect(request.headers()["x-csrf-token"]).toBe("test-csrf");
      const { expectedVersion, ...profile } = request.postDataJSON();
      expect(expectedVersion).toBe(0);
      draft = profile;
      return route.fulfill({ json: { profile, version: 1 } });
    }
    if (path.endsWith("/profiles/published")) {
      expect(request.postDataJSON()).toEqual({
        draftVersion: 1,
        previewDigest: "reviewed-preview",
        expectedPublishedVersion: 0,
      });
      published = true;
      return route.fulfill({
        status: 201,
        json: { id: "published-id", profile: draft, version: 1 },
      });
    }
    if (path.endsWith("/profiles/published/current"))
      return route.fulfill({ json: null });
    return route.fulfill({
      status: 404,
      json: { error: { code: "NOT_FOUND", message: "Missing route" } },
    });
  });
  await page.goto("/#/connect");
  await page.getByRole("button", { name: "Chỉnh hồ sơ kết nối" }).click();
  for (const label of [
    "Đọc sách",
    "Âm nhạc",
    "Đi bộ",
    "Tôn trọng",
    "Chân thành",
    "Tiếng Việt",
  ])
    await page.getByRole("checkbox", { name: label, exact: true }).check();
  await page.getByRole("button", { name: "Lưu bản nháp" }).click();
  await expect(
    page.getByRole("status").filter({ hasText: "Đã lưu bản nháp" }),
  ).toBeVisible();
  expect(published).toBe(false);
  await page.getByRole("button", { name: "Xem trước hồ sơ" }).click();
  await expect(
    page.getByRole("heading", { name: "Bạn muốn chia sẻ những điều này?" }),
  ).toBeVisible();
  expect(published).toBe(false);
  await page.getByRole("button", { name: "Xuất bản hồ sơ" }).click();
  await expect(
    page.getByText("Đã xuất bản hồ sơ.", { exact: true }),
  ).toBeVisible();
  expect(published).toBe(true);
  await expect(
    page.getByText("Chưa có gợi ý phù hợp.", { exact: true }),
  ).toBeVisible();
});

test("an incoming request shows the sender's public card before accepting", async ({
  page,
}) => {
  const session = {
    userId: "11111111-1111-4111-8111-111111111111",
    alias: "An",
    ageBand: "adult",
    eligible: true,
    csrfToken: "test-csrf",
    serverTime: "2026-10-23T08:00:00Z",
    timezone: "Asia/Bangkok",
    features: { ai: false, matching: true, voice: false },
    consents: Object.fromEntries(
      ["AI", "MEM", "MATCH", "VOICE"].map((p) => [
        p,
        { enabled: p === "MATCH", version: 1, policyVersion: "v1" },
      ]),
    ),
  };
  const profile = {
    interests: ["reading", "music", "walking"],
    values: ["respect", "sincerity"],
    style: "balanced",
    goal: "friendship",
    languages: ["vi"],
  };
  let accepted = false;
  await page.route("**/api/v1/**", async (route) => {
    const request = route.request(),
      path = new URL(request.url()).pathname;
    if (path.endsWith("/session")) return route.fulfill({ json: session });
    if (path.endsWith("/taxonomy"))
      return route.fulfill({
        json: {
          version: "v1",
          interests: {
            reading: "Đọc sách",
            music: "Âm nhạc",
            walking: "Đi bộ",
          },
          values: { respect: "Tôn trọng", sincerity: "Chân thành" },
          languages: { vi: "Tiếng Việt" },
          styles: { balanced: "Cân bằng" },
          goals: { friendship: "Tìm bạn trò chuyện" },
        },
      });
    if (path.endsWith("/matching/candidates"))
      return route.fulfill({ json: { candidates: [] } });
    if (path.endsWith("/accept")) {
      accepted = true;
      expect(request.postDataJSON()).toEqual({ expectedVersion: 1 });
      return route.fulfill({
        json: {
          id: "req-1",
          status: "accepted",
          version: 2,
          direction: "incoming",
          expiresAt: "2026-10-30T08:00:00Z",
          connectionId: "room-1",
        },
      });
    }
    if (path.endsWith("/connection-requests"))
      return route.fulfill({
        json: [
          {
            id: "req-1",
            status: accepted ? "accepted" : "pending",
            version: accepted ? 2 : 1,
            direction: "incoming",
            expiresAt: "2026-10-30T08:00:00Z",
            connectionId: accepted ? "room-1" : null,
            peer: accepted
              ? null
              : {
                  alias: "Bạn đồng hành 3fa9c1",
                  avatarSeed: "3fa9c1d2",
                  profile,
                  reasons: ["Cùng thích đọc sách", "Cùng coi trọng tôn trọng"],
                  matchLabel: "many",
                },
          },
        ],
      });
    if (path.endsWith("/connections")) return route.fulfill({ json: [] });
    if (path.endsWith("/matching-draft"))
      return route.fulfill({
        json: { profile, version: 1, publishedVersion: 1 },
      });
    if (path.endsWith("/profiles/published/current"))
      return route.fulfill({
        json: {
          id: "p1",
          profile,
          version: 1,
          state: "live",
          profileVersion: 1,
        },
      });
    return route.fulfill({
      status: 404,
      json: { error: { code: "NOT_FOUND", message: "Missing route" } },
    });
  });
  await page.goto("/#/connect");
  const card = page.getByLabel("Hồ sơ của Bạn đồng hành 3fa9c1");
  await expect(
    page.getByRole("heading", {
      name: "Bạn đồng hành 3fa9c1 muốn kết nối với bạn",
    }),
  ).toBeVisible();
  await expect(card).toContainText("Nhiều điểm chung");
  await expect(card).toContainText("Cùng thích đọc sách");
  await expect(card).toContainText("Đọc sách · Âm nhạc · Đi bộ");
  await expect(card).not.toContainText("%");
  await page.getByRole("button", { name: "Đồng ý kết nối" }).click();
  await expect(
    page.getByRole("link", { name: "Mở cuộc trò chuyện" }),
  ).toBeVisible();
  expect(accepted).toBe(true);
});

test("navigation badges, unread rows and the private read marker", async ({
  page,
}) => {
  const session = {
    userId: "11111111-1111-4111-8111-111111111111",
    alias: "An",
    ageBand: "adult",
    eligible: true,
    csrfToken: "test-csrf",
    serverTime: "2026-10-23T08:00:00Z",
    timezone: "Asia/Bangkok",
    features: { ai: false, matching: true, voice: false },
    consents: Object.fromEntries(
      ["AI", "MEM", "MATCH", "VOICE"].map((p) => [
        p,
        { enabled: p === "MATCH", version: 1, policyVersion: "v1" },
      ]),
    ),
  };
  const reads: unknown[] = [];
  const room = {
    id: "room-1",
    alias: "Bạn đồng hành 3fa9c1",
    status: "open",
    version: 1,
    highWaterSeq: "2",
    createdAt: "2026-10-23T07:00:00Z",
    unreadCount: 2,
    lastMessageAt: new Date(Date.now() - 5 * 60_000).toISOString(),
    lastMessagePreview: "Hôm nay bạn thế nào?",
    lastMessageSender: "peer",
  };
  const messages = ["Chào bạn", "Hôm nay bạn thế nào?"].map((text, i) => ({
    id: `m${i + 1}`,
    connectionId: "room-1",
    clientMessageId: `c${i + 1}`,
    sender: "peer",
    text,
    seq: String(i + 1),
    acceptedAt: "2026-10-23T07:30:00Z",
  }));
  await page.route("**/api/v1/**", async (route) => {
    const request = route.request(),
      url = new URL(request.url()),
      path = url.pathname;
    if (path.endsWith("/session")) return route.fulfill({ json: session });
    if (path.endsWith("/social/summary"))
      return route.fulfill({
        json: {
          pendingIncomingRequests: reads.length ? 0 : 1,
          unreadConnections: reads.length ? 0 : 1,
          activityInvites: 0,
        },
      });
    if (path.endsWith("/connections")) return route.fulfill({ json: [room] });
    if (path.endsWith("/connections/room-1")) return route.fulfill({ json: room });
    if (path.endsWith("/connections/room-1/messages"))
      return route.fulfill({
        json: {
          messages: url.searchParams.get("afterSeq") === "0" ? messages : [],
          highWaterSeq: "2",
        },
      });
    if (path.endsWith("/connections/room-1/read")) {
      expect(request.headers()["x-csrf-token"]).toBe("test-csrf");
      reads.push(request.postDataJSON());
      return route.fulfill({ json: { lastReadSeq: "2" } });
    }
    if (path.endsWith("/reveal-requests")) return route.fulfill({ json: [] });
    return route.fulfill({
      status: 404,
      json: { error: { code: "NOT_FOUND", message: "Missing route" } },
    });
  });
  await page.goto("/#/messages");
  await expect(
    page.getByRole("link", { name: "Tin nhắn, 1 cuộc trò chuyện chưa đọc" }),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Tìm bạn, 1 lời mời kết nối mới" }),
  ).toBeVisible();
  const row = page.getByRole("link", { name: /Bạn đồng hành 3fa9c1/ });
  await expect(row).toContainText("Hôm nay bạn thế nào?");
  await expect(row).toContainText("5 phút trước");
  await expect(row.getByRole("heading")).toHaveText(
    "Bạn đồng hành 3fa9c1, 2 tin nhắn chưa đọc",
  );
  await row.click();
  await expect(page.getByText("Hôm nay bạn thế nào?")).toBeVisible();
  await expect.poll(() => reads).toEqual([{ seq: "2" }]);
  await page.evaluate(() => window.dispatchEvent(new Event("focus")));
  await expect(page.getByRole("link", { name: "Tin nhắn", exact: true })).toBeVisible();
});
