import { expect, test } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { api } from "./helpers";
import { createGuest, guestCall, publicEntry } from "./guest-support";

test.beforeEach(async ({ request }) => { expect((await request.post("http://127.0.0.1:5174/__test/reset-admission")).ok()).toBe(true); });

test("public disclosure creates independent anonymous guests with fixed deadlines and no social access", async ({ browser }, testInfo) => {
  const first = await browser.newContext();
  const second = await browser.newContext();
  try {
    const page = await first.newPage();
    const one = await publicEntry(page);
    const two = await createGuest(second);
    expect(one.accountKind).toBe("guest");
    expect(two.userId).not.toBe(one.userId);
    expect(Date.parse(one.guestExpiresAt) - Date.parse(one.guestStartedAt)).toBe(7200000);
    expect(["AI", "MEM", "VOICE"].every(purpose => one.consents[purpose].enabled)).toBe(true);
    expect(one.consents.MATCH.enabled).toBe(false);
    for (const context of [first, second]) {
      for (const path of ["/matching/candidates", "/connections", "/connection-requests"]) {
        const denied = await guestCall(context, "GET", path);
        expect(denied.status(), path).toBe(403);
        expect((await denied.json()).error.code).toBe("REGISTERED_REQUIRED");
      }
    }
    const day = one.serverTime.slice(0, 10);
    expect((await guestCall(first, "PUT", `/moods/${day}`, { value: 4, note: "GUEST-ONE-PRIVATE", timezone: "Asia/Bangkok", expectedVersion: 0 })).status()).toBe(200);
    expect(await (await second.request.get(api + "/moods")).text()).not.toContain("GUEST-ONE-PRIVATE");
    await page.setViewportSize({ width: 320, height: 900 });
    await page.goto("/#/settings");
    const data = page.getByRole("region", { name: "Tài khoản & hỗ trợ" });
    await expect(page.getByRole("heading", { name: "Cá nhân", exact: true })).toBeVisible();
    await expect(page.getByText(/ngày để bạn tiếp tục trên thiết bị khác/)).toHaveCount(0);
    // The UI must use the guest confirmation path, never password reauthentication.
    await expect(page.getByRole("button", { name: "Tải bản sao dữ liệu", exact: true })).toHaveCount(0);
    await expect(data.getByRole("button", { name: "Kết thúc và xóa lượt dùng thử", exact: true })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    expect((await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze()).violations).toEqual([]);
    await page.screenshot({ path: testInfo.outputPath("guest-export-320.png"), fullPage: true });
    await expect(page.getByLabel("Mật khẩu", { exact: true })).toHaveCount(0);
    expect((await guestCall(first, "POST", "/auth/guest/end", {})).status()).toBe(204);
    expect((await first.request.get(api + "/session")).status()).toBe(401);
    expect((await second.request.get(api + "/session")).status()).toBe(200);
    await first.clearCookies();
    const fresh = await createGuest(first);
    expect(fresh.userId).not.toBe(one.userId);
    expect(Date.parse(fresh.guestExpiresAt)).toBeGreaterThan(Date.parse(one.guestExpiresAt));
    // Ordinary signup goes through production Auth routes; no anonymous identity conversion.
    expect((await guestCall(first, "PUT", `/moods/${day}`, { value: 3, note: "FRESH-GUEST-PRIVATE", timezone: "Asia/Bangkok", expectedVersion: 0 })).status()).toBe(200);
    const credentials = { email: `guest-conversion-${crypto.randomUUID()}@example.invalid`, password: "local-mvp-synthetic" };
    expect((await guestCall(first, "POST", "/auth/signup", credentials)).status()).toBe(202);
    expect((await (await first.request.get(api + "/session")).json()).userId).toBe(fresh.userId);
    expect((await guestCall(first, "POST", "/auth/logout", {})).status()).toBe(204);
    const login = await guestCall(first, "POST", "/auth/login", credentials);
    expect(login.status(), await login.text()).toBe(200);
    const registered = await login.json();
    expect(registered.accountKind).toBe("registered");
    expect(registered.userId).not.toBe(fresh.userId);
    expect((await guestCall(first, "PUT", "/users/me/eligibility", { birthYear: 2000, confirmedMinimumAge: true, confirmedAdultAge: false, policyVersion: "self-declared-age-v1", expectedVersion: 0 })).status()).toBe(200);
    expect(await (await first.request.get(api + "/moods")).json()).toEqual([]);
  } finally { await first.close(); await second.close(); }
});
