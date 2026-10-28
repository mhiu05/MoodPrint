import { expect, test } from "@playwright/test";
import { api } from "./helpers";
import { createGuest, guestCall } from "./guest-support";

test.beforeEach(async ({ request }) => { expect((await request.post("http://127.0.0.1:5174/__test/reset-admission")).ok()).toBe(true); });

test("guest uses five assistants with explicit consent, mood, memory and voice preview only", async ({ browser }) => {
  const context = await browser.newContext({ permissions: ["microphone"], viewport: { width: 390, height: 844 } });
  try {
    const owner = await createGuest(context);
    const bots = await (await context.request.get(api + "/bots")).json();
    expect(bots).toHaveLength(5);
    for (const purpose of ["AI", "MEM", "VOICE"]) {
      const result = await guestCall(context, "PUT", `/consents/${purpose}`, { enabled: true, expectedVersion: 1, policyVersion: "v1" });
      expect(result.status(), await result.text()).toBe(200);
    }
    for (const bot of bots) {
      const response = await guestCall(context, "POST", "/ai/conversations", { botId: bot.botId });
      expect(response.status(), await response.text()).toBe(201);
      const conversation = await response.json();
      const accepted = await guestCall(context, "POST", `/ai/conversations/${conversation.conversationId}/messages`, {
        text: "Chia sẻ tổng hợp để kiểm thử", clientMessageId: crypto.randomUUID(), expectedConversationVersion: conversation.version,
      });
      expect(accepted.status(), await accepted.text()).toBe(202);
      const run = await accepted.json();
      const stream = await context.request.get("http://127.0.0.1:5174" + run.eventsUrl);
      expect(stream.status()).toBe(200);
      expect(await stream.text()).toContain("event: final");
    }
    const page = await context.newPage();
    const proposal = await (await context.request.post("http://127.0.0.1:5174/__test/proposal", { data: { userId: owner.userId } })).json();
    expect((await guestCall(context, "POST", `/proposals/${proposal.id}/confirm`, { expectedVersion: proposal.version })).status()).toBe(200);
    expect(await (await context.request.get(api + "/memories")).text()).toContain("SYNTHETIC-GUEST-MEMORY");
    await page.goto("/#/memory");
    await expect(page.getByRole("main")).toBeVisible();
    expect((await context.request.get(api + "/memories")).status()).toBe(200);
    // Valid PCM goes through the actual upload/consent/budget route; only provider STT is synthetic.
    const pcm = Buffer.alloc(32044);
    pcm.write("RIFF"); pcm.writeUInt32LE(32036, 4); pcm.write("WAVEfmt ", 8);
    pcm.writeUInt32LE(16, 16); pcm.writeUInt16LE(1, 20); pcm.writeUInt16LE(1, 22);
    pcm.writeUInt32LE(16000, 24); pcm.writeUInt32LE(32000, 28); pcm.writeUInt16LE(2, 32); pcm.writeUInt16LE(16, 34);
    pcm.write("data", 36); pcm.writeUInt32LE(32000, 40);
    const csrf = (await context.cookies()).find(c => c.name === "moodprint_csrf")!.value;
    const voice = await context.request.post(api + "/voice/transcriptions", { data: pcm, headers: {
      "Content-Type": "audio/wav", "X-CSRF-Token": csrf, "Idempotency-Key": crypto.randomUUID(),
    }});
    expect(voice.status(), await voice.text()).toBe(200);
    expect(await voice.json()).toEqual({ text: "Bản chữ tổng hợp để bạn duyệt", durationSeconds: 1 });
    let sends = 0;
    page.on("request", request => { if (request.method() === "POST" && /\/messages$/.test(request.url())) sends += 1; });
    await page.goto("/#/assistants/may");
    await page.getByRole("button", { name: "Ghi âm", exact: true }).click();
    await expect(page.getByText(/Đang ghi âm/)).toBeVisible();
    await page.waitForTimeout(1200); // collect actual synthetic PCM frames in the browser worklet
    await page.getByRole("button", { name: "Dừng và chuyển thành văn bản" }).click();
    await expect(page.getByLabel("Xem và sửa bản chép lời")).toHaveValue("Bản chữ tổng hợp để bạn duyệt");
    await page.getByLabel("Xem và sửa bản chép lời").fill("Bản nháp giọng nói tổng hợp");
    expect(sends).toBe(0);
    await page.getByRole("button", { name: "Đưa vào ô tin nhắn" }).click();
    await expect(page.getByRole("textbox", { name: "Tin nhắn cho Mây" })).toHaveValue("Bản nháp giọng nói tổng hợp");
    expect(sends).toBe(0);
    expect((await context.request.get(api + "/session")).status()).toBe(200);
  } finally { await context.close(); }
});
