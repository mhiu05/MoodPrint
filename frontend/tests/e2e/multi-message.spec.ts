import { test, expect, type Page } from "@playwright/test";
import { baseSession } from "./ux-fixtures";

// P1-07 multi-bubble replies (ai-events-v2). Synthetic fixtures only: every API call is
// intercepted, so no backend, account or model is involved.
const CONV = "22222222-2222-4222-8222-222222222222";
const RUN = "33333333-3333-4333-8333-333333333333";
const IDS = ["aaaaaaa1-0000-4000-8000-000000000001", "aaaaaaa1-0000-4000-8000-000000000002", "aaaaaaa1-0000-4000-8000-000000000003"];
const BUBBLES = ["Nghe như hôm nay bạn đã gồng khá nhiều.", "Mây ở đây nghe bạn.", "Tối nay thử nghỉ sớm hơn 15 phút xem sao?"];
const bots = [{ botId: "may", name: "Mây", role: "Lắng nghe", description: "Một khoảng nhỏ để được lắng nghe.", starters: ["Hôm nay mình hơi mệt"], avatarKey: "may" }];
const prefs = { historyEnabled: true, semanticMemoryEnabled: false, version: 1, policyVersion: "ai-data-v1", retentionDays: 30, historyAvailable: true, semanticMemoryAvailable: true };
const now = "2026-10-23T08:00:00Z";

type Mode = { protocol: "v2" | "v1"; dropBeforeCompleted?: boolean; staleOnce?: boolean; beforeAccept?: () => Promise<void> };
type Message = Record<string, unknown>;

function sse(version: string, events: { type: string; data?: unknown }[]) {
  return events
    .map((event, index) => `id: ${index + 1}\ndata: ${JSON.stringify({ version, seq: String(index + 1), type: event.type, data: event.data ?? {} })}\n\n`)
    .join("");
}

async function mount(page: Page, mode: Mode) {
  const thread = { conversationId: CONV, botId: "may", version: 1, persistent: true, title: "Chat", expiresAt: "2026-11-26T08:00:00Z", createdAt: now, updatedAt: now, messages: [] as Message[], hasMoreMessages: false, activeRunId: null as string | null, activeRunVersion: null as number | null };
  const seen = { eventUrls: [] as string[], sends: 0, stale: mode.staleOnce ?? false };
  await page.route("**/api/v1/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname.replace("/api/v1", "");
    const json = (body: unknown, status = 200) => route.fulfill({ status, json: body });
    if (path === `/ai/conversations/${CONV}/messages` && request.method() === "POST") {
      seen.sends += 1;
      await mode.beforeAccept?.();
      if (seen.stale) {
        // A check-in arrived first: the server accepted nothing and its version moved on.
        seen.stale = false;
        thread.messages.push({ id: "bbbbbbb1-0000-4000-8000-000000000009", actor: "bot", text: "Chào buổi sáng!", cards: [], createdAt: now, runId: "bbbbbbb1-0000-4000-8000-00000000000a", status: "completed", partIndex: 0, partCount: 1, origin: "proactive", proactiveSlot: "morning" });
        thread.version = 2;
        return json({ error: { code: "STALE_VERSION", message: "Cuộc trò chuyện đã thay đổi. Vui lòng tải lại." } }, 409);
      }
      const body = request.postDataJSON();
      thread.messages.push({ id: body.clientMessageId, actor: "self", text: body.text, cards: [], createdAt: now, runId: RUN, status: "completed", partIndex: 0, partCount: 1, origin: "user", proactiveSlot: null });
      thread.version += 1;
      return json({ runId: RUN, conversationId: CONV, version: thread.version, runVersion: 1, eventsUrl: `/api/v1/ai/runs/${RUN}/events` }, 202);
    }
    if (path === `/ai/runs/${RUN}/events`) {
      seen.eventUrls.push(url.pathname + url.search);
      const parts = BUBBLES.map((text, index) => ({ messageId: IDS[index], partIndex: index, text, cards: index === 2 ? [{ kind: "mood_form" }] : [] }));
      if (mode.protocol === "v2") {
        thread.messages.push(...parts.map((part) => ({ id: part.messageId, actor: "bot", text: part.text, cards: part.cards, createdAt: now, runId: RUN, status: "completed", partIndex: part.partIndex, partCount: 3, origin: "user", proactiveSlot: null })));
        thread.version += 3;
        const events = [{ type: "progress" }, { type: "final", data: { partCount: 3, messages: parts } }, ...(mode.dropBeforeCompleted ? [] : [{ type: "completed" }])];
        return route.fulfill({ contentType: "text/event-stream", body: sse("ai-events-v2", events) }).catch(() => undefined);
      }
      thread.messages.push({ id: "ccccccc1-0000-4000-8000-000000000001", actor: "bot", text: "Một câu trả lời.", cards: [], createdAt: now, runId: RUN, status: "completed", partIndex: 0, partCount: 1, origin: "user", proactiveSlot: null });
      thread.version += 1;
      return route.fulfill({ contentType: "text/event-stream", body: sse("ai-events-v1", [{ type: "progress" }, { type: "final", data: { text: "Một câu trả lời.", cards: [] } }, { type: "completed" }]) }).catch(() => undefined);
    }
    if (path === `/ai/conversations/${CONV}` && request.method() === "GET") return json(thread);
    const fixed: Record<string, unknown> = {
      "/session": baseSession,
      "/bots": bots,
      "/ai/preferences": prefs,
      "/ai/conversations": [thread],
      "/proposals": [], "/memories": [],
    };
    if (request.method() === "GET" && path in fixed) return json(fixed[path]);
    return json({ error: { code: "NOT_FOUND", message: `Missing synthetic fixture ${path}` } }, 404);
  });
  return seen;
}

