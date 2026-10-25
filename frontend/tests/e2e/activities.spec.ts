import { expect, test, type Page } from "@playwright/test";

const session = {
  userId: "11111111-1111-4111-8111-111111111111",
  alias: "An",
  ageBand: "adult",
  eligible: true,
  csrfToken: "test-csrf",
  serverTime: "2026-10-23T08:00:00Z",
  timezone: "Asia/Bangkok",
  features: { ai: false, matching: true, voice: false },
  consents: Object.fromEntries(
    ["AI", "MEM", "MATCH", "VOICE"].map((p) => [
      p,
      { enabled: p === "MATCH", version: 1, policyVersion: "v1" },
    ]),
  ),
};
const room = {
  id: "room-1",
  alias: "Bạn đồng hành 3fa9c1",
  status: "open",
  version: 1,
  highWaterSeq: "0",
  unreadCount: 0,
};
const catalog = [
  { kind: "icebreaker", definitionVersion: "icebreaker-v1", title: "Câu hỏi làm quen", description: "Ba câu hỏi nhẹ nhàng.", estimatedMinutes: 5, rounds: 3 },
  { kind: "coop_quiz", definitionVersion: "coop_quiz-v1", title: "Đố vui đồng đội", description: "Năm câu đố vui.", estimatedMinutes: 7, rounds: 5 },
  { kind: "focus", definitionVersion: "focus-v1", title: "Cùng tập trung", description: "Pomodoro chung.", estimatedMinutes: 30, focusPlans: [[25, 5], [15, 3], [50, 10]], maxCycles: 4 },
];
const item = { id: "ib-l01", prompt: "Buổi sáng lý tưởng của bạn bắt đầu bằng gì?", options: ["Một ly cà phê", "Đi bộ một vòng", "Ngủ thêm chút nữa"], allowText: true };

function base(patch: Record<string, unknown> = {}): any {
  return {
    id: "s1",
    connectionId: "room-1",
    kind: "icebreaker",
    definitionVersion: "icebreaker-v1",
    state: "invited",
    version: 1,
    role: "invitee",
    createdAt: new Date().toISOString(),
    expiresAt: new Date(Date.now() + 600_000).toISOString(),
    serverTime: new Date().toISOString(),
    self: { accepted: false, readyRound: 0, feedbackGiven: false },
    peer: { accepted: true, readyRound: 0 },
    progress: { round: 0, totalRounds: 3, phase: "invited" },
    current: null,
    history: [],
    ...patch,
  };
}

type ChatState = {
  current: unknown;
  posts: { path: string; body: unknown }[];
  reply?: (path: string, body: any) => { status?: number; json: unknown } | undefined;
  messages?: { id: string; seq: string; sender: "self" | "peer"; text: string; acceptedAt: string }[];
  history?: unknown[];
};

async function chat(page: Page, state: ChatState) {
  await page.route("**/api/v1/**", async (route) => {
    const request = route.request(),
      path = new URL(request.url()).pathname.replace("/api/v1", "");
    if (path === "/session") return route.fulfill({ json: session });
    if (path === "/social/summary")
      return route.fulfill({ json: { pendingIncomingRequests: 0, unreadConnections: 0, activityInvites: 0 } });
    if (path === "/connections/room-1") return route.fulfill({ json: room });
    if (path === "/connections/room-1/messages" && request.method() === "GET") {
      const after = BigInt(new URL(request.url()).searchParams.get("afterSeq") ?? "0");
      const all = (state.messages ?? []).map((m) => ({ connectionId: "room-1", clientMessageId: m.id, ...m }));
      return route.fulfill({
        json: { messages: all.filter((m) => BigInt(m.seq) > after), highWaterSeq: all.at(-1)?.seq ?? "0" },
      });
    }
    if (path === "/connections/room-1/activities" && request.method() === "GET")
      return route.fulfill({ json: state.history ?? [] });
    if (path.endsWith("/reveal-requests")) return route.fulfill({ json: [] });
    if (path === "/activities/catalog") return route.fulfill({ json: catalog });
    if (path === "/connections/room-1/activities/current")
      return route.fulfill({ json: state.current });
    if (request.method() === "POST") {
      const body = request.postDataJSON();
      state.posts.push({ path, body });
      const answer = state.reply?.(path, body);
      if (answer) return route.fulfill({ status: answer.status ?? 200, json: answer.json });
    }
    return route.fulfill({ status: 404, json: { error: { code: "NOT_FOUND", message: "Missing" } } });
  });
}

