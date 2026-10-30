import { test, expect, type Page, type Route, type Request } from "@playwright/test";
import { app, baseSession } from "./ux-fixtures";

// Merge-readiness regressions MR01-MR11. Synthetic fixtures only; every API call is
// intercepted, so no backend, account or model is involved. Races are produced with
// explicit gates (deferred responses), never with sleeps.
const A = "22222222-2222-4222-8222-222222222222";
const B = "44444444-4444-4444-8444-444444444444";
const C = "66666666-6666-4666-8666-666666666666";
const R = "33333333-3333-4333-8333-333333333333";
const R2 = "55555555-5555-4555-8555-555555555555";
const bots = [{ botId: "may", name: "Mây", role: "Lắng nghe", description: "Một khoảng nhỏ để được lắng nghe.", starters: ["Hôm nay mình hơi mệt"], avatarKey: "may" }];
const prefs = { historyEnabled: true, semanticMemoryEnabled: false, version: 1, policyVersion: "ai-data-v1", retentionDays: 30, historyAvailable: true, semanticMemoryAvailable: true };

type Gate = { promise: Promise<void>; open: () => void };
function gate(opened = false): Gate {
  let open: () => void = () => {};
  const promise = new Promise<void>((resolve) => { open = resolve; });
  if (opened) open();
  return { promise, open };
}
type Message = { id: string; actor: "self" | "bot"; text: string; cards?: unknown[]; status?: string };
type Thread = { conversationId: string; botId: string; version: number; persistent: boolean; title: string; expiresAt: string; messages: Message[]; hasMoreMessages: boolean; activeRunId: string | null; activeRunVersion: number | null };
const thread = (id: string, patch: Partial<Thread> = {}): Thread => ({ conversationId: id, botId: "may", version: 1, persistent: true, title: `Chat ${id[0]}`, expiresAt: "2026-11-26T08:00:00Z", messages: [], hasMoreMessages: false, activeRunId: null, activeRunVersion: null, ...patch });
const sse = (events: { type: string; data?: unknown }[]) =>
  events.map((event, index) => `id: ${index + 1}\ndata: ${JSON.stringify({ version: "ai-events-v1", seq: String(index + 1), type: event.type, data: event.data ?? {} })}\n\n`).join("");

type Terminal = "completed" | "cancelled" | "failed" | "drop";
type Call = { method: string; path: string; body: any };
type Store = {
  threads: Record<string, Thread>;
  calls: Call[];
  runs: Record<string, string>;
  /** Gate every run's event stream waits on; keyed by run id. */
  finish: Record<string, Gate>;
  terminal: Record<string, Terminal>;
  accept: Gate;
  cancel: Gate;
  flags: { transcript503: boolean; message503: boolean; cancel503: boolean; createGate: Gate };
  count: (method: string, path: RegExp) => number;
};
type Handler = (ctx: { route: Route; request: Request; path: string; store: Store }) => Promise<boolean | void>;

async function mount(page: Page, handler?: Handler): Promise<Store> {
  const store: Store = {
    threads: { [A]: thread(A), [B]: thread(B) },
    calls: [],
    runs: {},
    finish: {},
    terminal: {},
    accept: gate(true),
    cancel: gate(true),
    flags: { transcript503: false, message503: false, cancel503: false, createGate: gate(true) },
    count: (method, path) => store.calls.filter((call) => call.method === method && path.test(call.path)).length,
  };
  await page.route("**/api/v1/**", async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname.replace("/api/v1", "");
    store.calls.push({ method: request.method(), path, body: request.method() === "GET" ? null : request.postDataJSON() });
    if (await handler?.({ route, request, path, store })) return;
    const json = (body: unknown, status = 200) => route.fulfill({ status, json: body });
    const unavailable = () => json({ error: { code: "UNAVAILABLE", message: "Dịch vụ tạm gián đoạn." } }, 503);
    if (path === "/ai/conversations" && request.method() === "POST") {
      await store.flags.createGate.promise;
      store.threads[C] = thread(C);
      return json(store.threads[C], 201);
    }
    const messages = path.match(/^\/ai\/conversations\/([^/]+)\/messages$/);
    if (messages && request.method() === "POST") {
      await store.accept.promise;
      if (store.flags.message503) return unavailable();
      const target = store.threads[messages[1]];
      target.messages.push({ id: request.postDataJSON().clientMessageId, actor: "self", text: request.postDataJSON().text });
      store.runs[R] = messages[1];
      return json({ runId: R, conversationId: messages[1], version: 2, runVersion: 1, eventsUrl: `/api/v1/ai/runs/${R}/events` }, 202);
    }
    const events = path.match(/^\/ai\/runs\/([^/]+)\/events$/);
    if (events) {
      const run = events[1];
      await store.finish[run]?.promise;
      const terminal = store.terminal[run] ?? "completed";
      if (terminal === "drop") return route.abort("connectionreset");
      if (terminal === "completed") {
        store.threads[store.runs[run] ?? A]?.messages.push({ id: `${run}-bot`, actor: "bot", text: "Mình nghe bạn đây.", cards: [] });
        const owner = store.threads[store.runs[run] ?? A];
        if (owner) { owner.activeRunId = null; owner.activeRunVersion = null; }
        return route.fulfill({ contentType: "text/event-stream", body: sse([{ type: "final", data: { text: "Mình nghe bạn đây.", cards: [] } }, { type: "completed" }]) }).catch(() => undefined);
      }
      return route.fulfill({ contentType: "text/event-stream", body: sse([{ type: terminal }]) }).catch(() => undefined);
    }
    if (/^\/ai\/runs\/[^/]+\/cancel$/.test(path)) {
      await store.cancel.promise;
      return store.flags.cancel503 ? unavailable() : json({ runId: R, version: 2, status: "ended" });
    }
    const one = path.match(/^\/ai\/conversations\/([^/]+)$/);
    if (one && request.method() === "GET") {
      if (store.flags.transcript503) return unavailable();
      return store.threads[one[1]] ? json(store.threads[one[1]]) : json({ error: { code: "NOT_FOUND", message: "Không có." } }, 404);
    }
    const fixed: Record<string, unknown> = {
      "/session": baseSession,
      "/bots": bots,
      "/ai/preferences": prefs,
      "/ai/conversations": [store.threads[A], store.threads[B]],
      "/social/summary": { pendingIncomingRequests: 0, unreadConnections: 0, activityInvites: 0 },
      "/proposals": [], "/memories": [], "/connections": [], "/connection-requests": [], "/activities/catalog": [],
      "/profiles/published/current": null,
    };
    if (request.method() === "GET" && path in fixed) return json(fixed[path]);
    return json({ error: { code: "NOT_FOUND", message: `Missing synthetic fixture ${path}` } }, 404);
  });
  return store;
}

