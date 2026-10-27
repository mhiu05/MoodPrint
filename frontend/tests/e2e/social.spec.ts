import { expect, test, type Page } from "@playwright/test";

const TAXONOMY = {
  version: "v2",
  interests: {
    reading: "Đọc sách",
    music: "Âm nhạc",
    walking: "Đi bộ",
    coffee: "Cà phê",
  },
  values: { respect: "Tôn trọng", sincerity: "Chân thành", humor: "Hài hước" },
  languages: { vi: "Tiếng Việt", en: "Tiếng Anh" },
  styles: { balanced: "Cân bằng", listening: "Thích lắng nghe" },
  goals: { friendship: "Tìm bạn trò chuyện", "study-buddy": "Tìm bạn cùng học" },
  activities: { focus: "Cùng tập trung", icebreaker: "Câu hỏi làm quen" },
  availability: { weekday_evening: "Tối ngày thường" },
  categories: {
    learning: ["reading"],
    creative: ["music"],
    active: ["walking"],
    lifestyle: ["coffee"],
  },
  categoryLabels: {
    learning: "Học hỏi",
    creative: "Sáng tạo",
    active: "Vận động",
    lifestyle: "Đời sống",
  },
  limits: {
    interests: [3, 10],
    values: [2, 4],
    languages: [1, 2],
    activities: [0, 4],
    availability: [0, 6],
  },
};

function sessionFor(consents: Record<string, boolean> = {}) {
  const base = {
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
        { enabled: consents[p] ?? p === "MATCH", version: 1, policyVersion: "v1" },
      ]),
    ),
  };
  return base;
}

async function mockDiscovery(
  page: Page,
  state: { draft?: unknown; published: boolean; candidates: unknown[] },
  consents: Record<string, boolean> = {},
) {
  const session = sessionFor(consents);
  await page.route("**/api/v1/**", async (route) => {
    const request = route.request(),
      path = new URL(request.url()).pathname;
    if (path.endsWith("/session")) return route.fulfill({ json: session });
    if (path.endsWith("/taxonomy")) return route.fulfill({ json: TAXONOMY });
    if (path.endsWith("/matching/candidates"))
      return route.fulfill({ json: { candidates: state.candidates } });
    if (path.endsWith("/connection-requests") || path.endsWith("/connections"))
      return route.fulfill({ json: [] });
    if (path.endsWith("/social/summary"))
      return route.fulfill({
        json: { pendingIncomingRequests: 0, unreadConnections: 0, activityInvites: 0 },
      });
    if (path.endsWith("/matching-draft/preview"))
      return route.fulfill({
        json: {
          profile: state.draft,
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
              activities: [],
              availability: [],
              strictGoal: false,
            },
            version: 0,
          },
        });
      expect(request.headers()["x-csrf-token"]).toBe("test-csrf");
      const { expectedVersion, ...profile } = request.postDataJSON();
      expect(expectedVersion).toBe(0);
      state.draft = profile;
      return route.fulfill({ json: { profile, version: 1 } });
    }
    if (path.endsWith("/profiles/published")) {
      expect(request.postDataJSON()).toEqual({
        draftVersion: 1,
        previewDigest: "reviewed-preview",
        expectedPublishedVersion: 0,
      });
      state.published = true;
      return route.fulfill({
        status: 201,
        json: {
          id: "published-id",
          profile: state.draft,
          version: 1,
          state: "live",
          profileVersion: 1,
        },
      });
    }
    if (path.endsWith("/profiles/published/current"))
      return route.fulfill({ json: null });
    return route.fulfill({
      status: 404,
      json: { error: { code: "NOT_FOUND", message: "Missing route" } },
    });
  });
}

