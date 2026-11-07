import { test, expect } from "./helpers/fixtures";
import { createUser, login, removeUser, signOut } from "./helpers/local";

test("E-DEMO-02: existing demo data survives a real session without entering the real account", async ({
  page,
}) => {
  const user = await createUser();
  try {
    await page.goto("/auth");
    await page
      .getByRole("button", { name: "Vào thử với tài khoản demo" })
      .click();
    await expect(page).toHaveURL(/\/home$/);
    await page.goto("/settings");
    await page
      .getByRole("button", { name: "Đăng xuất demo", exact: true })
      .click();
    await expect(page).toHaveURL(/\/auth$/);
    const demo = await page.evaluate(() =>
      localStorage.getItem("moodprint-demo"),
    );
    expect(demo).not.toBeNull();
    const payloads: string[] = [];
    page.on("request", (request) => {
      if (request.url().includes(":8008/") && request.postData())
        payloads.push(request.postData()!);
    });
    await login(page, user.email);
    await expect(page).toHaveURL(/\/(home|settings)$/);
    await page.goto("/cases");
    await expect(page.locator(".case-card")).toHaveCount(0);
    await expect(
      page.getByRole("heading", {
        name: "Mỗi câu chuyện có thể bắt đầu từ một dòng",
        exact: true,
      }),
    ).toBeVisible();
    await expect(page.getByText("CASE-AN-001")).toHaveCount(0);
    expect(
      await page.evaluate(() => localStorage.getItem("moodprint-demo")),
    ).toBe(demo);
    expect(
      payloads.some((payload) =>
        /CASE-AN-|mock_fixture|demo_submitted/.test(payload),
      ),
    ).toBe(false);
    await signOut(page);
    expect(
      await page.evaluate(() => localStorage.getItem("moodprint-demo")),
    ).toBe(demo);
    await page
      .getByRole("button", { name: "Vào thử với tài khoản demo" })
      .click();
    await page.goto("/cases/CASE-AN-001");
    await expect(page.getByRole("heading", { level: 1 })).not.toHaveText(
      "Không tìm thấy hồ sơ",
    );
  } finally {
    await removeUser(user.email);
  }
});
