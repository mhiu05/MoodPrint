import { test, expect, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

async function route(page: Page, path: string) {
  await page.evaluate((p) => {
    location.hash = p;
  }, path);
  await page.evaluate(
    () =>
      new Promise<void>((resolve) => requestAnimationFrame(() => resolve())),
  );
}
async function dismiss(page: Page) {
  for (const name of ["Đóng giới thiệu bản mẫu", "Đóng thông báo"]) {
    const b = page.getByRole("button", { name, exact: true });
    if (await b.isVisible()) await b.click();
  }
}
async function start(page: Page, query = "") {
  await page.goto(`/${query}`);
  await expect(
    page.getByRole("heading", { name: /Bạn muốn kể gì/ }),
  ).toBeVisible();
  await dismiss(page);
}
async function share(page: Page, link = false) {
  await route(page, "/profile?tab=sharing");
  await page.getByRole("button", { name: "Dùng lựa chọn mẫu" }).click();
  if (link)
    await page.getByRole("checkbox", { name: "Liên kết với sở thích" }).check();
  await page.getByRole("button", { name: "Xem trước hồ sơ" }).click();
  await page
    .getByRole("checkbox", { name: "Cho phép dùng hồ sơ này để tìm bạn" })
    .check();
  await page
    .getByRole("button", { name: "Cho phép chia sẻ", exact: true })
    .click();
  await expect(page.getByText("Đang chia sẻ", { exact: true })).toBeVisible();
  await dismiss(page);
}
async function connect(page: Page) {
  await route(page, "/connect");
  const card = page.getByRole("article").filter({
    has: page.getByRole("heading", { name: "Lá Non", exact: true }),
  });
  await card.getByRole("button", { name: "Làm quen" }).click();
  await expect(page.locator("#human-message")).toHaveCount(0);
  await page.getByRole("button", { name: "Đồng ý", exact: true }).click();
  await page.getByRole("link", { name: "Mở trò chuyện" }).click();
  await dismiss(page);
}
async function activity(page: Page) {
  await page.getByRole("button", { name: /Cùng làm gì đó/ }).click();
  await page
    .getByRole("button", { name: "Mời cùng tham gia", exact: true })
    .click();
  await expect(page.getByRole("radio")).toHaveCount(0);
  await page
    .getByRole("button", { name: "Đồng ý hoạt động", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: /Nếu có một ngày/ }),
  ).toBeVisible();
}

test("Entry: roster, four tabs, search and browser history without onboarding", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await start(page);
  await expect(page).toHaveTitle(/Me2We/);
  await expect(
    page
      .getByRole("navigation", { name: "Điều hướng chính" })
      .getByRole("link"),
  ).toHaveCount(4);
  await expect(page.locator(".bot-row")).toHaveCount(5);
  await expect(page.getByRole("radio")).toHaveCount(0);
  await page.getByRole("textbox", { name: "Tìm trợ lý" }).fill("Gương");
  await expect(page.locator(".bot-row")).toHaveCount(1);
  await page.getByRole("link", { name: "Trò chuyện với Gương" }).click();
  await expect(
    page.getByRole("heading", { level: 1, name: /Gương/ }),
  ).toBeVisible();
  await expect(
    page.getByRole("navigation", { name: "Điều hướng chính" }),
  ).not.toBeVisible();
  await page.getByRole("link", { name: "Về danh sách trợ lý" }).click();
  await expect(page.locator(".bot-row")).toHaveCount(1);
  await page.goBack();
  await expect(
    page.getByRole("log", { name: "Hội thoại với Gương" }),
  ).toBeVisible();
  await page.goForward();
  await expect(page.getByRole("textbox", { name: "Tìm trợ lý" })).toBeVisible();
});

