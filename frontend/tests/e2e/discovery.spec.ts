import { expect, test, type Page } from "@playwright/test";
import { friendshipFixture, LEGACY } from "./friendship-fixture";
import AxeBuilder from "@axe-core/playwright";

test.describe("mobile publication", () => {
  test.use({ isMobile: true, hasTouch: true });
  for (const width of [320, 390]) {
    test(`T13 T17 T32: complete deliberate publication by touch at ${width}px`, async ({
      page,
    }) => {
      const state = await friendshipFixture(page);
      await page.setViewportSize({ width, height: width === 320 ? 568 : 844 });
      await page.goto("/#/connect");
      await page
        .getByRole("radio", { name: "Có người tâm sự", exact: true })
        .check();
      await page.getByRole("button", { name: "Tiếp tục", exact: true }).click();
      for (const name of ["Âm nhạc", "Cà phê", "Đọc sách"])
        await page.getByRole("checkbox", { name, exact: true }).check();
      await page.getByRole("button", { name: "Tiếp tục", exact: true }).click();
      await page
        .getByRole("radio", { name: "Từ từ làm quen", exact: true })
        .check();
      await page
        .getByRole("button", {
          name: "Xem lại trước khi hiển thị",
          exact: true,
        })
        .click();
      const supplement = page.getByRole("region", {
        name: "Bổ sung để ghép bạn chính xác hơn",
        exact: true,
      });
      for (const name of ["Tôn trọng", "Chân thành", "Tiếng Việt"])
        await supplement.getByRole("checkbox", { name, exact: true }).check();
      await page
        .getByRole("button", { name: "Xem bản được chia sẻ", exact: true })
        .click();
      const reviewed = page.getByRole("article", {
        name: "Hồ sơ của Bạn",
        exact: true,
      });
      await expect(reviewed.locator("details")).toHaveAttribute("open", "");
      expect(state.live).toBe(false);
      const publish = page.getByRole("button", {
        name: "Hiển thị hồ sơ",
        exact: true,
      });
      await publish.scrollIntoViewIfNeeded();
      const buttonBounds = await publish.boundingBox();
      const navBounds = await page
        .getByRole("navigation", { name: "Điều hướng chính" })
        .boundingBox();
      expect(buttonBounds!.y + buttonBounds!.height).toBeLessThanOrEqual(
        navBounds!.y,
      );
      await publish.tap();
      await expect(
        page.getByText("Đã hiển thị hồ sơ tìm bạn.", { exact: true }),
      ).toBeVisible();
      expect(state.live).toBe(true);
    });
  }
});

