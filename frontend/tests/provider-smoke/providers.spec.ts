import { expect, test, type Page } from "@playwright/test";
import { writeFileSync, mkdirSync } from "node:fs";

async function login(page: Page) {
  await page.goto("/");
  await page
    .getByLabel("Email", { exact: true })
    .fill("local-mvp-45@example.invalid");
  await page
    .getByLabel("Mật khẩu", { exact: true })
    .fill("local-mvp-synthetic");
  await page.getByRole("button", { name: "Đăng nhập", exact: true }).click();
  await expect(page.getByLabel("Mật khẩu", { exact: true })).toHaveCount(0);
}

async function send(page: Page, name: string, text: string) {
  await page
    .getByRole("textbox", { name: `Tin nhắn cho ${name}`, exact: true })
    .fill(text);
  // Wait until history/selection has loaded before counting existing responses.
  await expect(
    page.getByRole("button", { name: "Gửi tin cho AI", exact: true }),
  ).toBeEnabled();
  const before = await page.locator(".from-bot").count();
  await page
    .getByRole("button", { name: "Gửi tin cho AI", exact: true })
    .click();
  await expect(page.locator(".from-bot")).toHaveCount(before + 1, {
    timeout: 40000,
  });
  await expect(
    page.getByRole("button", { name: "Dừng", exact: true }),
  ).toHaveCount(0);
  expect(
    (await page.locator(".from-bot").last().innerText()).length,
  ).toBeGreaterThan(5);
}

