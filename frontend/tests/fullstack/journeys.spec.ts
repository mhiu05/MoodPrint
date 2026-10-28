import { expect, test, type BrowserContext, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { randomUUID } from "node:crypto";
import { fillProfileEditor } from "./helpers";

async function session(context: BrowserContext, number: number) {
  await context.addCookies([
    {
      name: "moodprint_session",
      value: `e2e-synthetic-session-${number}`,
      url: "http://127.0.0.1:5174",
      httpOnly: true,
      sameSite: "Strict",
    },
    {
      name: "moodprint_csrf",
      value: `e2e-synthetic-csrf-${number}`,
      url: "http://127.0.0.1:5174",
      sameSite: "Strict",
    },
  ]);
}

async function publish(page: Page) {
  await page.goto("/#/connect?tab=profile");
  await fillProfileEditor(page);
}

test("birth-year onboarding persists16+ access while the server rejects social access and under16 users", async ({
  browser,
}) => {
  const context = await browser.newContext({
    viewport: { width: 390, height: 844 },
    reducedMotion: "reduce",
  });
  await session(context, 7);
  const page = await context.newPage();
  await page.goto("/#/");
  await expect(
    page.getByRole("heading", { name: "Xác nhận độ tuổi" }),
  ).toBeVisible();
  const initial = await (
    await context.request.get("http://127.0.0.1:5174/api/v1/session")
  ).json();
  const year = Number(
    new Intl.DateTimeFormat("en", {
      timeZone: "Asia/Bangkok",
      year: "numeric",
    }).format(new Date(initial.serverTime)),
  );
  await page.getByLabel("Năm sinh", { exact: true }).fill(String(year - 16));
  const axe = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
    .analyze();
  expect(axe.passes.length).toBeGreaterThan(0);
  expect(axe.violations).toEqual([]);
  await page.screenshot({
    path: "../docs/plans/validation-artifacts/visual/onboarding-390.png",
    fullPage: true,
  });
  await page
    .getByRole("checkbox", {
      name: "Tôi xác nhận mình đã đủ 16 tuổi.",
      exact: true,
    })
    .check();
  await page
    .getByRole("button", { name: "Xác nhận và tiếp tục", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: /Bạn muốn chia sẻ điều gì/ }),
  ).toBeVisible();
  await page.reload();
  await expect(
    page.getByRole("heading", { name: /Bạn muốn chia sẻ điều gì/ }),
  ).toBeVisible();
  await page.goto("/#/connect");
  await expect(
    page.getByText(
      "Tìm bạn và nhắn tin người thật dành cho người đã đủ 18 tuổi.",
      { exact: true },
    ),
  ).toBeVisible();
  const forbidden = await context.request.put(
    "http://127.0.0.1:5174/api/v1/consents/MATCH",
    {
      data: { enabled: true, expectedVersion: 1, policyVersion: "v1" },
      headers: {
        "X-CSRF-Token": "e2e-synthetic-csrf-7",
        "Idempotency-Key": randomUUID(),
      },
    },
  );
  expect(forbidden.status()).toBe(403);
  const stored = await (
    await context.request.get("http://127.0.0.1:5174/api/v1/session")
  ).json();
  expect(stored.ageBand).toBe("teen");
  expect(stored.birthYear).toBe(year - 16);
  expect(
    Object.values(stored.consents).every(
      (value: any) => value.enabled === false,
    ),
  ).toBe(true);
  await context.close();
  const younger = await browser.newContext();
  await session(younger, 8);
  const underage = await younger.newPage();
  await underage.goto("/#/");
  await underage
    .getByLabel("Năm sinh", { exact: true })
    .fill(String(year - 15));
  await underage
    .getByRole("checkbox", {
      name: "Tôi xác nhận mình đã đủ 16 tuổi.",
      exact: true,
    })
    .check();
  await underage
    .getByRole("button", { name: "Xác nhận và tiếp tục", exact: true })
    .click();
  await expect(
    underage.getByRole("heading", {
      name: "Ứng dụng dành cho người từ 16 tuổi",
    }),
  ).toBeVisible();
  await underage.reload();
  await expect(
    underage.getByRole("heading", {
      name: "Ứng dụng dành cho người từ 16 tuổi",
    }),
  ).toBeVisible();
  expect(
    (await younger.request.get("http://127.0.0.1:5174/api/v1/moods")).status(),
  ).toBe(403);
  await younger.close();
});

