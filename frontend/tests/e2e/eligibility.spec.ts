import { expect, test } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { app, baseSession, guestSession } from "./ux-fixtures";

test("guest export stays available behind the age gate and requires explicit confirmation", async ({ page }) => {
  let exports = 0;
  const guest = guestSession(7_000_000, { ageBand: "teen", eligible: false, birthYear: 2009 });
  await app(page, guest, {
    "/exports": request => {
      exports += 1;
      expect(request.postDataJSON()).toEqual({ scopes: ["account", "memories", "moods", "journal", "consents", "conversations"], guestConfirmation: "guest-data-v1" });
      return { json: { id: "guest-export", scope: "account", status: "ready", version: 1, createdAt: baseSession.serverTime } };
    },
    "/exports/guest-export/download": () => ({ json: { account: { userId: guest.userId }, conversations: [] } }),
  });
  await page.goto("/#/assistants");
  await page.getByRole("button", { name: "Tải dữ liệu của tôi", exact: true }).click();
  const dialog = page.getByRole("dialog", { name: "Tải dữ liệu lượt dùng thử?", exact: true });
  await expect(dialog).toBeVisible();
  expect(exports).toBe(0);
  const downloaded = page.waitForEvent("download");
  await dialog.getByRole("button", { name: "Xác nhận và tải dữ liệu", exact: true }).click();
  expect((await downloaded).suggestedFilename()).toBe("moodprint-data.json");
  expect(exports).toBe(1);
  await expect(page.getByLabel("Mật khẩu", { exact: true })).toHaveCount(0);
});

test("an age denial during a pending session read gets fresh eligibility context", async ({ page }) => {
  let reads = 0;
  let holdNext = false;
  let ageDenied = false;
  let release!: () => void;
  const held = new Promise<void>(resolve => { release = resolve; });
  await app(page, baseSession, {
    "/journal/entries": () => {
      ageDenied = true;
      return { status: 403, json: { error: { code: "ELIGIBILITY_REQUIRED", message: "Bạn cần đủ 18 tuổi để sử dụng MoodPrint." } } };
    },
  });
  await page.route("**/api/v1/session", async route => {
    reads += 1;
    if (holdNext) {
      holdNext = false;
      await held;
      return route.fulfill({ json: baseSession }).catch(() => undefined);
    }
    return route.fulfill({ json: ageDenied ? { ...baseSession, ageBand: "teen", eligible: false, birthYear: 2008, eligibilityVersion: 4, dataVersion: 8 } : baseSession });
  });
  await page.goto("/#/assistants/may");
  await expect(page.getByRole("textbox", { name: "Tin nhắn cho Mây", exact: true })).toBeVisible();
  const initialReads = reads;
  holdNext = true;
  await page.evaluate(() => window.dispatchEvent(new Event("focus")));
  await expect.poll(() => reads).toBe(initialReads + 1);
  try {
    await page.evaluate(() => { window.location.hash = "#/self"; });
    await expect.poll(() => reads).toBe(initialReads + 2);
    await expect(page.getByLabel("Năm sinh", { exact: true })).toHaveValue("2008");
    await expect(page.getByLabel("Năm sinh", { exact: true })).toHaveAttribute("readonly");
  } finally { release(); }
  await expect(page.getByText("Bạn cần đủ 18 tuổi để sử dụng MoodPrint.", { exact: true })).toBeVisible();
});