const field = (page: Page) => page.getByRole("textbox", { name: "Tin nhắn cho Mây" });
const sendButton = (page: Page) => page.getByRole("button", { name: "Gửi tin cho AI", exact: true });
const status = (page: Page) => page.locator(".ai-status [role=status]");
async function openChat(page: Page, id: string | "new" = A) {
  await page.goto(id === "new" ? "/#/assistants/may?new=1" : `/#/assistants/may?conversation=${id}`);
  await expect(field(page)).toBeVisible();
  await expect(page.getByText("Đang mở cuộc trò chuyện…")).toHaveCount(0);
}
const selectChat = (page: Page, id: string) => page.evaluate((target) => { location.hash = `#/assistants/may?conversation=${target}`; }, id);
async function submit(page: Page, text: string) {
  await field(page).fill(text);
  await sendButton(page).click();
}
const infoButton = (page: Page) => page.getByRole("button", { name: "Thông tin cuộc trò chuyện", exact: true });
async function requestNew(page: Page) {
  if ((await infoButton(page).getAttribute("aria-expanded")) !== "true") await infoButton(page).click();
  await page.getByRole("button", { name: "Cuộc trò chuyện mới", exact: true }).click();
}
const confirmNew = (page: Page) => page.getByRole("button", { name: "Dừng và mở mới", exact: true });
const UNCONFIRMED = "Chưa xác nhận được trạng thái. Kiểm tra lại cuộc trò chuyện.";
/** Hold React's scheduler so a router transition is applied only on release. */
async function holdScheduler(page: Page) {
  await page.addInitScript(() => {
    const w = window as any;
    w.__hold = false; w.__held = [];
    const Native = window.MessageChannel;
    window.MessageChannel = function () {
      const channel = new Native();
      let callback: any = null;
      Object.defineProperty(channel.port1, "onmessage", { configurable: true, get: () => callback, set: (value) => {
        callback = value;
        channel.port1.addEventListener("message", (event) => { if (w.__hold) w.__held.push(() => value(event)); else value(event); });
        channel.port1.start();
      } });
      return channel;
    } as unknown as typeof MessageChannel;
    w.__release = () => { w.__hold = false; for (const task of w.__held.splice(0)) task(); };
  });
}

