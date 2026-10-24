import { test, expect, type BrowserContext, type Page } from "@playwright/test";
import { randomUUID } from "node:crypto";
import { readFileSync, writeFileSync } from "node:fs";
import AxeBuilder from "@axe-core/playwright";

const base = "http://127.0.0.1:5177";
const artifacts = "../docs/plans/validation-artifacts/live-ai/";

async function request(context: BrowserContext, method: string, path: string, data?: unknown, status = 200) {
  const csrf = (await context.cookies(base)).find(c => c.name === "moodprint_csrf")?.value;
  const response = await context.request.fetch(base + "/api/v1" + path, {
    method, data, timeout: 30000,
    headers: { Origin: base, "X-CSRF-Token": csrf || "", "Idempotency-Key": randomUUID() },
  });
  expect(response.status(), `${method} ${path}`).toBe(status);
  if (status === 204) return undefined;
  try { return await response.json(); }
  catch { throw new Error(`Invalid JSON response for ${method} ${path}; status ${response.status()}, type ${response.headers()["content-type"]}`); }
}

async function login(page: Page, actor: "A" | "B") {
  await page.goto(base);
  try {
    await page.getByLabel("Email", { exact: true }).fill(process.env[`MOODPRINT_TEST_${actor}_EMAIL`]!);
    await page.getByLabel("Mật khẩu", { exact: true }).fill(process.env[`MOODPRINT_TEST_${actor}_PASSWORD`]!);
    await page.getByRole("button", { name: "Đăng nhập", exact: true }).click();
  } catch { throw new Error("Synthetic login failed; credential details redacted"); }
  await expect(page.getByLabel("Mật khẩu", { exact: true })).toHaveCount(0);
}

async function consent(context: BrowserContext, purpose: string, enabled: boolean) {
  const session = await request(context, "GET", "/session");
  if (session.consents[purpose].enabled !== enabled)
    await request(context, "PUT", `/consents/${purpose}`, {
      enabled, expectedVersion: session.consents[purpose].version, policyVersion: "v1",
    });
}

async function send(page: Page, name: string, text: string) {
  const before = await page.locator(".from-bot").count();
  await page.getByRole("textbox", { name: `Tin nhắn cho ${name}` }).fill(text);
  await page.getByRole("button", { name: "Gửi tin cho AI", exact: true }).click();
  await expect(page.locator(".from-bot")).toHaveCount(before + 1);
  await expect(page.getByRole("button", { name: "Dừng", exact: true })).toHaveCount(0);
  const reply = await page.locator(".from-bot").last().innerText();
  expect(reply.length).toBeGreaterThan(5);
  return reply;
}

