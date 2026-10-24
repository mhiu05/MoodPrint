import { test, expect, type Page, type Request } from "@playwright/test";

const session = {
  userId: "11111111-1111-4111-8111-111111111111",
  alias: "An",
  ageBand: "adult",
  eligible: true,
  csrfToken: "csrf-session-test",
  timezone: "Asia/Bangkok",
  serverTime: "2026-10-23T08:00:00Z",
  dataVersion: 3,
  features: { ai: false, matching: false, voice: false },
  consents: Object.fromEntries(
    ["AI", "MEM", "MATCH", "VOICE"].map((purpose) => [
      purpose,
      { enabled: false, version: 1, policyVersion: "v1" },
    ]),
  ),
};
const failure = (status: number, code: string, message: string) => ({
  status,
  json: { error: { code, message, retryable: false, requestId: "r" } },
});

type Handler = (request: Request) => Parameters<import("@playwright/test").Route["fulfill"]>[0] | undefined;

async function api(page: Page, authenticated: boolean, handlers: Record<string, Handler> = {}) {
  const calls: { path: string; method: string; body: any }[] = [];
  await page.route("**/api/v1/**", async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname.replace("/api/v1", "");
    const body = request.postData() ? JSON.parse(request.postData()!) : undefined;
    calls.push({ path, method: request.method(), body });
    const custom = handlers[`${request.method()} ${path}`]?.(request);
    if (custom) return route.fulfill(custom);
    if (path === "/session")
      return route.fulfill(
        authenticated ? { json: session } : failure(401, "AUTH_REQUIRED", "Vui lòng đăng nhập."),
      );
    if (["/bots", "/ai/conversations", "/moods", "/profiles/private-items", "/users/me/identity"].includes(path))
      return route.fulfill({ json: [] });
    if (path === "/ai/preferences")
      return route.fulfill({ json: { historyEnabled: false, semanticMemoryEnabled: false, version: 1, policyVersion: "ai-data-v1", retentionDays: 30, historyAvailable: true, semanticMemoryAvailable: false } });
    return route.fulfill(failure(503, "UNAVAILABLE", "Chưa thể kết nối."));
  });
  return calls;
}

