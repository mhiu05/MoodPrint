import { expect, test, type Page, type Route } from "@playwright/test";
import { app, baseSession, bots } from "./ux-fixtures";

type Handler = (route: Route, path: string) => Promise<void | false> | void | false;
async function mock(page: Page, override: Handler = () => false) {
  await app(page, baseSession);
  await page.route("**/api/v1/**", async route => {
    const path = new URL(route.request().url()).pathname.replace("/api/v1", "");
    if (await override(route, path) === false) await route.fallback();
  });
}
const failure = { status: 500, json: { error: { code: "INTERNAL_ERROR", message: "Chưa hoàn tất yêu cầu. Vui lòng thử lại.", retryable: true } } };

test("offline shows one banner, disables sending and keeps the draft", async ({ page, context }) => {
  await mock(page);
  await page.goto("/#/assistants/may?new=1");
  const composer = page.getByRole("textbox", { name: "Tin nhắn cho Mây" });
  await composer.fill("mình đây");
  const send = page.getByRole("button", { name: "Gửi tin cho AI", exact: true });
  await expect(send).toBeEnabled();
  await context.setOffline(true);
  const banner = page.getByRole("status").filter({ hasText: "Bạn đang mất kết nối mạng. Nội dung đang nhập được giữ trên màn hình này." });
  await expect(banner).toHaveCount(1);
  await expect(send).toBeDisabled();
  await expect(send).toHaveAttribute("title", "Đang mất kết nối mạng");
  await expect(composer).toHaveValue("mình đây");
  await context.setOffline(false);
  await expect(banner).toHaveCount(0);
  await expect(send).toBeEnabled();
});

test("a failed list shows retry, and coming back online retries by itself", async ({ page, context }) => {
  let fail = true;
  await mock(page, (route, path) => path === "/bots" && fail ? route.fulfill(failure) : false);
  await page.goto("/#/assistants");
  const alert = page.getByRole("alert");
  await expect(alert).toContainText("Chưa hoàn tất yêu cầu");
  await alert.getByRole("button", { name: "Thử lại" }).click();
  await expect(alert).toContainText("Chưa hoàn tất yêu cầu");
  fail = false;
  const offlineBanner = page.getByRole("status").filter({ hasText: "Bạn đang mất kết nối mạng. Nội dung đang nhập được giữ trên màn hình này." });
  await context.setOffline(true);
  await expect(offlineBanner).toBeVisible();
  await context.setOffline(false);
  await expect(offlineBanner).toHaveCount(0);
  await expect(page.getByRole("link", { name: /Mây/ }).first()).toBeVisible();
  await expect(page.getByRole("alert")).toHaveCount(0);
});

test("loading lists announce themselves", async ({ page }) => {
  let release!: () => void;
  const gate = new Promise<void>(resolve => release = resolve);
  await mock(page, async (route, path) => {
    if (path !== "/bots") return false;
    await gate;
    await route.fulfill({ json: bots });
  });
  await page.goto("/#/assistants");
  await expect(page.getByRole("status").filter({ hasText: "Đang tải trợ lý…" })).toBeVisible();
  release();
  await expect(page.getByRole("link", { name: /Mây/ }).first()).toBeVisible();
});

test("empty screens say so honestly and offer one next step", async ({ page }) => {
  await mock(page, (route, path) => path === "/bots" ? route.fulfill({ json: [] }) : false);
  await page.goto("/#/assistants");
  await expect(page.getByText("Chưa có trợ lý nào sẵn sàng. Bạn hãy thử lại sau.")).toBeVisible();
  await page.unroute("**/api/v1/**");
  await mock(page);
  await page.reload();
  await expect(page.getByRole("link", { name: /Mây/ }).first()).toBeVisible();
  await page.getByRole("textbox", { name: "Tìm trợ lý" }).fill("không khớp");
  await expect(page.getByText("Không có trợ lý nào khớp với “không khớp”.")).toBeVisible();
  await page.getByRole("button", { name: "Xóa tìm kiếm" }).click();
  await expect(page.getByRole("textbox", { name: "Tìm trợ lý" })).toHaveValue("");
  await expect(page.getByRole("link", { name: /Mây/ }).first()).toBeVisible();
});