test.describe("draft ownership (MR01-MR03)", () => {
  test.use({ viewport: { width: 1280, height: 900 } });

  test("MR02: an edit made while the message POST is pending survives acceptance", async ({ page }) => {
    const store = await mount(page);
    store.accept = gate();
    await openChat(page);
    await submit(page, "Bản gốc");
    await field(page).fill("Bản mới đang gõ");
    store.accept.open();
    await expect(page.locator(".from-self .chat-bubble")).toHaveText("Bản gốc");
    await expect(page.locator(".from-bot .chat-bubble")).toContainText("Mình nghe bạn đây.");
    await expect(field(page)).toHaveValue("Bản mới đang gõ");
    const posts = store.calls.filter((call) => call.method === "POST" && /\/messages$/.test(call.path));
    expect(posts.map((call) => call.body.text)).toEqual(["Bản gốc"]);
  });

  test("MR02: editing back to the submitted text is still a newer edit", async ({ page }) => {
    const store = await mount(page);
    store.accept = gate();
    await openChat(page);
    await submit(page, "Bản gốc");
    await field(page).fill("Bản khác");
    await field(page).fill("Bản gốc");
    store.accept.open();
    await expect(page.locator(".from-bot .chat-bubble")).toContainText("Mình nghe bạn đây.");
    await expect(field(page)).toHaveValue("Bản gốc");
  });

  test("MR02: an unedited submitted draft is still cleared on acceptance", async ({ page }) => {
    const store = await mount(page);
    await openChat(page);
    await submit(page, "Chỉ gửi một lần");
    await expect(page.locator(".from-bot .chat-bubble")).toContainText("Mình nghe bạn đây.");
    await expect(field(page)).toHaveValue("");
    expect(store.count("POST", /\/messages$/)).toBe(1);
  });

  test("MR02: a rejected POST never overwrites newer edits and a retry reuses the same intent", async ({ page }) => {
    const store = await mount(page);
    store.accept = gate();
    store.flags.message503 = true;
    await openChat(page);
    await submit(page, "Bản gốc");
    await field(page).fill("Bản mới");
    store.accept.open();
    await expect(page.getByRole("alert")).toContainText("Dịch vụ tạm gián đoạn.");
    await expect(field(page)).toHaveValue("Bản mới");
    await field(page).fill("Bản gốc");
    store.flags.message503 = false;
    await sendButton(page).click();
    await expect(page.locator(".from-bot .chat-bubble")).toContainText("Mình nghe bạn đây.");
    const ids = store.calls.filter((call) => call.method === "POST" && /\/messages$/.test(call.path)).map((call) => call.body.clientMessageId);
    expect(ids).toHaveLength(2);
    expect(ids[0]).toBe(ids[1]);
  });

  test("MR02: double submit creates one request", async ({ page }) => {
    const store = await mount(page);
    store.accept = gate();
    await openChat(page);
    await field(page).fill("Một lần thôi");
    await field(page).press("Enter");
    await field(page).press("Enter");
    store.accept.open();
    await expect(page.locator(".from-bot .chat-bubble")).toContainText("Mình nghe bạn đây.");
    expect(store.count("POST", /\/messages$/)).toBe(1);
  });

  test("MR03: a resumed failure in another chat never receives text submitted in the first chat", async ({ page }) => {
    const store = await mount(page);
    store.threads[B] = thread(B, { activeRunId: R2, activeRunVersion: 1 });
    store.finish[R2] = gate();
    store.terminal[R2] = "failed";
    await openChat(page, A);
    await submit(page, "Điều riêng tư của A");
    await expect(page.locator(".from-bot .chat-bubble")).toContainText("Mình nghe bạn đây.");
    await selectChat(page, B);
    await expect(status(page)).toHaveText("Đang trả lời…");
    store.finish[R2].open();
    await expect(page.getByRole("alert")).toBeVisible();
    await expect(field(page)).toHaveValue("");
    await expect(page.getByText("Điều riêng tư của A")).toHaveCount(0);
  });

  test("MR03: a matching terminal failure restores only its own text, and never over a newer edit", async ({ page }) => {
    const store = await mount(page);
    store.terminal[R] = "failed";
    store.finish[R] = gate();
    await openChat(page);
    await submit(page, "Bản của lượt này");
    await expect(status(page)).toHaveText("Đang trả lời…");
    store.finish[R].open();
    await expect(page.getByRole("alert")).toBeVisible();
    await expect(field(page)).toHaveValue("Bản của lượt này");
  });

  test("MR03: a newer edit wins over recovery after a terminal failure", async ({ page }) => {
    const store = await mount(page);
    store.terminal[R] = "failed";
    store.finish[R] = gate();
    await openChat(page);
    await submit(page, "Bản của lượt này");
    await expect(status(page)).toHaveText("Đang trả lời…");
    await field(page).fill("Mình vừa gõ tiếp");
    store.finish[R].open();
    await expect(page.getByRole("alert")).toBeVisible();
    await expect(field(page)).toHaveValue("Mình vừa gõ tiếp");
  });

  test("MR03: recovery text is dropped when the user opens a new chat first", async ({ page }) => {
    const store = await mount(page);
    store.terminal[R] = "failed";
    store.finish[R] = gate();
    await openChat(page);
    await submit(page, "Không được rò sang chat khác");
    await expect(status(page)).toHaveText("Đang trả lời…");
    await selectChat(page, B);
    await expect(page.getByText("Chat B")).toHaveCount(0);
    store.finish[R].open();
    await expect.poll(() => store.count("GET", /\/events$/)).toBe(1);
    await expect(field(page)).toHaveValue("");
  });
});

test.describe("human chat starters and receipts (MR01/MR02)", () => {
  test.use({ viewport: { width: 1280, height: 900 } });
  const posted = gate();
  async function humanRoom(page: Page, hold?: Gate) {
    const writes: string[] = [];
    const bodies: any[] = [];
    page.on("request", (request) => { if (request.method() !== "GET" && request.url().includes("/api/v1/")) writes.push(`${request.method()} ${new URL(request.url()).pathname}`); });
    await app(page, baseSession);
    await page.route("**/api/v1/connections/room-1/messages*", async (route) => {
      if (route.request().method() !== "POST") return route.fallback();
      bodies.push(route.request().postDataJSON());
      await (hold ?? posted).promise;
      const body = route.request().postDataJSON();
      return route.fulfill({ status: 201, json: { id: "m-1", connectionId: "room-1", clientMessageId: body.clientMessageId, sender: "self", text: body.text, seq: "1", acceptedAt: "2026-10-23T08:00:01Z" } });
    });
    await page.goto("/#/chat/room-1");
    const box = page.getByRole("textbox", { name: "Nhắn tin cho người bạn kết nối" });
    await expect(page.locator(".conversation-starters button").first()).toBeVisible();
    return { writes, bodies, box, starter: (index: number) => page.locator(".conversation-starters button").nth(index) };
  }
  test.beforeAll(() => posted.open());

  test("MR01: a starter fills an empty draft and sends nothing", async ({ page }) => {
    const { writes, box, starter } = await humanRoom(page);
    const text = (await starter(0).textContent())!;
    await starter(0).click();
    await expect(box).toHaveValue(text);
    await expect(box).toBeFocused();
    await expect(page.getByText("Đã thêm gợi ý vào ô nhắn.", { exact: true })).toHaveCount(0);
    expect(writes).toEqual([]);
  });

  test("MR01: a starter is inserted at the caret and keeps the existing draft", async ({ page }) => {
    const { writes, box, starter } = await humanRoom(page);
    const text = (await starter(1).textContent())!;
    await box.fill("Xin chào bạn");
    await box.evaluate((element: HTMLTextAreaElement) => element.setSelectionRange(8, 8));
    await starter(1).click();
    await expect(box).toHaveValue(`Xin chào ${text} bạn`);
    await expect(box).toBeFocused();
    expect(await box.evaluate((element: HTMLTextAreaElement) => element.selectionStart)).toBe(`Xin chào ${text}`.length);
    expect(writes).toEqual([]);
  });

  test("MR01: a starter replaces only the selected range", async ({ page }) => {
    const { box, starter } = await humanRoom(page);
    const text = (await starter(1).textContent())!;
    await box.fill("Xin chào XYZ nhé");
    await box.evaluate((element: HTMLTextAreaElement) => element.setSelectionRange(9, 12));
    await starter(1).click();
    await expect(box).toHaveValue(`Xin chào ${text} nhé`);
  });

  test("MR01: an insertion past 500 characters keeps the draft and says so", async ({ page }) => {
    const { writes, box, starter } = await humanRoom(page);
    const long = "a".repeat(480);
    await box.fill(long);
    await starter(0).click();
    await expect(box).toHaveValue(long);
    await expect(page.getByText("Gợi ý này sẽ làm tin nhắn dài hơn 500 ký tự. Hãy rút gọn trước khi thêm.", { exact: true })).toBeVisible();
    expect(writes).toEqual([]);
  });

  test("MR01: the contact-information advisory still guards a draft built from a starter", async ({ page }) => {
    const { bodies, box, starter } = await humanRoom(page);
    await box.fill("Gọi mình số 0912345678");
    await starter(1).click();
    await page.getByRole("button", { name: "Gửi tin nhắn", exact: true }).click();
    await expect(page.getByRole("dialog", { name: "Tin nhắn có vẻ chứa thông tin liên hệ" })).toBeVisible();
    expect(bodies).toEqual([]);
  });

  test("MR02: an edit made while a human-chat POST is pending survives its receipt", async ({ page }) => {
    const hold = gate();
    const { bodies, box } = await humanRoom(page, hold);
    await box.fill("Tin gốc");
    await page.getByRole("button", { name: "Gửi tin nhắn", exact: true }).click();
    await expect.poll(() => bodies.length).toBe(1);
    await box.fill("Tin mới đang gõ");
    hold.open();
    await expect(page.locator(".from-self .chat-bubble")).toHaveText("Tin gốc");
    await expect(box).toHaveValue("Tin mới đang gõ");
    expect(bodies.map((body) => body.text)).toEqual(["Tin gốc"]);
  });

  test("MR02: an unedited human-chat draft is cleared by its receipt", async ({ page }) => {
    const { box } = await humanRoom(page);
    await box.fill("Chỉ gửi một lần");
    await page.getByRole("button", { name: "Gửi tin nhắn", exact: true }).click();
    await expect(page.locator(".from-self .chat-bubble")).toHaveText("Chỉ gửi một lần");
    await expect(box).toHaveValue("");
  });
});