test("Multi-bot: continuity, pending reply isolation, unread and preview", async ({
  page,
}) => {
  await start(page);
  await route(page, "/assistants/may");
  await page
    .getByLabel("Tin nhắn cho Mây", { exact: true })
    .fill("Chuyện riêng mình kể với Mây");
  await page.getByRole("button", { name: "Gửi tin cho AI" }).click();
  await route(page, "/assistants/guong");
  await page
    .getByRole("button", { name: "Mình thích đọc sách", exact: true })
    .click();
  await expect(page.getByRole("log")).toContainText("Khi đọc sách");
  await expect(page.getByRole("log")).not.toContainText("Một ngày dài à?");
  await expect(page.getByRole("log")).not.toContainText(
    "Chuyện riêng mình kể với Mây",
  );
  await expect(
    page
      .getByRole("link", { name: "Trò chuyện với Mây" })
      .locator(".unread-dot"),
  ).toBeVisible();
  await route(page, "/assistants/may");
  await expect(page.getByRole("log")).toContainText(
    "Chuyện riêng mình kể với Mây",
  );
  await expect(page.getByRole("log")).toContainText("Một ngày dài à?");
  await expect(page.getByRole("log")).not.toContainText("Khi đọc sách");
  await expect(
    page.getByRole("link", { name: "Trò chuyện với Mây" }),
  ).toContainText("Một ngày dài à?");
});

test("Bot scenarios: mood, insights, edited private profile, puzzle and matching CTA", async ({
  page,
}) => {
  await start(page);
  await route(page, "/assistants/nhip");
  await page
    .getByRole("button", { name: "2 Hơi khó chịu", exact: true })
    .click();
  await expect(page.getByText("Đã giữ lại nhịp hôm nay")).toBeVisible();
  await page.getByRole("button", { name: "Xem xu hướng", exact: true }).click();
  await expect(page.getByRole("log")).toContainText("Nhịp cảm xúc của bạn");
  await expect(page.getByText("3,0", { exact: true })).toBeVisible();
  await route(page, "/assistants/guong");
  await page
    .getByRole("button", { name: "Mình thích đọc sách", exact: true })
    .click();
  await expect(page.getByRole("log")).toContainText("Khi đọc sách");
  await page
    .getByRole("button", {
      name: "Mình thích khoảng yên tĩnh khi đọc sách",
      exact: true,
    })
    .click();
  await page
    .getByRole("button", { name: "Chưa đúng lắm", exact: true })
    .click();
  await page
    .getByLabel("Điều muốn giữ lại")
    .fill("Mình thích đọc thơ lúc rảnh");
  await page.getByRole("button", { name: "Lưu điều đã sửa" }).click();
  await expect(page.getByRole("log")).toContainText("Đã lưu vào hồ sơ riêng");
  await route(page, "/profile");
  await expect(
    page.getByRole("heading", { name: "Mình thích đọc thơ lúc rảnh" }),
  ).toBeVisible();
  await expect(
    page.getByText("Chưa cho phép dùng lại khi trò chuyện.").last(),
  ).toBeVisible();
  await route(page, "/assistants/rure");
  await page.getByRole("button", { name: "Giải đố", exact: true }).click();
  await page.getByRole("button", { name: "Xem đáp án", exact: true }).click();
  await expect(page.getByRole("log")).toContainText("cái hố");
  await route(page, "/assistants/caunoi");
  await page
    .getByRole("button", { name: "Cùng học tiếng Anh", exact: true })
    .click();
  await page.getByRole("link", { name: /Xem người phù hợp/ }).click();
  await expect(page.getByRole("article")).toHaveCount(4);
  await expect(
    page.getByRole("heading", { name: /Gặp người cùng tần số/ }),
  ).toBeVisible();
});

test("T-B01/B02/B03: AI off, explicit sharing, ranking, mutual consent and contact preview", async ({
  page,
}) => {
  await start(page, "?fixture=fresh&ai=off&mem=off");
  await route(page, "/assistants/may");
  await expect(page.locator("#bot-message")).toHaveCount(0);
  await share(page);
  await route(page, "/connect");
  await expect(page.getByRole("article").locator("h2")).toHaveText([
    "Mầm Xanh",
    "Lá Non",
    "Nắng Mai",
    "Suối Nhỏ",
  ]);
  await page
    .getByRole("article")
    .nth(1)
    .getByRole("button", { name: "Làm quen" })
    .click();
  await route(page, "/chat/CON-C01-001");
  await expect(page.getByRole("log")).toHaveCount(0);
  await expect(page.getByText(/Phòng không tồn tại/)).toBeVisible();
  await page.getByRole("button", { name: "Đồng ý", exact: true }).click();
  await page.getByRole("link", { name: "Mở trò chuyện" }).click();
  await dismiss(page);
  await page
    .getByRole("button", { name: "Dạo này bạn đang đọc gì?", exact: true })
    .click();
  await expect(page.getByRole("log")).toContainText(
    "Mình đang đọc một tập truyện ngắn.",
  );
  await page.locator("#human-message").fill("mail@example.test");
  await page.getByRole("button", { name: "Gửi tin nhắn demo" }).click();
  await page.getByRole("button", { name: "Sửa tin nhắn", exact: true }).click();
  await expect(page.locator("#human-message")).toHaveValue("mail@example.test");
  await expect(page.getByRole("log")).not.toContainText("mail@example.test");
});