test("the eighteenth-year account explicitly confirms18 in settings without automatically enabling MATCH", async ({
  browser,
}) => {
  const context = await browser.newContext({
    viewport: { width: 1440, height: 960 },
    reducedMotion: "reduce",
  });
  await session(context, 9);
  const page = await context.newPage();
  await page.goto("/#/");
  const initial = await (
    await context.request.get("http://127.0.0.1:5174/api/v1/session")
  ).json();
  const year = Number(
    new Intl.DateTimeFormat("en", {
      timeZone: "Asia/Bangkok",
      year: "numeric",
    }).format(new Date(initial.serverTime)),
  );
  await page.getByLabel("Năm sinh", { exact: true }).fill(String(year - 18));
  await page
    .getByRole("checkbox", {
      name: "Tôi xác nhận mình đã đủ 16 tuổi.",
      exact: true,
    })
    .check();
  await page.screenshot({
    path: "../docs/plans/validation-artifacts/visual/onboarding-1440.png",
    fullPage: true,
  });
  await page
    .getByRole("button", { name: "Xác nhận và tiếp tục", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: /Bạn muốn chia sẻ điều gì/ }),
  ).toBeVisible();
  await page.goto("/#/settings");
  await expect(page.getByRole("link", { name: "Xem hoặc sửa hồ sơ tìm bạn" })).toBeVisible();
  await page
    .getByRole("checkbox", {
      name: "Tôi xác nhận mình đã đủ 18 tuổi để sử dụng Tìm bạn và nhắn tin người thật.",
      exact: true,
    })
    .check();
  await page
    .getByRole("button", { name: "Xác nhận đủ 18 tuổi", exact: true })
    .click();
  await page.reload();
  await expect(page.getByRole("link", { name: "Xem hoặc sửa hồ sơ tìm bạn" })).toBeVisible();
  const stored = await (
    await context.request.get("http://127.0.0.1:5174/api/v1/session")
  ).json();
  expect(stored.ageBand).toBe("adult");
  expect(stored.eligibilityVersion).toBe(2);
  expect(stored.consents.MATCH.enabled).toBe(false);
  await context.close();
});

