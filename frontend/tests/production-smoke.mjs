import { chromium, expect } from "@playwright/test";
import { writeFileSync } from "node:fs";
import assert from "node:assert/strict";
const base = "http://127.0.0.1:4173";
const browser = await chromium.launch({
  headless: true,
  executablePath:
    process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH ||
    "C:/Users/minhh/AppData/Local/ms-playwright/chromium-1243/chrome-win64/chrome.exe",
});
try {
  const page = await browser.newPage({
    viewport: { width: 390, height: 844 },
    reducedMotion: "reduce",
  });
  const external = [],
    errors = [];
  let microphone = 0;
  page.on("request", (r) => {
    if (!r.url().startsWith(base + "/")) external.push(r.url());
  });
  page.on("pageerror", (e) => errors.push(e.message));
  page.on("console", (m) => {
    if (["error", "warning"].includes(m.type())) errors.push(m.text());
  });
  await page.exposeFunction("micWasCalled", () => {
    microphone++;
  });
  await page.addInitScript(() => {
    if (navigator.mediaDevices)
      navigator.mediaDevices.getUserMedia = async () => {
        await window.micWasCalled();
        throw Error("Forbidden");
      };
  });
  const route = async (p) => {
    await page.evaluate((v) => {
      location.hash = v;
    }, p);
    await page.evaluate(
      () => new Promise((resolve) => requestAnimationFrame(resolve)),
    );
  };
  const dismiss = async () => {
    for (const name of ["Đóng giới thiệu bản mẫu", "Đóng thông báo"]) {
      const b = page.getByRole("button", { name, exact: true });
      if (await b.isVisible()) await b.click();
    }
  };
  // Development-only fixture flags must not change production eligibility.
  await page.goto(base + "/?fixture=under16&tools=1#/start");
  await expect(page.locator(".bot-row")).toHaveCount(5);
  await dismiss();
  await route("/assistants/may");
  await page
    .getByRole("button", { name: "Hôm nay mình hơi mệt", exact: true })
    .click();
  await route("/assistants/guong");
  await page
    .getByRole("button", { name: "Mình thích đọc sách", exact: true })
    .click();
  await expect(page.getByRole("log")).toContainText("Khi đọc sách");
  await expect(page.getByRole("log")).not.toContainText("Một ngày dài à?");
  await page
    .getByRole("button", {
      name: "Mình thích khoảng yên tĩnh khi đọc sách",
      exact: true,
    })
    .click();
  await page
    .getByRole("button", { name: "Lưu vào hồ sơ", exact: true })
    .click();
  await expect(page.getByRole("log")).toContainText("Đã lưu vào hồ sơ riêng");
  await route("/assistants/may");
  await expect(page.getByRole("log")).toContainText("Một ngày dài à?");
  await route("/assistants/nhip");
  await page
    .getByRole("button", { name: "2 Hơi khó chịu", exact: true })
    .click();
  await page.getByRole("button", { name: "Xem xu hướng", exact: true }).click();
  await expect(page.getByText("3,0", { exact: true })).toBeVisible();
  await route("/assistants/rure");
  await page.getByRole("button", { name: "Giải đố", exact: true }).click();
  await page.getByRole("button", { name: "Xem đáp án", exact: true }).click();
  await expect(page.getByRole("log")).toContainText("cái hố");
  await route("/assistants/caunoi");
  await page
    .getByRole("button", { name: "Tìm bạn cùng sở thích", exact: true })
    .click();
  await page.getByRole("link", { name: /Xem người phù hợp/ }).click();
  await expect(page.getByRole("article")).toHaveCount(4);
  await page
    .getByRole("article")
    .filter({ has: page.getByRole("heading", { name: "Lá Non", exact: true }) })
    .getByRole("button", { name: "Làm quen" })
    .click();
  await expect(page.locator("#human-message")).toHaveCount(0);
  await page.getByRole("button", { name: "Đồng ý", exact: true }).click();
  await page.getByRole("link", { name: "Mở trò chuyện" }).click();
  await dismiss();
  await page
    .getByRole("button", { name: "Dạo này bạn đang đọc gì?", exact: true })
    .click();
  await expect(page.getByRole("log")).toContainText(
    "Mình đang đọc một tập truyện ngắn.",
  );
  await page.getByRole("button", { name: /Cùng làm gì đó/ }).click();
  await page
    .getByRole("button", { name: "Mời cùng tham gia", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Đồng ý hoạt động", exact: true })
    .click();
  for (let i = 0; i < 3; i++) {
    await page
      .getByRole("button", { name: "Bỏ qua câu này", exact: true })
      .click();
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
  await route("/settings");
  await expect(page.getByText(/Công cụ demo/)).toHaveCount(0);
  await page
    .getByRole("button", { name: "Đặt lại bản trải nghiệm", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Đặt lại toàn bộ", exact: true })
    .click();
  await expect(page.locator(".bot-row")).toHaveCount(5);
  await route("/assistants/may");
  await expect(page.getByRole("log")).not.toContainText("Một ngày dài à?");
  const storage = await page.evaluate(async () => ({
    local: localStorage.length,
    session: sessionStorage.length,
    cookies: document.cookie,
    dbs: (await indexedDB.databases()).length,
  }));
  assert.deepEqual(storage, { local: 0, session: 0, cookies: "", dbs: 0 });
  assert.deepEqual(external, []);
  assert.deepEqual(errors, []);
  assert.equal(microphone, 0);
  writeFileSync(
    "evidence/production-smoke.json",
    JSON.stringify(
      {
        status: "PASS",
        browser: browser.version(),
        entry: "Me2We bot roster",
        journeys: [
          "five bot scenarios",
          "bot continuity and isolated pending replies",
          "mutual consent → human chat → ACT01 completed",
          "reset",
        ],
        externalRequests: external,
        pageAndConsoleErrors: errors,
        microphone,
        storage,
        productionHarness: "ignored",
      },
      null,
      2,
    ),
  );
  console.log(
    "Production Me2We journeys PASS; no external requests, storage, microphone or console errors.",
  );
} finally {
  await browser.close();
}