const field = (page: Page) => page.getByRole("textbox", { name: "Tin nhắn cho Mây" });
async function openAndSend(page: Page, text = "Hôm nay mình hơi uể oải") {
  await page.goto(`/#/assistants/may?conversation=${CONV}`);
  await expect(field(page)).toBeVisible();
  await expect(page.getByText("Đang mở cuộc trò chuyện…")).toHaveCount(0);
  await field(page).fill(text);
  await page.getByRole("button", { name: "Gửi tin cho AI", exact: true }).click();
}
const group = (page: Page) => page.getByRole("group", { name: "Tin nhắn từ Mây, 3 phần" });

for (const stale of [false, true]) {
  test(`Enter clears the composer and shows a pending bubble before acceptance (stale=${stale})`, async ({ page }) => {
    let release!: () => void;
    const gate = new Promise<void>((resolve) => { release = resolve; });
    await mount(page, { protocol: "v2", staleOnce: stale, beforeAccept: () => gate });
    await page.goto(`/#/assistants/may?conversation=${CONV}`);
    await expect(field(page)).toBeEnabled();
    await field(page).fill("A slow message");
    await field(page).press("Enter");
    try {
      await expect(field(page)).toHaveValue("");
      await expect(page.locator(".from-self .chat-bubble")).toHaveText(["A slow message"]);
      await expect(page.locator(".from-self").last()).toHaveAttribute("aria-busy", "true");
      await expect(page.locator(".message-pending svg")).toBeVisible();
      if (!stale) await field(page).fill("My next message");
    } finally { release(); }
    if (stale) {
      await expect(field(page)).toHaveValue("A slow message");
      await expect(page.locator(".from-self")).toHaveCount(0);
    } else {
      await expect(group(page)).toBeVisible();
      await expect(field(page)).toHaveValue("My next message");
      await expect(page.locator(".from-self .chat-bubble")).toHaveText(["A slow message"]);
    }
  });
}

