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
  await expect(page.getByRole("heading", { name: "Bắt đầu với MoodPrint" })).toBeVisible();
  await expect(page.getByText("Chưa thể bắt đầu lượt dùng thử. Thử lại sau.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Dùng thử 2 giờ" })).toBeDisabled();
  await expect(page.getByRole("link", { name: "Tạo tài khoản" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Đăng nhập", exact: true })).toBeVisible();
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
  await expect(page.getByRole("button", { name: "Dùng thử 2 giờ" })).toHaveCount(0);
  expect(requests.filter((request) => request.method() !== "GET")).toHaveLength(0);
});

test("keyboard users reach the skip link, the menu and every FAQ answer", async ({ page }) => {
  await serve(page, READY);
  await page.goto("/");
  await page.keyboard.press("Tab");
  await expect(page.getByRole("link", { name: "Đến nội dung chính" })).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.locator("#main")).toBeFocused();
  await expect(page.getByRole("button", { name: "Dùng thử 2 giờ" })).toBeEnabled();
  await expect(page.getByRole("link", { name: "Tạo tài khoản" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Đăng nhập", exact: true })).toBeVisible();
});

test("readiness keeps trial text readable throughout the disabled-to-enabled color change", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "no-preference" });
  await page.setViewportSize({ width: 390, height: 900 });
  await serve(page, READY);
  let release!: () => void;
  const ready = new Promise<void>(resolve => { release = resolve; });
  await page.route("**/api/v1/public/experience", async route => {
    await ready;
    await route.fulfill({ json: READY });
  });
  try {
    await page.goto("/");
    await expect(page.getByRole("button", { name: "Dùng thử 2 giờ" }).first()).toBeDisabled();
    await page.evaluate(() => {
      const buttons = [...document.querySelectorAll<HTMLButtonElement>(".home button")];
      buttons.forEach(button => { void getComputedStyle(button).backgroundColor; });
      const observer = new MutationObserver(() => {
        if (buttons.some(button => button.disabled)) return;
        const transitions = buttons.flatMap(button => button.getAnimations());
        transitions.forEach(animation => animation.pause());
        (window as any).__readinessTransitions = transitions;
        observer.disconnect();
      });
      buttons.forEach(button => observer.observe(button, { attributes: true, attributeFilter: ["disabled"] }));
    });
    release();
    await expect.poll(() => page.evaluate(() => Array.isArray((window as any).__readinessTransitions))).toBe(true);
    for (const progress of [0.25, 0.5, 0.75]) {
      await page.evaluate(progress => {
        for (const animation of (window as any).__readinessTransitions as Animation[]) {
          animation.currentTime = Number(animation.effect!.getTiming().duration) * progress;
        }
      }, progress);
      const axe = await new AxeBuilder({ page }).include(".home").withTags(["wcag2a", "wcag2aa"]).analyze();
      expect(axe.violations.map(v => v.id), JSON.stringify({ progress, violations: axe.violations }, null, 2)).toEqual([]);
    }
  } finally { release(); }
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
    expect(axe.violations.map((violation) => violation.id), JSON.stringify(axe.violations, null, 2)).toEqual([]);
    await page.addStyleTag({ content: "html{font-size:200%}" });
    expect(await overflow()).toBeLessThanOrEqual(0);
  });
}

test("reduced motion does not hide or delay public content", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await serve(page, READY);
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Bắt đầu với MoodPrint" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Dùng thử 2 giờ" })).toBeEnabled();
});

test("an unknown real path is a public not-found page, not the app", async ({ page }) => {
  const requests = await serve(page, READY);
  await page.goto("/khong-co-trang-nay");
  await expect(page.getByRole("heading", { name: "Không tìm thấy trang" })).toBeVisible();
  expect(requests).toHaveLength(0);
});