test("sign-up checks the password confirmation and never claims the account exists", async ({ page }) => {
  const calls = await api(page, false, {
    "POST /auth/signup": () => ({ status: 202, json: { status: "sent" } }),
  });
  await page.goto("/");
  await page.getByRole("button", { name: "Tạo tài khoản mới" }).click();
  await expect(page.getByRole("heading", { name: "Tạo tài khoản" })).toBeVisible();
  await page.getByLabel("Email", { exact: true }).fill("new@example.test");
  await page.getByLabel("Mật khẩu mới", { exact: true }).fill("a long passphrase");
  await page.getByLabel("Nhập lại mật khẩu", { exact: true }).fill("different passphrase");
  await page.getByRole("button", { name: "Tạo tài khoản", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("chưa khớp");
  expect(calls.some((call) => call.path === "/auth/signup")).toBe(false);
  await page.getByLabel("Nhập lại mật khẩu", { exact: true }).fill("a long passphrase");
  await page.getByRole("button", { name: "Tạo tài khoản", exact: true }).click();
  await expect(page.getByRole("status")).toContainText("thư xác nhận");
  await expect(page.getByRole("heading", { name: "Chào bạn trở lại" })).toBeVisible();
  const signup = calls.find((call) => call.path === "/auth/signup")!;
  expect(signup.body).toEqual({ email: "new@example.test", password: "a long passphrase" });
});

test("an unconfirmed email offers to resend the confirmation instead of a password error", async ({ page }) => {
  const calls = await api(page, false, {
    "POST /auth/login": () => failure(403, "EMAIL_NOT_CONFIRMED", "Email chưa được xác nhận."),
    "POST /auth/confirmation": () => ({ status: 202, json: { status: "sent" } }),
  });
  await page.goto("/");
  await page.getByLabel("Email", { exact: true }).fill("new@example.test");
  await page.getByLabel("Mật khẩu", { exact: true }).fill("a long passphrase");
  await page.getByRole("button", { name: "Đăng nhập", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("chưa được xác nhận");
  await page.getByRole("button", { name: "Gửi lại thư xác nhận" }).click();
  await expect(page.getByRole("status")).toContainText("thư xác nhận mới");
  expect(calls.find((call) => call.path === "/auth/confirmation")!.body).toEqual({ email: "new@example.test" });
});

test("forgot password sends a uniform notice", async ({ page }) => {
  const calls = await api(page, false, {
    "POST /auth/password-recovery": () => ({ status: 202, json: { status: "sent" } }),
  });
  await page.goto("/");
  await page.getByRole("button", { name: "Quên mật khẩu?" }).click();
  await expect(page.getByLabel("Mật khẩu", { exact: true })).toHaveCount(0);
  await page.getByLabel("Email", { exact: true }).fill("who@example.test");
  await page.getByRole("button", { name: "Gửi liên kết" }).click();
  await expect(page.getByRole("status")).toContainText("Nếu email có tài khoản");
  expect(calls.find((call) => call.path === "/auth/password-recovery")!.body).toEqual({ email: "who@example.test" });
});

test("a recovery link removes its token from the URL and sets a new password", async ({ page }) => {
  const token = "recovery-token-canary-0123456789";
  const calls = await api(page, false, {
    "POST /auth/password-reset": () => ({ json: { status: "updated" } }),
  });
  await page.goto(`/auth/callback#access_token=${token}&refresh_token=r&type=recovery`);
  await expect(page.getByRole("heading", { name: "Đặt mật khẩu mới" })).toBeVisible();
  expect(page.url()).not.toContain(token);
  expect(page.url()).not.toContain("refresh_token");
  await page.getByLabel("Mật khẩu mới", { exact: true }).fill("brand new secret");
  await page.getByLabel("Nhập lại mật khẩu", { exact: true }).fill("brand new secret");
  await page.getByRole("button", { name: "Lưu mật khẩu mới" }).click();
  await expect(page.getByRole("status")).toContainText("Đã đổi mật khẩu");
  expect(calls.find((call) => call.path === "/auth/password-reset")!.body).toEqual({
    accessToken: token,
    password: "brand new secret",
  });
});

test("an expired email link explains itself on the login screen", async ({ page }) => {
  await api(page, false);
  await page.goto("/auth/callback#error=access_denied&error_code=otp_expired&error_description=x");
  await expect(page.getByRole("status")).toContainText("đã hết hạn");
  await expect(page.getByRole("heading", { name: "Chào bạn trở lại" })).toBeVisible();
});

test("export asks for step-up re-authentication instead of signing the user out", async ({ page }) => {
  let reauthenticated = false;
  const calls = await api(page, true, {
    "POST /exports": () =>
      reauthenticated
        ? { status: 201, json: { id: "33333333-3333-4333-8333-333333333333", kind: "export", scope: "account", status: "completed", version: 1 } }
        : failure(401, "REAUTH_REQUIRED", "Hãy đăng nhập lại trước khi xuất dữ liệu."),
    "POST /auth/reauthenticate": () => {
      reauthenticated = true;
      return { json: { status: "confirmed" } };
    },
    "GET /exports/33333333-3333-4333-8333-333333333333/download": () => ({ json: { account: {} } }),
  });
  await page.goto("/#/settings");
  await page.getByRole("button", { name: "Xuất dữ liệu riêng" }).click();
  await expect(page.getByRole("heading", { name: "Xác nhận lại mật khẩu" })).toBeVisible();
  // Still signed in: the login screen must not appear.
  await expect(page.getByRole("heading", { name: "Chào bạn trở lại" })).toHaveCount(0);
  await page.locator("#reauth-email").fill("an@example.test");
  await page.locator("#reauth-password").fill("my password");
  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "Xác nhận", exact: true }).click();
  expect((await download).suggestedFilename()).toBe("moodprint-data.json");
  expect(calls.filter((call) => call.path === "/exports").length).toBe(2);
  const reauth = calls.find((call) => call.path === "/auth/reauthenticate")!;
  expect(reauth.body).toEqual({ email: "an@example.test", password: "my password" });
});

test("account deletion requires explicit acknowledgement and confirms sign-out", async ({ page }) => {
  const calls = await api(page, true, {
    "POST /data-deletions": () => ({ status: 202, json: { id: "44444444-4444-4444-8444-444444444444", kind: "deletion", scope: "account", status: "queued", version: 1 } }),
  });
  await page.goto("/#/settings");
  await page.getByRole("button", { name: "Xóa tài khoản" }).click();
  const confirm = page.getByRole("button", { name: "Xóa vĩnh viễn" });
  await expect(confirm).toBeDisabled();
  await page.getByLabel("Tôi hiểu tài khoản không thể khôi phục.").check();
  await confirm.click();
  await expect(page.getByRole("heading", { name: "Tài khoản đang được xóa" })).toBeVisible();
  expect(calls.find((call) => call.path === "/data-deletions")!.body).toEqual({ scope: "account", expectedVersion: 3 });
});

test("identity values typed while the stored value loads are never overwritten", async ({ page }) => {
  let saved: any;
  await api(page, true, {
    "PATCH /users/me/identity": (request) => {
      saved = JSON.parse(request.postData()!);
      return { json: { field: saved.field, value: saved.value, version: 2 } };
    },
  });
  await page.route("**/api/v1/users/me/identity", async (route) => {
    if (route.request().method() !== "GET") return route.fallback();
    await new Promise((resolve) => setTimeout(resolve, 600));
    await route.fulfill({ json: [{ field: "displayName", value: "Old stored name", version: 1 }] });
  });
  await page.goto("/#/profile");
  const input = page.locator("#identity-displayName");
  await expect(input).toBeDisabled();
  await input.fill("New typed name");
  await page.getByRole("button", { name: "Lưu tên hiển thị" }).click();
  await expect(page.getByText("Đã cập nhật thông tin riêng.")).toBeVisible();
  expect(saved).toMatchObject({ field: "displayName", value: "New typed name", expectedVersion: 1 });
});