test("matching publishes the reviewed profile only after a committed receipt", async ({
  page,
}) => {
  const state = { published: false, candidates: [] as unknown[], draft: undefined };
  await mockDiscovery(page, state);
  await page.goto("/#/connect");
  await page.getByRole("button", { name: "Chỉnh hồ sơ tìm bạn" }).click();
  await expect(page.getByRole("heading", { name: "Bước 1/5: Sở thích" })).toBeFocused();
  const next = page.getByRole("button", { name: "Tiếp tục" });
  await page.getByRole("checkbox", { name: "Đọc sách", exact: true }).check();
  await page.getByRole("checkbox", { name: "Âm nhạc", exact: true }).check();
  await expect(page.getByText("Đã chọn 2 · cần ít nhất 3")).toBeVisible();
  await expect(next).toBeDisabled();
  await page.getByRole("checkbox", { name: "Đi bộ", exact: true }).check();
  await expect(next).toBeEnabled();
  await next.click();
  for (const label of ["Tôn trọng", "Chân thành"])
    await page.getByRole("checkbox", { name: label, exact: true }).check();
  await next.click();
  await page.getByRole("checkbox", { name: "Tiếng Việt", exact: true }).check();
  await next.click();
  await page.getByRole("checkbox", { name: "Cùng tập trung", exact: true }).check();
  expect(state.published).toBe(false);
  await page.getByRole("button", { name: "Xem trước hồ sơ" }).click();
  const card = page.getByLabel("Hồ sơ của Bạn");
  await expect(card).toContainText("Đọc sách · Âm nhạc · Đi bộ");
  await expect(card).toContainText("Tôn trọng · Chân thành");
  await expect(card).toContainText("Cùng tập trung");
  await expect(card).not.toContainText("Cà phê");
  expect(state.published).toBe(false);
  await page.getByRole("button", { name: "Hiển thị hồ sơ" }).click();
  await expect(
    page.getByText("Đã hiển thị hồ sơ tìm bạn.", { exact: true }),
  ).toBeVisible();
  expect(state.published).toBe(true);
  await expect(
    page.getByText("Chưa có gợi ý phù hợp.", { exact: true }),
  ).toBeVisible();
});