test("bounded real provider browser smoke with local history and approved memory", async ({
  page,
}) => {
  test.skip(
    process.env.MOODPRINT_SMOKE_RESUME === "true",
    "Resume keeps prior provider results and DB state",
  );
  test.skip(
    process.env.MOODPRINT_ALLOW_LIVE_OPENAI !== "true",
    "Explicit live provider opt-in required",
  );
  const proof: Record<string, unknown> = {
    status: "FAIL",
    auth: "SYNTHETIC_PROVIDER",
    database: "LOCAL_POSTGRESQL",
    bots: [],
  };
  try {
    await login(page);
    await page.goto("/#/settings");
    for (const name of ["trò chuyện AI", "ghi nhớ đã duyệt"]) {
      // The actual consent label is checked below through its visible button.
      const button = page.getByRole("button", {
        name: `Bật ${name}`,
        exact: true,
      });
      if (await button.count()) await button.click();
    }
    // MEM label comes from product copy; use the shared API only if needed.
    const session = await (await page.request.get("/api/v1/session")).json();
    const csrf = session.csrfToken;
    if (!session.consents.MEM.enabled) {
      const response = await page.request.put("/api/v1/consents/MEM", {
        headers: {
          "X-CSRF-Token": csrf,
          "Idempotency-Key": crypto.randomUUID(),
        },
        data: {
          enabled: true,
          expectedVersion: session.consents.MEM.version,
          policyVersion: "v1",
        },
      });
      expect(response.ok()).toBe(true);
      await page.reload();
    }
    await page
      .getByRole("checkbox", { name: "Lưu lịch sử trò chuyện", exact: true })
      .check();
    await expect(
      page.getByText("Đã cập nhật lựa chọn dữ liệu AI.", { exact: true }),
    ).toBeVisible();
    for (const [bot, name, prompt] of [
      [
        "may",
        "Mây",
        "Mình đang tập vẽ màu nước. Từ khóa buổi hôm nay là LÁ-XANH-47. Chỉ chào mình ngắn gọn.",
      ],
      [
        "rure",
        "Rủ Rê",
        "Gợi ý một trò chơi giấy bút một người trong hai phút, trả lời ngắn.",
      ],
      [
        "caunoi",
        "Cầu Nối",
        "Mình muốn tự chọn khi nào chia sẻ hồ sơ tìm bạn. Mình cần làm gì? Trả lời ngắn.",
      ],
      [
        "nhip",
        "Nhịp",
        "Gợi ý một cách ghi nhận cảm xúc hôm nay, không đọc dữ liệu riêng.",
      ],
      [
        "guong",
        "Gương",
        "Mình tự xác nhận sở thích: thích vẽ màu nước. Hãy gọi công cụ propose_memory để tạo đề xuất cho mình duyệt, không tự lưu.",
      ],
    ]) {
      await page.goto(`/#/assistants/${bot}`);
      await expect(page.getByRole("note")).toHaveCount(0);
      await send(page, name, prompt);
      (proof.bots as string[]).push(bot);
      await page.reload();
      await expect(
        page.getByRole("log").getByText(prompt, { exact: true }),
      ).toBeVisible();
    }
    const before = await (await page.request.get("/api/v1/memories")).json();
    expect(before).toHaveLength(0);
    await page.goto("/#/memory");
    const proposal = page
      .locator("article")
      .filter({
        has: page.getByLabel("Nội dung bạn muốn duyệt", { exact: true }),
      })
      .first();
    await expect(proposal).toBeVisible();
    await proposal
      .getByRole("button", { name: "Duyệt và lưu", exact: true })
      .click();
    await expect(
      page.getByText("Đã cập nhật ghi nhớ.", { exact: true }),
    ).toBeVisible();
    proof.memoryApproval = "PASS";
    const info = await (
      await page.request.get("/api/v1/__local_smoke/status")
    ).json();
    if (info.voyageEnabled) {
      await page.goto("/#/settings");
      await page
        .getByRole("checkbox", {
          name: "Giúp trợ lý tìm lại ghi nhớ liên quan",
          exact: true,
        })
        .check();
      await expect
        .poll(
          async () =>
            (
              await (
                await page.request.get("/api/v1/__local_smoke/status")
              ).json()
            ).indexedMemories,
          { timeout: 30000 },
        )
        .toBe(1);
      await page.goto("/#/assistants/guong");
      await send(
        page,
        "Gương",
        "Sở thích mỹ thuật mình đã duyệt là gì? Chỉ nhắc lại nếu có trong ghi nhớ.",
      );
      const semantic = await (
        await page.request.get("/api/v1/__local_smoke/status")
      ).json();
      expect(semantic.voyageQueriesSucceeded).toBeGreaterThan(0);
      expect(semantic.voyageDocumentsSucceeded).toBeGreaterThan(0);
      proof.semanticWorkerAndRetrieval = "PASS";
      await page.goto("/#/settings");
      await page
        .getByRole("checkbox", {
          name: "Giúp trợ lý tìm lại ghi nhớ liên quan",
          exact: true,
        })
        .uncheck();
      await expect
        .poll(
          async () =>
            (
              await (
                await page.request.get("/api/v1/__local_smoke/status")
              ).json()
            ).indexedMemories,
        )
        .toBe(0);
      proof.semanticRevocation = "PASS";
    } else proof.semanticWorkerAndRetrieval = "NOT_REQUESTED";
    await page.goto("/#/settings");
    await page.getByRole("button", { name: "Đăng xuất", exact: true }).click();
    await login(page);
    await page.goto("/#/assistants/may");
    await expect(page.getByRole("log").getByText(/LÁ-XANH-47/)).toBeVisible();
    await send(
      page,
      "Mây",
      "Từ khóa mình đã nói lúc trước là gì? Nhắc lại đúng từ đó thôi.",
    );
    expect(await page.locator(".from-bot").last().innerText()).toContain(
      "LÁ-XANH-47",
    );
    proof.historyAndProviderContextAfterLogin = "PASS";
    proof.status = "REAL_PROVIDER_VERIFIED";
  } finally {
    const status = await page.request
      .get("/api/v1/__local_smoke/status")
      .catch(() => undefined);
    if (status?.ok()) proof.usage = await status.json();
    mkdirSync(".cache/local-mvp", { recursive: true });
    writeFileSync(
      ".cache/local-mvp/real-provider.json",
      JSON.stringify(proof, null, 2),
    );
  }
});

