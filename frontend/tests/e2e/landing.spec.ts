import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page, type Request } from "@playwright/test";
import { baseSession } from "./ux-fixtures";

const READY = {
  guestAvailable: true,
  guestUnavailableReason: null,
  feedbackAvailable: false,
  productTourAvailable: false,
  captchaSiteKey: "public-site-key",
};
const CLOSED = { ...READY, guestAvailable: false, guestUnavailableReason: "disabled", captchaSiteKey: null };

/** Records every API call; the landing may read readiness/session but never create anything. */
async function serve(page: Page, experience: unknown, session: unknown = null) {
  const requests: Request[] = [];
  await page.route("**/api/v1/**", async (route) => {
    const request = route.request();
    requests.push(request);
    const path = new URL(request.url()).pathname.replace("/api/v1", "");
    if (path === "/public/experience") return route.fulfill({ json: experience });
    if (path === "/session")
      return session
        ? route.fulfill({ json: session })
        : route.fulfill({ status: 401, json: { error: { code: "AUTH_REQUIRED", message: "Cần đăng nhập" } } });
    return route.fulfill({ status: 404, json: { error: { code: "NOT_FOUND", message: "Missing fixture" } } });
  });
  return requests;
}

const CREATION = /\/api\/v1\/auth\/(guest|guest-intents|login|signup)/;

test("public root works with the API offline and sends nothing that creates an identity", async ({ page }) => {
  const attempted: string[] = [];
  await page.route("**/api/v1/**", (route) => {
    attempted.push(`${route.request().method()} ${route.request().url()}`);
    return route.abort("connectionrefused");
  });
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Hiểu mình hơn, kết nối chân thành hơn." }),
  ).toBeVisible();
  for (const name of ["Mây", "Gương", "Nhịp", "Rủ Rê", "Cầu Nối"])
    await expect(page.getByRole("heading", { name, exact: true })).toBeVisible();
  await expect(page.getByText("Chưa thể bắt đầu lượt dùng thử. Thử lại sau.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Dùng thử 2 giờ" }).first()).toBeDisabled();
  await expect(page.getByRole("link", { name: "Đăng nhập / Đăng ký" })).toBeVisible();
  expect(attempted.filter((entry) => CREATION.test(entry) || entry.startsWith("POST"))).toEqual([]);
});

test("loading the page sends no guest-intent, signup or create request", async ({ page }) => {
  const requests = await serve(page, READY);
  await page.goto("/");
  await expect(page.getByRole("button", { name: "Dùng thử 2 giờ" }).first()).toBeEnabled();
  await page.waitForTimeout(300);
  expect(requests.filter((request) => request.method() !== "GET")).toHaveLength(0);
  expect(requests.filter((request) => CREATION.test(request.url()))).toHaveLength(0);
  const paths = requests.map((request) => new URL(request.url()).pathname.replace("/api/v1", ""));
  expect(new Set(paths)).toEqual(new Set(["/public/experience", "/session"]));
});

test("the guest CTA stays unavailable until readiness says the trial is configured", async ({ page }) => {
  await serve(page, CLOSED);
  await page.goto("/");
  await expect(page.getByText("Chưa thể bắt đầu lượt dùng thử. Thử lại sau.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Dùng thử 2 giờ" }).first()).toBeDisabled();
});

test("a registered visitor sees Continue and the session is untouched", async ({ page }) => {
  const requests = await serve(page, READY, baseSession);
  await page.goto("/");
  const link = page.getByRole("link", { name: "Tiếp tục sử dụng" });
  await expect(link).toBeVisible();
  await expect(link).toHaveAttribute("href", "/#/assistants");
  await expect(page.getByRole("button", { name: "Dùng thử 2 giờ" }).first()).toBeDisabled();
  expect(requests.filter((request) => request.method() !== "GET")).toHaveLength(0);
});

test("keyboard users reach the skip link, the menu and every FAQ answer", async ({ page }) => {
  await serve(page, READY);
  await page.goto("/");
  await page.keyboard.press("Tab");
  await expect(page.getByRole("link", { name: "Đến nội dung chính" })).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.locator("#noi-dung")).toBeFocused();
  const summary = page.getByText("Hết 2 giờ thì sao?");
  await summary.focus();
  await page.keyboard.press("Enter");
  await expect(page.getByText("dữ liệu của lượt này không mở lại được")).toBeVisible();
  await expect(page.getByText("Tìm bạn và nhắn tin cần tài khoản").first()).toBeAttached();
});

for (const width of [320, 390, 768, 1440]) {
  test(`landing has no horizontal overflow and no axe violations at ${width}px and 200% text`, async ({ page }) => {
    await serve(page, READY);
    await page.setViewportSize({ width, height: 900 });
    await page.goto("/");
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    const overflow = () => page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(await overflow()).toBeLessThanOrEqual(0);
    const axe = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze();
    expect(axe.violations.map((violation) => violation.id)).toEqual([]);
    await page.addStyleTag({ content: "html{font-size:200%}" });
    expect(await overflow()).toBeLessThanOrEqual(0);
  });
}

test("reduced motion does not hide or delay public content", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await serve(page, READY);
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Nhật ký cảm xúc" })).toBeVisible();
});

test("an unknown real path is a public not-found page, not the app", async ({ page }) => {
  const requests = await serve(page, READY);
  await page.goto("/khong-co-trang-nay");
  await expect(page.getByRole("heading", { name: "Không tìm thấy trang" })).toBeVisible();
  expect(requests).toHaveLength(0);
});
