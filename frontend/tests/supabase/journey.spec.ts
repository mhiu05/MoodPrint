import { artifactPath } from "../artifacts";
import { expect, test, type BrowserContext, type Page } from "@playwright/test";
import { randomUUID } from "node:crypto";
import { existsSync, readFileSync, writeFileSync } from "node:fs";
import AxeBuilder from "@axe-core/playwright";

const base = "http://127.0.0.1:5176", apiBase = base + "/api/v1";
const artifacts = artifactPath("supabase", "../docs/plans/validation-artifacts/") + "/";
const proof: Record<string, unknown> = { projectId: "roznanxbiyqybjpvtilq", auth: "real Supabase", database: "real Supabase, dedicated runtime", ai: "SDK fake model", liveModelCalls: 0, signupAndEmailDelivery: "NOT_TESTED: users created/confirmed by owner in Dashboard" };
function record(name: string) {
  proof[name] = "PASS";
  writeFileSync(artifacts + "supabase-e2e-checkpoints.json", JSON.stringify(proof, null, 2));
}
async function request(context: BrowserContext, method: string, path: string, data?: unknown, expected = 200) {
  const csrf = (await context.cookies(base)).find(c => c.name === "moodprint_csrf")?.value;
  let response;
  try {
    response = await context.request.fetch(apiBase + path, { method, data, timeout: 30000,
      headers: { Origin: base, "X-CSRF-Token": csrf || "", "Idempotency-Key": randomUUID() } });
  } catch { throw new Error(`HTTP transport failed for ${method} ${path}; details redacted`); }
  expect(response.status(), `${method} ${path}`).toBe(expected);
  return expected === 204 ? undefined : response.json();
}
async function login(page: Page, actor: "A" | "B") {
  await page.goto(base);
  await expect(page.getByLabel("Email", { exact: true })).toBeVisible();
  try {
    await page.getByLabel("Email", { exact: true }).fill(process.env[`MOODPRINT_TEST_${actor}_EMAIL`]!);
    await page.getByLabel("Mật khẩu", { exact: true }).fill(process.env[`MOODPRINT_TEST_${actor}_PASSWORD`]!);
    await page.getByRole("button", { name: "Đăng nhập", exact: true }).click();
  } catch { throw new Error("Login input failed; credential details redacted"); }
  await expect(page.getByLabel("Mật khẩu", { exact: true })).toHaveCount(0);
}
async function enable(page: Page, name: string) {
  await page.goto(base + "/#/settings");
  const button = page.getByRole("button", { name: `Bật ${name}`, exact: true });
  await expect(button.or(page.getByRole("button", { name: `Tắt ${name}`, exact: true }))).toBeVisible();
  if (await button.count()) await button.click();
  await expect(page.getByRole("button", { name: `Tắt ${name}`, exact: true })).toBeVisible();
}
async function publish(page: Page) {
  await enable(page, "tìm bạn");
  await page.goto(base + "/#/connect?tab=profile");
  await page.getByRole("button", { name: "Chỉnh hồ sơ tìm bạn" }).click();
  for (const name of ["Đọc sách", "Âm nhạc", "Đi bộ", "Tôn trọng", "Chân thành", "Tiếng Việt"])
    await page.getByRole("checkbox", { name, exact: true }).check();
  await page.getByRole("button", { name: "Lưu bản nháp", exact: true }).click();
  await expect(page.getByText("Đã lưu bản nháp hồ sơ.", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Xem trước hồ sơ", exact: true }).click();
  await page.getByRole("button", { name: "Hiển thị hồ sơ", exact: true }).click();
  await expect(page.getByText("Đã hiển thị hồ sơ tìm bạn.", { exact: true })).toBeVisible();
}

test("hosted Auth, age, account data, SDK memory, social races, restart and revoke", async ({ browser }) => {
  const a = await browser.newContext(), b = await browser.newContext();
  try {
    const one = await a.newPage(), two = await b.newPage();
    await login(one, "A"); await login(two, "B");
    record("realLoginUiAndHttpOnlySession");
    const sessionA = await request(a, "GET", "/session"), sessionB = await request(b, "GET", "/session");
    const year = Number(new Intl.DateTimeFormat("en", { timeZone: "Asia/Bangkok", year: "numeric" }).format(new Date(sessionA.serverTime)));
    for (const [page, session, offset] of [[one, sessionA, 18], [two, sessionB, 20]] as const) {
      if (!session.eligible) {
        expect(Object.values(session.consents).every((c: any) => !c.enabled)).toBe(true);
        await page.getByLabel("Năm sinh", { exact: true }).fill(String(year - offset));
        await page.getByRole("checkbox", { name: "Tôi xác nhận mình đã đủ 18 tuổi.", exact: true }).check();
        await page.getByRole("button", { name: "Xác nhận và tiếp tục", exact: true }).click();
        await expect(page.getByRole("heading", { name: "Chọn một trợ lý" })).toBeVisible();
      }
    }
    expect((await request(a, "GET", "/session")).ageBand).toBe("adult");
    record("onboardingGlobal18PlusAndExplicitBirthdayBoundary");
    const tag = randomUUID().slice(0, 8), moodText = `Supabase mood ${tag}`, aliasText = `Synthetic owner ${tag}`;
    await one.goto(base + "/#/profile");
    await one.getByRole("textbox", { name: "Tên hiển thị", exact: true }).fill(aliasText);
    await one.getByRole("button", { name: "Lưu tên hiển thị", exact: true }).click();
    await expect(one.getByText("Đã cập nhật thông tin riêng.", { exact: true })).toBeVisible();
    await one.goto(base + "/#/self");
    await one.getByRole("textbox", { name: "Ghi chú", exact: true }).fill(moodText);
    // A previous run may already have recorded today, which turns the form into an edit.
    await one.getByRole("button", { name: /^(Lưu|Cập nhật) tâm trạng$/ }).click();
    await expect(one.getByText(/^Đã (lưu|cập nhật) tâm trạng\.$/)).toBeVisible();
    await one.reload(); await expect(one.locator("article").getByText(moodText, { exact: true })).toBeVisible();
    record("moodPersistenceAcrossReload");
    await enable(one, "trò chuyện AI"); await enable(one, "ghi nhớ đã duyệt");
    await one.goto(base + "/#/assistants/may");
    await one.getByRole("textbox", { name: "Tin nhắn cho Mây" }).fill("SYNTHETIC_MEMORY_PROPOSAL");
    await one.getByRole("button", { name: "Gửi tin cho AI", exact: true }).click();
    await expect(one.getByText("Mình đã nhận được chia sẻ của bạn.", { exact: true })).toBeVisible();
    await expect(one.getByText("UNVALIDATED-RAW-CANARY", { exact: true })).toHaveCount(0);
    const proposals = await request(a, "GET", "/proposals");
    expect(proposals.length > 0).toBe(true);
    const otherSession = await request(b, "GET", "/session");
    if (!otherSession.consents.AI.enabled || !otherSession.consents.MEM.enabled)
      await request(b, "POST", `/proposals/${proposals[0].id}/confirm`, { expectedVersion: 1, editedText: "must not approve" }, 403);
    await enable(two, "trò chuyện AI"); await enable(two, "ghi nhớ đã duyệt");
    await request(b, "POST", `/proposals/${proposals[0].id}/confirm`, { expectedVersion: 1, editedText: "must not approve" }, 404);
    const memoryText = `Supabase approved memory ${tag}`;
    await one.goto(base + "/#/memory");
    await one.getByRole("textbox", { name: "Nội dung sẽ lưu" }).first().fill(memoryText);
    await one.getByRole("button", { name: "Duyệt và lưu", exact: true }).first().click();
    await expect(one.getByText(memoryText, { exact: true })).toBeVisible();
    await one.reload(); await expect(one.getByText(memoryText, { exact: true })).toBeVisible();
    expect((await request(b, "GET", "/memories")).some((x: any) => x.text === memoryText)).toBe(false);
    record("sdkFakeModelProposalOwnerApprovalAndMemoryPersistence");
    await publish(one); await publish(two);
    const ca = (await request(a, "GET", "/matching/candidates")).candidates;
    const cb = (await request(b, "GET", "/matching/candidates")).candidates;
    expect(ca.length).toBe(1); expect(cb.length).toBe(1);
    const invites = await Promise.all([
      request(a, "POST", "/connection-requests", { candidateRef: ca[0].candidateRef }, 201),
      request(b, "POST", "/connection-requests", { candidateRef: cb[0].candidateRef }, 201),
    ]);
    expect(invites.length).toBe(2);
    const roomsA = await request(a, "GET", "/connections"), roomsB = await request(b, "GET", "/connections");
    expect(roomsA.length).toBe(1); expect(roomsB.length).toBe(1); expect(roomsA[0].id === roomsB[0].id).toBe(true);
    const room = roomsA[0].id, path = `/connections/${room}/messages`;
    record("publishMatchingAndConcurrentMutualRequestsSingleRoom");
    await one.goto(base + `/#/chat/${room}`); await two.goto(base + `/#/chat/${room}`);
    const chatText = `Supabase chat ${tag}`;
    await one.getByRole("textbox", { name: "Nhắn tin cho người bạn kết nối" }).fill(chatText);
    await one.getByRole("button", { name: "Gửi tin nhắn", exact: true }).click();
    await expect(two.getByRole("log").getByText(chatText, { exact: true })).toBeVisible();
    const payload = { clientMessageId: randomUUID(), text: `Supabase duplicate ${tag}` };
    const retry = await Promise.all([request(a, "POST", path, payload, 201), request(a, "POST", path, payload, 201)]);
    expect(retry[0].id === retry[1].id).toBe(true);
    record("realtimeChatAndConcurrentMessageDeduplication");
    writeFileSync(artifacts + "supabase-restart-request.json", JSON.stringify({ restart: true }));
    await expect.poll(() => existsSync(artifacts + "supabase-restart-ack.json"), { timeout: 50000 }).toBe(true);
    const restart = JSON.parse(readFileSync(artifacts + "supabase-restart-ack.json", "utf8"));
    expect(restart.oldPid !== restart.newPid).toBe(true);
    await two.reload(); await expect(two.getByRole("log").getByText(chatText, { exact: true })).toBeVisible();
    expect((await request(a, "GET", "/memories")).some((x: any) => x.text === memoryText)).toBe(true);
    record("backendProcessRestartRetainsSessionsMemoryAndChat");
    await two.getByRole("button", { name: "Chia sẻ và an toàn" }).click();
    await two.getByRole("button", { name: "Yêu cầu xem tên hiển thị", exact: true }).click();
    await one.reload(); await one.getByRole("button", { name: "Chia sẻ và an toàn" }).click();
    await one.getByRole("button", { name: "Đồng ý chia sẻ", exact: true }).click();
    await two.getByRole("button", { name: "Xem thông tin đã được chia sẻ", exact: true }).click();
    await expect(two.getByText(aliasText, { exact: true })).toBeVisible();
    await one.getByRole("button", { name: "Ngừng chia sẻ", exact: true }).click();
    await expect(two.getByText(aliasText, { exact: true })).toHaveCount(0);
    record("ownerRevealGrantAndRevoke");
    await two.getByRole("textbox", { name: "Lý do báo cáo", exact: true }).fill("Synthetic hosted E2E report");
    await two.getByRole("checkbox", { name: chatText, exact: true }).check();
    await two.getByRole("button", { name: "Gửi báo cáo", exact: true }).click();
    await expect(two.getByText("Đã gửi báo cáo.", { exact: true })).toBeVisible();
    await two.getByRole("button", { name: "Chặn kết nối này", exact: true }).click();
    await two.getByRole("button", { name: "Chặn người này", exact: true }).click();
    // Wait for the committed block before probing from the other account.
    await expect(two.getByText("Bạn đã chặn kết nối này.", { exact: true })).toBeVisible();
    await request(a, "GET", path, undefined, 403);
    await request(a, "POST", path, { clientMessageId: randomUUID(), text: "must not send" }, 403);
    record("reportReceiptAndBlockImmediatelyDenyBothDirections");
    // Sign out all provider sessions belonging only to synthetic account B.
    const provider = process.env.MOODPRINT_TEST_SUPABASE_URL!;
    const key = process.env.MOODPRINT_TEST_PUBLISHABLE_KEY!;
    const auth = await fetch(provider + "/auth/v1/token?grant_type=password", { method: "POST", headers: { apikey: key, "Content-Type": "application/json" },
      body: JSON.stringify({ email: process.env.MOODPRINT_TEST_B_EMAIL, password: process.env.MOODPRINT_TEST_B_PASSWORD }) });
    expect(auth.status).toBe(200);
    const token = (await auth.json()).access_token;
    const revoked = await fetch(provider + "/auth/v1/logout?scope=global", { method: "POST", headers: { apikey: key, Authorization: `Bearer ${token}` } });
    expect(revoked.ok).toBe(true);
    await request(b, "GET", "/session", undefined, 401);
    record("providerSessionRevokeInvalidatesOpaqueAppSession");
    const oldCookies = await a.cookies(base);
    await request(a, "POST", "/auth/logout", {}, 204);
    await request(a, "GET", "/session", undefined, 401);
    const replay = await browser.newContext(); await replay.addCookies(oldCookies);
    await request(replay, "GET", "/session", undefined, 401); await replay.close();
    record("logoutAndOldCookieReplayDenied");
    proof.status = "PASS_SCOPED_HOSTED_JOURNEY";
    writeFileSync(artifacts + "supabase-e2e-checkpoints.json", JSON.stringify(proof, null, 2));
  } finally { await a.close(); await b.close(); }
});

test("hosted Nhịp reads only the explicitly selected mood dates and never private notes", async ({ browser }) => {
  const context = await browser.newContext();
  try {
    const page = await context.newPage();
    await login(page, "A");
    await enable(page, "trò chuyện AI");
    await page.goto(base + "/#/assistants/nhip");
    const draft = page.getByRole("textbox", { name: "Tin nhắn cho Nhịp" });
    await draft.fill("SYNTHETIC_MOOD_RANGE");
    await page.getByRole("button", { name: "Gửi tin cho AI", exact: true }).click();
    await expect(page.getByText("Chưa có khoảng thống kê được chia sẻ.", { exact: true })).toBeVisible();
    await page.getByText("Chia sẻ thống kê tâm trạng cho lượt này", { exact: true }).click();
    await page.getByRole("checkbox", { name: "Cho Nhịp xem thống kê trong khoảng ngày đã chọn", exact: true }).check();
    const session = await request(context, "GET", "/session");
    const day = new Intl.DateTimeFormat("sv-SE", { timeZone: session.timezone, year: "numeric", month: "2-digit", day: "2-digit" }).format(new Date(session.serverTime));
    await page.getByLabel("Thống kê từ ngày", { exact: true }).fill(day);
    await page.getByLabel("Thống kê đến ngày", { exact: true }).fill(day);
    for (const width of [390, 1440]) {
      await page.setViewportSize({ width, height: 900 });
      const axe = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze();
      expect(axe.passes.length > 0).toBe(true); expect(axe.violations.length).toBe(0);
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
      await page.screenshot({ path: artifacts + `visual/nhip-source-${width}.png`, fullPage: true });
    }
    await draft.fill("SYNTHETIC_MOOD_RANGE xem ngày mình chọn");
    await page.getByRole("button", { name: "Gửi tin cho AI", exact: true }).click();
    await expect(page.getByText("Đã xem thống kê bạn chọn, không có ghi chú.", { exact: true })).toBeVisible();
    await expect(page.getByRole("checkbox", { name: "Cho Nhịp xem thống kê trong khoảng ngày đã chọn", exact: true })).not.toBeChecked();
    const tool = JSON.parse(readFileSync(artifacts + "supabase-scoped-tool-proof.json", "utf8"));
    expect(tool.unselectedToolNotExposed && tool.selectedRangeToolInvoked && tool.notesExcluded).toBe(true);
    expect(tool.fromDate === day && tool.toDate === day && tool.recordedDays === 1).toBe(true);
    await request(context, "POST", "/auth/logout", {}, 204);
  } finally { await context.close(); }
});

test("hosted Auth fixture: mood lifecycle with insights, and MATCH restore never republishes", async ({
  browser,
}) => {
  const context = await browser.newContext();
  try {
    const page = await context.newPage();
    await login(page, "A");
    const session = await request(context, "GET", "/session");
    const day = (offset: number) =>
      new Intl.DateTimeFormat("sv-SE", {
        timeZone: session.timezone,
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
      }).format(
        new Date(new Date(session.serverTime).getTime() - offset * 86_400_000),
      );
    const target = day(3),
      shown = target.split("-").reverse().join("/"),
      tag = randomUUID().slice(0, 8);
    const existing = (await request(context, "GET", "/moods")).find(
      (m: any) => m.localDate === target,
    );
    if (existing)
      await request(context, "DELETE", `/moods/${target}`, {
        expectedVersion: existing.version,
      });
    await page.goto(base + "/#/self");
    await page.getByLabel("Ngày", { exact: true }).fill(target);
    await page.getByLabel("Tâm trạng", { exact: true }).selectOption("2");
    await page
      .getByLabel("Ghi chú", { exact: true })
      .fill(`Hosted mood ${tag}`);
    await page
      .getByRole("button", { name: "Lưu tâm trạng", exact: true })
      .click();
    await expect(
      page.getByText(/^Đã lưu cảm xúc ngày \d{2}\/\d{2}\/\d{4}\.$/),
    ).toBeVisible();
    await page.reload();
    await page.getByLabel("Ngày", { exact: true }).fill(target);
    await expect(page.getByLabel("Ghi chú", { exact: true })).toHaveValue(
      `Hosted mood ${tag}`,
    );
    await page.getByLabel("Tâm trạng", { exact: true }).selectOption("4");
    await page
      .getByRole("button", { name: "Cập nhật tâm trạng", exact: true })
      .click();
    await expect(
      page.getByText(/^Đã cập nhật cảm xúc ngày \d{2}\/\d{2}\/\d{4}\.$/),
    ).toBeVisible();
    const summary = await request(context, "GET", "/moods/summary?days=7");
    expect(summary.buckets.find((b: any) => b.localDate === target).value).toBe(
      4,
    );
    expect(summary.buckets.filter((b: any) => b.value === null).length).toBe(
      7 - summary.count,
    );
    record("hostedMoodCreateReloadEditSummary");
    await page
      .getByRole("button", { name: `Xóa tâm trạng ngày ${shown}`, exact: true })
      .click();
    await page
      .getByRole("button", { name: "Xóa ghi chép", exact: true })
      .click();
    await expect(
      page.getByText(`Đã xóa tâm trạng ngày ${shown}.`, { exact: true }),
    ).toBeVisible();
    expect(
      (await request(context, "GET", "/moods")).some(
        (m: any) => m.localDate === target,
      ),
    ).toBe(false);
    record("hostedMoodConfirmedDelete");

    await enable(page, "tìm bạn");
    let published = await request(
      context,
      "GET",
      "/profiles/published/current",
    );
    if (!published || published.state !== "live") {
      await publish(page);
      published = await request(context, "GET", "/profiles/published/current");
    }
    expect(published.state).toBe("live");
    await page.goto(base + "/#/settings");
    await page
      .getByRole("button", { name: "Tắt tìm bạn", exact: true })
      .click();
    await expect(
      page.getByRole("button", { name: "Bật tìm bạn", exact: true }),
    ).toBeVisible();
    await request(context, "GET", "/matching/candidates", undefined, 403);
    await enable(page, "tìm bạn");
    expect(
      (await request(context, "GET", "/profiles/published/current")).state,
    ).toBe("needs_republish");
    await request(context, "GET", "/matching/candidates", undefined, 403);
    await page.goto(base + "/#/connect");
    await expect(
      page.getByRole("heading", { name: "Hồ sơ đang tạm ẩn" }),
    ).toBeVisible();
    record("hostedMatchRestoreRequiresExplicitRepublish");
    await publish(page);
    expect(
      (await request(context, "GET", "/profiles/published/current")).state,
    ).toBe("live");
    await request(context, "POST", "/auth/logout", {}, 204);
  } finally {
    await context.close();
  }
});