test("an invitee accepts, answers, waits, then sees both answers revealed", async ({ page }) => {
  const state: any = { current: base(), posts: [] };
  const active = base({
    state: "active",
    version: 2,
    self: { accepted: true, readyRound: 0, feedbackGiven: false },
    progress: { round: 1, totalRounds: 3, phase: "answering" },
    current: { item, peerSubmitted: false },
  });
  state.reply = (path: string, body: any) => {
    if (path.endsWith("/accept")) {
      expect(body).toEqual({ expectedVersion: 1 });
      state.current = active;
      return { json: active };
    }
    if (path.endsWith("/responses")) {
      expect(body).toMatchObject({ round: 1, choice: 0, expectedVersion: 2 });
      state.current = { ...active, version: 3, current: { item, peerSubmitted: false, selfResponse: { choice: 0, skipped: false } } };
      return { json: state.current };
    }
  };
  await chat(page, state);
  await page.goto("/#/chat/room-1");
  const invite = page.getByRole("group", { name: "Lời mời Câu hỏi làm quen" });
  await expect(invite).toContainText("Bạn đồng hành 3fa9c1 mời bạn chơi Câu hỏi làm quen (khoảng 5 phút)");
  await invite.getByRole("button", { name: "Đồng ý" }).click();
  const dock = page.getByRole("region", { name: "Hoạt động chung: Câu hỏi làm quen" });
  await expect(dock.getByRole("heading", { name: item.prompt })).toBeVisible();
  await dock.getByRole("radio", { name: "Một ly cà phê" }).check();
  await dock.getByRole("textbox", { name: /Hoặc viết vài chữ/ }).fill("cà phê sữa");
  await dock.getByRole("textbox", { name: /Hoặc viết vài chữ/ }).fill("");
  await dock.getByRole("button", { name: "Gửi câu trả lời" }).click();
  await expect(dock.getByRole("status")).toHaveText("Đang chờ Bạn đồng hành 3fa9c1 trả lời…");
  state.current = {
    ...active,
    version: 4,
    progress: { round: 1, totalRounds: 3, phase: "revealed" },
    current: { item, peerSubmitted: true, selfResponse: { choice: 0, skipped: false }, reveal: { self: { choice: 0, skipped: false }, peer: { choice: 1, text: "đi dạo", skipped: false } } },
  };
  await expect(dock.getByText("Đi bộ một vòng · đi dạo")).toBeVisible({ timeout: 10_000 });
  await expect(dock.getByRole("button", { name: "Câu tiếp theo" })).toBeVisible();
});

test("a skipper sees the reciprocal-hidden message", async ({ page }) => {
  const revealed = base({
    state: "active",
    role: "inviter",
    self: { accepted: true, readyRound: 0, feedbackGiven: false },
    progress: { round: 2, totalRounds: 3, phase: "revealed" },
    current: { item, peerSubmitted: true, selfResponse: { skipped: true }, reveal: { self: { skipped: true }, peer: "hidden" } },
  });
  await chat(page, { current: revealed, posts: [] });
  await page.goto("/#/chat/room-1");
  await expect(page.getByText("Bạn đã bỏ qua câu này — câu trả lời của bạn kia được giữ kín.")).toBeVisible();
  await expect(page.getByText("Đã bỏ qua", { exact: true })).toBeVisible();
});

test("quiz reveal marks the correct answer and choices with text, not colour alone", async ({ page }) => {
  const quiz = base({
    kind: "coop_quiz",
    state: "active",
    self: { accepted: true, readyRound: 0, feedbackGiven: false },
    progress: { round: 2, totalRounds: 5, phase: "revealed" },
    score: { team: 4, max: 15, rounds: [3, 1] },
    current: {
      item: { id: "q1", prompt: "Hành tinh nào gần Mặt Trời nhất?", options: ["Sao Kim", "Sao Thủy", "Trái Đất", "Sao Hỏa"], allowText: false },
      peerSubmitted: true,
      selfResponse: { choice: 1, skipped: false },
      reveal: { self: { choice: 1, skipped: false }, peer: { choice: 0, skipped: false }, correctIndex: 1, explanation: "Sao Thủy gần nhất.", points: 1 },
    },
  });
  await chat(page, { current: quiz, posts: [] });
  await page.goto("/#/chat/room-1");
  const dock = page.getByRole("region", { name: "Hoạt động chung: Đố vui đồng đội" });
  await expect(dock.getByText("Vòng 2/5 · Đội: 4 điểm")).toBeVisible();
  const right = dock.getByRole("listitem").filter({ hasText: "Sao Thủy" });
  await expect(right.getByText("Đáp án đúng")).toBeVisible();
  await expect(right.getByText("Bạn chọn")).toBeVisible();
  await expect(dock.getByRole("listitem").filter({ hasText: "Sao Kim" }).getByText("Bạn đồng hành 3fa9c1 chọn")).toBeVisible();
  await expect(dock.getByText("+1", { exact: true })).toBeVisible();
});