test("real FastAPI/PostgreSQL preserves private records and mood, streams through the SDK, and connects two users", async ({
  browser,
}) => {
  const a = await browser.newContext(),
    b = await browser.newContext();
  await session(a, 1);
  await session(b, 2);
  const one = await a.newPage(),
    two = await b.newPage();
  await one.goto("/#/profile");
  await one
    .getByRole("textbox", { name: "Điều bạn muốn ghi lại" })
    .fill("Mình thích những buổi sáng yên tĩnh");
  await one
    .getByRole("button", { name: "Lưu vào hồ sơ riêng", exact: true })
    .click();
  await expect(
    one.getByText("Đã lưu vào hồ sơ riêng.", { exact: true }),
  ).toBeVisible();
  await one.reload();
  await expect(
    one
      .locator("article")
      .getByText("Mình thích những buổi sáng yên tĩnh", { exact: true }),
  ).toBeVisible();
  await two.goto("/#/profile");
  await expect(
    two.getByText("Mình thích những buổi sáng yên tĩnh", { exact: true }),
  ).toHaveCount(0);
  await one.goto("/#/self");
  await one
    .getByRole("textbox", { name: "Ghi chú", exact: true })
    .fill("Một ngày bình yên");
  await one.getByRole("button", { name: "Lưu tâm trạng", exact: true }).click();
  await expect(
    one.getByText(/^Đã lưu cảm xúc ngày \d{2}\/\d{2}\/\d{4}\.$/),
  ).toBeVisible();
  await one.reload();
  await expect(
    one.locator("article").getByText("Một ngày bình yên", { exact: true }),
  ).toBeVisible();
  await one.goto("/#/settings");
  await one.getByRole("checkbox", { name: "Lưu lịch sử trò chuyện", exact: true }).click();
  await expect(one.getByText("Đã lưu lựa chọn của bạn.", { exact: true })).toBeVisible();
  await one.goto("/#/assistants/may");
  await one
    .getByRole("textbox", { name: "Tin nhắn cho Mây" })
    .fill("Hôm nay mình thấy khá ổn");
  await one
    .getByRole("button", { name: "Gửi tin cho AI", exact: true })
    .click();
  await expect(
    one.getByText("Mây đã nhận được chia sẻ của bạn qua SDK.", { exact: true }),
  ).toBeVisible();
  await one.reload();
  await expect(
    one.getByText("Mây đã nhận được chia sẻ của bạn qua SDK.", { exact: true }),
  ).toBeVisible();
  await publish(one);
  await publish(two);
  await one.goto("/#/connect");
  await one.getByRole("button", { name: "Tải lại gợi ý", exact: true }).click();
  await one.getByRole("button", { name: "Gửi lời mời kết nối", exact: true }).click();
  await expect(one.getByText("Đã gửi lời mời kết nối.", { exact: true })).toBeVisible();
  await two.goto("/#/connect?tab=requests");
  await two
    .getByRole("button", { name: "Tải lại lời mời", exact: true })
    .click();
  await two
    .getByRole("button", { name: "Đồng ý kết nối", exact: true })
    .click();
  await two
    .getByRole("link", { name: "Mở cuộc trò chuyện", exact: true })
    .click();
  await one.goto("/#/messages");
  await one.getByRole("link", { name: /Bạn đồng hành/ }).click();
  await one
    .getByRole("textbox", { name: "Nhắn tin cho người bạn kết nối" })
    .fill("Chào bạn, mình cũng thích đọc sách!");
  await one.getByRole("button", { name: "Gửi tin nhắn", exact: true }).click();
  await expect(
    two
      .getByRole("log")
      .getByText("Chào bạn, mình cũng thích đọc sách!", { exact: true }),
  ).toBeVisible({ timeout: 10000 });
  await two.reload();
  await expect(
    two
      .getByRole("log")
      .getByText("Chào bạn, mình cũng thích đọc sách!", { exact: true }),
  ).toBeVisible();
  await a.close();
  await b.close();
});