test("candidate cards show a qualitative label and at most three reasons, never a percentage", async ({
  page,
}) => {
  const card = {
    candidateRef: "ref-1",
    alias: "Bạn đồng hành 7c1e02",
    avatarSeed: "7c1e02aa",
    profile: {
      interests: ["reading", "coffee", "music"],
      values: ["respect", "humor"],
      style: "listening",
      goal: "study-buddy",
      languages: ["vi"],
      activities: ["focus"],
      availability: ["weekday_evening"],
      strictGoal: false,
    },
    reasons: ["Cả hai muốn thử tập trung cùng nhau", "Cùng thích đọc sách", "Cùng coi trọng tôn trọng"],
    matchLabel: "some",
    sharedActivities: ["focus"],
    scoringVersion: "rules-v2",
    profileVersion: 1,
    peerVersion: 1,
  };
  await mockDiscovery(page, { published: true, candidates: [card] });
  await page.route("**/api/v1/profiles/published/current", (route) =>
    route.fulfill({
      json: {
        id: "p",
        profile: card.profile,
        version: 1,
        state: "live",
        profileVersion: 1,
      },
    }),
  );
  await page.goto("/#/connect");
  const shown = page.getByLabel("Hồ sơ của Bạn đồng hành 7c1e02");
  await expect(shown).toContainText("Có vài điểm chung");
  await expect(shown.getByRole("listitem")).toHaveCount(3);
  await expect(shown).toContainText("Cùng tập trung (cả hai)");
  expect(await shown.innerText()).not.toMatch(/\d\s*%/);
  await expect(shown.getByRole("button", { name: "Gửi lời mời kết nối" })).toBeVisible();
  await expect(
    page.getByText(/không phải đánh giá mức độ hợp nhau/),
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
  // Requests live behind their tab (H-01); the nav badge links here.
  await page.goto("/#/connect?tab=requests");
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
  await expect(
    page.getByRole("log").getByText("Hôm nay bạn thế nào?"),
  ).toBeVisible();
  await expect.poll(() => reads).toEqual([{ seq: "2" }]);
  await page.evaluate(() => window.dispatchEvent(new Event("focus")));
  await expect(page.getByRole("link", { name: "Tin nhắn", exact: true })).toBeVisible();
});

// ---- Reviewed sharing and invitations (V-PUBLISH / V-MATCH-SAFETY / V-CONSENT-COPY) ----
async function reviewProfile(page: Page) {
  await page.getByRole("button", { name: "Chỉnh hồ sơ tìm bạn" }).click();
  for (const label of ["Đọc sách", "Âm nhạc", "Đi bộ"]) await page.getByRole("checkbox", { name: label, exact: true }).check();
  await page.getByRole("button", { name: "Tiếp tục" }).click();
  for (const label of ["Tôn trọng", "Chân thành"]) await page.getByRole("checkbox", { name: label, exact: true }).check();
  await page.getByRole("button", { name: "Tiếp tục" }).click();
  await page.getByRole("checkbox", { name: "Tiếng Việt", exact: true }).check();
  await page.getByRole("button", { name: "Tiếp tục" }).click();
  await page.getByRole("button", { name: "Xem trước hồ sơ" }).click();
  await expect(page.getByLabel("Hồ sơ của Bạn")).toContainText("Đọc sách · Âm nhạc · Đi bộ");
}

test("a refused publish keeps the reviewed choices and never claims the profile is shown", async ({ page }) => {
  const state = { published: false, candidates: [] as unknown[], draft: undefined };
  await mockDiscovery(page, state);
  await page.route("**/api/v1/profiles/published", (route) =>
    route.fulfill({ status: 409, json: { error: { code: "PREVIEW_CHANGED", message: "Hãy xem lại bản xem trước mới nhất." } } }));
  await page.goto("/#/connect");
  await reviewProfile(page);
  await page.getByRole("button", { name: "Hiển thị hồ sơ", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("Hãy xem lại bản xem trước mới nhất.");
  await expect(page.getByText(/Đã hiển thị hồ sơ/)).toHaveCount(0);
  await expect(page.getByLabel("Hồ sơ của Bạn")).toContainText("Đọc sách · Âm nhạc · Đi bộ");
  expect(state.published).toBe(false);
});

test("closing the editor with unsaved choices asks before discarding them", async ({ page }) => {
  await mockDiscovery(page, { published: false, candidates: [] });
  await page.goto("/#/connect");
  await page.getByRole("button", { name: "Chỉnh hồ sơ tìm bạn" }).click();
  await page.getByRole("checkbox", { name: "Đọc sách", exact: true }).check();
  await page.getByRole("button", { name: "Đóng", exact: true }).click();
  const confirm = page.getByRole("dialog", { name: "Đóng mà chưa lưu thay đổi?" });
  await expect(confirm.getByRole("button", { name: "Tiếp tục chỉnh" })).toBeFocused();
  await confirm.getByRole("button", { name: "Tiếp tục chỉnh" }).click();
  await expect(page.getByRole("checkbox", { name: "Đọc sách", exact: true })).toBeChecked();
  await page.getByRole("button", { name: "Đóng", exact: true }).click();
  await page.getByRole("dialog", { name: "Đóng mà chưa lưu thay đổi?" }).getByRole("button", { name: "Bỏ thay đổi" }).click();
  await expect(page.getByRole("button", { name: "Chỉnh hồ sơ tìm bạn" })).toBeVisible();
});

test("with MATCH withdrawn the profile tab says showing a reviewed profile is the way back", async ({ page }) => {
  await mockDiscovery(page, { published: false, candidates: [] }, { MATCH: false });
  await page.goto("/#/connect");
  const panel = page.getByRole("tabpanel", { name: "Hồ sơ tìm bạn" });
  await expect(panel).toContainText("Quyền tìm bạn đang tắt.");
  await expect(panel).toContainText("Hiển thị hồ sơ");
  await expect(panel.getByRole("link", { name: /cài đặt/i })).toHaveCount(0);
});

test("sending an invitation is named as an invitation, with a matching receipt", async ({ page }) => {
  const card = {
    candidateRef: "ref-1", alias: "Bạn đồng hành 7c1e02", avatarSeed: "7c1e02aa",
    profile: { interests: ["reading", "coffee", "music"], values: ["respect", "humor"], style: "listening", goal: "study-buddy", languages: ["vi"], activities: ["focus"], availability: ["weekday_evening"], strictGoal: false },
    reasons: ["Cùng thích đọc sách"], matchLabel: "some", sharedActivities: ["focus"], scoringVersion: "rules-v2", profileVersion: 1, peerVersion: 1,
  };
  await mockDiscovery(page, { published: true, candidates: [card] });
  await page.route("**/api/v1/profiles/published/current", (route) => route.fulfill({ json: { id: "p", profile: card.profile, version: 1, state: "live", profileVersion: 1 } }));
  await page.route("**/api/v1/connection-requests", (route) =>
    route.request().method() === "POST" ? route.fulfill({ status: 201, json: { id: "req-1" } }) : route.fulfill({ json: [] }));
  await page.goto("/#/connect");
  const shown = page.getByLabel("Hồ sơ của Bạn đồng hành 7c1e02");
  await shown.getByRole("button", { name: "Gửi lời mời kết nối" }).click();
  await expect(page.getByText("Đã gửi lời mời kết nối.", { exact: true })).toBeVisible();
  await expect(shown).toContainText("Đã gửi lời mời kết nối");
});