test("focus countdown follows server time, not the device clock", async ({ page }) => {
  const serverNow = Date.now() + 30_000; // server is 30 s ahead of this browser
  const focus = base({
    kind: "focus",
    state: "active",
    serverTime: new Date(serverNow).toISOString(),
    self: { accepted: true, readyRound: 0, feedbackGiven: false, joined: true },
    progress: { round: 1, totalRounds: null, phase: "focus" },
    timer: { phase: "focus", cycle: 1, cycles: 1, plan: [25, 5], phaseEndsAt: new Date(serverNow + 600_000).toISOString(), selfPresent: true, peerPresent: true },
  });
  const state: any = { current: focus, posts: [] };
  state.reply = (path: string) => {
    if (path.endsWith("/focus/pause")) {
      state.current = { ...focus, state: "paused", version: 2, timer: { ...focus.timer, phaseEndsAt: null, pausedRemainingSec: 590, pausedBySelf: true } };
      return { json: state.current };
    }
  };
  await chat(page, state);
  await page.goto("/#/chat/room-1");
  const dock = page.getByRole("region", { name: "Hoạt động chung: Cùng tập trung" });
  await expect(dock.locator(".focus-countdown")).toHaveText(/^(10:00|09:5\d)$/);
  await dock.getByRole("button", { name: "Tạm dừng" }).click();
  await expect(dock.getByText("Bạn đã tạm dừng")).toBeVisible();
  await expect(dock.getByRole("button", { name: "Tiếp tục" })).toBeVisible();
  await expect(dock.locator(".focus-countdown")).toHaveText("09:50");
});

test("a decline cooldown disables only that invitation kind", async ({ page }) => {
  const state: any = { current: null, posts: [] };
  state.reply = (path: string) => {
    if (path === "/connections/room-1/activities")
      return { status: 429, json: { error: { code: "ACTIVITY_COOLDOWN", message: "Bạn kia chưa muốn chơi hoạt động này lúc này. Hãy thử lại sau.", retryable: true } } };
  };
  await chat(page, state);
  await page.goto("/#/chat/room-1");
  await page.getByRole("button", { name: "Cùng làm gì đó?" }).click();
  const invite = page.getByRole("button", { name: "Mời cùng chơi Câu hỏi làm quen" });
  await invite.click();
  await expect(invite).toBeDisabled();
  await expect(page.getByRole("button", { name: "Mời cùng chơi Đố vui đồng đội" })).toBeEnabled();
});