test("real five companions, scoped mood tool, memory proposal and explicit approval", async ({ browser }) => {
  const a = await browser.newContext(), b = await browser.newContext();
  const proof: Record<string, unknown> = { synthetic: true, transport: "real browser → FastAPI → Agents SDK → OpenAI", replies: [] };
  let moodDay: string | undefined, memoryId: string | undefined;
  const initialConsents: Record<string, boolean> = {};
  try {
    const page = await a.newPage(), peer = await b.newPage();
    await login(page, "A"); await login(peer, "B");
    const initial = await request(a, "GET", "/session");
    for (const purpose of ["AI", "MEM"]) initialConsents[purpose] = initial.consents[purpose].enabled;
    await consent(a, "AI", true); await consent(a, "MEM", true);
    const moods = await request(a, "GET", "/moods");
    const anchor = new Date(initial.serverTime);
    for (let days = 40; days < 80; days++) {
      const day = new Date(anchor); day.setUTCDate(day.getUTCDate() - days);
      const selected = day.toISOString().slice(0, 10);
      if (!moods.some((m: any) => m.localDate === selected)) { moodDay = selected; break; }
    }
    expect(moodDay).toBeDefined();
    await request(a, "PUT", `/moods/${moodDay}`, { value: 2, note: "SYNTHETIC_NOTE_CANARY", timezone: initial.timezone, expectedVersion: 0 });
    const prompts = [
      ["may", "Mây", "Mình vừa thắng một ván cờ, chỉ muốn khoe thôi!"],
      ["rure", "Rủ Rê", "Cho mình một trò chơi một người trong 3 phút, chỉ cần giấy và bút."],
      ["caunoi", "Cầu Nối", "Bật tìm bạn có tự đăng hồ sơ riêng không? Mình chưa muốn gửi lời mời."],
    ];
    for (const [bot, name, prompt] of prompts) {
      await page.goto(base + `/#/assistants/${bot}`);
      const reply = await send(page, name, prompt);
      (proof.replies as unknown[]).push({ bot, prompt, reply });
    }
    await page.goto(base + "/#/assistants/nhip");
    await page.getByText("Chia sẻ thống kê tâm trạng cho lượt này", { exact: true }).click();
    await page.getByRole("checkbox", { name: "Cho Nhịp đọc khoảng ngày mình chọn", exact: true }).check();
    await page.getByLabel("Thống kê từ ngày", { exact: true }).fill(moodDay!);
    await page.getByLabel("Thống kê đến ngày", { exact: true }).fill(moodDay!);
    const moodReply = await send(page, "Nhịp", "Hãy dùng công cụ đọc thống kê khoảng ngày mình chọn, nói số ngày đã ghi và điểm trung bình. Không đọc ghi chú.");
    expect(moodReply).not.toContain("SYNTHETIC_NOTE_CANARY");
    expect(moodReply).toContain("2");
    (proof.replies as unknown[]).push({ bot: "nhip", reply: moodReply });
    const usage = readFileSync(artifacts + "http-usage.jsonl", "utf8").split("\n").filter(Boolean).map(line => JSON.parse(line));
    expect(usage.some(e => e.bot_id === "nhip" && e.kind === "tool_started" && e.tool_name === "read_mood_summary")).toBe(true);
    proof.realMoodTool = "PASS";

    const memoriesBefore = await request(a, "GET", "/memories");
    await page.goto(base + "/#/assistants/guong");
    const memoryReply = await send(page, "Gương", "Mình tự xác nhận sở thích: thích vẽ tranh bằng màu nước. Hãy dùng công cụ tạo đề xuất ghi nhớ để mình duyệt, đừng tự lưu.");
    const proposals = await request(a, "GET", "/proposals");
    const proposal = proposals.find((p: any) => p.botId === "guong" && p.purpose === "memory");
    expect(proposal).toBeDefined();
    expect(await request(a, "GET", "/memories")).toHaveLength(memoriesBefore.length);
    await request(b, "POST", `/proposals/${proposal.id}/confirm`, { expectedVersion: proposal.version }, 404);
    await page.goto(base + "/#/memory");
    const card = page.locator("article").filter({ has: page.getByLabel("Nội dung bạn muốn duyệt", { exact: true }) }).filter({ hasText: "Gương" }).first();
    await card.getByRole("button", { name: "Duyệt và lưu", exact: true }).click();
    await expect(page.getByText("Đã cập nhật ghi nhớ.", { exact: true })).toBeVisible();
    const memoriesAfter = await request(a, "GET", "/memories");
    memoryId = memoriesAfter.find((m: any) => !memoriesBefore.some((old: any) => old.id === m.id))?.id;
    expect(memoryId).toBeDefined();
    (proof.replies as unknown[]).push({ bot: "guong", reply: memoryReply });
    proof.memoryProposalApprovalAndPeerDenial = "PASS";
    await page.goto(base + "/#/assistants/may");
    await page.setViewportSize({ width: 390, height: 844 });
    await expect(page.getByRole("textbox", { name: "Tin nhắn cho Mây" })).toBeVisible();
    const a11y = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze();
    expect(a11y.violations).toEqual([]);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.screenshot({ path: artifacts + "live-mobile.png", fullPage: true });
    await page.setViewportSize({ width: 1440, height: 1000 });
    await page.screenshot({ path: artifacts + "live-desktop.png", fullPage: true });
    proof.mobileAndA11y = "PASS";
    proof.status = "PASS";
  } finally {
    if (memoryId) {
      const m = (await request(a, "GET", "/memories")).find((m: any) => m.id === memoryId);
      if (m) await request(a, "DELETE", `/memories/${memoryId}`, { expectedVersion: m.version });
    }
    if (moodDay) {
      const m = (await request(a, "GET", "/moods")).find((m: any) => m.localDate === moodDay);
      if (m) await request(a, "DELETE", `/moods/${moodDay}`, { expectedVersion: m.version });
    }
    for (const [purpose, enabled] of Object.entries(initialConsents)) await consent(a, purpose, enabled);
    writeFileSync(artifacts + "tool-calling-results.json", JSON.stringify(proof, null, 2));
    await a.close(); await b.close();
  }
});

