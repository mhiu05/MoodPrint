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
