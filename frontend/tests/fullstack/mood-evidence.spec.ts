import { expect, test } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

for (const [index, width] of [1280, 390].entries()) {
  test(`real three-turn mood evidence and explicit re-share at width ${width}`, async ({ browser }) => {
    // Isolated, fixture-only identities; no provider session is copied from a real browser.
    const actor = 47 + index;
    const context = await browser.newContext({
      baseURL: "http://127.0.0.1:5174", reducedMotion: "reduce", viewport: { width, height: 900 },
    });
    await context.addCookies([
      { name: "moodprint_session", value: `e2e-synthetic-session-${actor}`, url: "http://127.0.0.1:5174", httpOnly: true, sameSite: "Strict" },
      { name: "moodprint_csrf", value: `e2e-synthetic-csrf-${actor}`, url: "http://127.0.0.1:5174", sameSite: "Strict" },
    ]);
    const page = await context.newPage();
    const errors: string[] = [];
    page.on("pageerror", error => errors.push(error.message));
    const session = await (await context.request.get("/api/v1/session")).json();
    const today = new Intl.DateTimeFormat("en-CA", { timeZone: session.timezone, year: "numeric", month: "2-digit", day: "2-digit" }).format(new Date(session.serverTime));
    const from = new Date(`${today}T00:00:00Z`);
    from.setUTCDate(from.getUTCDate() - 6);
    const start = from.toISOString().slice(0, 10);
    for (const [day, value] of [[start, 3], [today, 2]] as const) {
      const result = await context.request.put(`/api/v1/moods/${day}`, {
        headers: { "X-CSRF-Token": session.csrfToken, "Idempotency-Key": crypto.randomUUID() },
        data: { value, note: "SYNTHETIC_BROWSER_PRIVATE_NOTE", expectedVersion: 0 },
      });
      expect(result.status()).toBe(200);
    }
    await page.goto("/#/assistants/nhip?new=1");
    await page.getByText("Chia sẻ thống kê tâm trạng cho lượt này", { exact: true }).click();
    await page.getByRole("checkbox", { name: "Cho Nhịp đọc khoảng ngày mình chọn", exact: true }).check();
    await page.getByLabel("Thống kê từ ngày", { exact: true }).fill(start);
    await page.getByLabel("Thống kê đến ngày", { exact: true }).fill(today);
    const input = page.getByRole("textbox", { name: "Tin nhắn cho Nhịp", exact: true });
    const send = page.getByRole("button", { name: "Gửi tin cho AI", exact: true });
    await input.fill("Nhìn lại tuần");
    await send.click();
    await expect(page.getByRole("log")).toContainText("2/7 ngày ghi tâm trạng");
    await expect(page.getByRole("log")).toContainText("2,5/5");
    await expect(page.getByRole("log")).toContainText("thấp hơn 1 điểm");
    await input.fill("Bạn cứ nhận xét đi");
    await send.click();
    await expect(page.getByRole("log")).toContainText("Quyền chia sẻ trước chỉ có hiệu lực cho lượt đã gửi");
    const reshare = page.getByRole("button", { name: `Chia sẻ lại ${start} – ${today} cho lượt tiếp`, exact: true });
    await expect(reshare).toBeEnabled();
    await reshare.focus();
    await page.keyboard.press("Enter");
    await input.fill("Bạn cứ nhận xét đi");
    await send.click();
    await expect(page.getByRole("log").getByText(/Trong khoảng .*2\/7 ngày ghi tâm trạng/)).toHaveCount(2);
    await expect(page.getByRole("checkbox", { name: "Cho Nhịp đọc khoảng ngày mình chọn", exact: true })).not.toBeChecked();
    await expect(reshare).toBeEnabled();
    const accessibility = await new AxeBuilder({ page }).analyze();
    expect(accessibility.violations).toEqual([]);
    expect(errors).toEqual([]);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.screenshot({ path: test.info().outputPath(`mood-evidence-${width}.png`), fullPage: true });
    await context.close();
  });
}