test("real React ten-turn context, correction, reload and bot isolation", async ({ page }) => {
  await login(page, "A");
  const session = await request(page.context(), "GET", "/session");
  await consent(page.context(), "AI", true);
  const transcript: { prompt: string; reply: string }[] = [];
  try {
    await page.goto(base + "/#/assistants/guong");
    const prompts = [
      "Trong cuộc trò chuyện này, mình đang tập vẽ sơn dầu. Đừng tạo ghi nhớ.",
      "Mình có khoảng mười phút rảnh mỗi tối.",
      "Mình thích những gợi ý cụ thể, không cần khen nhé.",
      "Gợi ý một cách quan sát ánh sáng khi vẽ.",
      "Nói ngắn thôi, mình đang ghi chú.",
      "Quay lại: lúc đầu mình nói đang tập chất liệu gì?",
      "Mình muốn ưu tiên hoạt động thư giãn hơn thi đua.",
      "Sửa thông tin trước: mình đã bỏ sơn dầu và chuyển sang màu nước. Chỉ dùng thông tin mới trong phiên này, không lưu.",
      "Chuyển chủ đề một chút: kể một ý tưởng đặt tên bức tranh.",
      "Giờ mình đang tập chất liệu gì? Trả lời đúng điều mình sửa gần nhất.",
    ];
    for (const prompt of prompts) transcript.push({ prompt, reply: await send(page, "Gương", prompt) });
    expect(transcript[5].reply.toLowerCase()).toContain("sơn dầu");
    expect(transcript[9].reply.toLowerCase()).toContain("màu nước");
    const count = await page.locator(".from-bot").count();
    await page.reload();
    await expect(page.locator(".from-bot")).toHaveCount(count);
    await page.goto(base + "/#/assistants/caunoi");
    const isolated = await send(page, "Cầu Nối", "Bạn biết mình đang tập chất liệu vẽ gì từ cuộc trò chuyện ở Gương không? Đừng đoán.");
    expect(isolated.toLowerCase()).not.toContain("màu nước");
    writeFileSync(artifacts + "multi-turn-results.json", JSON.stringify({ status: "PASS", synthetic: true, turnCount: 10, transcript, isolated, reloadNoDuplicate: true }, null, 2));
  } finally {
    await consent(page.context(), "AI", session.consents.AI.enabled);
  }
});

test("real provider cancel, duplicate intent and consent revoke suppress late output", async ({ page }) => {
  await login(page, "A");
  const context = page.context();
  const before = await request(context, "GET", "/session");
  const proof: Record<string, unknown> = { synthetic: true };
  await consent(context, "AI", true);
  async function start() {
    const thread = await request(context, "POST", "/ai/conversations", { botId: "guong" }, 201);
    const body = { text: "Viết một bài tập tưởng tượng chi tiết gồm mười đoạn về việc vẽ phong cảnh. Chỉ là ví dụ tổng hợp, không tạo ghi nhớ.", clientMessageId: randomUUID(), expectedConversationVersion: 1 };
    const run = await request(context, "POST", `/ai/conversations/${thread.conversationId}/messages`, body, 202);
    const duplicate = await request(context, "POST", `/ai/conversations/${thread.conversationId}/messages`, body, 202);
    expect(duplicate.runId).toBe(run.runId);
    await expect.poll(() => readFileSync(artifacts + "http-usage.jsonl", "utf8").split("\n").filter(Boolean).map(line => JSON.parse(line)).some(e => e.run_id === run.runId && e.kind === "request_started")).toBe(true);
    return run;
  }
  try {
    const cancelled = await start();
    await request(context, "POST", `/ai/runs/${cancelled.runId}/cancel`, { expectedVersion: 1 });
    const events = await context.request.get(base + cancelled.eventsUrl);
    expect(events.status()).toBe(200);
    const stream = await events.text();
    expect(stream).toContain("event: cancelled");
    expect(stream).not.toContain("event: final");
    const usage = readFileSync(artifacts + "http-usage.jsonl", "utf8").split("\n").filter(Boolean).map(line => JSON.parse(line));
    expect(usage.filter(e => e.run_id === cancelled.runId && e.kind === "request_started")).toHaveLength(1);
    proof.cancelAndIdempotency = "PASS";
    const revoked = await start();
    await consent(context, "AI", false);
    const denied = await context.request.get(base + revoked.eventsUrl);
    expect([403, 404, 410]).toContain(denied.status());
    proof.consentRevoke = "PASS";
    proof.status = "PASS";
  } finally {
    await consent(context, "AI", before.consents.AI.enabled);
    writeFileSync(artifacts + "safety-regressions.json", JSON.stringify(proof, null, 2));
  }
});