test.describe("New, cancellation and reconciliation races (MR04-MR07)", () => {
  test.use({ viewport: { width: 1280, height: 900 } });

  test("MR04: sending right after New is not aborted by the delayed URL effect", async ({ page }) => {
    await holdScheduler(page);
    const store = await mount(page);
    store.flags.createGate = gate();
    await openChat(page, A);
    await infoButton(page).click();
    await page.evaluate(() => {
      (window as any).__hold = true;
      [...document.querySelectorAll<HTMLButtonElement>(".conversation-info button")].find((button) => button.textContent === "Cuộc trò chuyện mới")!.click();
    });
    await field(page).fill("Gửi ngay sau khi mở mới");
    await field(page).press("Enter");
    await expect(status(page)).toHaveText("Đang gửi tin nhắn…");
    await page.evaluate(() => (window as any).__release());
    store.flags.createGate.open();
    await expect(page.locator(".from-self .chat-bubble")).toHaveText("Gửi ngay sau khi mở mới");
    await expect(page.locator(".from-bot .chat-bubble")).toContainText("Mình nghe bạn đây.");
    expect(store.count("POST", /^\/ai\/conversations$/)).toBe(1);
    expect(store.count("POST", /\/messages$/)).toBe(1);
    await expect(page).toHaveURL(new RegExp(`conversation=${C}`));
    await expect(page.getByRole("alert")).toHaveCount(0);
  });

  test("MR04: a genuine failure after New keeps the draft", async ({ page }) => {
    await holdScheduler(page);
    const store = await mount(page);
    store.flags.message503 = true;
    await openChat(page, A);
    await infoButton(page).click();
    await page.evaluate(() => {
      (window as any).__hold = true;
      [...document.querySelectorAll<HTMLButtonElement>(".conversation-info button")].find((button) => button.textContent === "Cuộc trò chuyện mới")!.click();
    });
    await field(page).fill("Giữ lại khi lỗi thật");
    await field(page).press("Enter");
    await page.evaluate(() => (window as any).__release());
    await expect(page.getByRole("alert")).toContainText("Dịch vụ tạm gián đoạn.");
    await expect(field(page)).toHaveValue("Giữ lại khi lỗi thật");
    expect(store.count("POST", /^\/ai\/conversations$/)).toBe(1);
  });

  test("MR04: a real navigation still aborts the old reader", async ({ page }) => {
    const store = await mount(page);
    store.finish[R] = gate();
    await openChat(page, A);
    await submit(page, "Đang chờ trả lời");
    await expect(status(page)).toHaveText("Đang trả lời…");
    await selectChat(page, B);
    await expect(page.getByText("Đang mở cuộc trò chuyện…")).toHaveCount(0);
    store.finish[R].open();
    await expect(status(page)).toHaveText("");
    await expect(page.locator(".from-bot .chat-bubble")).toHaveCount(0);
  });

  // The complementary order to the first MR04 test: the new thread's canonical URL
  // commits together with the still-held New render, so the view never sees New's URL.
  for (const late of ["completed", "failed"] as const) {
    test(`MR04: a fast canonical first-send URL still lets Back select the previous chat (late ${late})`, async ({ page }) => {
      const pageErrors: string[] = [];
      page.on("pageerror", (error) => pageErrors.push(error.message));
      const failed: string[] = [];
      page.on("requestfailed", (request) => failed.push(new URL(request.url()).pathname));
      const events = `/api/v1/ai/runs/${R}/events`;
      const readerAborts = () => failed.filter((path) => path === events).length;
      let released = false;
      await holdScheduler(page);
      const store = await mount(page, async ({ path, store }) => {
        // Only observes the delayed terminal; the shared fixture still delivers it.
        if (path === `/ai/runs/${R}/events`) { await store.finish[R].promise; released = true; }
      });
      store.threads[A].messages.push({ id: "a-1", actor: "self", text: "Tin nhắn cũ của A" });
      store.finish[R] = gate();
      store.terminal[R] = late;
      const readA = new RegExp(`^/ai/conversations/${A}$`), readC = new RegExp(`^/ai/conversations/${C}$`);
      const text = "Tin riêng của cuộc trò chuyện mới";
      const own = page.locator(".from-self .chat-bubble");
      await openChat(page, A);
      await expect(own).toHaveText(["Tin nhắn cũ của A"]);
      await infoButton(page).click();
      await page.evaluate(() => {
        (window as any).__hold = true;
        [...document.querySelectorAll<HTMLButtonElement>(".conversation-info button")].find((button) => button.textContent === "Cuộc trò chuyện mới")!.click();
      });
      await field(page).fill(text);
      await field(page).press("Enter");
      // Creation and acceptance both finish, and the URL is already canonical, while New's render is held.
      await expect.poll(() => store.count("POST", /\/messages$/)).toBe(1);
      await expect(page).toHaveURL(new RegExp(`conversation=${C}`));
      expect(await page.evaluate(() => (window as any).__held.length)).toBeGreaterThan(0);
      await page.evaluate(() => (window as any).__release());
      await expect(own).toHaveText([text]);
      await expect(status(page)).toHaveText("Đang trả lời…");
      await expect(page).toHaveURL(new RegExp(`conversation=${C}`));
      // Same-view canonicalisation keeps the accepted run's reader.
      expect(store.count("GET", /\/events$/)).toBe(1);
      expect(readerAborts()).toBe(0);

      const readsBeforeBack = store.count("GET", readA);
      await page.goBack();
      await expect(page).toHaveURL(new RegExp(`conversation=${A}`));
      await expect(own).toHaveText(["Tin nhắn cũ của A"]);
      await expect(page.getByText(text)).toHaveCount(0);
      await expect(status(page)).toHaveText("");
      expect(store.count("GET", readA)).toBeGreaterThan(readsBeforeBack);
      await expect.poll(readerAborts).toBe(1);
      const heading = page.locator("[data-route-heading]");
      await expect(heading).toBeFocused();

      // C's delayed terminal arrives only after Back and must not reach A.
      store.finish[R].open();
      await expect.poll(() => released).toBe(true);
      await page.evaluate(() => new Promise((resolve) => requestAnimationFrame(resolve)));
      await expect(own).toHaveText(["Tin nhắn cũ của A"]);
      await expect(page.locator(".from-bot .chat-bubble")).toHaveCount(0);
      await expect(status(page)).toHaveText("");
      await expect(field(page)).toHaveValue("");
      await expect(page.getByRole("alert")).toHaveCount(0);
      await expect(heading).toBeFocused();

      // Forward rebuilds C from its stored transcript; nothing is sent again.
      const readsBeforeForward = store.count("GET", readC);
      await page.goForward();
      await expect(page).toHaveURL(new RegExp(`conversation=${C}`));
      await expect(own).toHaveText([text]);
      if (late === "completed") await expect(page.locator(".from-bot .chat-bubble")).toHaveText(["Mình nghe bạn đây."]);
      else await expect(page.locator(".from-bot .chat-bubble")).toHaveCount(0);
      expect(store.count("GET", readC)).toBeGreaterThan(readsBeforeForward);
      await expect(field(page)).toHaveValue("");
      expect(store.count("POST", /^\/ai\/conversations$/)).toBe(1);
      expect(store.count("POST", /\/messages$/)).toBe(1);
      expect(store.count("GET", /\/events$/)).toBe(1);
      expect(pageErrors).toEqual([]);
    });
  }

  test("MR05: a reply that finishes while the New confirmation is open still permits New", async ({ page }) => {
    const store = await mount(page);
    store.finish[R] = gate();
    await openChat(page, A);
    await submit(page, "Xin chào");
    await expect(status(page)).toHaveText("Đang trả lời…");
    await requestNew(page);
    await expect(page.getByRole("dialog", { name: "Dừng phản hồi và mở cuộc trò chuyện mới?" })).toBeVisible();
    store.finish[R].open();
    await expect(page.locator(".from-bot .chat-bubble")).toContainText("Mình nghe bạn đây.");
    await expect(status(page)).toHaveText("");
    await confirmNew(page).click();
    await expect(page).toHaveURL(/new=/);
    await expect(page.getByText("Câu trả lời vừa hoàn tất trước khi dừng. Đã mở cuộc trò chuyện mới.", { exact: true })).toBeVisible();
    await expect(page.getByRole("link", { name: "Xem cuộc trò chuyện trước" })).toHaveAttribute("href", new RegExp(`conversation=${A}`));
    await expect(page.getByText(UNCONFIRMED)).toHaveCount(0);
    expect(store.count("POST", /\/cancel$/)).toBe(0);
    expect(store.count("POST", /\/messages$/)).toBe(1);
  });

  test("MR05: an unknown outcome keeps the current conversation and its recovery path", async ({ page }) => {
    const store = await mount(page);
    store.finish[R] = gate();
    store.terminal[R] = "drop";
    await openChat(page, A);
    await submit(page, "Xin chào");
    await expect(status(page)).toHaveText("Đang trả lời…");
    await requestNew(page);
    store.finish[R].open();
    await expect(status(page)).toHaveText("");
    await confirmNew(page).click();
    await expect(page.getByText(UNCONFIRMED)).toBeVisible();
    await expect(page).not.toHaveURL(/new=/);
    await expect(page.locator(".from-self .chat-bubble")).toHaveText("Xin chào");
    await expect(page.getByRole("button", { name: "Thử lại" })).toBeVisible();
    expect(store.count("POST", /\/cancel$/)).toBe(0);
  });

  test("MR06: New while an ordinary Stop is pending reuses it: one cancel, one New", async ({ page }) => {
    const store = await mount(page);
    store.finish[R] = gate();
    store.cancel = gate();
    store.terminal[R] = "cancelled";
    await openChat(page, A);
    await submit(page, "Xin chào");
    await expect(status(page)).toHaveText("Đang trả lời…");
    await page.getByRole("button", { name: "Dừng phản hồi", exact: true }).click();
    await expect.poll(() => store.count("POST", /\/cancel$/)).toBe(1);
    const history = await page.evaluate(() => window.history.length);
    await requestNew(page);
    await confirmNew(page).click();
    await expect(page.getByText(UNCONFIRMED)).toHaveCount(0);
    await expect(page).not.toHaveURL(/new=/);
    store.cancel.open();
    store.finish[R].open();
    await expect(page).toHaveURL(/new=/);
    await expect(page.getByText("Đã dừng phản hồi và mở cuộc trò chuyện mới.", { exact: true })).toBeVisible();
    expect(store.count("POST", /\/cancel$/)).toBe(1);
    expect(await page.evaluate(() => window.history.length)).toBe(history + 1);
  });

  test("MR06: a failed cancel keeps the thread and draft, and a later finish does not open New", async ({ page }) => {
    const store = await mount(page);
    store.finish[R] = gate();
    store.cancel = gate();
    store.flags.cancel503 = true;
    await openChat(page, A);
    await submit(page, "Xin chào");
    await expect(status(page)).toHaveText("Đang trả lời…");
    await page.getByRole("button", { name: "Dừng phản hồi", exact: true }).click();
    await expect.poll(() => store.count("POST", /\/cancel$/)).toBe(1);
    await field(page).fill("Bản nháp tiếp theo");
    await requestNew(page);
    await confirmNew(page).click();
    await expect(field(page)).toHaveValue("Bản nháp tiếp theo");
    store.cancel.open();
    await expect(page.getByRole("alert")).toBeVisible();
    await expect(field(page)).toHaveValue("Bản nháp tiếp theo");
    store.finish[R].open();
    await expect(page.locator(".from-bot .chat-bubble")).toContainText("Mình nghe bạn đây.");
    await expect(page).not.toHaveURL(/new=/);
    await expect(field(page)).toHaveValue("Bản nháp tiếp theo");
    expect(store.count("POST", /\/cancel$/)).toBe(1);
  });

  test("MR07: after a cancellation whose refresh fails, Send stays blocked until a retry succeeds", async ({ page }) => {
    const store = await mount(page);
    store.finish[R] = gate();
    store.terminal[R] = "cancelled";
    await openChat(page, A);
    await submit(page, "Xin chào");
    await expect(status(page)).toHaveText("Đang trả lời…");
    await page.getByRole("button", { name: "Dừng phản hồi", exact: true }).click();
    store.flags.transcript503 = true;
    store.finish[R].open();
    await expect(page.getByRole("alert")).toContainText("Dịch vụ tạm gián đoạn.");
    await field(page).fill("Bản nháp mới");
    await expect(sendButton(page)).toBeDisabled();
    await field(page).press("Enter");
    store.flags.transcript503 = false;
    await page.getByRole("button", { name: "Thử lại" }).click();
    await expect(sendButton(page)).toBeEnabled();
    await expect(field(page)).toHaveValue("Bản nháp mới");
    expect(store.count("POST", /\/messages$/)).toBe(1);
  });

  test("MR07: a retry that finds an active run reattaches it without another message POST", async ({ page }) => {
    const store = await mount(page);
    store.finish[R] = gate();
    store.terminal[R] = "cancelled";
    store.finish[R2] = gate();
    await openChat(page, A);
    await submit(page, "Xin chào");
    await expect(status(page)).toHaveText("Đang trả lời…");
    store.flags.transcript503 = true;
    store.finish[R].open();
    await expect(page.getByRole("alert")).toBeVisible();
    store.flags.transcript503 = false;
    store.threads[A].activeRunId = R2;
    store.threads[A].activeRunVersion = 1;
    store.runs[R2] = A;
    await page.getByRole("button", { name: "Thử lại" }).click();
    await expect(status(page)).toHaveText("Đang trả lời…");
    store.finish[R2].open();
    await expect(page.locator(".from-bot .chat-bubble")).toContainText("Mình nghe bạn đây.");
    expect(store.count("POST", /\/messages$/)).toBe(1);
  });
});

