import { test, expect } from "./helpers/fixtures";
import {
  apiJson,
  createUser,
  login,
  removeUser,
  tokenFor,
} from "./helpers/local";

test("E-SUP-01: trusted contacts and a support draft persist without a fake sent status", async ({
  page,
  context,
}) => {
  const user = await createUser();
  try {
    await context.grantPermissions(["clipboard-read", "clipboard-write"]);
    await login(page, user.email);
    await expect(page).toHaveURL(/\/home$/);
    await page.goto("/support/find-help");
    await page
      .getByRole("textbox", { name: "Tên gọi dễ nhớ", exact: true })
      .fill("Cô giáo tổng hợp");
    await page
      .getByRole("button", { name: "Thêm người tin cậy", exact: true })
      .click();
    await expect(
      page.getByText("Cô giáo tổng hợp", { exact: true }),
    ).toBeVisible();
    await page.reload();
    await expect(
      page.getByText("Cô giáo tổng hợp", { exact: true }),
    ).toBeVisible();
    await page.goto("/support/prepare");
    const content =
      "Đây là lời nhắn hoàn toàn tổng hợp. Mình muốn chuẩn bị nói chuyện cùng một người lớn tin cậy.";
    await page
      .getByRole("textbox", { name: "Nội dung xem trước", exact: true })
      .fill(content);
    await page
      .getByRole("button", { name: "Lưu bản nháp", exact: true })
      .click();
    await expect(
      page
        .getByText("Đã lưu bản nháp trong tài khoản. Chưa gửi cho ai.")
        .first(),
    ).toBeVisible();
    await page.getByRole("button", { name: "Sao chép", exact: true }).click();
    expect(await page.evaluate(() => navigator.clipboard.readText())).toBe(
      content,
    );
    await expect(
      page.getByRole("button", { name: "Lưu báo cáo demo", exact: true }),
    ).toHaveCount(0);
    const token = await tokenFor(user.email);
    const response = await apiJson("/v1/support-drafts", token);
    expect(response.status).toBe(200);
    const data = await response.json();
    expect(data.items).toHaveLength(1);
    expect(data.items[0].status).toBe("draft");
    expect(data.items[0].content).toBe(content);
    await page.goto(`/support/prepare?draftId=${data.items[0].id}`);
    await page.reload();
    await expect(
      page.getByRole("textbox", { name: "Nội dung xem trước", exact: true }),
    ).toHaveValue(content);
  } finally {
    await removeUser(user.email);
  }
});
