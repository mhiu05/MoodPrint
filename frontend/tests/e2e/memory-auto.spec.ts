import { expect, test } from "@playwright/test";
import { app, baseSession } from "./ux-fixtures";

test("automatic memories show their source and support versioned edits, deletion and confirmed bulk removal", async ({ page }) => {
  const source = "22222222-2222-4222-8222-222222222222";
  const tea = "44444444-4444-4444-8444-444444444444";
  const walk = "55555555-5555-4555-8555-555555555555";
  const approved = "66666666-6666-4666-8666-666666666666";
  const receipt = { actionId: "77777777-7777-4777-8777-777777777777", resourceId: "journal_auto", resourceVersion: 1 };
  let rows = [
    { id: tea, botId: "nhatky", text: "Bạn thích trà xanh.", version: 1, status: "active", origin: "journal_auto", sourceEntryId: source, sourceLocalDate: "2026-11-04" },
    { id: walk, botId: "nhatky", text: "Bạn đi bộ vào buổi sáng.", version: 1, status: "active", origin: "journal_auto", sourceEntryId: source, sourceLocalDate: "2026-11-04" },
    { id: approved, botId: "nhatky", text: "Bạn thích vẽ tranh.", version: 1, status: "active", origin: "approved", sourceEntryId: null, sourceLocalDate: null },
  ];
  const seen = { patches: [] as any[], deletes: [] as any[], bulk: [] as any[], journalDeletes: 0 };
  await app(page, { ...baseSession, serverTime: "2026-11-04T08:00:00Z", features: { ...baseSession.features, threeAgents: true } }, {
    "/memories": () => ({ json: rows }),
    [`/memories/${tea}`]: request => {
      const body = request.postDataJSON();
      if (request.method() === "PATCH") {
        seen.patches.push(body);
        rows = rows.map(row => row.id === tea ? { ...row, text: body.text, version: row.version + 1 } : row);
        return { json: rows.find(row => row.id === tea) };
      }
      if (request.method() === "DELETE") {
        seen.deletes.push(body);
        rows = rows.filter(row => row.id !== tea);
        return { json: { ...receipt, resourceId: tea, resourceVersion: 3 } };
      }
    },
    "/memories/auto": request => {
      seen.bulk.push({ body: request.postDataJSON(), key: request.headers()["idempotency-key"] });
      rows = rows.filter(row => row.origin !== "journal_auto");
      return { json: receipt };
    },
    [`/journal/entries/${source}`]: request => {
      if (request.method() === "DELETE") seen.journalDeletes++;
      return { json: { id: source, localDate: "2026-11-04", timezone: "Asia/Bangkok", mood: 3,
        emotions: [], factors: [], text: "SYNTHETIC_MEMORY_SOURCE", status: "saved", version: 1,
        createdAt: "2026-11-04T08:00:00Z", updatedAt: "2026-11-04T08:00:00Z", media: [] } };
    },
  });
  await page.goto("/#/memory");
  await expect(page.locator("article").getByText("Tự động từ nhật ký", { exact: true })).toHaveCount(2);
  await page.getByRole("link", { name: "Xem trang 04/11/2026", exact: true }).first().click();
  await expect(page).toHaveURL(new RegExp(`/self/entry/${source}`));
  await expect(page.getByText("SYNTHETIC_MEMORY_SOURCE", { exact: true })).toBeVisible();
  await page.goto("/#/memory");
  const item = page.locator("article").filter({ hasText: "Bạn thích trà xanh." });
  await item.getByRole("button", { name: "Sửa", exact: true }).click();
  await page.getByRole("textbox", { name: "Sửa ghi nhớ" }).fill("Bạn thích trà nóng vào buổi sáng.");
  await page.getByRole("button", { name: "Lưu thay đổi" }).click();
  await expect(page.getByText("Bạn thích trà nóng vào buổi sáng.", { exact: true })).toBeVisible();
  expect(seen.patches).toEqual([{ text: "Bạn thích trà nóng vào buổi sáng.", expectedVersion: 1 }]);
  const changed = page.locator("article").filter({ hasText: "Bạn thích trà nóng vào buổi sáng." });
  await changed.getByRole("button", { name: "Xóa ghi nhớ", exact: true }).click();
  expect(seen.deletes).toHaveLength(0);
  await changed.getByRole("button", { name: "Xóa ghi nhớ này", exact: true }).click();
  await expect(page.getByText("Bạn thích trà nóng vào buổi sáng.", { exact: true })).toHaveCount(0);
  expect(seen.deletes).toEqual([{ expectedVersion: 2 }]);
  await page.getByRole("button", { name: "Xóa mọi ghi nhớ tự động", exact: true }).click();
  const dialog = page.getByRole("dialog", { name: "Xóa ghi nhớ tự động" });
  await expect(dialog.getByText("Xóa 1 ghi nhớ tự động? Trang nhật ký không bị ảnh hưởng.")).toBeVisible();
  await expect(dialog.getByRole("button", { name: "Giữ lại" })).toBeFocused();
  expect(seen.bulk).toHaveLength(0);
  await dialog.getByRole("button", { name: "Giữ lại" }).click();
  await page.getByRole("button", { name: "Xóa mọi ghi nhớ tự động", exact: true }).click();
  await dialog.getByRole("button", { name: "Xóa ghi nhớ tự động", exact: true }).click();
  await expect(page.locator("article").getByText("Tự động từ nhật ký", { exact: true })).toHaveCount(0);
  await expect(page.getByText("Bạn thích vẽ tranh.", { exact: true })).toBeVisible();
  expect(seen.bulk).toHaveLength(1);
  expect(seen.bulk[0].body).toEqual({});
  expect(seen.bulk[0].key).toBeTruthy();
  expect(seen.journalDeletes).toBe(0);
});