test.describe("conversation-scoped notices (MR08)", () => {
  test.use({ viewport: { width: 1280, height: 900 } });

  test("MR08: the starter notice does not follow the user into another chat", async ({ page }) => {
    await mount(page);
    await openChat(page, A);
    await page.getByRole("button", { name: "Hôm nay mình hơi mệt", exact: true }).click();
    await expect(page.getByText("Đã thêm gợi ý vào ô nhắn.", { exact: true })).toHaveCount(0);
    await selectChat(page, B);
    await expect(page.locator("[data-route-heading]")).toBeVisible();
    await expect(page.getByText("Đã thêm gợi ý vào ô nhắn.", { exact: true })).toHaveCount(0);
    await expect(field(page)).toHaveValue("");
  });

  test("MR08: the starter notice is cleared by New", async ({ page }) => {
    await mount(page);
    await openChat(page, A);
    await page.getByRole("button", { name: "Hôm nay mình hơi mệt", exact: true }).click();
    await expect(page.getByText("Đã thêm gợi ý vào ô nhắn.", { exact: true })).toHaveCount(0);
    await requestNew(page);
    await expect(page).toHaveURL(/new=/);
    await expect(page.getByText("Đã thêm gợi ý vào ô nhắn.", { exact: true })).toHaveCount(0);
  });

  test("MR08: the stop-and-new receipt survives its one URL change but not a later selection", async ({ page }) => {
    const store = await mount(page);
    store.finish[R] = gate();
    store.terminal[R] = "cancelled";
    await openChat(page, A);
    await submit(page, "Xin chào");
    await expect(status(page)).toHaveText("Đang trả lời…");
    await requestNew(page);
    await confirmNew(page).click();
    store.finish[R].open();
    await expect(page).toHaveURL(/new=/);
    const receipt = page.getByText("Đã dừng phản hồi và mở cuộc trò chuyện mới.", { exact: true });
    await expect(receipt).toBeVisible();
    await page.waitForTimeout(300);
    await expect(receipt).toBeVisible();
    await selectChat(page, B);
    await expect(page.locator("[data-route-heading]")).toBeVisible();
    await expect(receipt).toHaveCount(0);
  });
});