test("resume real semantic retrieval, re-indexing, revocation and one history continuation within remaining budget", async ({
  page,
}) => {
  test.skip(
    process.env.MOODPRINT_SMOKE_RESUME !== "true" ||
      process.env.MOODPRINT_ALLOW_LIVE_OPENAI !== "true",
    "Explicit bounded resume only",
  );
  const proof: Record<string, unknown> = { status: "FAIL", resumed: true };
  try {
    await login(page);
    const status = async () =>
      await (await page.request.get("/api/v1/__local_smoke/status")).json();
    const write = async (method: string, path: string, data: unknown) => {
      const session = await (await page.request.get("/api/v1/session")).json();
      return page.request.fetch(`/api/v1${path}`, {
        method,
        data,
        headers: {
          "X-CSRF-Token": session.csrfToken,
          "Idempotency-Key": crypto.randomUUID(),
        },
      });
    };
    expect((await status()).indexedMemories).toBe(1);
    const query = await write("POST", "/__local_smoke/retrieve", {});
    expect(query.ok()).toBe(true);
    expect((await query.json()).memoriesRetrieved).toBeGreaterThan(0);
    expect((await status()).voyageQueriesSucceeded).toBe(1);
    proof.semanticRetrieval = "PASS";
    const memories = await (await page.request.get("/api/v1/memories")).json();
    expect(memories).toHaveLength(1);
    const memory = memories[0];
    const changed = await write("PATCH", `/memories/${memory.id}`, {
      expectedVersion: memory.version,
      text: "Mình thích vẽ tranh bằng màu nước trên giấy dày.",
    });
    expect(changed.ok()).toBe(true);
    const updated = await changed.json();
    await expect
      .poll(async () => (await status()).indexedVersion, { timeout: 30000 })
      .toBe(updated.version);
    const next = await write("POST", "/__local_smoke/retrieve", {});
    expect(next.ok()).toBe(true);
    expect((await next.json()).memoriesRetrieved).toBeGreaterThan(0);
    expect((await status()).voyageDocumentsSucceeded).toBe(1);
    expect((await status()).voyageQueriesSucceeded).toBe(2);
    proof.editReindexAndRetrieval = "PASS";
    await page.goto("/#/settings");
    await page
      .getByRole("checkbox", {
        name: "Giúp trợ lý tìm lại ghi nhớ liên quan",
        exact: true,
      })
      .uncheck();
    await expect.poll(async () => (await status()).indexedMemories).toBe(0);
    proof.semanticRevocation = "PASS";
    const removed = await write("DELETE", `/memories/${memory.id}`, {
      expectedVersion: updated.version,
    });
    expect(removed.ok()).toBe(true);
    expect(
      await (await page.request.get("/api/v1/memories")).json(),
    ).toHaveLength(0);
    proof.memoryDeletion = "PASS";
    await page.getByRole("button", { name: "Đăng xuất", exact: true }).click();
    await login(page);
    await page.goto("/#/assistants/may");
    await expect(
      page
        .getByRole("log")
        .getByText(
          "Mình đang tập vẽ màu nước. Từ khóa buổi hôm nay là LÁ-XANH-47. Chỉ chào mình ngắn gọn.",
          { exact: true },
        ),
    ).toBeVisible();
    await send(
      page,
      "Mây",
      "Từ khóa mình đã nói lúc trước là gì? Nhắc lại đúng từ đó thôi.",
    );
    expect(await page.locator(".from-bot").last().innerText()).toContain(
      "LÁ-XANH-47",
    );
    proof.historyAndProviderContextAfterLogin = "PASS";
    proof.status = "REAL_PROVIDER_VERIFIED";
  } finally {
    const state = await page.request
      .get("/api/v1/__local_smoke/status")
      .catch(() => undefined);
    if (state?.ok()) proof.usage = await state.json();
    mkdirSync(".cache/local-mvp", { recursive: true });
    writeFileSync(
      ".cache/local-mvp/real-provider-resume.json",
      JSON.stringify(proof, null, 2),
    );
  }
});
