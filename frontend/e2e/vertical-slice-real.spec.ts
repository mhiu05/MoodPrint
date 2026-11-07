import { randomUUID } from "node:crypto";
import AxeBuilder from "@axe-core/playwright";
import { test, expect, guardNetwork } from "./helpers/fixtures";
import {
  apiJson,
  createUser,
  followEmail,
  login,
  password,
  removeUser,
  settings,
  signOut,
  tokenFor,
} from "./helpers/local";

test("E-AUTH-01 E-CASE-01 E-EV-03 E-PLAN-02: confirmed account → six-step wizard → 20 MB TUS resume → persistent plan → isolated B", async ({
  page,
  browser,
  baseURL,
}) => {
  test.setTimeout(180000);
  const email = `e2e+${randomUUID()}@example.test`;
  const userB = await createUser("Gió tổng hợp");
  let registered = false;
  const title = `Nhóm chat hư cấu ${randomUUID().slice(0, 8)}`;
  try {
    await page.goto("/auth");
    await page.getByRole("button", { name: "Đăng ký", exact: true }).click();
    await page
      .getByRole("textbox", { name: "Bí danh", exact: true })
      .fill("Mây tổng hợp");
    await page.getByRole("textbox", { name: "Email", exact: true }).fill(email);
    await page.getByLabel("Mật khẩu", { exact: true }).fill(password);
    const signup = page.waitForResponse(
      (response) =>
        response.url().includes("/auth/v1/signup") &&
        response.request().method() === "POST",
    );
    await page
      .getByRole("button", { name: "Tạo tài khoản", exact: true })
      .click();
    expect((await signup).status()).toBe(200);
    registered = true;
    await expect(page.getByRole("status")).toContainText("Kiểm tra email");
    await expect(page).toHaveURL(/\/auth$/);
    await followEmail(page, email, "signup");
    await expect(page).toHaveURL(/\/home$/, { timeout: 15000 });
    await signOut(page);
    await login(page, email);
    await expect(page).toHaveURL(/\/settings$/);
    await page.goto("/home");
    await expect(page.getByRole("heading", { level: 1 })).toContainText(
      "Mây tổng hợp",
    );
    await expect(page.getByText("CASE-AN-001")).toHaveCount(0);

    await page.goto("/cases/new");
    await expect(page.getByText("Bước 1/6", { exact: true })).toBeVisible();
    await page.getByRole("textbox", { name: "Đặt tên hồ sơ" }).fill(title);
    await page.getByRole("button", { name: "Tiếp tục", exact: true }).click();
    await page
      .getByRole("textbox", { name: "Chuyện gì đã xảy ra?" })
      .fill(
        "Một nhóm học sinh hư cấu gửi tin trêu chọc trong bài tập mô phỏng.",
      );
    await page.getByRole("button", { name: "Lưu nháp", exact: true }).click();
    await expect(page).toHaveURL(/\/cases\/[0-9a-f-]{36}$/);
    const caseUrl = page.url();
    const id = new URL(caseUrl).pathname.split("/").pop()!;
    await page.reload();
    await expect(page.getByRole("heading", { level: 1 })).toHaveText(title);
    await page
      .getByRole("link", { name: "Bổ sung hồ sơ", exact: true })
      .click();
    await page.getByRole("button", { name: /Chuyện xảy ra/ }).click();
    await expect(
      page.getByRole("textbox", { name: "Chuyện gì đã xảy ra?" }),
    ).toHaveValue(/hư cấu/);
    await page.getByRole("button", { name: "Tiếp tục", exact: true }).click();
    await expect(page.getByText("Bước 3/6", { exact: true })).toBeVisible();
    await page
      .getByRole("textbox", { name: "Những người liên quan" })
      .fill("Bạn A, bạn B (bí danh hư cấu)");
    await page.getByRole("button", { name: "Tiếp tục", exact: true }).click();
    await expect(page.getByText("Bước 4/6", { exact: true })).toBeVisible();
    await page
      .getByRole("checkbox", { name: "Khó tập trung", exact: true })
      .check();
    await page.getByRole("button", { name: "Tiếp tục", exact: true }).click();
    await expect(page.getByText("Bước 5/6", { exact: true })).toBeVisible();
    const accessibility = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa"])
      .analyze();
    expect(
      accessibility.violations.filter((violation) =>
        ["serious", "critical"].includes(violation.impact ?? ""),
      ),
    ).toEqual([]);

    // Hold the second real PATCH so the first 6 MB chunk reaches Storage before pause.
    let patches = 0;
    let release!: () => void;
    const held = new Promise<void>((resolve) => {
      release = resolve;
    });
    await page.route("**/storage/v1/upload/resumable/**", async (route) => {
      if (route.request().method() === "PATCH" && ++patches === 2) await held;
      await route.fallback();
    });
    const file = Buffer.alloc(20 * 1024 * 1024, 0x61);
    await page.getByLabel("Chọn tệp bằng chứng").setInputFiles({
      name: "synthetic-20mb.txt",
      mimeType: "text/plain",
      buffer: file,
    });
    await expect
      .poll(() => patches, { timeout: 20000 })
      .toBeGreaterThanOrEqual(2);
    await page.getByRole("button", { name: "Tạm dừng", exact: true }).click();
    await expect(
      page.getByRole("status").filter({ hasText: "Đã tạm dừng" }),
    ).toBeVisible();
    release();
    const resumed = page.waitForResponse(
      (response) =>
        response.request().method() === "HEAD" &&
        response.url().includes("/storage/v1/upload/resumable/"),
    );
    await page
      .getByRole("button", { name: "Tiếp tục tải", exact: true })
      .click();
    expect((await resumed).headers()["upload-offset"]).toBe(
      String(6 * 1024 * 1024),
    );
    await expect(
      page.getByRole("status").filter({ hasText: "Đã tải xong" }),
    ).toBeVisible({ timeout: 30000 });
    expect(patches).toBeGreaterThanOrEqual(4);
    await page.unroute("**/storage/v1/upload/resumable/**");
    await expect(page.locator(".evidence-attachments li")).toHaveCount(1);
    await page.getByRole("button", { name: "Tiếp tục", exact: true }).click();
    await expect(page.getByText("Bước 6/6", { exact: true })).toBeVisible();
    await page.getByRole("button", { name: "Lưu hồ sơ", exact: true }).click();
    await expect(page).toHaveURL(caseUrl);

    await page
      .getByRole("link", { name: "Dòng thời gian", exact: true })
      .click();
    await page.getByRole("button", { name: "Thêm mốc", exact: true }).click();
    await page
      .getByRole("textbox", { name: "Điều đã xảy ra", exact: true })
      .fill("Mốc bổ sung hoàn toàn tổng hợp.");
    await page.getByRole("button", { name: "Lưu mốc", exact: true }).click();
    await expect(page.locator(".case-timeline li")).toHaveCount(2);
    await page.getByRole("button", { name: /Sửa mốc Mốc bổ sung/ }).click();
    await page
      .getByRole("textbox", { name: "Điều đã xảy ra", exact: true })
      .fill("Mốc tổng hợp đã sửa.");
    await page.getByRole("button", { name: "Lưu mốc", exact: true }).click();
    await expect(page.locator(".case-timeline")).toContainText(
      "Mốc tổng hợp đã sửa.",
    );
    await page
      .getByRole("link", { name: "Kế hoạch ứng phó", exact: true })
      .click();
    await page
      .getByRole("button", { name: "Chọn phương án này" })
      .first()
      .click();
    await page
      .getByRole("button", { name: "Lưu kế hoạch", exact: true })
      .filter({ visible: true })
      .first()
      .click();
    await expect(page.locator(".plan-save button")).toBeDisabled();
    await page.goto("/home");
    const checkbox = page.locator(".home-check input").first();
    await checkbox.click();
    await expect(checkbox).toBeChecked();
    await page.reload();
    await expect(checkbox).toBeChecked();

    const token = await tokenFor(email);
    const detail = await (await apiJson(`/v1/cases/${id}`, token)).json();
    expect(detail.status).toBe("active");
    expect(detail.evidenceIds).toHaveLength(1);
    const evidence = await (
      await apiJson(`/v1/evidence/${detail.evidenceIds[0]}`, token)
    ).json();
    expect(evidence.byteSize).toBe(file.length);
    expect(evidence.uploadStatus).toBe("uploaded");
    const signed = await (
      await apiJson(`/v1/evidence/${evidence.id}/download-url`, token)
    ).json();
    expect(new URL(signed.url).origin).toBe(
      new URL(settings().supabase).origin,
    );
    const download = await fetch(signed.url);
    expect(download.status).toBe(200);
    expect(Buffer.from(await download.arrayBuffer()).equals(file)).toBe(true);

    const second = await browser.newContext({ baseURL });
    const forbidden = await guardNetwork(second, true, baseURL);
    try {
      const other = await second.newPage();
      await login(other, email);
      await expect(other).toHaveURL(/\/home$/);
      await expect(other.locator(".home-check input").first()).toBeChecked();
      await other.goto(`${caseUrl}/timeline`);
      await expect(other.locator(".case-timeline li")).toHaveCount(2);
      await expect(other.locator(".case-timeline")).toContainText(
        "Mốc tổng hợp đã sửa.",
      );
      expect(forbidden).toEqual([]);
    } finally {
      await second.close();
    }

    await signOut(page);
    await login(page, userB.email);
    await expect(page).toHaveURL(/\/settings$/);
    await page.goto("/home");
    await expect(page.getByText(title, { exact: true })).toHaveCount(0);
    await page.goto(caseUrl);
    await expect(
      page.getByRole("heading", {
        name: "Không tìm thấy hồ sơ",
        exact: true,
        level: 1,
      }),
    ).toBeVisible();
    const tokenB = await tokenFor(userB.email);
    for (const path of [
      `/v1/cases/${id}`,
      `/v1/cases/${id}/plan`,
      `/v1/evidence/${evidence.id}`,
      `/v1/evidence/${evidence.id}/download-url`,
    ])
      expect((await apiJson(path, tokenB)).status).toBe(404);
    await signOut(page);
    await page
      .getByRole("button", { name: "Vào thử với tài khoản demo" })
      .click();
    await expect(page).toHaveURL(/\/settings$/);
    await page.goto("/home");
    await expect(page.getByRole("heading", { level: 1 })).toContainText(
      "Chào An",
    );
    await expect(page.getByText(title, { exact: true })).toHaveCount(0);
  } finally {
    await removeUser(userB.email);
    if (registered) await removeUser(email);
  }
});