// ---- Activity invitations (MR09 / MR10) ----
const definitions = [
  { kind: "icebreaker", definitionVersion: "icebreaker-v1", title: "Câu hỏi làm quen", description: "Ba câu hỏi nhẹ nhàng.", estimatedMinutes: 5, rounds: 3 },
  { kind: "coop_quiz", definitionVersion: "coop_quiz-v1", title: "Đố vui đồng đội", description: "Năm câu đố vui.", estimatedMinutes: 7, rounds: 5 },
  { kind: "focus", definitionVersion: "focus-v1", title: "Cùng tập trung", description: "Pomodoro chung.", estimatedMinutes: 30, focusPlans: [[25, 5], [15, 3], [50, 10]], maxCycles: 4 },
];
const invitationFor = (kind: string, options?: { plan?: number[]; cycles?: number }) => ({
  id: "s1", connectionId: "room-1", kind, definitionVersion: `${kind}-v1`, state: "invited", version: 1, role: "inviter",
  createdAt: new Date().toISOString(), expiresAt: new Date(Date.now() + 600_000).toISOString(), serverTime: new Date().toISOString(),
  self: { accepted: true, readyRound: 0, feedbackGiven: false }, peer: { accepted: false, readyRound: 0 },
  progress: { round: 0, totalRounds: kind === "focus" ? null : 3, phase: "invited" }, current: null, history: [],
  ...(kind === "focus" ? { timer: { phase: "focus", cycle: 0, cycles: options?.cycles ?? 1, plan: options?.plan ?? [25, 5], selfPresent: false, peerPresent: false } } : {}),
});