test("synthetic media stream, real STT preview, edit, explicit send and proposal-only tools", async ({ page, context }) => {
  test.skip(!process.env.MOODPRINT_TEST_AUDIO, "Generate the synthetic test-only audio fixture first");
  await context.grantPermissions(["microphone"], { origin: base });
  const browserErrors: string[] = [];
  page.on("pageerror", error => browserErrors.push(error.message));
  page.on("console", message => { if (message.type() === "error") browserErrors.push(message.text()); });
  await page.route("**/__synthetic_voice.wav", route => route.fulfill({ path: process.env.MOODPRINT_TEST_AUDIO!, contentType: "audio/wav" }));
  // Native fake-device capture returns NotSupportedError in this Windows runner.
  // Only the input source is synthetic; AudioWorklet, WAV upload, auth, STT and
  // model responses use the real application and network providers.
  await page.addInitScript(() => {
    navigator.mediaDevices.getUserMedia = async () => {
      const context = new AudioContext();
      const data = await (await fetch("/__synthetic_voice.wav")).arrayBuffer();
      const source = context.createBufferSource();
      source.buffer = await context.decodeAudioData(data);
      source.loop = true;
      const destination = context.createMediaStreamDestination();
      source.connect(destination);
      await context.resume(); source.start();
      const stream = destination.stream;
      for (const track of stream.getTracks()) {
        const stop = track.stop.bind(track);
        track.stop = () => { stop(); source.stop(); void context.close(); };
      }
      return stream;
    };
  });
  await login(page, "A");
  const before = await request(context, "GET", "/session");
  const replies: Record<string, unknown>[] = [];
  try {
    for (const purpose of ["AI", "MEM", "VOICE"]) await consent(context, purpose, true);
    await page.goto(base + "/#/assistants/may");
    await page.reload();
    await page.getByRole("button", { name: "Ghi âm tối đa 30 giây", exact: true }).click();
    await expect(page.getByRole("status").filter({ hasText: "Đang ghi âm" }), `Microphone startup errors: ${browserErrors.join("; ")}`).toContainText(/8\/30/);
    await page.getByRole("button", { name: "Dừng và xem bản chữ", exact: true }).click();
    const preview = page.getByRole("textbox", { name: "Xem và sửa bản chữ", exact: true });
    await expect(preview).toBeVisible();
    expect((await preview.inputValue()).toLowerCase()).toContain("màu nước");
    const botCount = await page.locator(".from-bot").count();
    await preview.fill("Mình muốn đi dạo mười phút, chỉ trò chuyện thôi.");
    await page.getByRole("button", { name: "Dùng bản chữ trong ô nhắn", exact: true }).click();
    const input = page.getByRole("textbox", { name: "Tin nhắn cho Mây" });
    await expect(input).toHaveValue("Mình muốn đi dạo mười phút, chỉ trò chuyện thôi.");
    expect(await page.locator(".from-bot").count()).toBe(botCount);
    await send(page, "Mây", await input.inputValue());
    await page.setViewportSize({ width: 390, height: 844 });
    await expect(page.getByText("Đang mở cuộc trò chuyện…", { exact: true })).toHaveCount(0);
    await page.screenshot({ path: artifacts + "live-mobile.png", fullPage: true });
    await page.setViewportSize({ width: 1440, height: 1000 });
    await page.screenshot({ path: artifacts + "live-desktop.png", fullPage: true });
    replies.push({ bot: "may", reply: await send(page, "Mây", "Mình xác nhận thích trò chuyện chậm. Hãy tạo đề xuất ghi nhớ bằng công cụ để mình duyệt riêng.") });
    await page.goto(base + "/#/assistants/guong");
    replies.push({ bot: "guong", reply: await send(page, "Gương", "Mình tự xác nhận thích khám phá qua hội họa. Hãy dùng propose_private_item tạo một mô tả hồ sơ riêng để mình xem và duyệt. Chưa lưu.") });
    const proposals = await request(context, "GET", "/proposals");
    expect(proposals.some((p: any) => p.botId === "may" && p.purpose === "memory")).toBe(true);
    expect(proposals.some((p: any) => p.botId === "guong" && p.purpose === "private_item")).toBe(true);
    for (const proposal of proposals.filter((p: any) => ["may", "guong"].includes(p.botId)))
      await request(context, "POST", `/proposals/${proposal.id}/reject`, { expectedVersion: proposal.version });
    writeFileSync(artifacts + "voice-browser-results.json", JSON.stringify({ status: "PASS", synthetic: true, physicalMicUsed: false, nativeGetUserMedia: "BLOCKED: NotSupportedError in Chromium runner", captureSource: "Web Audio MediaStream from synthetic Vietnamese WAV", sttModel: "gpt-transcribe", sttRequests: 1, previewEditExplicitSend: true, replies }, null, 2));
  } finally {
    for (const purpose of ["VOICE", "MEM", "AI"]) await consent(context, purpose, before.consents[purpose].enabled);
  }
});