test("contact details in a message prompt a non-blocking advisory", async ({ page }) => {
  const state: any = { current: null, posts: [] };
  state.reply = (path: string, body: any) => {
    if (path === "/connections/room-1/messages")
      return {
        status: 201,
        json: { id: "m1", connectionId: "room-1", clientMessageId: body.clientMessageId, sender: "self", text: body.text, seq: "1", acceptedAt: new Date().toISOString() },
      };
  };
  await chat(page, state);
  await page.goto("/#/chat/room-1");
  const composer = page.getByRole("textbox", { name: "Tin nhắn cho bạn kết nối" });
  await composer.fill("số mình 0912 345 678");
  await page.getByRole("button", { name: "Gửi tin nhắn" }).click();
  const dialog = page.getByRole("dialog", { name: "Tin nhắn có vẻ chứa thông tin liên hệ" });
  await dialog.getByRole("button", { name: "Sửa lại" }).click();
  await expect(composer).toHaveValue("số mình 0912 345 678");
  expect(state.posts.filter((p: any) => p.path.endsWith("/messages"))).toHaveLength(0);
  await page.getByRole("button", { name: "Gửi tin nhắn" }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Vẫn gửi" }).click();
  await expect.poll(() => state.posts.filter((p: any) => p.path.endsWith("/messages")).length).toBe(1);
});

const running = () =>
  base({
    state: "active",
    version: 2,
    self: { accepted: true, readyRound: 0, feedbackGiven: false },
    progress: { round: 1, totalRounds: 3, phase: "answering" },
    current: { item, peerSubmitted: false },
  });

test("on a phone the dock is a sheet above the composer that collapses and keeps the draft", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await chat(page, { current: running(), posts: [] });
  await page.goto("/#/chat/room-1");
  const dock = page.getByRole("region", { name: "Hoạt động chung: Câu hỏi làm quen" });
  await expect(dock.getByRole("heading", { name: item.prompt })).toBeVisible();
  const composer = page.getByRole("textbox", { name: "Tin nhắn cho bạn kết nối" });
  await composer.fill("chờ chút nhé");
  const [sheet, input] = [await dock.boundingBox(), await composer.boundingBox()];
  expect(sheet!.y + sheet!.height).toBeLessThanOrEqual(input!.y + 1);
  expect(sheet!.height).toBeLessThanOrEqual(844 * 0.6 + 1);
  // Escape collapses the sheet and returns focus to its toggle.
  await dock.getByRole("radio", { name: "Một ly cà phê" }).focus();
  await page.keyboard.press("Escape");
  const toggle = dock.getByRole("button", { name: "Mở hoạt động" });
  await expect(toggle).toBeFocused();
  await expect(toggle).toHaveAttribute("aria-expanded", "false");
  expect((await dock.boundingBox())!.height).toBeLessThanOrEqual(57);
  await expect(dock.getByRole("heading", { name: item.prompt })).toHaveCount(0);
  await expect(composer).toBeVisible();
  await expect(composer).toHaveValue("chờ chút nhé");
  await toggle.click();
  await expect(dock.getByRole("heading", { name: item.prompt })).toBeVisible();
  await expect(dock.getByRole("button", { name: "Thu gọn hoạt động" })).toHaveAttribute("aria-expanded", "true");
});

test("on a desktop the dock is a side panel next to the log", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  await chat(page, { current: running(), posts: [] });
  await page.goto("/#/chat/room-1");
  const dock = page.getByRole("region", { name: "Hoạt động chung: Câu hỏi làm quen" });
  await expect(dock.getByRole("heading", { name: item.prompt })).toBeVisible();
  const [panel, log] = [await dock.boundingBox(), await page.getByRole("log").boundingBox()];
  expect(panel!.x).toBeGreaterThanOrEqual(log!.x + log!.width);
  expect(panel!.width).toBeLessThanOrEqual(381);
  await expect(page.getByRole("textbox", { name: "Tin nhắn cho bạn kết nối" })).toBeVisible();
});

test("finished activities appear in the log where they ended", async ({ page }) => {
  const at = (minute: number) => `2026-10-23T08:${String(minute).padStart(2, "0")}:00Z`;
  await chat(page, {
    current: null,
    posts: [],
    messages: [
      { id: "m1", seq: "1", sender: "peer", text: "Chào bạn", acceptedAt: at(0) },
      { id: "m2", seq: "2", sender: "self", text: "Vui ghê", acceptedAt: at(20) },
    ],
    history: [
      base({ id: "h2", kind: "coop_quiz", state: "declined", endReason: "invite_declined", role: "inviter", createdAt: at(25), endedAt: at(30) }),
      base({ id: "h1", state: "completed", endReason: "completed", createdAt: at(1), endedAt: at(10) }),
    ],
  });
  await page.goto("/#/chat/room-1");
  const log = page.getByRole("log", { name: "Tin nhắn trong kết nối" });
  await expect(log.getByRole("group", { name: "Hoạt động đã qua: Đố vui đồng đội" })).toBeVisible();
  const order = (await log.locator(":scope > *").allInnerTexts()).map((text) => text.trim());
  expect(order).toEqual([
    "Chào bạn",
    "Câu hỏi làm quen: hai bạn đã hoàn thành.",
    "Vui ghê",
    "Đố vui đồng đội: Bạn đồng hành 3fa9c1 chưa muốn chơi lúc này",
  ]);
});