test("only the identity owner grants reveal, revocation removes access, and reporting is separate from blocking", async ({
  browser,
}) => {
  const a = await browser.newContext(),
    b = await browser.newContext();
  await session(a, 3);
  await session(b, 4);
  const one = await a.newPage(),
    two = await b.newPage();
  const base = "http://127.0.0.1:5174/api/v1";
  const write = async (
    context: BrowserContext,
    number: number,
    path: string,
    data: unknown,
  ) => {
    const result = await context.request.post(base + path, {
      data,
      headers: {
        "X-CSRF-Token": `e2e-synthetic-csrf-${number}`,
        "Idempotency-Key": crypto.randomUUID(),
      },
    });
    expect(result.ok(), await result.text()).toBeTruthy();
    return result.json();
  };
  for (const [context, number] of [
    [a, 3],
    [b, 4],
  ] as const) {
    const headers = {
      "X-CSRF-Token": `e2e-synthetic-csrf-${number}`,
      "Idempotency-Key": crypto.randomUUID(),
    };
    expect(
      (
        await context.request.put(base + "/consents/MATCH", {
          data: { enabled: true, expectedVersion: 1, policyVersion: "v1" },
          headers,
        })
      ).ok(),
    ).toBeTruthy();
    const draft = {
      interests: ["reading", "music", "walking"],
      values: ["respect", "kindness"],
      style: "balanced",
      goal: "shared-interests",
      languages: ["vi"],
      expectedVersion: 0,
    };
    expect(
      (
        await context.request.put(base + "/profiles/matching-draft", {
          data: draft,
          headers: { ...headers, "Idempotency-Key": crypto.randomUUID() },
        })
      ).ok(),
    ).toBeTruthy();
    const preview = await write(
      context,
      number,
      "/profiles/matching-draft/preview",
      {},
    );
    await write(context, number, "/profiles/published", {
      draftVersion: preview.draftVersion,
      previewDigest: preview.previewDigest,
      expectedPublishedVersion: 0,
    });
  }
  const candidates = await (
    await a.request.get(base + "/matching/candidates")
  ).json();
  const pending = await write(a, 3, "/connection-requests", {
    candidateRef: candidates.candidates[0].candidateRef,
  });
  const accepted = await write(
    b,
    4,
    `/connection-requests/${pending.id}/accept`,
    { expectedVersion: pending.version },
  );
  const room = accepted.connectionId;
  await one.goto("/#/profile");
  await one
    .getByRole("textbox", { name: "Tên hiển thị", exact: true })
    .fill("Tên được chủ nhân lựa chọn");
  await one
    .getByRole("button", { name: "Lưu tên hiển thị", exact: true })
    .click();
  await expect(
    one.getByText("Đã cập nhật thông tin riêng.", { exact: true }),
  ).toBeVisible();
  await one.goto(`/#/chat/${room}`);
  await two.goto(`/#/chat/${room}`);
  await one
    .getByRole("textbox", { name: "Nhắn tin cho người bạn kết nối" })
    .fill("Một tin nhắn để chọn báo cáo");
  await one.getByRole("button", { name: "Gửi tin nhắn", exact: true }).click();
  await expect(
    two
      .getByRole("log")
      .getByText("Một tin nhắn để chọn báo cáo", { exact: true }),
  ).toBeVisible();
  await two
    .getByRole("button", { name: "Chia sẻ và an toàn" })
    .click();
  await two
    .getByRole("button", { name: "Yêu cầu xem tên hiển thị", exact: true })
    .click();
  await one
    .getByRole("button", { name: "Chia sẻ và an toàn" })
    .click();
  await one
    .getByRole("button", { name: "Đồng ý chia sẻ", exact: true })
    .click();
  await two
    .getByRole("button", { name: "Xem thông tin đã được chia sẻ", exact: true })
    .click();
  await expect(
    two.getByText("Tên được chủ nhân lựa chọn", { exact: true }),
  ).toBeVisible();
  await one
    .getByRole("button", { name: "Ngừng chia sẻ", exact: true })
    .click();
  await expect(
    two.getByText("Tên được chủ nhân lựa chọn", { exact: true }),
  ).toHaveCount(0, { timeout: 10000 });
  await two
    .getByRole("textbox", { name: "Lý do báo cáo", exact: true })
    .fill("Kiểm tra tiếp nhận báo cáo");
  await two
    .getByRole("checkbox", {
      name: "Một tin nhắn để chọn báo cáo",
      exact: true,
    })
    .check();
  await two.getByRole("button", { name: "Gửi báo cáo", exact: true }).click();
  await expect(
    two.getByText("Đã gửi báo cáo.", { exact: true }),
  ).toBeVisible();
  await two
    .getByRole("button", { name: "Chặn kết nối này", exact: true })
    .click();
  await two.getByRole("button", { name: "Chặn người này", exact: true }).click();
  await expect(
    one
      .locator('[role="log"]')
      .getByText("Một tin nhắn để chọn báo cáo", { exact: true }),
  ).toHaveCount(0, { timeout: 10000 });
  await a.close();
  await b.close();
});