test("deleting a conversation while sending clears its pending bubble", async ({ page }) => {
  let release!: () => void;
  const gate = new Promise<void>((resolve) => { release = resolve; });
  await mount(page, { protocol: "v2", beforeAccept: () => gate });
  await page.route(`**/api/v1/ai/conversations/${CONV}`, (route) => route.request().method() === "DELETE"
    ? route.fulfill({ status: 204 }) : route.fallback());
  await page.goto(`/#/assistants/may?conversation=${CONV}`);
  await expect(field(page)).toBeEnabled();
  await field(page).fill("Deleted pending message");
  await field(page).press("Enter");
  try {
    await expect(page.locator(".message-pending")).toBeVisible();
    await page.getByRole("button", { name: "Thông tin cuộc trò chuyện", exact: true }).click();
    await page.getByRole("button", { name: "Xóa cuộc trò chuyện", exact: true }).click();
    await page.getByRole("dialog").getByRole("button", { name: "Xóa cuộc trò chuyện", exact: true }).click();
    await expect(page.locator(".message-pending")).toHaveCount(0);
    await expect(page.locator(".from-self")).toHaveCount(0);
  } finally { release(); }
});

test("a new conversation shows the pending message while the conversation itself is being created", async ({ page }) => {
  let release!: () => void;
  const gate = new Promise<void>((resolve) => { release = resolve; });
  await mount(page, { protocol: "v2" });
  await page.route("**/api/v1/ai/conversations", async (route) => {
    if (route.request().method() !== "POST") return route.fallback();
    await gate;
    return route.fulfill({ status: 201, json: { conversationId: CONV, botId: "may", version: 1, persistent: true, title: "Chat", expiresAt: "2026-11-26T08:00:00Z" } });
  });
  await page.goto("/#/assistants/may?new=new-test");
  await expect(field(page)).toBeEnabled();
  await field(page).fill("My first message");
  await field(page).press("Enter");
  try {
    await expect(field(page)).toHaveValue("");
    await expect(page.locator(".from-self .chat-bubble")).toHaveText(["My first message"]);
    await expect(page.locator(".message-pending svg")).toBeVisible();
  } finally { release(); }
  await expect(group(page)).toBeVisible();
  await expect(page.locator(".from-self .chat-bubble")).toHaveText(["My first message"]);
});

for (const edit of [false, true]) {
  test(`a rejected send removes its pending bubble and preserves the draft (edited=${edit})`, async ({ page }) => {
    let release!: () => void;
    const gate = new Promise<void>((resolve) => { release = resolve; });
    await mount(page, { protocol: "v2" });
    await page.route(`**/api/v1/ai/conversations/${CONV}/messages`, async (route) => {
      await gate;
      return route.fulfill({ status: 503, json: { error: { code: "AI_UNAVAILABLE", message: "Try again" } } });
    });
    await page.goto(`/#/assistants/may?conversation=${CONV}`);
    await expect(field(page)).toBeEnabled();
    await field(page).fill("My message");
    await field(page).press("Enter");
    try {
      await expect(page.locator(".message-pending")).toBeVisible();
      await expect(field(page)).toHaveValue("");
      if (edit) await field(page).fill("A new draft");
    } finally { release(); }
    await expect(page.locator(".message-pending")).toHaveCount(0);
    await expect(page.locator(".from-self")).toHaveCount(0);
    await expect(field(page)).toHaveValue(edit ? "A new draft" : "My message");
  });
}

for (const width of [1440, 768, 390]) {
  test(`three validated bubbles appear together as one group at ${width}px`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width, height: width === 390 ? 844 : 900 });
    const seen = await mount(page, { protocol: "v2" });
    await openAndSend(page);
    await expect(group(page)).toBeVisible();
    await expect(group(page).locator(".message-content")).toHaveCount(3);
    await expect(group(page).locator(".chat-bubble")).toHaveText(BUBBLES);
    await expect(group(page).locator(".chat-bubble").first()).toHaveCSS("background-color", "rgb(240, 240, 242)");
    expect(seen.eventUrls).toEqual([`/api/v1/ai/runs/${RUN}/events?protocol=3`]);
    // The card belongs to the last bubble only.
    await expect(group(page).locator(".message-row").nth(2).getByRole("link", { name: /Ghi lại cảm xúc/ })).toBeVisible();
    await expect(group(page).locator(".message-row").nth(0).locator(".inline-card")).toHaveCount(0);
    // After reconciliation with the server copy the group is unchanged (same ids, no -final leftovers).
    await expect(page.locator(".message-content[aria-label^='Phần']")).toHaveCount(3);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    await page.screenshot({ path: testInfo.outputPath(`chat-${width}.png`) });
  });
}