test("T19: session expiry clears a dirty editor and ignores a delayed save response", async ({
  page,
}) => {
  await friendshipFixture(page);
  let expired = false;
  let release!: () => void;
  const gate = new Promise<void>((resolve) => {
    release = resolve;
  });
  let pending!: () => void;
  const started = new Promise<void>((resolve) => {
    pending = resolve;
  });
  await page.route("**/api/v1/session", (route) =>
    expired
      ? route.fulfill({
          status: 401,
          json: {
            error: { code: "SESSION_EXPIRED", message: "Phiên đã kết thúc." },
          },
        })
      : route.fallback(),
  );
  await page.route("**/api/v1/profiles/matching-draft", async (route) => {
    if (route.request().method() !== "PUT") return route.fallback();
    pending();
    await gate;
    const { expectedVersion, ...profile } = route.request().postDataJSON();
    await route
      .fulfill({
        json: { profile, version: expectedVersion + 1, publishedVersion: 0 },
      })
      .catch(() => {});
  });
  let unloadWarnings = 0;
  page.on("dialog", async (dialog) => {
    unloadWarnings++;
    await dialog.dismiss();
  });
  await page.goto("/#/connect");
  await page.getByRole("radio", { name: "Bạn cùng học", exact: true }).check();
  await page.getByRole("button", { name: "Lưu bản nháp", exact: true }).click();
  await started;
  expired = true;
  await page.evaluate(() => window.dispatchEvent(new Event("focus")));
  await expect(page.locator(".profile-editor")).toHaveCount(0);
  release();
  await expect(
    page.getByRole("textbox", { name: "Email", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Đăng nhập", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("dialog", {
      name: "Bạn muốn lưu thay đổi trước khi rời đi?",
      exact: true,
    }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("radio", { name: "Bạn cùng học", exact: true }),
  ).toHaveCount(0);
  expect(unloadWarnings).toBe(0);
});

test("T12 T14 T19: refresh failure keeps the mounted dirty reducer and exit confirmation", async ({
  page,
}) => {
  const state = await friendshipFixture(page, LEGACY, true);
  let failRead = false;
  await page.route("**/api/v1/profiles/matching-draft", (route) =>
    failRead && route.request().method() === "GET"
      ? route.fulfill({
          status: 503,
          json: {
            error: {
              code: "TEMPORARY",
              message: "Đọc bản nháp tạm thời thất bại.",
            },
          },
        })
      : route.fallback(),
  );
  await page.route("**/api/v1/profiles/published/current", (route) => {
    if (route.request().method() !== "DELETE") return route.fallback();
    state.live = false;
    state.publication++;
    failRead = true;
    return route.fulfill({ status: 204 });
  });
  await page.goto("/#/connect?tab=profile");
  await page
    .getByRole("button", { name: "Chỉnh hồ sơ tìm bạn", exact: true })
    .click();
  await page.getByRole("radio", { name: "Bạn cùng học", exact: true }).check();
  await page
    .getByRole("button", { name: "Ngừng hiển thị hồ sơ", exact: true })
    .click();
  await expect(page.getByRole("alert")).toContainText(
    "Đọc bản nháp tạm thời thất bại.",
  );
  await expect(
    page.getByRole("radio", { name: "Bạn cùng học", exact: true }),
  ).toBeChecked();
  await page
    .getByRole("navigation", { name: "Điều hướng chính" })
    .getByRole("link", { name: "Tin nhắn", exact: true })
    .click();
  await expect(
    page.getByRole("dialog", {
      name: "Bạn muốn lưu thay đổi trước khi rời đi?",
      exact: true,
    }),
  ).toBeVisible();
});

test("T14 T19: terminal eligibility refusal clears publication and preserves secure exit", async ({
  page,
}) => {
  const state = await friendshipFixture(page);
  await page.route("**/api/v1/auth/logout", (route) => route.fulfill({ status: 204 }));
  await page.route("**/api/v1/profiles/matching-draft", (route) =>
    route.request().method() === "PUT"
      ? (state.eligible = false, route.fulfill({
          status: 403,
          json: {
            error: {
              code: "ADULT_REQUIRED",
              message: "Tính năng kết nối không còn khả dụng.",
            },
          },
        }))
      : route.fallback(),
  );
  await page.goto("/#/connect");
  await page.getByRole("radio", { name: "Bạn cùng học", exact: true }).check();
  await page.getByRole("button", { name: "Lưu bản nháp", exact: true }).click();
  await expect(
    page.getByText("Bạn cần đủ 18 tuổi để sử dụng MoodPrint.", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Hiển thị hồ sơ", exact: true }),
  ).toHaveCount(0);
  await expect(page.locator(".profile-editor")).toHaveCount(0);
  await page.getByRole("button", { name: "Đăng xuất", exact: true }).click();
  await expect(page.getByRole("textbox", { name: "Email", exact: true })).toBeVisible();
});

test("T12 T14: a CSRF refusal retains edits and an accessible exit guard", async ({
  page,
}) => {
  await friendshipFixture(page);
  await page.route("**/api/v1/profiles/matching-draft", (route) =>
    route.request().method() === "PUT"
      ? route.fulfill({
          status: 403,
          json: {
            error: {
              code: "CSRF_DENIED",
              message: "Phiên yêu cầu đã thay đổi. Thử lại nhé.",
            },
          },
        })
      : route.fallback(),
  );
  await page.goto("/#/connect");
  await page.getByRole("radio", { name: "Bạn cùng học", exact: true }).check();
  await page.getByRole("button", { name: "Lưu bản nháp", exact: true }).click();
  await page
    .getByRole("navigation", { name: "Điều hướng chính" })
    .getByRole("link", { name: "Tin nhắn", exact: true })
    .click();
  const dialog = page.getByRole("dialog", {
    name: "Bạn muốn lưu thay đổi trước khi rời đi?",
    exact: true,
  });
  await expect(dialog).toBeVisible();
  await dialog
    .getByRole("button", { name: "Tiếp tục chỉnh", exact: true })
    .click();
  await expect(
    page.getByRole("radio", { name: "Bạn cùng học", exact: true }),
  ).toBeChecked();
});

const candidate = (ref: string, alias: string) => ({
  candidateRef: ref,
  alias,
  avatarSeed: "aabbccdd",
  profileVersion: 7,
  peerVersion: 2,
  reasons: ["Cùng thích âm nhạc"],
  matchLabel: "some",
  scoringVersion: "rules-v2",
  profile: LEGACY,
});

test("T33: consecutive featured removals retain next, previous and final heading focus", async ({
  page,
}) => {
  const state = await friendshipFixture(page, {
    ...LEGACY,
    interests: ["music", "coffee", "reading"],
  });
  await page.goto("/#/connect?tab=profile");
  await page
    .getByRole("button", { name: "Chỉnh hồ sơ tìm bạn", exact: true })
    .click();
  const tray = page.getByRole("list", {
    name: "Sở thích nổi bật đã chọn",
    exact: true,
  });
  await tray
    .getByRole("button", { name: "Bỏ nổi bật: Cà phê", exact: true })
    .focus();
  await page.keyboard.press("Enter");
  await expect(
    tray.getByRole("button", { name: "Bỏ nổi bật: Đọc sách", exact: true }),
  ).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(
    tray.getByRole("button", { name: "Bỏ nổi bật: Âm nhạc", exact: true }),
  ).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.locator("#friendship-q1")).toBeFocused();
  await expect(page.locator(".editor-status")).toContainText("Còn 0 trên 3");
  expect(state.writes).toEqual([]);
});

test("T06 T33: picker tray removal keeps keyboard focus and Escape restores its launcher", async ({
  page,
}) => {
  await friendshipFixture(page, {
    ...LEGACY,
    interests: ["music", "coffee", "reading"],
  });
  await page.goto("/#/connect?tab=profile");
  await page
    .getByRole("button", { name: "Chỉnh hồ sơ tìm bạn", exact: true })
    .click();
  const launcher = page.getByRole("button", {
    name: "Xem thêm sở thích",
    exact: true,
  });
  await launcher.focus();
  await page.keyboard.press("Enter");
  const picker = page.getByRole("dialog", {
    name: "Chọn sở thích nổi bật",
    exact: true,
  });
  await picker
    .getByRole("button", { name: "Bỏ nổi bật: Âm nhạc", exact: true })
    .focus();
  for (const next of ["Cà phê", "Đọc sách"]) {
    await page.keyboard.press("Enter");
    await expect(
      picker.getByRole("button", { name: `Bỏ nổi bật: ${next}`, exact: true }),
    ).toBeFocused();
  }
  await page.keyboard.press("Enter");
  await expect(
    picker.getByRole("searchbox", { name: "Tìm sở thích", exact: true }),
  ).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(picker).toHaveCount(0);
  await expect(launcher).toBeFocused();
});

test("T08 T33: full-interest deletion retains consecutive and final action focus and announces removal", async ({
  page,
}) => {
  const state = await friendshipFixture(page, {
    ...LEGACY,
    interests: ["music", "coffee", "reading"],
  });
  await page.goto("/#/connect?tab=profile");
  await page
    .getByRole("button", { name: "Chỉnh hồ sơ tìm bạn", exact: true })
    .click();
  const launcher = page.getByRole("button", {
    name: "Quản lý sở thích đã lưu",
    exact: true,
  });
  await launcher.focus();
  await page.keyboard.press("Enter");
  const picker = page.getByRole("dialog", {
    name: "Quản lý sở thích đã lưu",
    exact: true,
  });
  await picker
    .getByRole("button", { name: "Xóa khỏi hồ sơ: Cà phê", exact: true })
    .focus();
  await page.keyboard.press("Enter");
  await expect(
    picker.getByRole("button", {
      name: "Xóa khỏi hồ sơ: Đọc sách",
      exact: true,
    }),
  ).toBeFocused();
  await expect(picker.getByRole("status")).toContainText(
    "Đã xóa Cà phê khỏi hồ sơ",
  );
  await page.keyboard.press("Enter");
  await expect(
    picker.getByRole("button", {
      name: "Xóa khỏi hồ sơ: Âm nhạc",
      exact: true,
    }),
  ).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(
    picker.getByRole("button", { name: "Xong", exact: true }),
  ).toBeFocused();
  await expect(picker.getByRole("status")).toContainText(
    "Còn 0 sở thích đã lưu",
  );
  await page.keyboard.press("Escape");
  await expect(picker).toHaveCount(0);
  // The management trigger disappears with the final full interest.
  await expect(page.locator("#friendship-q1")).toBeFocused();
  expect(state.writes).toEqual([]);
});

test("T32 T33 T34 T35 T37: concise announcements, errors, forced colors, 200% text and targets", async ({
  page,
}, testInfo) => {
  const state = await friendshipFixture(page);
  await page.goto("/#/connect");
  await page.getByRole("radio", { name: "Bạn cùng học", exact: true }).check();
  await expect(page.locator(".editor-status")).toContainText(
    "Đã chọn Bạn cùng học",
  );
  await page
    .getByRole("button", { name: "Xem lại trước khi hiển thị", exact: true })
    .click();
  const errors = page.getByRole("group", {
    name: "Cần bổ sung thông tin",
    exact: true,
  });
  await expect(errors).toBeFocused();
  await errors.getByRole("link").first().click();
  await expect(page.locator("#friendship-q1")).toBeFocused();
  const controlContrast = await page
    .locator(".friendship-choice:not([data-checked])")
    .first()
    .evaluate((node) => {
      const style = getComputedStyle(node);
      const luminance = (color: string) => {
        const channels = color
          .match(/[\d.]+/g)!
          .slice(0, 3)
          .map(Number)
          .map((channel) => channel / 255)
          .map((channel) =>
            channel <= 0.04045
              ? channel / 12.92
              : ((channel + 0.055) / 1.055) ** 2.4,
          );
        return (
          channels[0] * 0.2126 + channels[1] * 0.7152 + channels[2] * 0.0722
        );
      };
      const border = luminance(style.borderTopColor),
        surface = luminance(style.backgroundColor);
      return (
        (Math.max(border, surface) + 0.05) / (Math.min(border, surface) + 0.05)
      );
    });
  expect(controlContrast).toBeGreaterThanOrEqual(3);
  await page.emulateMedia({ forcedColors: "active", reducedMotion: "reduce" });
  await page.getByRole("checkbox", { name: "Âm nhạc", exact: true }).focus();
  await page.keyboard.press("Space");
  await expect(
    page.getByRole("checkbox", { name: "Âm nhạc", exact: true }),
  ).toBeChecked();
  const sizes = await page.locator(".friendship-choice").evaluateAll((nodes) =>
    nodes.map((node) => ({
      height: node.getBoundingClientRect().height,
      width: node.getBoundingClientRect().width,
    })),
  );
  expect(sizes.every(({ width, height }) => width >= 44 && height >= 44)).toBe(
    true,
  );
  await page.evaluate(() => {
    document.documentElement.style.fontSize = "200%";
  });
  for (const [width, height] of [
    [320, 568],
    [768, 1024],
    [1280, 900],
  ]) {
    await page.setViewportSize({ width, height });
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
  }
  await page.screenshot({
    path: testInfo.outputPath("forced-colors-200percent.png"),
    fullPage: true,
  });
  await page.evaluate(() => {
    document.documentElement.style.fontSize = "";
  });
  await page.emulateMedia({ forcedColors: "none", reducedMotion: "reduce" });
  const timing = await page
    .getByRole("radio", { name: "Có người tâm sự", exact: true })
    .evaluate(
      (node) =>
        new Promise<number>((resolve) => {
          const start = performance.now();
          (node as HTMLInputElement).click();
          requestAnimationFrame(() => resolve(performance.now() - start));
        }),
    );
  expect(timing).toBeLessThan(100);
  await testInfo.attach("local-selection-latency", {
    body: JSON.stringify({
      milliseconds: timing,
      environment: "local Chromium, not physical mobile hardware",
    }),
    contentType: "application/json",
  });
  const ui = await page.getByRole("main").innerText();
  for (const forbidden of [
    "Demo",
    "Một chút về bạn, để những cuộc gặp gỡ thú vị hơn.",
    "Ví dụ minh họa với dữ liệu giả định, không phải hồ sơ thật.",
  ])
    expect(ui).not.toContain(forbidden);
  expect(state.writes).toEqual([]);
});

test("T18: reconcile an uncertain save through GET without repeating the write", async ({
  page,
}) => {
  const state = await friendshipFixture(page);
  let first = true,
    writes = 0;
  await page.route("**/api/v1/profiles/matching-draft", async (route) => {
    if (route.request().method() !== "PUT" || !first) return route.fallback();
    first = false;
    writes++;
    const { expectedVersion, ...profile } = route.request().postDataJSON();
    state.profile = profile;
    state.version = expectedVersion + 1;
    return route.fulfill({
      status: 503,
      json: {
        error: { code: "UNCERTAIN", message: "Chưa nhận được xác nhận." },
      },
    });
  });
  await page.goto("/#/connect");
  await page.getByRole("radio", { name: "Bạn cùng học", exact: true }).check();
  await page.getByRole("button", { name: "Lưu bản nháp", exact: true }).click();
  await page
    .getByRole("button", { name: "Kiểm tra bản nháp đã lưu", exact: true })
    .click();
  await expect(
    page.getByText("Đã lưu bản nháp. Hồ sơ chưa được công khai.", {
      exact: true,
    }),
  ).toBeVisible();
  expect(writes).toBe(1);
  expect(state.live).toBe(false);
  await page
    .getByRole("radio", { name: "Có người tâm sự", exact: true })
    .check();
  await page.getByRole("button", { name: "Lưu bản nháp", exact: true }).click();
  await expect(
    page.getByText("Đã lưu bản nháp. Hồ sơ chưa được công khai.", {
      exact: true,
    }),
  ).toBeVisible();
  expect(state.writes.at(-1)?.body.expectedVersion).toBe(1);
  expect(state.profile.goal).toBe("study-buddy");
});

test("T18: uncertain publication reconciles the exact live snapshot without auto retry", async ({
  page,
}) => {
  const state = await friendshipFixture(page, LEGACY);
  let writes = 0;
  await page.route("**/api/v1/profiles/published/current", (route) =>
    route.fulfill({
      json: state.live
        ? {
            id: "p",
            profile: state.profile,
            version: state.publication,
            profileVersion: state.publication,
            state: "live",
          }
        : null,
    }),
  );
  await page.route("**/api/v1/profiles/published", (route) => {
    writes++;
    state.publication++;
    state.live = true;
    return route.fulfill({
      status: 503,
      json: {
        error: { code: "UNCERTAIN", message: "Chưa nhận được xác nhận." },
      },
    });
  });
  await page.goto("/#/connect?tab=profile");
  await page
    .getByRole("button", { name: "Chỉnh hồ sơ tìm bạn", exact: true })
    .click();
  await page.getByRole("radio", { name: "Bạn cùng học", exact: true }).check();
  await page
    .getByRole("radio", { name: "Từ từ làm quen", exact: true })
    .check();
  await page
    .getByRole("button", { name: "Xem lại trước khi hiển thị", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Hiển thị hồ sơ", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Kiểm tra hồ sơ đang hiển thị", exact: true })
    .click();
  await expect(
    page.getByText("Đã hiển thị hồ sơ tìm bạn.", { exact: true }),
  ).toBeVisible();
  expect(writes).toBe(1);
});

test("T27 T28: sent status stays, skip focuses next peer and expired ref never replays", async ({
  page,
}) => {
  const state = await friendshipFixture(page, LEGACY, true);
  state.candidates = [
    candidate("ref-1", "Bạn đồng hành A"),
    candidate("ref-2", "Bạn đồng hành B"),
    candidate("ref-3", "Bạn đồng hành C"),
  ];
  await page.route("**/api/v1/connection-requests", async (route) => {
    if (route.request().method() === "GET") return route.fallback();
    state.candidates = state.candidates.filter(
      (c) => c.candidateRef !== "ref-1",
    );
    return route.fulfill({ status: 201, json: { actionId: "receipt" } });
  });
  await page.route("**/api/v1/matching/skips", async (route) => {
    const ref = route.request().postDataJSON().candidateRef;
    state.candidates = state.candidates.filter((c) => c.candidateRef !== ref);
    return route.fulfill({ json: { actionId: "skip" } });
  });
  await page.goto("/#/connect");
  const first = page.getByRole("article", {
    name: "Hồ sơ của Bạn đồng hành A",
    exact: true,
  });
  await first
    .getByRole("button", { name: "Gửi lời mời kết nối", exact: true })
    .click();
  await expect(first.getByRole("status")).toHaveText("Đã gửi lời mời kết nối");
  await expect(
    first.getByRole("button", { name: "Chặn", exact: true }),
  ).toBeVisible();
  const second = page.getByRole("article", {
    name: "Hồ sơ của Bạn đồng hành B",
    exact: true,
  });
  await second.getByRole("button", { name: "Bỏ qua", exact: true }).click();
  await expect(second).toHaveCount(0);
  const third = page.getByRole("article", {
    name: "Hồ sơ của Bạn đồng hành C",
    exact: true,
  });
  await expect(third.getByRole("heading")).toBeFocused();
  let expiredWrites = 0;
  await page.route("**/api/v1/connection-requests", async (route) => {
    if (route.request().method() === "GET") return route.fallback();
    expiredWrites++;
    return route.fulfill({
      status: 410,
      json: {
        error: {
          code: "CANDIDATE_EXPIRED",
          message: "Gợi ý đã hết hạn. Vui lòng tải lại.",
        },
      },
    });
  });
  await third
    .getByRole("button", { name: "Gửi lời mời kết nối", exact: true })
    .click();
  await expect(third).toContainText("Gợi ý đã hết hạn");
  await third
    .getByRole("button", { name: "Tải lại gợi ý", exact: true })
    .click();
  expect(expiredWrites).toBe(1);
});

test("T11 T12 T14 T18: private partial save, same-intent retry and explicit conflict overwrite", async ({
  page,
}) => {
  const state = await friendshipFixture(page);
  await page.goto("/#/connect");
  await page.getByRole("radio", { name: "Bạn cùng học", exact: true }).check();
  await page.getByRole("tab", { name: "Gợi ý", exact: true }).click();
  const leave = page.getByRole("dialog", {
    name: "Bạn muốn lưu thay đổi trước khi rời đi?",
    exact: true,
  });
  state.failSave = true;
  await leave
    .getByRole("button", { name: "Lưu bản nháp và rời đi", exact: true })
    .click();
  await expect(leave).toContainText("Chưa lưu được bản nháp");
  state.failSave = false;
  await leave
    .getByRole("button", { name: "Lưu bản nháp và rời đi", exact: true })
    .click();
  await expect(
    page.getByRole("tab", { name: "Gợi ý", exact: true }),
  ).toHaveAttribute("aria-selected", "true");
  expect(state.writes[0].key).toBe(state.writes[1].key);
  expect(state.live).toBe(false);
  await page.getByRole("tab", { name: "Hồ sơ tìm bạn", exact: true }).click();
  await page
    .getByRole("button", { name: "Chỉnh hồ sơ tìm bạn", exact: true })
    .click();
  await expect(
    page.getByRole("radio", { name: "Bạn cùng học", exact: true }),
  ).toBeChecked();
  await page
    .getByRole("radio", { name: "Có người tâm sự", exact: true })
    .check();
  state.version++;
  state.staleSave = true;
  await page.getByRole("button", { name: "Lưu bản nháp", exact: true }).click();
  const conflict = page.getByRole("dialog", {
    name: "Bản nháp đã được cập nhật ở nơi khác.",
    exact: true,
  });
  await expect(conflict).toBeVisible();
  state.staleSave = false;
  await conflict
    .getByRole("button", { name: "Xem bản mới nhất", exact: true })
    .click();
  await conflict
    .getByRole("button", { name: "Ghi đè bằng bản đang chỉnh", exact: true })
    .click();
  const before = state.writes.length;
  expect(state.writes.at(-1)?.body.expectedVersion).toBe(1);
  await conflict
    .getByRole("button", { name: "Xác nhận ghi đè bản nháp", exact: true })
    .click();
  await expect(conflict).toHaveCount(0);
  expect(state.writes).toHaveLength(before + 1);
  expect(state.writes.at(-1)?.body.expectedVersion).toBe(2);
});

test("T14 T15: Forward, repeated Back, shell route, discard and native reload warning", async ({
  page,
}) => {
  await friendshipFixture(page);
  await page.goto("/#/assistants");
  const nav = page.getByRole("navigation", { name: "Điều hướng chính" });
  await nav.getByRole("link", { name: "Tìm bạn", exact: true }).click();
  await expect(
    page.getByRole("radio", { name: "Có người tâm sự", exact: true }),
  ).toBeVisible();
  await nav.getByRole("link", { name: "Tin nhắn", exact: true }).click();
  await page.goBack();
  await page
    .getByRole("radio", { name: "Có người tâm sự", exact: true })
    .check();
  await expect(
    page.getByRole("article", { name: "Hồ sơ của Bạn", exact: true }),
  ).toContainText("Có người tâm sự");
  const original = await page.evaluate(() => ({
    href: location.href,
    state: history.state,
  }));
  const dialog = page.getByRole("dialog", {
    name: "Bạn muốn lưu thay đổi trước khi rời đi?",
    exact: true,
  });
  await page.evaluate(() => history.forward());
  await expect(dialog).toBeVisible();
  await dialog
    .getByRole("button", { name: "Tiếp tục chỉnh", exact: true })
    .click();
  expect(
    await page.evaluate(() => ({ href: location.href, state: history.state })),
  ).toEqual(original);
  await page.evaluate(() => history.back());
  await expect(dialog).toBeVisible();
  await page.evaluate(() => history.back());
  await expect(dialog).toBeVisible();
  await dialog
    .getByRole("button", { name: "Tiếp tục chỉnh", exact: true })
    .click();
  expect(
    await page.evaluate(() => ({ href: location.href, state: history.state })),
  ).toEqual(original);
  const native = page.waitForEvent("dialog");
  const reload = page.evaluate(() => location.reload());
  const warning = await native;
  expect(warning.type()).toBe("beforeunload");
  await warning.dismiss();
  await reload;
  await nav.getByRole("link", { name: "Tin nhắn", exact: true }).click();
  await expect(dialog).toBeVisible();
  await dialog
    .getByRole("button", { name: "Bỏ thay đổi", exact: true })
    .click();
  await expect(page).toHaveURL(/#\/messages$/);
  await page.goBack();
  await expect(
    page.getByRole("radio", { name: "Có người tâm sự", exact: true }),
  ).not.toBeChecked();
});

test("T11 T13 T17 T36: missing public facets stay explicit; preview then final consent click", async ({
  page,
}) => {
  const state = await friendshipFixture(page);
  await page.goto("/#/connect");
  await page.getByRole("radio", { name: "Bạn cùng học", exact: true }).check();
  for (const name of ["Âm nhạc", "Cà phê", "Đọc sách"])
    await page.getByRole("checkbox", { name, exact: true }).check();
  await page
    .getByRole("radio", { name: "Từ từ làm quen", exact: true })
    .check();
  await page
    .getByRole("button", { name: "Xem lại trước khi hiển thị", exact: true })
    .click();
  const supplement = page.getByRole("region", {
    name: "Bổ sung để ghép bạn chính xác hơn",
    exact: true,
  });
  await expect(supplement.getByRole("checkbox", { checked: true })).toHaveCount(
    0,
  );
  await page
    .getByRole("button", { name: "Xem bản được chia sẻ", exact: true })
    .click();
  expect(state.writes).toEqual([]);
  for (const name of ["Tôn trọng", "Chân thành", "Tiếng Việt"])
    await supplement.getByRole("checkbox", { name, exact: true }).check();
  await expect(
    supplement.getByRole("checkbox", { name: "Tiếng Việt", exact: true }),
  ).toBeFocused();
  await page
    .getByRole("button", { name: "Xem bản được chia sẻ", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Hiển thị hồ sơ", exact: true }),
  ).toBeVisible();
  expect(state.writes.map((write) => write.path)).toEqual([
    "/profiles/matching-draft",
    "/profiles/matching-draft/preview",
  ]);
  expect(state.live).toBe(false);
  const reviewed = page.getByRole("article", {
    name: "Hồ sơ của Bạn",
    exact: true,
  });
  await expect(reviewed.locator("details")).toHaveAttribute("open", "");
  await expect(reviewed).toContainText("Tiếng Việt");
  expect(
    (
      await new AxeBuilder({ page }).include(".profile-editor").analyze()
    ).violations.filter((v) =>
      ["serious", "critical"].includes(v.impact ?? ""),
    ),
  ).toEqual([]);
  await page
    .getByRole("button", { name: "Hiển thị hồ sơ", exact: true })
    .click();
  await expect(
    page.getByText("Đã hiển thị hồ sơ tìm bạn.", { exact: true }),
  ).toBeVisible();
  expect(state.writes.at(-1)?.body).toEqual({
    draftVersion: 1,
    previewDigest: "token-1",
    expectedPublishedVersion: 0,
  });
  expect(state.live).toBe(true);
  await page.getByRole("tab", { name: "Hồ sơ tìm bạn", exact: true }).click();
  await page
    .getByRole("button", { name: "Chỉnh hồ sơ tìm bạn", exact: true })
    .click();
  await page
    .getByRole("radio", { name: "Có người tâm sự", exact: true })
    .check();
  await page.getByRole("button", { name: "Lưu bản nháp", exact: true }).click();
  await expect(
    page.getByText("Đã lưu bản nháp. Hồ sơ đang hiển thị chưa thay đổi.", {
      exact: true,
    }),
  ).toBeVisible();
  expect(state.writes.at(-1)?.body.expectedVersion).toBe(1);
  expect(state.profile.goal).toBe("study-buddy");
  expect(
    await page.evaluate(() =>
      [...Object.values(localStorage), ...Object.values(sessionStorage)].join(
        " ",
      ),
    ),
  ).not.toContain("featuredInterests");
});

test("T05 T06 T32 T33 T34 T35: mobile preview, concrete picker, reflow and keyboard", async ({
  page,
}, testInfo) => {
  const state = await friendshipFixture(page);
  await page.setViewportSize({ width: 320, height: 568 });
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/#/connect");
  await page
    .getByRole("radio", { name: "Có người tâm sự", exact: true })
    .check();
  await page.getByRole("button", { name: "Tiếp tục", exact: true }).click();
  await page
    .getByRole("button", { name: "Chọn sở thích sáng tạo", exact: true })
    .click();
  const picker = page.getByRole("dialog", {
    name: "Chọn sở thích nổi bật",
    exact: true,
  });
  await picker.getByRole("checkbox", { name: "Vẽ", exact: true }).check();
  await picker
    .getByRole("checkbox", { name: "Viết lách", exact: true })
    .check();
  await picker
    .getByRole("searchbox", { name: "Tìm sở thích", exact: true })
    .fill("ca phe");
  await expect(picker.getByRole("checkbox")).toHaveCount(1);
  await picker.getByRole("checkbox", { name: "Cà phê", exact: true }).check();
  await picker
    .getByRole("searchbox", { name: "Tìm sở thích", exact: true })
    .fill("no-such-interest");
  await expect(picker).toContainText(
    "Chưa thấy sở thích này. Thử từ khác nhé.",
  );
  await page.keyboard.press("Escape");
  await expect(
    page.getByRole("button", { name: /^Chọn sở thích sáng tạo/ }),
  ).toBeFocused();
  await page.getByRole("button", { name: "Xem hồ sơ", exact: true }).click();
  const preview = page.getByRole("dialog", {
    name: "Xem trước hồ sơ",
    exact: true,
  });
  await expect(preview).toContainText("Vẽ · Viết lách · Cà phê");
  await page.keyboard.press("Escape");
  await expect(
    page.getByRole("button", { name: "Xem hồ sơ", exact: true }),
  ).toBeFocused();
  for (const width of [320, 390, 430]) {
    await page.setViewportSize({ width, height: width === 320 ? 568 : 844 });
    await page.screenshot({
      path: testInfo.outputPath(`interest-entries-${width}.png`),
      fullPage: true,
    });
  }
  await page.getByRole("button", { name: "Tiếp tục", exact: true }).click();
  const gradual = page.getByRole("radio", {
    name: "Từ từ làm quen",
    exact: true,
  });
  await gradual.focus();
  await page.keyboard.press("Space");
  await page.keyboard.press("ArrowDown");
  await expect(
    page.getByRole("radio", { name: "Nói chuyện rôm rả", exact: true }),
  ).toBeChecked();
  for (const [width, height] of [
    [320, 568],
    [390, 844],
    [430, 932],
    [768, 1024],
    [1024, 768],
    [1280, 900],
    [1440, 900],
    [844, 390],
  ]) {
    await page.setViewportSize({ width, height });
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth,
      ),
    ).toBe(true);
    await page.screenshot({
      path: testInfo.outputPath(`builder-${width}x${height}.png`),
      fullPage: true,
    });
  }
  await page.setViewportSize({ width: 1280, height: 900 });
  const accessibility = await new AxeBuilder({ page })
    .include(".profile-editor")
    .analyze();
  expect(
    accessibility.violations.filter((v) =>
      ["serious", "critical"].includes(v.impact ?? ""),
    ),
  ).toEqual([]);
  expect(state.writes).toEqual([]);
});

test("T24 T25 T26: peer alias, factual reasons and grounded starter stay public-only", async ({
  page,
}) => {
  const state = await friendshipFixture(page, LEGACY, true);
  state.candidates = [
    {
      candidateRef: "ref-1",
      alias: "Bạn đồng hành aabbcc",
      avatarSeed: "aabbccdd",
      profileVersion: 7,
      peerVersion: 2,
      reasons: ["Cùng thích âm nhạc", "Cùng coi trọng tôn trọng"],
      matchLabel: "some",
      scoringVersion: "rules-v2",
      profile: {
        ...LEGACY,
        discovery: {
          version: 1,
          intention: "talk",
          connectionApproach: "gradual",
          featuredInterests: ["music"],
        },
      },
    },
  ];
  await page.goto("/#/connect");
  const card = page.getByRole("article", {
    name: "Hồ sơ của Bạn đồng hành aabbcc",
    exact: true,
  });
  await expect(
    card.getByRole("region", { name: "Gợi ý bắt đầu câu chuyện" }),
  ).toContainText(/bài hát/);
  await expect(card).toContainText("Có người tâm sự");
  await expect(
    card.getByRole("list", { name: "Điểm chung" }).getByRole("listitem"),
  ).toHaveCount(2);
  await card.getByText("Thông tin công khai", { exact: true }).click();
  await expect(card).toContainText("Cầu lông");
  await expect(card).not.toContainText("Private Name");
  expect(await card.innerText()).not.toMatch(/\d\s*%/);
  expect(state.writes).toEqual([]);
});

test("T01 T03 T04 T10: three questions, eight entries and immediate local preview", async ({
  page,
}) => {
  const state = await friendshipFixture(page);
  await page.goto("/#/connect");
  await expect(
    page.getByRole("heading", { name: "Tìm một người bạn hợp gu 🌷" }),
  ).toBeVisible();
  const builder = page.getByRole("region", {
    name: "Hồ sơ tìm bạn",
    exact: true,
  });
  await expect(
    builder
      .getByRole("group", { name: "Bạn đang tìm kiếm điều gì?", exact: true })
      .getByRole("radio"),
  ).toHaveCount(4);
  await expect(
    builder.locator(".friendship-entry-choices").locator("label, button"),
  ).toHaveCount(8);
  for (const name of ["Âm nhạc", "Cà phê", "Chơi game", "Xem phim", "Đọc sách", "Du lịch"])
    await expect(builder.getByRole("checkbox", { name, exact: true })).toBeVisible();
  for (const name of ["Chọn sở thích sáng tạo", "Chọn sở thích thể thao"])
    await expect(builder.getByRole("button", { name, exact: true })).toHaveAttribute("aria-haspopup", "dialog");
  await page.getByRole("radio", { name: "Bạn cùng học", exact: true }).check();
  for (const label of ["Âm nhạc", "Cà phê", "Đọc sách"])
    await builder.getByRole("checkbox", { name: label, exact: true }).check();
  await builder
    .getByRole("checkbox", { name: "Xem phim", exact: true })
    .click();
  await expect(
    page
      .getByRole("status")
      .filter({ hasText: "Bạn đã chọn 3 sở thích nổi bật" }),
  ).toBeVisible();
  await expect(
    builder.getByRole("checkbox", { name: "Xem phim", exact: true }),
  ).not.toBeChecked();
  await expect(
    builder.getByRole("checkbox", { name: "Xem phim", exact: true }),
  ).toBeFocused();
  await page
    .getByRole("radio", { name: "Nói chuyện rôm rả", exact: true })
    .check();
  const preview = page.getByRole("article", {
    name: "Hồ sơ của Bạn",
    exact: true,
  });
  await expect(preview).toContainText("Bạn cùng học");
  await expect(preview).toContainText("Nói chuyện rôm rả");
  await expect(preview).not.toContainText("Private Name");
  expect(state.writes).toEqual([]);
});

test("T14 T15: dirty Back/cancel/save/Forward retains native history state", async ({
  page,
}) => {
  const state = await friendshipFixture(page);
  await page.goto("/#/assistants");
  await page
    .getByRole("navigation", { name: "Điều hướng chính" })
    .getByRole("link", { name: "Tìm bạn", exact: true })
    .click();
  await page
    .getByRole("radio", { name: "Có người tâm sự", exact: true })
    .check();
  await expect(
    page.getByRole("article", { name: "Hồ sơ của Bạn", exact: true }),
  ).toContainText("Có người tâm sự");
  const original = await page.evaluate(() => ({
    href: location.href,
    state: history.state,
  }));
  await page.evaluate(() => history.back());
  const dialog = page.getByRole("dialog", {
    name: "Bạn muốn lưu thay đổi trước khi rời đi?",
    exact: true,
  });
  await expect(dialog).toBeVisible();
  await expect(
    dialog.getByRole("button", { name: "Tiếp tục chỉnh", exact: true }),
  ).toBeFocused();
  await dialog
    .getByRole("button", { name: "Tiếp tục chỉnh", exact: true })
    .click();
  expect(
    await page.evaluate(() => ({ href: location.href, state: history.state })),
  ).toEqual(original);
  await page.evaluate(() => history.back());
  await expect(dialog).toBeVisible();
  await dialog
    .getByRole("button", { name: "Lưu bản nháp và rời đi", exact: true })
    .click();
  await expect(page).toHaveURL(/#\/assistants$/);
  expect(
    state.writes.filter((w) => w.path === "/profiles/matching-draft"),
  ).toHaveLength(1);
  await page.goForward();
  await expect(page).toHaveURL(/#\/connect$/);
  await page
    .getByRole("button", { name: "Chỉnh hồ sơ tìm bạn", exact: true })
    .click();
  await expect(
    page.getByRole("radio", { name: "Có người tâm sự", exact: true }),
  ).toBeChecked();
  expect(await page.evaluate(() => history.state)).toEqual(original.state);
});

test("T07 T12 T13 T16: legacy full data, failed save, exact reviewed snapshot and separate publish", async ({
  page,
}) => {
  const state = await friendshipFixture(page, LEGACY, true);
  await page.goto("/#/connect?tab=profile");
  await page
    .getByRole("button", { name: "Chỉnh hồ sơ tìm bạn", exact: true })
    .click();
  await page.getByRole("radio", { name: "Bạn cùng học", exact: true }).check();
  await page
    .getByRole("radio", { name: "Cùng làm gì đó trước", exact: true })
    .check();
  await page
    .getByRole("button", { name: "Bỏ nổi bật: Đọc sách", exact: true })
    .click();
  state.failSave = true;
  await page.getByRole("button", { name: "Đóng", exact: true }).click();
  const dialog = page.getByRole("dialog", {
    name: "Bạn muốn lưu thay đổi trước khi rời đi?",
    exact: true,
  });
  await dialog
    .getByRole("button", { name: "Lưu bản nháp và rời đi", exact: true })
    .click();
  await expect(dialog).toContainText("Chưa lưu được bản nháp");
  state.failSave = false;
  await dialog
    .getByRole("button", { name: "Tiếp tục chỉnh", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Xem lại trước khi hiển thị", exact: true })
    .click();
  const reviewed = page.getByRole("article", {
    name: "Hồ sơ của Bạn",
    exact: true,
  });
  await expect(reviewed.locator("details")).toHaveAttribute("open", "");
  await expect(reviewed).toContainText("Tìm bạn luyện ngoại ngữ");
  await expect(reviewed).toContainText("Thích nói thẳng");
  expect(state.profile.interests).toEqual(LEGACY.interests);
  expect(
    state.writes.filter((w) => w.path === "/profiles/published"),
  ).toHaveLength(0);
  state.expirePreview = true;
  await page
    .getByRole("button", { name: "Cập nhật hồ sơ hiển thị", exact: true })
    .click();
  await expect(
    page.getByText(
      "Bản xem trước đã thay đổi hoặc hết hạn. Xem lại trước khi hiển thị nhé.",
      { exact: true },
    ),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Cập nhật hồ sơ hiển thị", exact: true }),
  ).toHaveCount(0);
});

const TAXONOMY = {
  version: "v2",
  interests: { reading: "Đọc sách", music: "Âm nhạc", walking: "Đi bộ" },
  values: { respect: "Tôn trọng", sincerity: "Chân thành" },
  languages: { vi: "Tiếng Việt" },
  styles: { balanced: "Cân bằng" },
  goals: { friendship: "Tìm bạn trò chuyện" },
  activities: { focus: "Cùng tập trung" },
  availability: { weekday_evening: "Tối ngày thường" },
  categories: {
    learning: ["reading"],
    creative: ["music"],
    active: ["walking"],
  },
  categoryLabels: {
    learning: "Học hỏi",
    creative: "Sáng tạo",
    active: "Vận động",
  },
  limits: {
    interests: [3, 10],
    values: [2, 4],
    languages: [1, 2],
    activities: [0, 4],
    availability: [0, 6],
  },
};
const PROFILE = {
  interests: ["reading", "music", "walking"],
  values: ["respect", "sincerity"],
  style: "balanced",
  goal: "friendship",
  languages: ["vi"],
  activities: [],
  availability: [],
  strictGoal: false,
};

type Options = { live?: boolean; incoming?: number; ageBand?: string };

async function mock(
  page: Page,
  { live = false, incoming = 0, ageBand = "adult" }: Options = {},
) {
  const session = {
    userId: "11111111-1111-4111-8111-111111111111",
    alias: "An",
    ageBand,
    eligible: true,
    csrfToken: "test-csrf",
    serverTime: "2026-10-23T08:00:00Z",
    timezone: "Asia/Bangkok",
    features: { ai: false, matching: true, voice: false },
    staff: null,
    notices: [],
    consents: Object.fromEntries(
      ["AI", "MEM", "MATCH", "VOICE"].map((p) => [
        p,
        {
          enabled: p === "MATCH" && ageBand === "adult",
          version: 1,
          policyVersion: "v1",
        },
      ]),
    ),
  };
  const requests = Array.from({ length: incoming }, (_, index) => ({
    id: `req-${index}`,
    status: "pending",
    version: 1,
    direction: "incoming",
    expiresAt: "2026-10-30T08:00:00Z",
    peer: {
      alias: `Bạn đồng hành 00000${index}`,
      avatarSeed: `seed${index}`,
      profile: PROFILE,
      reasons: [],
      matchLabel: "some",
      sharedActivities: [],
    },
  }));
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname.replace("/api/v1", "");
    const json: Record<string, unknown> = {
      "/session": session,
      "/social/summary": {
        pendingIncomingRequests: incoming,
        unreadConnections: 0,
        activityInvites: 0,
      },
      "/taxonomy": TAXONOMY,
      "/profiles/matching-draft": {
        profile: PROFILE,
        version: 1,
        publishedVersion: live ? 1 : null,
      },
      "/profiles/published/current": live
        ? {
            id: "p",
            profile: PROFILE,
            version: 1,
            state: "live",
            profileVersion: 1,
          }
        : null,
      "/matching/candidates": { candidates: [] },
      "/connection-requests": requests,
      "/bots": [],
      "/ai/conversations": [],
    };
    if (path in json) return route.fulfill({ json: json[path] });
    return route.fulfill({
      status: 404,
      json: { error: { code: "NOT_FOUND", message: "Missing" } },
    });
  });
}

test("discovery tabs follow the arrow keys and keep the tab in the URL", async ({
  page,
}) => {
  await mock(page);
  await page.goto("/#/connect");
  const tabs = page.getByRole("tablist", { name: "Tìm bạn" });
  const profile = tabs.getByRole("tab", { name: "Hồ sơ tìm bạn" });
  // Without a live profile the editor tab comes first.
  await expect(profile).toHaveAttribute("aria-selected", "true");
  await expect(
    page.getByRole("tabpanel", { name: "Hồ sơ tìm bạn" }),
  ).toContainText("Chỉnh hồ sơ tìm bạn");
  await profile.focus();
  await page.keyboard.press("ArrowRight");
  await expect(
    tabs.getByRole("tab", { name: "Thông tin riêng" }),
  ).toBeFocused();
  await page.keyboard.press("ArrowRight");
  const suggestions = tabs.getByRole("tab", { name: "Gợi ý" });
  await expect(suggestions).toBeFocused();
  await expect(suggestions).toHaveAttribute("aria-selected", "true");
  await expect(page).toHaveURL(/#\/connect\?tab=suggestions$/);
  await expect(page.getByRole("tabpanel", { name: "Gợi ý" })).toContainText(
    "Hãy hiển thị hồ sơ tìm bạn để nhận gợi ý.",
  );
  await page.keyboard.press("End");
  await expect(
    tabs.getByRole("tab", { name: "Thông tin riêng" }),
  ).toBeFocused();
  await page.keyboard.press("Home");
  await expect(suggestions).toBeFocused();
  await page.keyboard.press("ArrowLeft");
  await expect(
    tabs.getByRole("tab", { name: "Thông tin riêng" }),
  ).toBeFocused();
  await page.keyboard.press("ArrowLeft");
  await expect(profile).toBeFocused();
  await page.keyboard.press("ArrowLeft");
  await expect(tabs.getByRole("tab", { name: /Lời mời/ })).toBeFocused();
  await expect(page).toHaveURL(/tab=requests$/);
  // Only the selected tab is in the tab order.
  await expect(tabs.locator('[tabindex="0"]')).toHaveCount(1);
  await page.reload();
  await expect(tabs.getByRole("tab", { name: /Lời mời/ })).toHaveAttribute(
    "aria-selected",
    "true",
  );
  await page.goto("/#/messages");
  await page.goBack();
  await expect(tabs.getByRole("tab", { name: /Lời mời/ })).toHaveAttribute(
    "aria-selected",
    "true",
  );
});

test("pending invitations badge the nav and the tab, and the nav opens them", async ({
  page,
}) => {
  await mock(page, { live: true, incoming: 2 });
  await page.goto("/#/assistants");
  const nav = page.getByRole("navigation", { name: "Điều hướng chính" });
  const connect = nav.getByRole("link", {
    name: "Tìm bạn, 2 lời mời kết nối mới",
  });
  await expect(connect).toHaveAttribute("href", "#/connect?tab=requests");
  await connect.click();
  const tab = page.getByRole("tab", { name: "Lời mời (2)" });
  await expect(tab).toHaveAttribute("aria-selected", "true");
  await expect(
    page.getByRole("tabpanel", { name: "Lời mời (2)" }),
  ).toContainText("Bạn đồng hành 000000 muốn kết nối với bạn");
  await page.goto("/#/connect");
  // A live profile opens on suggestions when no tab is named.
  await expect(page.getByRole("tab", { name: "Gợi ý" })).toHaveAttribute(
    "aria-selected",
    "true",
  );
});

test("the main navigation opens the profile editor for adults without a live profile", async ({
  page,
}) => {
  await mock(page);
  await page.goto("/#/assistants");
  const connect = page
    .getByRole("navigation", { name: "Điều hướng chính" })
    .getByRole("link", { name: "Tìm bạn", exact: true });
  await expect(connect).toHaveAttribute("href", "#/connect");
  await connect.click();
  await expect(
    page.getByRole("tab", { name: "Hồ sơ tìm bạn" }),
  ).toHaveAttribute("aria-selected", "true");
  await expect(
    page.getByRole("tabpanel", { name: "Hồ sơ tìm bạn" }),
  ).toContainText("Chỉnh hồ sơ tìm bạn");
});

test("the main navigation opens suggestions for a live profile", async ({
  page,
}) => {
  await mock(page, { live: true });
  await page.goto("/#/assistants");
  await page
    .getByRole("navigation", { name: "Điều hướng chính" })
    .getByRole("link", { name: "Tìm bạn", exact: true })
    .click();
  await expect(page.getByRole("tab", { name: "Gợi ý" })).toHaveAttribute(
    "aria-selected",
    "true",
  );
  await expect(page.getByRole("tabpanel", { name: "Gợi ý" })).toBeVisible();
});

test("minors reach the global age gate without loading candidates", async ({ page }) => {
  const reads: string[] = [];
  page.on("request", request => { if (request.url().includes("/matching/candidates")) reads.push(request.url()); });
  await mock(page, { ageBand: "teen" });
  await page.goto("/#/connect");
  await expect(page.getByText("Bạn cần đủ 18 tuổi để sử dụng MoodPrint.", { exact: true })).toBeVisible();
  await expect(page.getByRole("navigation", { name: "Điều hướng chính" })).toHaveCount(0);
  expect(reads).toEqual([]);
});
