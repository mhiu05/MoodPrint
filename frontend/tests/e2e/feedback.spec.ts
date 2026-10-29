import { expect, test, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { app, baseSession, guestSession } from "./ux-fixtures";

const receipt = { feedbackId: "33333333-3333-4333-8333-333333333333", createdAt: baseSession.serverTime, status: "received" };
const session = { ...baseSession, features: { ...baseSession.features, feedback: true } };

async function setup(page: Page, value: unknown = session, submitted = false) {
  const requests: { body: unknown; key: string | undefined }[] = [];
  await app(page, value, {
    "/feedback/submission-state": () => ({ json: { submitted, lastSubmittedAt: submitted ? baseSession.serverTime : null } }),
    "/feedback": (request) => {
      if (request.method() !== "POST") return undefined;
      requests.push({ body: request.postDataJSON(), key: request.headers()["idempotency-key"] });
      return { status: 201, json: receipt };
    },
  });
  return requests;
}

test("rating-only submits with no preselected or private fields", async ({ page }) => {
  const requests = await setup(page);
  await page.goto("/#/feedback");
  const group = page.getByRole("group", { name: "Bạn thấy MoodPrint thế nào?" });
  await expect(group.getByRole("radio", { checked: true })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Gửi góp ý", exact: true })).toBeDisabled();
  await group.getByRole("radio", { name: "4 Hài lòng", exact: true }).check();
  await page.getByRole("button", { name: "Gửi góp ý", exact: true }).click();
  await expect(page.getByRole("status").filter({ hasText: "Cảm ơn bạn. MoodPrint đã nhận góp ý." })).toBeVisible();
  expect(requests).toHaveLength(1);
  expect(requests[0].body).toEqual({ rating: 4, categories: [], comment: null, context: "general", disclosureVersion: "feedback-v1" });
  await expect(page.getByText(receipt.feedbackId, { exact: true })).toBeVisible();
});

test("keyboard rating and optional plain text categories preserve Unicode codepoint bounds", async ({ page }) => {
  const requests = await setup(page);
  await page.goto("/#/feedback");
  const first = page.getByRole("radio", { name: "1 Rất chưa hài lòng", exact: true });
  await first.focus();
  await page.keyboard.press("ArrowRight");
  await expect(page.getByRole("radio", { name: "2 Chưa hài lòng", exact: true })).toBeChecked();
  await page.getByRole("checkbox", { name: "Lỗi gặp phải", exact: true }).check();
  const comment = page.getByRole("textbox", { name: "Chia sẻ thêm nếu bạn muốn" });
  await comment.fill("😀".repeat(1000));
  await expect(page.getByText("1000/1000 ký tự", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Gửi góp ý", exact: true })).toBeEnabled();
  await comment.fill("😀".repeat(1001));
  await expect(page.getByRole("button", { name: "Gửi góp ý", exact: true })).toBeDisabled();
  await comment.fill("<script>private-canary</script>");
  await page.getByRole("button", { name: "Gửi góp ý", exact: true }).click();
  await expect(page.getByText(receipt.feedbackId, { exact: true })).toBeVisible();
  expect(requests[0].body).toMatchObject({ rating: 2, categories: ["bug"], comment: "<script>private-canary</script>" });
  expect(await page.evaluate(() => (window as any)["private-canary"])).toBeUndefined();
});

test("busy duplicate is refused and transient retry keeps the same key and draft", async ({ page }) => {
  await setup(page);
  const calls: { key?: string; body: unknown }[] = [];
  await page.route("**/api/v1/feedback", async (route) => {
    calls.push({ key: route.request().headers()["idempotency-key"], body: route.request().postDataJSON() });
    if (calls.length === 1) {
      await new Promise((resolve) => setTimeout(resolve, 200));
      return route.fulfill({ status: 503, json: { error: { code: "FEEDBACK_UNAVAILABLE", message: "Chưa thể gửi góp ý.", retryable: true } } });
    }
    return route.fulfill({ status: 201, json: receipt });
  });
  await page.goto("/#/feedback");
  await page.getByRole("radio", { name: "3 Bình thường", exact: true }).check();
  await page.getByRole("textbox", { name: "Chia sẻ thêm nếu bạn muốn" }).fill("Bản nháp tự nguyện");
  await page.getByRole("button", { name: "Gửi góp ý", exact: true }).click();
  await expect(page.getByRole("button", { name: "Đang gửi…", exact: true })).toBeDisabled();
  await expect(page.getByRole("alert")).toContainText("Chưa thể gửi góp ý.");
  await expect(page.getByRole("textbox", { name: "Chia sẻ thêm nếu bạn muốn" })).toHaveValue("Bản nháp tự nguyện");
  await page.getByRole("button", { name: "Gửi góp ý", exact: true }).click();
  await expect(page.getByText(receipt.feedbackId, { exact: true })).toBeVisible();
  expect(calls).toHaveLength(2);
  expect(calls[0].key).toBeTruthy();
  expect(calls[0]).toEqual(calls[1]);
});

test("guest expiry clears draft and no persistent browser draft exists", async ({ page }) => {
  await page.clock.install({ time: new Date() });
  await setup(page, guestSession(60_000, { features: { ai: false, matching: false, voice: false, feedback: true } }));
  await page.goto("/#/feedback");
  await page.getByRole("textbox", { name: "Chia sẻ thêm nếu bạn muốn" }).fill("private-draft-canary");
  await page.clock.fastForward(61_000);
  await expect(page.getByRole("heading", { name: "Lượt dùng thử đã kết thúc" })).toBeVisible();
  expect(await page.evaluate(() => JSON.stringify([localStorage, sessionStorage]))).not.toContain("private-draft-canary");
  await expect(page.getByRole("textbox")).toHaveCount(0);
});

test("malformed success is not presented as a received submission", async ({ page }) => {
  await setup(page);
  await page.route("**/api/v1/feedback", (route) => route.fulfill({ status: 201, json: {} }));
  await page.goto("/#/feedback");
  await page.getByRole("radio", { name: "3 Bình thường", exact: true }).check();
  await page.getByRole("button", { name: "Gửi góp ý", exact: true }).click();
  await expect(page.getByRole("alert")).toBeVisible();
  await expect(page.getByText("Cảm ơn bạn. MoodPrint đã nhận góp ý.", { exact: true })).toHaveCount(0);
});

test("closed collection and already submitted guest show truthful states", async ({ page }) => {
  await setup(page, baseSession);
  await page.goto("/#/feedback");
  await expect(page.getByText("MoodPrint chưa mở nhận góp ý.", { exact: true })).toBeVisible();
  await setup(page, guestSession(7_000_000, { features: { ai: false, matching: false, voice: false, feedback: true } }), true);
  await page.reload();
  await expect(page.getByText("Bạn đã gửi góp ý trong lượt dùng thử này.", { exact: true })).toBeVisible();
  await expect(page.getByRole("radio")).toHaveCount(0);
});

test("no-session feedback explains entry without creating an identity", async ({ page }) => {
  let mutations = 0;
  await app(page, null, { "/session": () => ({ status: 401, json: { error: { code: "AUTH_REQUIRED" } } }) });
  page.on("request", (request) => { if (request.method() === "POST") mutations++; });
  await page.goto("/#/feedback");
  await expect(page.getByRole("heading", { name: "Góp ý cho MoodPrint" })).toBeVisible();
  await expect(page.getByText(/lượt dùng thử đang hoạt động hoặc đăng nhập/)).toBeVisible();
  expect(mutations).toBe(0);
});

for (const width of [320, 390, 1440]) {
  test(`feedback accessible and fits at ${width}px with 200% text`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width, height: 900 });
    await setup(page);
    await page.goto("/#/feedback");
    await expect(page.getByRole("radio")).toHaveCount(5);
    await page.addStyleTag({ content: "html { font-size: 200% !important; }" });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    const result = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze();
    expect(result.violations).toEqual([]);
    await page.screenshot({ path: testInfo.outputPath(`feedback-${width}.png`), fullPage: true });
  });
}