test.describe("activity invitations (MR09/MR10)", () => {
  test.use({ viewport: { width: 1280, height: 900 } });

  /** `outcome` decides the answer to each invite POST; an idempotent server commits once per Idempotency-Key. */
  async function inviteRoom(page: Page, outcome: (attempt: number) => "ok" | "commit-then-503" | "commit-then-abort" | "422", hold?: Gate) {
    const committed = new Map<string, any>();
    const keys: string[] = [];
    let attempts = 0;
    let current: unknown = null;
    await app(page, baseSession);
    await page.route("**/api/v1/**", async (route) => {
      const request = route.request();
      const path = new URL(request.url()).pathname.replace("/api/v1", "");
      if (path === "/activities/catalog") return route.fulfill({ json: definitions });
      if (path === "/connections/room-1/activities/current") return route.fulfill({ json: current });
      if (path === "/connections/room-1/activities" && request.method() === "POST") {
        attempts += 1;
        const key = request.headers()["idempotency-key"];
        keys.push(key);
        await hold?.promise;
        const answer = outcome(attempts);
        if (answer === "422") return route.fulfill({ status: 422, json: { error: { code: "VALIDATION_ERROR", message: "Hoạt động này chưa mở cho hai bạn." } } });
        const body = request.postDataJSON();
        if (!committed.has(key)) committed.set(key, invitationFor(body.kind, body.options));
        if (answer === "commit-then-503") return route.fulfill({ status: 503, json: { error: { code: "UNAVAILABLE", message: "Dịch vụ tạm gián đoạn." } } });
        if (answer === "commit-then-abort") return route.abort("connectionreset");
        current = committed.get(key);
        return route.fulfill({ json: current });
      }
      return route.fallback();
    });
    await page.goto("/#/chat/room-1");
    await page.getByRole("button", { name: "Cùng làm gì đó?", exact: true }).click();
    const dialog = page.getByRole("dialog", { name: "Cùng làm gì đó?" });
    await expect(dialog).toBeVisible();
    return { dialog, committed, keys };
  }
  const inviteButton = (dialog: ReturnType<Page["getByRole"]>, title: string) => dialog.getByRole("button", { name: `Mời tham gia ${title}`, exact: true });

  test("MR09: a committed-but-lost response is reported as unconfirmed, keeps the plan, and the retry creates one invitation", async ({ page }) => {
    const { dialog, committed, keys } = await inviteRoom(page, (attempt) => (attempt === 1 ? "commit-then-503" : "ok"));
    await dialog.getByLabel("Nhịp", { exact: true }).selectOption("15,3");
    await dialog.getByLabel("Số lượt", { exact: true }).selectOption("2");
    await inviteButton(dialog, "Cùng tập trung").click();
    await expect(dialog.getByRole("alert")).toHaveText("Chưa xác nhận được lời mời. Lựa chọn của bạn vẫn được giữ. Bạn hãy thử lại.");
    await expect(dialog.getByText("Chưa gửi được lời mời")).toHaveCount(0);
    await expect(dialog.getByLabel("Nhịp", { exact: true })).toHaveValue("15,3");
    await expect(dialog.getByLabel("Số lượt", { exact: true })).toHaveValue("2");
    await inviteButton(dialog, "Cùng tập trung").click();
    await expect(dialog).toHaveCount(0);
    await expect(page.getByRole("group", { name: "Lời mời Cùng tập trung" })).toContainText("15 phút tập trung / 3 phút nghỉ · 2 lượt");
    expect(keys).toHaveLength(2);
    expect(keys[1]).toBe(keys[0]);
    expect(committed.size).toBe(1);
  });

  test("MR09: a dropped connection is also unconfirmed, not a definite failure", async ({ page }) => {
    const { dialog, committed } = await inviteRoom(page, (attempt) => (attempt === 1 ? "commit-then-abort" : "ok"));
    await inviteButton(dialog, "Câu hỏi làm quen").click();
    await expect(dialog.getByRole("alert")).toContainText("Chưa xác nhận được lời mời.");
    await inviteButton(dialog, "Câu hỏi làm quen").click();
    await expect(dialog).toHaveCount(0);
    expect(committed.size).toBe(1);
  });

  test("MR09: a refusal keeps the server's own explanation", async ({ page }) => {
    const { dialog } = await inviteRoom(page, () => "422");
    await inviteButton(dialog, "Đố vui đồng đội").click();
    await expect(dialog.getByRole("alert")).toHaveText("Hoạt động này chưa mở cho hai bạn.");
    await expect(dialog.getByText("Chưa xác nhận được lời mời")).toHaveCount(0);
  });

  test("MR10: only the invitation being sent says it is sending", async ({ page }) => {
    const hold = gate();
    const { dialog } = await inviteRoom(page, () => "ok", hold);
    await inviteButton(dialog, "Câu hỏi làm quen").click();
    await expect(inviteButton(dialog, "Câu hỏi làm quen")).toHaveText("Đang gửi lời mời…");
    for (const title of ["Đố vui đồng đội", "Cùng tập trung"]) {
      await expect(inviteButton(dialog, title)).toHaveText("Mời tham gia");
      await expect(inviteButton(dialog, title)).toBeDisabled();
    }
    hold.open();
    await expect(dialog).toHaveCount(0);
  });
});

