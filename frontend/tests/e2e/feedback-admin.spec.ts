import { expect, test, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { app, baseSession, guestSession } from "./ux-fixtures";

const id = "33333333-3333-4333-8333-333333333333";
const row = { id, rating: 1, categories: ["bug"], comment: "<script>private-canary</script>", context: "general", accountKind: "guest", disclosureVersion: "feedback-v1", appVersion: "test-v1", createdAt: baseSession.serverTime, status: "new", version: 1, reviewedAt: null };
const summary = { count: 2, meanRating: 3, ratingCounts: { "1": 1, "2": 0, "3": 0, "4": 0, "5": 1 }, categoryCounts: { bug: 1 }, accountKindCounts: { guest: 1, registered: 1 }, byDate: [{ date: "2026-10-23", count: 2, meanRating: 3 }], byVersion: [{ appVersion: "test-v1", count: 2, meanRating: 3 }] };
const admin = { ...baseSession, staff: "admin", features: { ...baseSession.features, ai: false } };

async function setup(page: Page, value: unknown = admin, options: { empty?: boolean; conflict?: boolean; reauth?: boolean; revoked?: boolean } = {}) {
  const calls: { path: string; method: string; body: unknown; query: string }[] = [];
  let current = { ...row };
  let reauthenticated = !options.reauth;
  let revoked = false;
  await app(page, value, {
    "/admin/feedback": () => {
      if (!reauthenticated) return { status: 403, json: { error: { code: "REAUTH_REQUIRED", message: "Vui lòng xác nhận lại mật khẩu." } } };
      if (revoked) return { status: 403, json: { error: { code: "STAFF_REQUIRED", message: "Bạn không có quyền xem góp ý." } } };
      return { json: { items: options.empty ? [] : [current], nextCursor: null } };
    },
    "/admin/feedback/summary": () => reauthenticated
      ? { json: options.empty ? { ...summary, count: 0, meanRating: null, ratingCounts: { "1": 0, "2": 0, "3": 0, "4": 0, "5": 0 }, categoryCounts: {}, accountKindCounts: { guest: 0, registered: 0 }, byDate: [], byVersion: [] } : summary }
      : { status: 403, json: { error: { code: "REAUTH_REQUIRED", message: "Vui lòng xác nhận lại mật khẩu." } } },
    [`/admin/feedback/${id}`]: (request) => {
      if (request.method() !== "PATCH") return undefined;
      if (options.revoked) { revoked = true; return { status: 403, json: { error: { code: "STAFF_REQUIRED", message: "Bạn không có quyền xem góp ý." } } }; }
      if (options.conflict) { current = { ...current, status: "reviewed", version: 2 }; return { status: 409, json: { error: { code: "STALE_VERSION", message: "Góp ý đã thay đổi." } } }; }
      current = { ...current, status: request.postDataJSON().status, version: current.version + 1 };
      return { json: current };
    },
    "/auth/reauthenticate": () => { reauthenticated = true; return { json: { message: "OK" } }; },
  });
  page.on("request", (request) => {
    if (!request.url().includes("/api/v1/")) return;
    const url = new URL(request.url());
    calls.push({ path: url.pathname.replace("/api/v1", ""), method: request.method(), body: request.postData() ? request.postDataJSON() : null, query: url.search });
  });
  return calls;
}

test("guest even with forged staff and normal user direct dashboard make no admin request", async ({ page }) => {
  const calls = await setup(page, guestSession(7_000_000, { staff: "admin" }));
  await page.goto("/#/admin/feedback");
  await expect(page.getByRole("alert")).toContainText("Chưa thể xác minh phiên.");
  expect(calls.filter((call) => call.path.startsWith("/admin/feedback"))).toHaveLength(0);
  await setup(page, guestSession(7_000_000));
  await page.reload();
  await expect(page.getByText("Bạn không có quyền xem góp ý.", { exact: true })).toBeVisible();
  expect(calls.filter((call) => call.path.startsWith("/admin/feedback"))).toHaveLength(0);
  await setup(page, { ...baseSession, staff: null });
  await page.reload();
  await expect(page.getByText("Bạn không có quyền xem góp ý.", { exact: true })).toBeVisible();
});

test("admin sees sample counts, matching filters, escaped comment and versioned status", async ({ page }) => {
  const calls = await setup(page);
  await page.goto("/#/admin/feedback");
  await expect(page.getByRole("heading", { name: "Góp ý và đánh giá" })).toBeVisible();
  await expect(page.getByText("<script>private-canary</script>", { exact: true })).toBeVisible();
  await expect(page.getByText("2 góp ý", { exact: true })).toBeVisible();
  await expect(page.getByLabel("1 điểm: 1 góp ý")).toBeVisible();
  await page.getByLabel("Phiên bản ứng dụng", { exact: true }).fill("test-v2");
  await page.getByRole("button", { name: "Áp dụng bộ lọc" }).click();
  await expect.poll(() => calls.filter((call) => call.path.startsWith("/admin/feedback") && call.query.includes("appVersion=test-v2")).length).toBeGreaterThanOrEqual(2);
  await page.getByLabel(`Trạng thái góp ý ${id}`).selectOption("reviewed");
  await page.getByRole("button", { name: `Lưu trạng thái ${id}` }).click();
  await expect(page.getByRole("status").filter({ hasText: "Đã cập nhật trạng thái góp ý." })).toBeVisible();
  expect(calls.find((call) => call.method === "PATCH")?.body).toEqual({ status: "reviewed", expectedVersion: 1 });
  expect(calls.filter((call) => /^\/(ai\/conversations|moods|memories)/.test(call.path))).toHaveLength(0);
});

test("empty feedback has null mean and no invented rating", async ({ page }) => {
  await setup(page, admin, { empty: true });
  await page.goto("/#/admin/feedback");
  await expect(page.getByText("Chưa có đánh giá", { exact: true })).toBeVisible();
  await expect(page.getByText("Không có góp ý trong bộ lọc này.", { exact: true })).toBeVisible();
  await expect(page.getByText("0/5", { exact: true })).toHaveCount(0);
});

test("temporary dashboard read failure retries without exposing stale comments", async ({ page }) => {
  await setup(page);
  let unavailable = true;
  await page.route(/\/api\/v1\/admin\/feedback(?:\?.*)?$/, (route) => unavailable
    ? route.fulfill({ status: 503, json: { error: { code: "UNAVAILABLE", message: "Chưa thể tải góp ý." } } })
    : route.fallback());
  await page.goto("/#/admin/feedback");
  await expect(page.getByRole("alert")).toContainText("Chưa thể tải góp ý.");
  await expect(page.getByText("<script>private-canary</script>", { exact: true })).toHaveCount(0);
  unavailable = false;
  await page.getByRole("button", { name: "Thử lại", exact: true }).click();
  await expect(page.getByText("<script>private-canary</script>", { exact: true })).toBeVisible();
});

test("load more carries cursor and appends the next bounded page", async ({ page }) => {
  const calls = await setup(page);
  await page.route(/\/api\/v1\/admin\/feedback(?:\?.*)?$/, (route) => {
    const next = new URL(route.request().url()).searchParams.get("cursor");
    return route.fulfill({ json: next
      ? { items: [{ ...row, id: "44444444-4444-4444-8444-444444444444", comment: "Góp ý thứ hai" }], nextCursor: null }
      : { items: [row], nextCursor: "next-page" } });
  });
  await page.goto("/#/admin/feedback");
  await page.getByRole("button", { name: "Xem thêm góp ý", exact: true }).click();
  await expect(page.getByText("Góp ý thứ hai", { exact: true })).toBeVisible();
  await expect(page.getByText("<script>private-canary</script>", { exact: true })).toBeVisible();
  expect(calls.some((call) => call.path === "/admin/feedback" && call.query.includes("cursor=next-page"))).toBe(true);
  await expect(page.getByRole("button", { name: "Xem thêm góp ý", exact: true })).toHaveCount(0);
});

test("step-up reauthentication retries without logging out", async ({ page }) => {
  const calls = await setup(page, admin, { reauth: true });
  await page.goto("/#/admin/feedback");
  await expect(page.getByRole("heading", { name: "Xác nhận tài khoản" })).toBeVisible();
  await page.getByLabel("Email", { exact: true }).fill("synthetic@example.invalid");
  await page.getByLabel("Mật khẩu", { exact: true }).fill("synthetic-only");
  await page.getByRole("button", { name: "Xác nhận", exact: true }).click();
  await expect(page.getByText("<script>private-canary</script>", { exact: true })).toBeVisible();
  expect(calls.filter((call) => call.path === "/auth/logout")).toHaveLength(0);
});

test("stale status reload preserves focus and role revocation clears comments", async ({ page }) => {
  await setup(page, admin, { conflict: true });
  await page.goto("/#/admin/feedback");
  const save = page.getByRole("button", { name: `Lưu trạng thái ${id}` });
  await page.getByLabel(`Trạng thái góp ý ${id}`).selectOption("planned");
  await save.click();
  await expect(page.getByRole("status").filter({ hasText: /Góp ý đã thay đổi/ })).toBeVisible();
  await expect(save).toBeFocused();
  await expect(page.getByLabel(`Trạng thái góp ý ${id}`)).toHaveValue("reviewed");
  await setup(page, admin, { revoked: true });
  await page.reload();
  await page.getByLabel(`Trạng thái góp ý ${id}`).selectOption("planned");
  await save.click();
  await expect(page.getByText("Bạn không có quyền xem góp ý.", { exact: true })).toBeVisible();
  await expect(page.getByText("<script>private-canary</script>", { exact: true })).toHaveCount(0);
});

for (const width of [320, 1440]) {
  test(`dashboard keyboard and 200% text at ${width}px`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width, height: 900 });
    await page.emulateMedia({ reducedMotion: "reduce" });
    await setup(page);
    await page.goto("/#/admin/feedback");
    await expect(page.getByText("<script>private-canary</script>", { exact: true })).toBeVisible();
    await page.addStyleTag({ content: "html { font-size: 200% !important; }" });
    const layout = await page.evaluate(() => ({
      width: document.documentElement.scrollWidth, viewport: innerWidth,
      outside: Array.from(document.querySelectorAll("body *")).filter((element) => element.getBoundingClientRect().right > innerWidth + 1).slice(0, 12).map((element) => ({ tag: element.tagName, class: element.className, width: element.getBoundingClientRect().width, right: element.getBoundingClientRect().right })),
    }));
    expect(layout.width <= layout.viewport, JSON.stringify(layout)).toBe(true);
    await expect(page.getByRole("region", { name: "Danh sách góp ý, có thể cuộn ngang" })).toHaveAttribute("tabindex", "0");
    expect((await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze()).violations).toEqual([]);
    await page.screenshot({ path: testInfo.outputPath(`feedback-admin-${width}.png`), fullPage: true });
  });
}
