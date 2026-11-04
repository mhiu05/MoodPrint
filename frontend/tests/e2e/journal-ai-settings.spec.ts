import { expect, test } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { app, baseSession, guestSession } from "./ux-fixtures";

const initial = { embeddingEnabled: true, autoMemoryEnabled: true, embeddingAvailable: false,
  autoMemoryAvailable: false, noticeVersion: "journal-ai-v1", version: 1,
  indexedEntries: 7, pendingEntries: 2, autoMemories: 0 };

for (const width of [1440, 390]) {
  test(`journal opt-out notice, unavailable save and reload at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    let view = { ...initial };
    await app(page, baseSession, {
      "/journal/ai-settings": request => {
        if (request.method() === "PUT") {
          expect(request.postDataJSON()).toEqual({ embeddingEnabled: false, autoMemoryEnabled: true,
            noticeVersion: "journal-ai-v1", expectedVersion: 1 });
          view = { ...view, embeddingEnabled: false, version: 2, indexedEntries: 0, pendingEntries: 0 };
        }
        return { json: view };
      },
    });
    await page.goto("/#/profile");
    const section = page.getByRole("region", { name: "Nhật ký và trợ lý AI" });
    await expect(section.getByText(/Voyage AI/)).toBeVisible();
    await expect(section.getByText(/Bản sao ở nhà cung cấp/)).toBeVisible();
    const toggle = section.getByRole("checkbox", { name: "Tìm theo ý nghĩa trong nhật ký", exact: true });
    await expect(toggle).toBeChecked();
    await expect(section.getByText(/Đã lập chỉ mục 7 trang/)).toBeVisible();
    await toggle.uncheck();
    await expect(section.getByText("Đã lưu tùy chọn nhật ký.")).toBeVisible();
    await page.reload();
    await expect(toggle).not.toBeChecked();
    await expect(section.getByRole("checkbox")).toHaveCount(1);
    expect((await new AxeBuilder({ page }).include('[aria-labelledby="journal-ai-heading"]').analyze()).violations).toEqual([]);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
  });
}

test("guest account never requests journal derivation preferences", async ({ page }) => {
  const requests: string[] = [];
  page.on("request", request => { if (request.url().includes("/journal/ai-settings")) requests.push(request.url()); });
  await app(page, guestSession(7_000_000));
  await page.goto("/#/profile");
  await expect(page.getByRole("heading", { name: "Nhật ký và trợ lý AI" })).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "Tài khoản", exact: true })).toBeVisible();
  expect(requests).toEqual([]);
});