test("bubbles of one reply sit close together and each still reveals its own copy action", async ({ page }) => {
  await mount(page, { protocol: "v2" });
  await openAndSend(page);
  const rows = group(page).locator(".message-row");
  await expect(rows).toHaveCount(3);
  const gaps = await rows.evaluateAll((elements) =>
    elements.slice(1).map((element, index) => {
      const previous = elements[index].querySelector(".chat-bubble")!.getBoundingClientRect();
      return Math.round(element.querySelector(".chat-bubble")!.getBoundingClientRect().top - previous.bottom);
    }),
  );
  // One turn, not three: no reserved metadata row between bubbles.
  for (const gap of gaps) expect(gap).toBeLessThanOrEqual(16);
  // Keyboard modality first, so focus is :focus-visible as when a person tabs in.
  await page.keyboard.press("Shift");
  await rows.nth(0).locator(".message-content").focus();
  await expect(rows.nth(0).getByRole("button", { name: "Sao chép câu trả lời" })).toBeVisible();
  await rows.nth(2).locator(".message-content").focus();
  await expect(rows.nth(2).getByRole("button", { name: "Sao chép câu trả lời" })).toBeVisible();
});

test("a final without its completed receipt shows no bubble", async ({ page }) => {
  await mount(page, { protocol: "v2", dropBeforeCompleted: true });
  await openAndSend(page);
  await expect(page.getByText("Chưa nhận được phản hồi hợp lệ", { exact: false })).toBeVisible();
  await expect(page.locator(".message-group")).toHaveCount(0);
  for (const text of BUBBLES) await expect(page.getByText(text)).toHaveCount(0);
});

test("an older server answering ai-events-v1 still shows one ordinary message", async ({ page }) => {
  await mount(page, { protocol: "v1" });
  await openAndSend(page);
  await expect(page.locator(".from-bot .chat-bubble")).toHaveText(["Một câu trả lời."]);
  await expect(page.locator(".message-group")).toHaveCount(0);
  await expect(page.getByText("Chưa nhận được phản hồi hợp lệ", { exact: false })).toHaveCount(0);
});

test("a newer message (STALE_VERSION) reloads the thread and keeps the draft for a resend", async ({ page }) => {
  const seen = await mount(page, { protocol: "v2", staleOnce: true });
  await openAndSend(page, "Mình muốn kể chuyện hôm qua");
  await expect(page.getByRole("status").filter({ hasText: "Có tin mới từ Mây. Tin của bạn vẫn còn trong ô nhập" })).toBeVisible();
  await expect(field(page)).toHaveValue("Mình muốn kể chuyện hôm qua");
  await expect(page.getByText("Chào buổi sáng!")).toBeVisible();
  expect(seen.sends).toBe(1);
  await page.getByRole("button", { name: "Gửi tin cho AI", exact: true }).click();
  await expect(group(page)).toBeVisible();
  expect(seen.sends).toBe(2);
});

test("each bubble is keyboard focusable and the group renders statically with reduced motion", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await mount(page, { protocol: "v2" });
  await openAndSend(page);
  const parts = group(page).locator(".message-content");
  await expect(parts).toHaveCount(3);
  for (let index = 0; index < 3; index += 1) {
    await parts.nth(index).focus();
    await expect(parts.nth(index)).toBeFocused();
    await expect(parts.nth(index)).toHaveAttribute("aria-label", `Phần ${index + 1} trên 3`);
  }
  const style = await group(page).evaluate((element) => {
    const computed = getComputedStyle(element);
    return { opacity: computed.opacity, transform: computed.transform };
  });
  expect(style).toEqual({ opacity: "1", transform: "none" });
});
