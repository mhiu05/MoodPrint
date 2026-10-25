import { expect, test, type Page } from "@playwright/test";

const TAXONOMY = {
  version: "v2",
  interests: { reading: "Đọc sách", music: "Âm nhạc", walking: "Đi bộ" },
  values: { respect: "Tôn trọng", sincerity: "Chân thành" },
  languages: { vi: "Tiếng Việt" },
  styles: { balanced: "Cân bằng" },
  goals: { friendship: "Tìm bạn trò chuyện" },
  activities: { focus: "Cùng tập trung" },
  availability: { weekday_evening: "Tối ngày thường" },
  categories: { learning: ["reading"], creative: ["music"], active: ["walking"] },
  categoryLabels: { learning: "Học hỏi", creative: "Sáng tạo", active: "Vận động" },
  limits: { interests: [3, 10], values: [2, 4], languages: [1, 2], activities: [0, 4], availability: [0, 6] },
};
const PROFILE = {
  interests: ["reading", "music", "walking"],
  values: ["respect", "sincerity"],
  style: "balanced",
  goal: "friendship",
  languages: ["vi"],
  activities: [],
  availability: [],
  strictGoal: false,
};

type Options = { live?: boolean; incoming?: number; ageBand?: string };

async function mock(page: Page, { live = false, incoming = 0, ageBand = "adult" }: Options = {}) {
  const session = {
    userId: "11111111-1111-4111-8111-111111111111",
    alias: "An",
    ageBand,
    eligible: true,
    csrfToken: "test-csrf",
    serverTime: "2026-10-23T08:00:00Z",
    timezone: "Asia/Bangkok",
    features: { ai: false, matching: true, voice: false },
    staff: null,
    notices: [],
    consents: Object.fromEntries(
      ["AI", "MEM", "MATCH", "VOICE"].map((p) => [
        p,
        { enabled: p === "MATCH" && ageBand === "adult", version: 1, policyVersion: "v1" },
      ]),
    ),
  };
  const requests = Array.from({ length: incoming }, (_, index) => ({
    id: `req-${index}`,
    status: "pending",
    version: 1,
    direction: "incoming",
    expiresAt: "2026-10-30T08:00:00Z",
    peer: { alias: `Bạn đồng hành 00000${index}`, avatarSeed: `seed${index}`, profile: PROFILE, reasons: [], matchLabel: "some", sharedActivities: [] },
  }));
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname.replace("/api/v1", "");
    const json: Record<string, unknown> = {
      "/session": session,
      "/social/summary": { pendingIncomingRequests: incoming, unreadConnections: 0, activityInvites: 0 },
      "/taxonomy": TAXONOMY,
      "/profiles/matching-draft": { profile: PROFILE, version: 1, publishedVersion: live ? 1 : null },
      "/profiles/published/current": live
        ? { id: "p", profile: PROFILE, version: 1, state: "live", profileVersion: 1 }
        : null,
      "/matching/candidates": { candidates: [] },
      "/connection-requests": requests,
      "/bots": [],
      "/ai/conversations": [],
    };
    if (path in json) return route.fulfill({ json: json[path] });
    return route.fulfill({ status: 404, json: { error: { code: "NOT_FOUND", message: "Missing" } } });
  });
}

test("discovery tabs follow the arrow keys and keep the tab in the URL", async ({ page }) => {
  await mock(page);
  await page.goto("/#/connect");
  const tabs = page.getByRole("tablist", { name: "Tìm bạn" });
  const profile = tabs.getByRole("tab", { name: "Hồ sơ kết nối" });
  // Without a live profile the editor tab comes first.
  await expect(profile).toHaveAttribute("aria-selected", "true");
  await expect(page.getByRole("tabpanel", { name: "Hồ sơ kết nối" })).toContainText(
    "Chỉnh hồ sơ kết nối",
  );
  await profile.focus();
  await page.keyboard.press("ArrowRight");
  const suggestions = tabs.getByRole("tab", { name: "Gợi ý" });
  await expect(suggestions).toBeFocused();
  await expect(suggestions).toHaveAttribute("aria-selected", "true");
  await expect(page).toHaveURL(/#\/connect\?tab=suggestions$/);
  await expect(page.getByRole("tabpanel", { name: "Gợi ý" })).toContainText(
    "Hãy xuất bản hồ sơ kết nối để nhận gợi ý.",
  );
  await page.keyboard.press("End");
  await expect(profile).toBeFocused();
  await page.keyboard.press("Home");
  await expect(suggestions).toBeFocused();
  await page.keyboard.press("ArrowLeft");
  await expect(profile).toBeFocused();
  await page.keyboard.press("ArrowLeft");
  await expect(tabs.getByRole("tab", { name: /Lời mời/ })).toBeFocused();
  await expect(page).toHaveURL(/tab=requests$/);
  // Only the selected tab is in the tab order.
  await expect(tabs.locator('[tabindex="0"]')).toHaveCount(1);
  await page.reload();
  await expect(tabs.getByRole("tab", { name: /Lời mời/ })).toHaveAttribute("aria-selected", "true");
  await page.goto("/#/messages");
  await page.goBack();
  await expect(tabs.getByRole("tab", { name: /Lời mời/ })).toHaveAttribute("aria-selected", "true");
});

test("pending invitations badge the nav and the tab, and the nav opens them", async ({ page }) => {
  await mock(page, { live: true, incoming: 2 });
  await page.goto("/#/assistants");
  const nav = page.getByRole("navigation", { name: "Điều hướng chính" });
  const connect = nav.getByRole("link", { name: "Tìm bạn, 2 lời mời kết nối mới" });
  await expect(connect).toHaveAttribute("href", "#/connect?tab=requests");
  await connect.click();
  const tab = page.getByRole("tab", { name: "Lời mời (2)" });
  await expect(tab).toHaveAttribute("aria-selected", "true");
  await expect(page.getByRole("tabpanel", { name: "Lời mời (2)" })).toContainText(
    "Bạn đồng hành 000000 muốn kết nối với bạn",
  );
  await page.goto("/#/connect");
  // A live profile opens on suggestions when no tab is named.
  await expect(page.getByRole("tab", { name: "Gợi ý" })).toHaveAttribute("aria-selected", "true");
});

test("the profile nudge shows only for adults without a live profile", async ({ page }) => {
  await mock(page);
  await page.goto("/#/assistants");
  const nudge = page.getByRole("link", { name: /Sẵn sàng tìm người cùng tần số\?/ });
  await expect(nudge).toContainText("Tạo hồ sơ kết nối");
  await expect(nudge).toHaveAttribute("href", "#/connect?tab=profile");
  await nudge.click();
  await expect(page.getByRole("tab", { name: "Hồ sơ kết nối" })).toHaveAttribute("aria-selected", "true");
});

test("a live profile keeps the plain bridge link instead of the nudge", async ({ page }) => {
  await mock(page, { live: true });
  await page.goto("/#/assistants");
  await expect(page.getByRole("link", { name: /Từ hiểu mình/ })).toHaveAttribute("href", "#/connect");
  await expect(page.getByText("Sẵn sàng tìm người cùng tần số?")).toHaveCount(0);
});

test("minors never see the nudge", async ({ page }) => {
  await mock(page, { ageBand: "teen" });
  await page.goto("/#/assistants");
  await expect(page.getByRole("link", { name: /Từ hiểu mình/ })).toBeVisible();
  await expect(page.getByText("Sẵn sàng tìm người cùng tần số?")).toHaveCount(0);
});
