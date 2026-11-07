import AxeBuilder from "@axe-core/playwright";
import { test, expect } from "./helpers/fixtures";
import {
  createCaseViaApi,
  createUser,
  followEmail,
  login,
  password,
  removeUser,
  signOut,
} from "./helpers/local";

test("E-AUTH-03: an unauthenticated case deep link returns to that case after real login", async ({
  page,
}) => {
  const user = await createUser();
  try {
    const item = await createCaseViaApi(user.email);
    await page.goto(`/cases/${item.id}`);
    await expect(page).toHaveURL(/\/auth$/);
    await login(page, user.email);
    await expect(page).toHaveURL(new RegExp(`/cases/${item.id}$`));
    await expect(
      page.getByRole("heading", { name: "Hồ sơ tổng hợp", exact: true }),
    ).toBeVisible();
    await page.reload();
    await expect(page).toHaveURL(new RegExp(`/cases/${item.id}$`));
    // Wait until the reloaded case is visible before account cleanup.
    // Cleanup sets deletion_started_at immediately, so an in-flight GET would 409.
    await expect(
      page.getByRole("heading", { name: "Hồ sơ tổng hợp", exact: true }),
    ).toBeVisible();
  } finally {
    await removeUser(user.email);
  }
});

test.describe("Expected Auth validation errors", () => {
  test.use({ expectedHttpStatuses: [400] });
  test("E-AUTH-04: wrong password shows a Vietnamese error and keeps login available", async ({
    page,
  }) => {
    const user = await createUser();
    try {
      await login(page, user.email, "Wrong-synthetic-42!");
      await expect(
        page.getByText(
          "Chưa thể đăng nhập. Kiểm tra thông tin hoặc dùng chức năng quên mật khẩu.",
          { exact: true },
        ),
      ).toBeVisible();
      await expect(page).toHaveURL(/\/auth$/);
      await page.getByLabel("Mật khẩu", { exact: true }).fill(password);
      await page
        .locator("form")
        .filter({
          has: page.getByRole("textbox", { name: "Email", exact: true }),
        })
        .getByRole("button", { name: "Đăng nhập", exact: true })
        .click();
      await expect(page).toHaveURL(/\/home$/);
    } finally {
      await removeUser(user.email);
    }
  });
});

test("Password recovery follows a local email link and updates the real Auth password", async ({
  page,
}) => {
  test.setTimeout(60000);
  const user = await createUser();
  const replacement = "Synthetic-recovered-43!";
  let changed = false;
  try {
    await page.goto("/auth");
    await page
      .getByRole("button", { name: "Quên mật khẩu?", exact: true })
      .click();
    await page
      .getByRole("textbox", { name: "Email", exact: true })
      .fill(user.email);
    await page
      .getByRole("button", {
        name: "Gửi hướng dẫn đặt lại mật khẩu",
        exact: true,
      })
      .click();
    await expect(page.getByRole("status")).toContainText("Nếu địa chỉ phù hợp");
    await followEmail(page, user.email, "recovery");
    await expect(page).toHaveURL(/\/auth\/reset(?:[?#].*)?$/);
    await page.getByLabel("Mật khẩu mới", { exact: true }).fill(replacement);
    await page
      .getByRole("button", { name: "Lưu mật khẩu", exact: true })
      .click();
    await expect(
      page.getByText("Mật khẩu đã được cập nhật.", { exact: true }),
    ).toBeVisible();
    changed = true;
    await signOut(page);
    await login(page, user.email, replacement);
    await expect(page).toHaveURL(/\/settings$/);
  } finally {
    await removeUser(user.email, changed ? replacement : password);
  }
});

test("N-01 N-02: Auth and recovery fit mobile/desktop and pass serious WCAG A/AA axe rules", async ({
  page,
}) => {
  for (const width of [320, 390, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    for (const path of ["/auth", "/auth/reset"]) {
      await page.goto(path);
      await expect(
        page.getByRole("heading", { level: 1 }).first(),
      ).toBeVisible();
      expect(
        await page.evaluate(() => document.documentElement.scrollWidth),
      ).toBeLessThanOrEqual(width);
      const results = await new AxeBuilder({ page })
        .withTags(["wcag2a", "wcag2aa"])
        .analyze();
      expect(
        results.violations.filter((violation) =>
          ["critical", "serious"].includes(violation.impact ?? ""),
        ),
      ).toEqual([]);
    }
  }
});

test("N-02: real account deletion confirmation passes serious axe rules", async ({
  page,
}) => {
  const user = await createUser();
  try {
    await login(page, user.email);
    await expect(page).toHaveURL(/\/home$/);
    await page.goto("/settings");
    await page
      .getByRole("button", { name: "Xóa tài khoản", exact: true })
      .click();
    await expect(page.getByRole("dialog")).toBeVisible();
    const results = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa"])
      .analyze();
    expect(
      results.violations.filter((violation) =>
        ["critical", "serious"].includes(violation.impact ?? ""),
      ),
    ).toEqual([]);
  } finally {
    await removeUser(user.email);
  }
});