// ---- Info panel ARIA (MR11) ----
test.describe("aria-controls relationships (MR11)", () => {
  const trigger = (page: Page) => page.getByRole("button", { name: "Thông tin cuộc trò chuyện", exact: true });
  const danglingControls = (page: Page) =>
    page.evaluate(() => [...document.querySelectorAll("[aria-controls]")]
      .flatMap((node) => node.getAttribute("aria-controls")!.split(/\s+/).filter((id) => !document.getElementById(id))));

  test("MR11: a closed panel is not referenced, an open one is", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 900 });
    await mount(page);
    await openChat(page, A);
    await expect(trigger(page)).toHaveAttribute("aria-expanded", "false");
    await expect(trigger(page)).not.toHaveAttribute("aria-controls", /.+/);
    expect(await danglingControls(page)).toEqual([]);
    await trigger(page).click();
    await expect(trigger(page)).toHaveAttribute("aria-expanded", "true");
    const id = await trigger(page).getAttribute("aria-controls");
    expect(id).toBeTruthy();
    await expect(page.locator(`[id="${id}"]`)).toBeVisible();
    expect(await danglingControls(page)).toEqual([]);
  });

  test("MR11: on a phone the sheet is referenced while open and not once a child dialog replaces it", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await mount(page);
    await openChat(page, A);
    await trigger(page).click();
    const id = await trigger(page).getAttribute("aria-controls");
    await expect(page.locator(`dialog[id="${id}"]`)).toBeVisible();
    await page.getByRole("dialog", { name: "Thông tin cuộc trò chuyện" }).getByRole("button", { name: "Đổi tên", exact: true }).click();
    await expect(page.getByRole("dialog", { name: "Đổi tên cuộc trò chuyện" })).toBeVisible();
    await expect(trigger(page)).not.toHaveAttribute("aria-controls", /.+/);
    expect(await danglingControls(page)).toEqual([]);
  });

  test("MR11: narrowing while a child dialog is open suspends the panel without leaving a dangling reference", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 900 });
    await mount(page);
    await openChat(page, A);
    await trigger(page).click();
    await page.getByRole("region", { name: "Thông tin cuộc trò chuyện" }).getByRole("button", { name: "Đổi tên", exact: true }).click();
    const field = page.getByRole("dialog", { name: "Đổi tên cuộc trò chuyện" }).getByRole("textbox", { name: "Tên cuộc trò chuyện" });
    await expect(field).toBeVisible();
    await expect(field).toBeFocused();
    await expect(trigger(page)).toHaveAttribute("aria-controls", /.+/);
    expect(await danglingControls(page)).toEqual([]);
    await page.setViewportSize({ width: 900, height: 900 });
    await expect(trigger(page)).not.toHaveAttribute("aria-controls", /.+/);
    await expect(trigger(page)).toHaveAttribute("aria-expanded", "true");
    await expect(field).toBeFocused();
    expect(await danglingControls(page)).toEqual([]);
    await page.setViewportSize({ width: 1280, height: 900 });
    await expect(trigger(page)).toHaveAttribute("aria-controls", /.+/);
    expect(await danglingControls(page)).toEqual([]);
  });

  test("MR11: Escape still closes the open panel and returns focus to its trigger", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 900 });
    await mount(page);
    await openChat(page, A);
    await trigger(page).click();
    await page.keyboard.press("Escape");
    await expect(trigger(page)).toHaveAttribute("aria-expanded", "false");
    await expect(trigger(page)).toBeFocused();
    await expect(trigger(page)).not.toHaveAttribute("aria-controls", /.+/);
  });

  test("MR11: every tab in the discovery tablist points at a panel that exists", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 900 });
    await app(page, baseSession);
    await page.goto("/#/connect");
    await expect(page.getByRole("tablist", { name: "Tìm bạn" })).toBeVisible();
    expect(await danglingControls(page)).toEqual([]);
    const tabs = page.getByRole("tab");
    const count = await tabs.count();
    expect(count).toBeGreaterThan(1);
    for (let index = 0; index < count; index += 1) {
      await tabs.nth(index).click();
      await expect(tabs.nth(index)).toHaveAttribute("aria-selected", "true");
      expect(await danglingControls(page)).toEqual([]);
    }
  });
});