test("approved memory uses the edited approval, survives reload, and local privacy actions return real receipts", async ({
  browser,
}) => {
  const context = await browser.newContext({ acceptDownloads: true });
  await session(context, 5);
  const page = await context.newPage();
  await page.goto("/#/memory");
  await page
    .getByRole("textbox", { name: "Nội dung sẽ lưu" })
    .fill("Nội dung đã được chính bạn chỉnh và duyệt");
  await page.getByRole("button", { name: "Duyệt và lưu", exact: true }).click();
  await expect(
    page.getByText("Nội dung đã được chính bạn chỉnh và duyệt", {
      exact: true,
    }),
  ).toBeVisible();
  await page.reload();
  await expect(
    page.getByText("Nội dung đã được chính bạn chỉnh và duyệt", {
      exact: true,
    }),
  ).toBeVisible();
  await page.goto("/#/settings");
  const download = page.waitForEvent("download");
  await page
    .getByRole("button", { name: "Tải bản sao dữ liệu", exact: true })
    .click();
  expect((await download).suggestedFilename()).toBe("moodprint-data.json");
  await page
    .getByLabel("Dữ liệu bạn muốn xóa", { exact: true })
    .selectOption("memories");
  await page
    .getByRole("button", { name: "Xóa dữ liệu đã chọn", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Xác nhận xóa dữ liệu", exact: true })
    .click();
  await expect(
    page.getByText("Đã xóa dữ liệu đã chọn trong ứng dụng.", { exact: true }),
  ).toBeVisible();
  await page.goto("/#/memory");
  await expect(
    page.getByText("Bạn chưa lưu ghi nhớ nào. Khi trò chuyện, bạn có thể nhờ trợ lý đề xuất điều cần nhớ rồi duyệt tại đây.", { exact: true }),
  ).toBeVisible();
  await context.close();
});

test("real authenticated screens reflow and pass automated accessibility checks at mobile and desktop sizes", async ({
  browser,
}) => {
  const context = await browser.newContext({ reducedMotion: "reduce" });
  await session(context, 6);
  const page = await context.newPage();
  const findings = [];
  const deniedPurposeRequests: string[] = [];
  page.on("request", (request) => {
    if (
      /\/api\/v1\/(matching\/candidates|connection-requests)(\?|$)/.test(
        request.url(),
      )
    )
      deniedPurposeRequests.push(request.url());
  });
  for (const width of [390, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    for (const [route, heading] of [
      ["/assistants", "Bạn muốn chia sẻ điều gì"],
      ["/profile", "Hồ sơ riêng"],
      ["/settings", "Quyền riêng tư"],
      ["/self", "Nhật ký cảm xúc"],
      ["/connect", "Tìm bạn đồng điệu"],
    ]) {
      await page.goto(`/#${route}`);
      await expect(
        page.getByRole("heading", { level: 1 }).filter({ hasText: heading }),
      ).toBeVisible();
      await expect
        .poll(() =>
          page.evaluate(
            () => document.documentElement.scrollWidth <= window.innerWidth + 1,
          ),
        )
        .toBe(true);
      const result = await new AxeBuilder({ page })
        .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
        .analyze();
      expect(result.passes.length).toBeGreaterThan(0);
      findings.push({
        width,
        route,
        passes: result.passes.length,
        violations: result.violations.map((item) => ({
          id: item.id,
          impact: item.impact,
          nodes: item.nodes.map((node) => node.target),
        })),
      });
      expect(result.violations).toEqual([]);
      await page.screenshot({
        path: `../docs/plans/validation-artifacts/visual/real-${route.slice(1)}-${width}.png`,
        fullPage: true,
      });
    }
  }
  await test.info().attach("accessibility-results", {
    body: JSON.stringify(findings, null, 2),
    contentType: "application/json",
  });
  expect(deniedPurposeRequests).toEqual([]);
  await context.close();
});