test("T-F01/F03: activity consent, answers, skip, peer reply, completion and previews", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await start(page);
  await connect(page);
  await page.getByRole("button", { name: /Cùng làm gì đó/ }).click();
  for (const name of ["Học cùng nhau", "Luyện tiếng Anh", "Trò chơi nhỏ"]) {
    await page.getByRole("button", { name: new RegExp(name) }).click();
    await expect(page.getByRole("dialog")).toContainText("Bản xem trước");
    await page.getByRole("button", { name: "Về hoạt động chung" }).click();
  }
  await page
    .getByRole("button", { name: "Về trò chuyện", exact: true })
    .click();
  await activity(page);
  for (let i = 0; i < 3; i++) {
    if (i === 1)
      await page
        .getByRole("button", { name: "Bỏ qua câu này", exact: true })
        .click();
    else await page.getByRole("radio").first().check();
    await expect(page.getByText(/Bạn cùng chơi:/)).toBeVisible();
    await page
      .getByRole("button", {
        name: i === 2 ? "Hoàn tất hoạt động" : "Câu tiếp theo",
        exact: true,
      })
      .click();
  }
  await expect(
    page.getByRole("heading", { name: "Thêm một chút hiểu nhau!" }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Tiếp tục trò chuyện", exact: true })
    .click();
  await expect(page.locator("#human-message")).toBeVisible();
});

test("T-F02: Back and Escape respect active activity; stopping never resumes", async ({
  page,
}) => {
  await start(page);
  await connect(page);
  await activity(page);
  await page
    .getByRole("button", { name: "Bỏ qua câu này", exact: true })
    .click();
  await page.goBack();
  await expect(
    page.getByRole("dialog", { name: "Dừng hoạt động trước khi rời đi?" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Ở lại chơi tiếp" }).click();
  await expect(
    page.getByRole("heading", { name: /Nếu có một ngày/ }),
  ).toBeVisible();
  await page.keyboard.press("Escape");
  await page.getByRole("button", { name: "Dừng và rời đi" }).click();
  await route(page, "/chat/CON-C01-001?panel=activity&activityId=ACT01");
  await expect(
    page.getByRole("button", { name: "Mời cùng tham gia" }),
  ).toBeVisible();
  await expect(page.getByRole("radio")).toHaveCount(0);
});

test("T-C03/C04: MATCH revocation closes rooms and re-enable never revives", async ({
  page,
}) => {
  await start(page);
  await connect(page);
  await route(page, "/settings");
  const permission = page.getByRole("switch", {
    name: /Dùng hồ sơ để tìm bạn/,
  });
  await permission.click();
  await page.getByRole("button", { name: "Hủy", exact: true }).click();
  await expect(permission).toBeChecked();
  await permission.click();
  await page.getByRole("button", { name: "Tắt quyền này" }).click();
  await permission.check();
  await route(page, "/chat/CON-C01-001?panel=activity&activityId=ACT01");
  await expect(page.getByRole("log")).toHaveCount(0);
  await expect(
    page.getByRole("link", { name: "Soạn hồ sơ kết nối" }),
  ).toBeVisible();
  await route(page, "/assistants/may");
  await expect(page.locator("#bot-message")).toBeVisible();
});

test("T-E01/E02/E03/E04: teen, unknown, under16 and route injection stay guarded", async ({
  page,
}) => {
  for (const fixture of ["teen", "unknown", "under16"]) {
    for (const path of [
      "/chat/CON-C01-001",
      "/chat/CON-C01-001?panel=activity&activityId=ACT01",
    ]) {
      await page.goto(`/?fixture=${fixture}#${path}`);
      await expect(page.locator("#human-message")).toHaveCount(0);
      await expect(page.getByRole("log")).toHaveCount(0);
    }
  }
  await page.goto("/?fixture=teen#/profile?tab=sharing");
  await dismiss(page);
  await page.getByRole("button", { name: "Dùng lựa chọn mẫu" }).click();
  await page.getByRole("button", { name: "Xem trước hồ sơ" }).click();
  await expect(
    page.getByRole("button", { name: "Cho phép chia sẻ", exact: true }),
  ).toBeDisabled();
  await page.getByRole("button", { name: "Mình chưa muốn chia sẻ" }).click();
  await route(page, "/settings?fixture=adult&age=adult");
  await expect(
    page.getByRole("switch", { name: /Dùng hồ sơ để tìm bạn/ }),
  ).toBeDisabled();
  for (const fixture of ["unknown", "under16"]) {
    await page.goto(`/?fixture=${fixture}#/assistants/may`);
    await expect(
      page.getByRole("heading", { name: "Phiên chưa được khởi tạo" }),
    ).toBeVisible();
    await expect(page.locator("#bot-message")).toHaveCount(0);
  }
});

test("T-D01/D02/D03/D04: directional field consent, revoke, deny, block and report", async ({
  page,
}) => {
  await start(page);
  await connect(page);
  await page.getByText("Chia sẻ từng thông tin", { exact: true }).click();
  await page
    .getByRole("button", { name: "Mô phỏng yêu cầu xem tên mình", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Xem trước & quyết định", exact: true })
    .click();
  await expect(page.getByRole("dialog")).toContainText("Người nhận: Lá Non");
  await page.getByRole("button", { name: "Đồng ý chia sẻ trường này" }).click();
  await page.getByRole("button", { name: "Thu hồi", exact: true }).click();
  await expect(
    page.getByText("Tên hiển thị · An → Lá Non · Đã thu hồi"),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Xin xem tên đối phương", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Mô phỏng phản hồi", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Từ chối chia sẻ", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Dạo này bạn đang đọc gì?", exact: true })
    .click();
  await page.getByRole("button", { name: "Tùy chọn cuộc trò chuyện" }).click();
  await page.getByRole("button", { name: "Chặn ngay", exact: true }).click();
  await expect(page.getByRole("log")).toHaveCount(0);
  await route(page, "/settings?tab=safety");
  await page
    .getByRole("button", { name: "Tạo phiếu demo", exact: true })
    .click();
  await expect(page.getByRole("alert")).toContainText("chọn một lý do");
  await page.getByRole("radio", { name: "Bị ép chia sẻ", exact: true }).check();
  await page
    .getByRole("button", { name: "Tạo phiếu demo", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Phiếu DEMO-R001" }),
  ).toBeVisible();
  await route(page, "/chat/CON-C01-001");
  await expect(page.getByRole("log")).toHaveCount(0);
});

test("T-C05: editing a linked private source invalidates rooms without publishing the edit", async ({
  page,
}) => {
  await start(page);
  await share(page, true);
  await connect(page);
  await route(page, "/profile");
  await page.getByRole("button", { name: "Sửa lại PI01", exact: true }).click();
  await page
    .getByLabel("Nội dung mẫu", { exact: true })
    .fill("Mình thích thử sở thích mới");
  await page.getByRole("button", { name: "Lưu thay đổi", exact: true }).click();
  await route(page, "/chat/CON-C01-001");
  await expect(page.getByRole("log")).toHaveCount(0);
  await expect(
    page.getByRole("link", { name: "Soạn hồ sơ kết nối" }),
  ).toBeVisible();
});

test("T-A03/A04/R01/R02: error/retry, stop, AI revoke, reset cancel/confirm and stale timers", async ({
  page,
}) => {
  await start(page, "?tools=1");
  await route(page, "/settings");
  await page
    .getByText("Công cụ demo · Dành cho kiểm thử nội bộ", { exact: true })
    .click();
  await page
    .getByRole("button", { name: "Thử lỗi một lần", exact: true })
    .click();
  await route(page, "/assistants/may");
  await page.getByRole("button", { name: "Kể một chút", exact: true }).click();
  await page
    .getByRole("button", { name: "Thử lại phản hồi", exact: true })
    .click();
  await expect(page.getByRole("log")).toContainText("Một ngày dài à?");
  await page.getByRole("button", { name: "Kể một chút", exact: true }).click();
  await page.getByRole("button", { name: "Dừng", exact: true }).click();
  await route(page, "/settings");
  await page.getByRole("switch", { name: /Trò chuyện với AI/ }).click();
  await page.getByRole("button", { name: "Tắt quyền này" }).click();
  await route(page, "/assistants/guong");
  await expect(page.locator("#bot-message")).toHaveCount(0);
  await route(page, "/settings");
  await page
    .getByRole("button", { name: "Đặt lại bản trải nghiệm", exact: true })
    .click();
  await page.getByRole("button", { name: "Hủy", exact: true }).click();
  await expect(
    page.getByRole("switch", { name: /Trò chuyện với AI/ }),
  ).not.toBeChecked();
  await page
    .getByRole("button", { name: "Đặt lại bản trải nghiệm", exact: true })
    .click();
  await page.getByRole("button", { name: "Đặt lại toàn bộ" }).click();
  await expect(page.locator(".bot-row")).toHaveCount(5);
  await route(page, "/assistants/may");
  await expect(page.getByRole("log")).not.toContainText("Một ngày dài à?");
  await page.reload();
  await dismiss(page);
  await expect(page.getByRole("log")).not.toContainText("Một ngày dài à?");
});

test("Mood CRUD, keyboard controls and real recomputation", async ({
  page,
}) => {
  await start(page);
  await route(page, "/self?tab=mood");
  await page.getByRole("radio", { name: "1 Rất khó chịu" }).focus();
  await page.keyboard.press("ArrowRight");
  await expect(
    page.getByRole("radio", { name: "2 Hơi khó chịu" }),
  ).toBeChecked();
  await page
    .getByRole("button", { name: "Lưu tâm trạng", exact: true })
    .click();
  await route(page, "/self?tab=week");
  await expect(page.getByText("3,0", { exact: true })).toBeVisible();
  await route(page, "/self?tab=mood");
  await page.getByRole("button", { name: "Xóa 2026-10-22" }).click();
  await page.getByRole("button", { name: "Xóa ghi nhận", exact: true }).click();
  await route(page, "/self?tab=week");
  await expect(page.getByText("3,2", { exact: true })).toBeVisible();
});

test("T-U02/N01: focus trap, Escape return, invalid bot and legacy route", async ({
  page,
}) => {
  await start(page);
  await route(page, "/settings");
  const open = page.getByRole("button", {
    name: "Đặt lại bản trải nghiệm",
    exact: true,
  });
  await open.click();
  await page.keyboard.press("Shift+Tab");
  await expect(
    page.getByRole("button", { name: "Đóng hộp thoại" }),
  ).toBeFocused();
  await page.keyboard.press("Shift+Tab");
  await expect(
    page.getByRole("button", { name: "Đặt lại toàn bộ" }),
  ).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(
    page.getByRole("button", { name: "Đóng hộp thoại" }),
  ).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(open).toBeFocused();
  await route(page, "/assistants/nonexistent");
  await expect(page).toHaveURL(/#\/assistants$/);
  await route(page, "/self?tab=chat");
  await expect(page).toHaveURL(/#\/assistants\/may$/);
});

test("T-N02: no external network, persistence, microphone or sensitive console", async ({
  page,
  baseURL,
}) => {
  const external: string[] = [],
    errors: string[] = [];
  let micCalls = 0;
  page.on("request", (r) => {
    if (!r.url().startsWith(`${new URL(baseURL!).origin}/`)) external.push(r.url());
  });
  page.on("pageerror", () => errors.push("pageerror"));
  page.on("console", (m) => {
    if (["error", "warning"].includes(m.type())) errors.push(m.type());
  });
  await page.exposeFunction("micWasCalled", () => {
    micCalls++;
  });
  await page.addInitScript(() => {
    if (navigator.mediaDevices)
      navigator.mediaDevices.getUserMedia = async () => {
        await (window as any).micWasCalled();
        throw new Error("Forbidden");
      };
  });
  await start(page);
  await route(page, "/assistants/may");
  await page
    .getByLabel("Tin nhắn cho Mây", { exact: true })
    .fill("Nội dung riêng không được lưu");
  await page.getByRole("button", { name: "Gửi tin cho AI" }).click();
  await expect(page.getByRole("log")).toContainText("Một ngày dài à?");
  await connect(page);
  await activity(page);
  await page.getByRole("button", { name: "Dừng ở đây", exact: true }).click();
  await page
    .getByRole("button", { name: "Dừng hoạt động", exact: true })
    .click();
  await route(page, "/settings");
  await page.getByRole("button", { name: "Xem bản xuất dữ liệu giả" }).click();
  await expect(page.getByRole("dialog")).not.toContainText(
    "Nội dung riêng không được lưu",
  );
  const storage = await page.evaluate(async () => ({
    local: localStorage.length,
    session: sessionStorage.length,
    cookies: document.cookie,
    dbs: (await indexedDB.databases()).length,
  }));
  expect(storage).toEqual({ local: 0, session: 0, cookies: "", dbs: 0 });
  expect(external).toEqual([]);
  expect(errors).toEqual([]);
  expect(micCalls).toBe(0);
});

test("T-U01/U02/U03/V01: seven viewports, reduced motion, full viewport and axe", async ({
  page,
}) => {
  test.setTimeout(240000);
  await start(page);
  for (const width of [360, 375, 390, 430, 768, 1280, 1440]) {
    await page.setViewportSize({ width, height: 844 });
    for (const path of [
      "/assistants",
      "/assistants/may",
      "/assistants/nhip",
      "/connect",
      "/messages",
      "/profile",
      "/profile?tab=sharing",
      "/settings",
    ]) {
      await route(page, path);
      await expect(page.locator("main")).toBeVisible();
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= innerWidth,
        ),
      ).toBe(true);
      if (path === "/assistants/may" && width < 768) {
        const box = await page.locator(".bot-conversation").boundingBox();
        expect(Math.abs(box!.height - 844)).toBeLessThan(2);
        expect(box!.x).toBe(0);
        await expect(page.locator(".bot-composer")).toBeInViewport();
      }
    }
  }
  const violations: unknown[] = [];
  for (const width of [390, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    await page.emulateMedia({ reducedMotion: "reduce" });
    for (const path of [
      "/assistants",
      "/assistants/may",
      "/assistants/nhip",
      "/connect",
      "/messages",
      "/profile",
      "/profile?tab=sharing",
      "/self?tab=mood",
      "/self?tab=week",
      "/settings",
    ]) {
      await route(page, path);
      await dismiss(page);
      const result = await new AxeBuilder({ page })
        .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
        .analyze();
      violations.push(
        ...result.violations.map((v) => ({
          width,
          path,
          id: v.id,
          nodes: v.nodes.map((n) => ({
            target: n.target,
            summary: n.failureSummary,
          })),
        })),
      );
    }
  }
  expect(violations).toEqual([]);
  await page.setViewportSize({ width: 390, height: 844 });
  await connect(page);
  for (const phase of ["human", "activity", "icebreaker"]) {
    if (phase === "activity")
      await page.getByRole("button", { name: /Cùng làm gì đó/ }).click();
    if (phase === "icebreaker") {
      await page.getByRole("button", { name: "Mời cùng tham gia" }).click();
      await page.getByRole("button", { name: "Đồng ý hoạt động" }).click();
    }
    await dismiss(page);
    for (const width of [360, 375, 390, 430, 768, 1280, 1440]) {
      await page.setViewportSize({ width, height: 844 });
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= innerWidth,
        ),
      ).toBe(true);
      if (phase === "human")
        await expect(page.locator("#human-message")).toBeInViewport();
    }
    await page.setViewportSize({ width: 390, height: 844 });
    expect(
      (
        await new AxeBuilder({ page })
          .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
          .analyze()
      ).violations,
    ).toEqual([]);
  }
  await page.emulateMedia({ reducedMotion: "no-preference" });
  await page.getByRole("button", { name: "Dừng ở đây" }).click();
  await page
    .getByRole("button", { name: "Dừng hoạt động", exact: true })
    .click();
  await route(page, "/assistants/may");
  await page.waitForTimeout(300);
  expect(await page.locator("main [style*=opacity]").count()).toBe(0);
});
