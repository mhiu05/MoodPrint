import { test, expect } from "./helpers/fixtures";
import {
  apiJson,
  createUser,
  login,
  removeUser,
  tokenFor,
} from "./helpers/local";

test("E-EV-04: cancelling an actual pending TUS upload removes its evidence", async ({
  page,
}) => {
  const user = await createUser();
  let release!: () => void;
  const held = new Promise<void>((resolve) => {
    release = resolve;
  });
  try {
    await login(page, user.email);
    await expect(page).toHaveURL(/\/home$/);
    await page.goto("/cases/new");
    await page.getByRole("button", { name: /Nguồn đính kèm/ }).click();
    let pending = false;
    await page.route("**/storage/v1/upload/resumable/**", async (route) => {
      if (route.request().method() !== "PATCH") {
        await route.fallback();
        return;
      }
      pending = true;
      await held;
      await route.abort("aborted");
    });
    await page.getByLabel("Chọn tệp bằng chứng").setInputFiles({
      name: "synthetic-cancelled.txt",
      mimeType: "text/plain",
      buffer: Buffer.alloc(1024 * 1024, 0x62),
    });
    await expect.poll(() => pending).toBe(true);
    await page.getByRole("button", { name: "Hủy tải", exact: true }).click();
    await expect(
      page.getByRole("status").filter({ hasText: "Đã hủy" }),
    ).toBeVisible();
    release();
    await expect(page.locator(".evidence-attachments li")).toHaveCount(0);
    const response = await apiJson("/v1/evidence", await tokenFor(user.email));
    expect(response.status).toBe(200);
    expect((await response.json()).items).toEqual([]);
  } finally {
    release();
    await removeUser(user.email);
  }
});
