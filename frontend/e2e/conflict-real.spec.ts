import { test, expect, guardNetwork } from "./helpers/fixtures";
import {
  apiJson,
  createCaseViaApi,
  createUser,
  login,
  removeUser,
} from "./helpers/local";

test.use({ expectedHttpStatuses: [409] });

test("E-CASE-03: two contexts expose a real version conflict while retaining the later draft", async ({
  page,
  browser,
  baseURL,
}) => {
  const user = await createUser();
  const second = await browser.newContext({ baseURL });
  const forbidden = await guardNetwork(second, true, baseURL);
  try {
    const item = await createCaseViaApi(user.email);
    const other = await second.newPage();
    await login(page, user.email);
    await login(other, user.email);
    await page.goto(`/cases/${item.id}/edit`);
    await other.goto(`/cases/${item.id}/edit`);
    await page
      .getByRole("textbox", { name: "Đặt tên hồ sơ" })
      .fill("Tiêu đề từ ngữ cảnh thứ nhất");
    await other.getByRole("button", { name: /Chuyện xảy ra/ }).click();
    const story = other.getByRole("textbox", { name: "Chuyện gì đã xảy ra?" });
    await story.fill("Nội dung tổng hợp đang nhập ở ngữ cảnh thứ hai.");
    await page.getByRole("button", { name: /Xem lại và lưu/ }).click();
    await page.getByRole("button", { name: "Lưu hồ sơ", exact: true }).click();
    await expect(page).toHaveURL(new RegExp(`/cases/${item.id}$`));
    await other.getByRole("button", { name: /Xem lại và lưu/ }).click();
    const conflict = other.waitForResponse(
      (response) =>
        response.url().endsWith(`/v1/cases/${item.id}`) &&
        response.request().method() === "PATCH",
    );
    await other.getByRole("button", { name: "Lưu hồ sơ", exact: true }).click();
    expect((await conflict).status()).toBe(409);
    await expect(
      other.getByText(
        "Hồ sơ đã được sửa ở nơi khác. Nội dung đang nhập vẫn được giữ.",
      ),
    ).toBeVisible();
    await other.getByRole("button", { name: /Chuyện xảy ra/ }).click();
    await expect(story).toHaveValue(
      "Nội dung tổng hợp đang nhập ở ngữ cảnh thứ hai.",
    );
    const canonical = await (
      await apiJson(`/v1/cases/${item.id}`, item.token)
    ).json();
    expect(canonical.title).toBe("Tiêu đề từ ngữ cảnh thứ nhất");
    expect(canonical.summary).toBe(
      "Một tình huống hoàn toàn hư cấu để kiểm thử.",
    );
    expect(forbidden).toEqual([]);
  } finally {
    await second.close();
    await removeUser(user.email);
  }
});
