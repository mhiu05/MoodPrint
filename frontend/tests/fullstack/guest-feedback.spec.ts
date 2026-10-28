import { expect, test } from "@playwright/test";
import { api, call, session } from "./helpers";
import { createGuest, guestCall } from "./guest-support";

test.beforeEach(async ({ request }) => { expect((await request.post("http://127.0.0.1:5174/__test/reset-admission")).ok()).toBe(true); });

test("guest rating survives unlinking and expiry while receipt and private data are purged", async ({ browser }) => {
  const guest = await browser.newContext();
  const admin = await browser.newContext();
  try {
    const owner = await createGuest(guest);
    const page = await guest.newPage();
    await page.goto("/#/feedback");
    await page.getByRole("radio", { name: "4 Hài lòng", exact: true }).check();
    await page.getByLabel("Chia sẻ thêm nếu bạn muốn").fill("SYNTHETIC-GUEST-RATING");
    await page.getByRole("button", { name: "Gửi góp ý", exact: true }).click();
    await expect(page.getByText("Cảm ơn bạn. MoodPrint đã nhận góp ý.")).toBeVisible();
    const state = await (await guest.request.get(api + "/feedback/submission-state")).json();
    expect(state.submitted).toBe(true);
    expect((await guestCall(guest, "POST", "/auth/guest/end", {})).status()).toBe(204);
    await session(admin, 49);
    const reviewed = await call(admin, 49, "GET", "/admin/feedback?accountKind=guest");
    expect(reviewed.status).toBe(200);
    expect(reviewed.text).toContain("SYNTHETIC-GUEST-RATING");
    expect(reviewed.text).not.toContain(owner.userId);
    // Pre-existing guest near T is seeded with the SAME immutable 7200-second lifetime.
    const near = await guest.request.post("http://127.0.0.1:5174/__test/near-expiry");
    expect(near.status()).toBe(200);
    const seed = await near.json();
    await guest.addCookies(seed.cookies);
    await page.goto("/#/self");
    await page.reload(); // new cookie identity must be read from the real session endpoint
    await expect(page.getByRole("heading", { name: "Lượt dùng thử đã kết thúc" })).toBeVisible({ timeout: 15000 });
    expect((await guest.request.get(api + "/session")).status()).toBe(401);
    const purge = await guest.request.post("http://127.0.0.1:5174/__test/purge");
    expect(purge.status()).toBe(200);
    expect((await purge.json()).remainingExpired).toBe(0);
  } finally { await guest.close(); await admin.close(); }
});
