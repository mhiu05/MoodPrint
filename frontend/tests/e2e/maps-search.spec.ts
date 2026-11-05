import { expect, test } from "@playwright/test";
import { field, JOB, openSearch, searchFixture, send } from "./search-fixtures";

test("Maps card resolves async; reuse edits next turn and persists normalized places", async ({ page }) => {
  const seen = await searchFixture(page);
  await openSearch(page);
  await page.getByRole("button", { name: "Thêm kỹ năng hoặc công cụ" }).click();
  await page.getByRole("button", { name: "Maps Search Tìm kiếm công khai" }).click();
  await page.getByRole("textbox", { name: "Khu vực", exact: true }).fill("Quận 3");
  await send(page, "Tìm quán cà phê");
  await expect(page.getByRole("link", { name: "Mở Google Maps" })).toBeVisible();
  await page.getByRole("button", { name: "Nhờ trợ lý gợi ý từ kết quả" }).click();
  await expect(field(page)).toHaveValue("Gợi ý giúp mình từ các địa điểm vừa tìm.");
  expect(seen.sends).toHaveLength(1);
  await page.getByRole("button", { name: "Gửi tin cho AI", exact: true }).click();
  await expect(field(page)).toHaveValue("");
  expect(seen.sends[1].promptOptions.mapsSearchId).toBe(JOB);
  await expect(page.getByRole("region", { name: "Địa điểm đã dùng cho gợi ý" })).toBeVisible();
  await page.reload();
  await expect(page.getByRole("region", { name: "Địa điểm đã dùng cho gợi ý" })).toBeVisible();
});
test("missing area asks without creating a job card", async ({ page }) => {
  const seen = await searchFixture(page);
  await openSearch(page);
  await page.getByRole("button", { name: "Thêm kỹ năng hoặc công cụ" }).click();
  await page.getByRole("button", { name: "Maps Search Tìm kiếm công khai" }).click();
  await send(page, "Tìm quán gần mình");
  await expect(page.getByText("Bạn muốn tìm ở khu vực nào?", { exact: true })).toBeVisible();
  expect(seen.mapsReads).toBe(0);
});

async function findPlaces(page: import("@playwright/test").Page) {
  await openSearch(page);
  await page.getByRole("button", { name: "Thêm kỹ năng hoặc công cụ" }).click();
  await page.getByRole("button", { name: "Maps Search Tìm kiếm công khai" }).click();
  await page.getByRole("textbox", { name: "Khu vực", exact: true }).fill("Quận 3");
  await send(page, "Tìm quán cà phê");
}

test("deferred tool-selection focus does not steal an area already being edited", async ({ page }) => {
  const seen = await searchFixture(page);
  await openSearch(page);
  await page.getByRole("button", { name: "Thêm kỹ năng hoặc công cụ" }).click();
  const maps = page.getByRole("button", { name: "Maps Search Tìm kiếm công khai" });
  await maps.evaluate(button => button.addEventListener("click", () => {
    const actual = window.requestAnimationFrame.bind(window);
    const pending: FrameRequestCallback[] = [];
    window.requestAnimationFrame = callback => { pending.push(callback); return pending.length; };
    (window as any).__releaseSelectionFrames = () => {
      window.requestAnimationFrame = actual;
      for (const callback of pending.splice(0)) callback(performance.now());
    };
  }, { capture: true, once: true }));
  await maps.click();
  const area = page.getByRole("textbox", { name: "Khu vực", exact: true });
  await area.focus();
  await page.evaluate(() => (window as any).__releaseSelectionFrames());
  await expect(area).toBeFocused();
  await page.keyboard.insertText("Quận 3");
  await expect(area).toHaveValue("Quận 3");
  await send(page, "Tìm quán cà phê");
  expect(seen.sends).toHaveLength(1);
  expect(seen.sends[0].promptOptions).toMatchObject({ tools: ["maps_search"], area: "Quận 3" });
  await expect(page.getByRole("link", { name: "Mở Google Maps" })).toBeVisible();
});

test("an expired or revoked Maps result offers a fresh turn instead of a dead reload loop", async ({ page }) => {
  await searchFixture(page, { mapsOutcome: "gone" });
  await findPlaces(page);
  const card = page.getByRole("region", { name: "Kết quả tìm địa điểm" });
  await expect(card).toContainText("Kết quả không còn khả dụng");
  await expect(card).toContainText("một lượt mới");
  await expect(card.getByRole("button", { name: "Thử tải lại" })).toHaveCount(0);
  await expect(card.getByRole("button", { name: "Nhờ trợ lý gợi ý từ kết quả" })).toHaveCount(0);
  await page.reload();
  await expect(card).toContainText("Kết quả không còn khả dụng");
});

test("a Maps network failure retries the same job and keyboard reuse only edits the draft on mobile", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  const seen = await searchFixture(page, { mapsOutcome: "offlineOnce" });
  await findPlaces(page);
  const retry = page.getByRole("button", { name: "Thử tải lại" });
  await expect(retry).toBeVisible();
  const readsBeforeRetry = seen.mapsReads;
  seen.restoreMaps();
  await retry.focus(); await page.keyboard.press("Enter");
  await expect(page.getByRole("link", { name: "Mở Google Maps" })).toBeVisible();
  const reuse = page.getByRole("button", { name: "Nhờ trợ lý gợi ý từ kết quả" });
  await reuse.focus(); await page.keyboard.press("Enter");
  await expect(field(page)).toHaveValue("Gợi ý giúp mình từ các địa điểm vừa tìm.");
  expect(seen.sends).toHaveLength(1);
  expect(seen.mapsReads).toBe(readsBeforeRetry + 1);
  await page.goto("/#/profile"); await page.goBack();
  await expect(page.getByRole("link", { name: "Mở Google Maps" })).toBeVisible();
  expect(seen.sends).toHaveLength(1);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});

for (const outcome of ["empty", "failed", "timed_out"] as const) {
  test(`Maps ${outcome} never fabricates places or restarts a paid search`, async ({ page }) => {
    const seen = await searchFixture(page, { mapsOutcome: outcome });
    await findPlaces(page);
    const card = page.getByRole("region", { name: "Kết quả tìm địa điểm" });
    await expect(card).toContainText(outcome === "empty" ? "Chưa tìm thấy địa điểm phù hợp" : "Không tự chạy lại lượt trả phí");
    await expect(card.getByRole("link")).toHaveCount(0);
    expect(seen.sends).toHaveLength(1);
  });
}

test("cancelling a pending Maps job does not send another chat turn", async ({ page }) => {
  const seen = await searchFixture(page, { mapsOutcome: "pending" });
  await findPlaces(page);
  await expect(page.getByRole("button", { name: "Dừng tìm địa điểm", exact: true })).toBeVisible();
  const readsBeforeCancel = seen.mapsReads;
  await page.getByRole("button", { name: "Dừng tìm địa điểm", exact: true }).click();
  await expect(page.getByRole("region", { name: "Kết quả tìm địa điểm" })).toContainText("Đã yêu cầu dừng");
  expect(seen.mapsCancels).toBe(1);
  expect(seen.sends).toHaveLength(1);
  await page.waitForTimeout(2200); // Observe beyond the pending card's next 2s poll.
  expect(seen.mapsReads).toBe(readsBeforeCancel);
});