test("an API age denial immediately leaves protected content and rechecks its session", async ({ page }) => {
  let denied = false;
  await app(page, baseSession, {
    "/session": () => ({ json: denied ? { ...baseSession, ageBand: "teen", eligible: false, birthYear: 2009 } : baseSession }),
    "/journal/entries": () => {
      denied = true;
      return { status: 403, json: { error: { code: "ELIGIBILITY_REQUIRED", message: "Bạn cần đủ 18 tuổi để sử dụng MoodPrint." } } };
    },
  });
  await page.goto("/#/self");
  await expect(page.getByText("Bạn cần đủ 18 tuổi để sử dụng MoodPrint.", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Tải dữ liệu của tôi", exact: true })).toBeVisible();
});

test("a retained underage account securely reauthenticates and downloads its data", async ({ page }) => {
  let reauthenticated = false;
  const account = { ...baseSession, ageBand: "teen", eligible: false, birthYear: 2009, dataVersion: 2 };
  await app(page, account, {
    "/auth/reauthenticate": request => {
      expect(request.postDataJSON()).toEqual({ email: "owner@example.test", password: "synthetic password" });
      reauthenticated = true;
      return { json: { status: "confirmed" } };
    },
    "/exports": request => {
      expect(request.postDataJSON().scopes).toEqual(["account", "memories", "moods", "journal", "consents", "social", "conversations"]);
      return reauthenticated ? { json: { id: "synthetic-export", scope: "account", status: "ready", version: 1, createdAt: account.serverTime } } : { status: 401, json: { error: { code: "REAUTH_REQUIRED", message: "Xác nhận tài khoản để tải dữ liệu." } } };
    },
    "/exports/synthetic-export/download": () => ({ json: { account: { userId: account.userId }, conversations: [] } }),
  });
  await page.goto("/#/assistants");
  await page.getByRole("button", { name: "Tải dữ liệu của tôi", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Xác nhận tài khoản", exact: true })).toBeVisible();
  await page.getByLabel("Email", { exact: true }).fill("owner@example.test");
  await page.getByLabel("Mật khẩu", { exact: true }).fill("synthetic password");
  const downloaded = page.waitForEvent("download");
  await page.getByRole("button", { name: "Xác nhận", exact: true }).click();
  expect((await downloaded).suggestedFilename()).toBe("moodprint-data.json");
  await expect(page.getByText("Bạn cần đủ 18 tuổi để sử dụng MoodPrint.", { exact: true })).toBeVisible();
});

test("an ineligible account can confirm its own deletion without opening protected views", async ({ page }) => {
  let deleted = false;
  await app(page, { ...baseSession, ageBand: "teen", eligible: false, birthYear: 2009, dataVersion: 3 }, {
    "/data-deletions": request => {
      expect(request.postDataJSON()).toEqual({ scope: "account", expectedVersion: 3 });
      deleted = true;
      return { status: 202, json: { id: "synthetic-deletion", scope: "account", status: "pending", version: 1, createdAt: baseSession.serverTime } };
    },
  });
  await page.goto("/#/assistants");
  await page.getByRole("button", { name: "Xóa tài khoản", exact: true }).click();
  const dialog = page.getByRole("dialog", { name: "Xóa vĩnh viễn tài khoản?", exact: true });
  await expect(dialog).toBeVisible();
  expect(deleted).toBe(false);
  await dialog.getByRole("checkbox", { name: "Tôi hiểu tài khoản không thể khôi phục.", exact: true }).check();
  await dialog.getByRole("button", { name: "Xóa vĩnh viễn tài khoản", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Tài khoản đang được xóa", exact: true })).toBeVisible();
  expect(deleted).toBe(true);
});

for (const ageBand of ["teen", "under16", "unknown"]) {
  test(`old ${ageBand} session cannot open private routes even with stale eligible=true`, async ({
    page,
  }) => {
    const calls: string[] = [];
    await app(page, {
      ...baseSession,
      ageBand,
      eligible: true,
      birthYear: 2009,
      eligibilityVersion: 1,
    });
    await page.route("**/api/v1/**", (route) => {
      calls.push(new URL(route.request().url()).pathname);
      return route.fallback();
    });
    await page.goto("/#/assistants/may");
    await expect(
      page.getByText("Bạn cần đủ 18 tuổi để sử dụng MoodPrint.", {
        exact: true,
      }),
    ).toBeVisible();
    await expect(page.getByRole("textbox", { name: /Tin nhắn/ })).toHaveCount(
      0,
    );
    expect(
      calls.filter((path) => /\/(bots|ai\/|journal\/|social\/)/.test(path)),
    ).toEqual([]);
  });
}

test("a boundary-year user confirms actual eighteenth birthday before private access", async ({
  page,
}) => {
  let declared = false;
  await app(
    page,
    {
      ...baseSession,
      ageBand: "teen",
      eligible: false,
      birthYear: 2008,
      eligibilityVersion: 1,
    },
    {
      "/users/me/eligibility": (request) => {
        expect(request.postDataJSON()).toEqual({
          birthYear: 2008,
          confirmedMinimumAge: true,
          confirmedAdultAge: true,
          policyVersion: "self-declared-age-v2-18plus",
          expectedVersion: 1,
        });
        declared = true;
        return {
          json: { ...baseSession, birthYear: 2008, eligibilityVersion: 2 },
        };
      },
    },
  );
  await page.goto("/#/assistants");
  await expect(
    page.getByRole("button", { name: "Xác nhận và tiếp tục", exact: true }),
  ).toBeDisabled();
  await page
    .getByRole("checkbox", {
      name: "Tôi xác nhận mình đã đủ 18 tuổi.",
      exact: true,
    })
    .check();
  await page
    .getByRole("button", { name: "Xác nhận và tiếp tục", exact: true })
    .click();
  await expect(page.getByText("Mây").first()).toBeVisible();
  expect(declared).toBe(true);
});

test("eligibility denial on session refresh removes the open AI draft", async ({
  page,
}) => {
  let denied = false;
  await app(page, baseSession, {
    "/session": () => ({
      json: denied
        ? { ...baseSession, ageBand: "teen", eligible: false, birthYear: 2009 }
        : baseSession,
    }),
  });
  await page.goto("/#/assistants/may");
  await page
    .getByRole("textbox", { name: "Tin nhắn cho Mây" })
    .fill("private-unsent-canary");
  denied = true;
  await page.evaluate(() => window.dispatchEvent(new Event("focus")));
  await expect(
    page.getByText("Bạn cần đủ 18 tuổi để sử dụng MoodPrint.", { exact: true }),
  ).toBeVisible();
  await expect(page.getByText("private-unsent-canary")).toHaveCount(0);
});

test("an old guest declaration cannot use the private tree", async ({
  page,
}) => {
  await app(
    page,
    guestSession(7_000_000, {
      ageBand: "teen",
      eligible: true,
      birthYear: 2009,
    }),
  );
  await page.goto("/#/self");
  await expect(
    page.getByText("Bạn cần đủ 18 tuổi để sử dụng MoodPrint.", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", {
      name: "Kết thúc và xóa lượt dùng thử",
      exact: true,
    }),
  ).toBeVisible();
});

for (const width of [320, 390, 1280]) {
  test(`ineligible account keeps secure account controls and accessible layout at ${width}px`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 844 });
    await app(page, {
      ...baseSession,
      ageBand: "teen",
      eligible: false,
      birthYear: 2009,
    });
    await page.goto("/#/connect");
    await expect(
      page.getByRole("button", { name: "Xóa tài khoản", exact: true }),
    ).toBeVisible();
    await expect(
      page.getByRole("button", { name: "Tải dữ liệu của tôi", exact: true }),
    ).toBeVisible();
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    const axe = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
      .analyze();
    expect(axe.violations).toEqual([]);
  });
}
