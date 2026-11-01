import { expect, test, type BrowserContext, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { api, call, noHorizontalOverflow, origin, session, userId } from "./helpers";

// V3 against the real backend (tests.e2e_server: three agents, smart orchestration and groups on
// for the users 60-69 cohort only) and the synthetic SDK model, which plays every V3 role
// deterministically (planner, as_tool specialists, handoff target, group selector and speakers).
test.skip(process.env.E2E_V3 === "0" || process.env.E2E_MULTI_MESSAGE === "0", "V3 is off for this run");
const ASK = "Giúp mình xem lại những điều mình đã ghi trong tuần rồi lên vài hoạt động nhẹ nhàng cho cuối tuần.";
const TRANSFER = "Mình muốn nói chuyện trực tiếp với Nhật ký để nhìn lại cảm xúc tuần này.";
const today = () => new Date().toISOString().slice(0, 10);

async function open(context: BrowserContext, user: number, width = 1440) {
  await session(context, user);
  const page = await context.newPage();
  await page.setViewportSize({ width, height: width < 500 ? 844 : 960 });
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("console", (message) => { if (message.type() === "error") errors.push(message.text()); });
  return { page, errors };
}

async function prepare(context: BrowserContext, user: number, edges: string[]) {
  expect((await call(context, user, "PUT", "/consents/AI", { enabled: true, expectedVersion: 1, policyVersion: "v1" })).status).toBe(200);
  expect((await call(context, user, "PUT", "/ai/preferences", { historyEnabled: true, semanticMemoryEnabled: false, expectedVersion: 1, policyVersion: "ai-data-v1" })).status).toBe(200);
  const proactive = await call(context, user, "GET", "/ai/proactive");
  expect((await call(context, user, "PUT", "/ai/proactive/settings", { timezone: "Asia/Ho_Chi_Minh", quietStart: "22:00", quietEnd: "07:00", badgesEnabled: true, journalContextEnabled: true, expectedVersion: proactive.body.settings.version, policyVersion: "proactive-v1" })).status).toBe(200);
  for (const edge of edges) {
    const view = await call(context, user, "GET", "/ai/sharing");
    const version = view.body.edges.find((item: { edge: string }) => item.edge === edge).version;
    expect((await call(context, user, "PUT", `/ai/sharing/${edge}`, { enabled: true, expectedVersion: version, policyVersion: "sharing-v1" })).status).toBe(200);
  }
}

async function controls(page: Page, body: Record<string, unknown>) {
  expect((await page.request.post(`${origin}/__test/v3`, { data: body })).ok()).toBe(true);
}

async function sendDirect(page: Page, bot: string, botName: string, text: string) {
  await page.goto(`/#/assistants/${bot}`);
  await page.getByRole("textbox", { name: `Tin nhắn cho ${botName}`, exact: true }).fill(text);
  await page.getByRole("button", { name: "Gửi tin cho AI", exact: true }).click();
}

test("V3-A: exactly three agents, legacy history readable and read-only", async ({ browser }) => {
  const context = await browser.newContext({ baseURL: origin });
  const { page, errors } = await open(context, 60);
  await prepare(context, 60, []);
  await page.goto("/#/assistants");
  const roster = page.locator(".bot-list .bot-row");
  await expect(roster).toHaveCount(3);
  await expect(roster.nth(0)).toContainText("Điều phối");
  await expect(roster.nth(1)).toContainText("Nhật ký");
  await expect(roster.nth(2)).toContainText("Hoạt động");
  await expect(page.locator(".history-legacy")).toContainText("Cuộc trò chuyện cũ");
  await page.getByRole("link", { name: /Chuyện cũ với Mây/ }).click();
  await expect(page.getByText("Mây nghe bạn nè.")).toBeVisible();
  await expect(page.locator(".chat-readonly[data-legacy]")).toContainText("Đây là cuộc trò chuyện cũ với Mây");
  await expect(page.getByRole("link", { name: "Trò chuyện với Điều phối" })).toBeVisible();
  await expect(page.getByRole("textbox", { name: "Tin nhắn cho Mây" })).toHaveCount(0);
  // Each agent has its own conversation.
  await sendDirect(page, "hoatdong", "Hoạt động", "Chào bạn");
  await expect(page.getByText("Hoạt động đây, mình gợi ý một việc nhỏ nhé.")).toBeVisible();
  await noHorizontalOverflow(page);
  expect(errors).toEqual([]);
  await context.close();
});

test("V3-B: Điều phối answers directly, then consults both specialists through as_tool", async ({ browser }) => {
  const context = await browser.newContext({ baseURL: origin });
  const { page, errors } = await open(context, 61);
  await prepare(context, 61, ["dieuphoi_consult_nhatky", "dieuphoi_consult_hoatdong"]);
  await controls(page, { journal: userId(61), day: today(), delay: 1.2 });

  await sendDirect(page, "dieuphoi", "Điều phối", "Chào Điều phối");
  await expect(page.getByText("Điều phối đây, mình nghe bạn nè.")).toBeVisible();
  await expect(page.locator(".agent-steps-line")).toHaveCount(0);

  await page.getByRole("textbox", { name: "Tin nhắn cho Điều phối", exact: true }).fill(ASK);
  await page.getByRole("button", { name: "Gửi tin cho AI", exact: true }).click();
  // Real progress from receipts: the consultation is named only while it is reported.
  await expect(page.locator(".ai-status [role=status]")).toHaveText(/Điều phối đang hỏi (Nhật ký|Hoạt động) một chút…/, { timeout: 15000 });
  await expect(page.locator(".agent-steps-line")).toHaveText(/Điều phối đã hỏi ý (Nhật ký và Hoạt động|Hoạt động và Nhật ký) để trả lời bạn\./, { timeout: 20000 });
  await expect(page.getByText(/V3-E2E Tuần rồi bạn hay mệt/)).toBeVisible();
  await page.reload();
  await expect(page.locator(".agent-steps-line")).toHaveText(/Nhật ký và Hoạt động|Hoạt động và Nhật ký/);
  const conversationId = new URL(page.url().replace("/#", "")).searchParams.get("conversation");
  const thread = await (await page.request.get(`${api}/ai/conversations/${conversationId}`)).json();
  const reply = thread.messages.filter((m: { actor: string }) => m.actor === "bot").at(-2);
  // Both ran in parallel; the receipts keep the real order in which they started.
  expect([...reply.steps].sort((a: { companion: string }, b: { companion: string }) => a.companion.localeCompare(b.companion)))
    .toEqual([{ kind: "consult", companion: "hoatdong" }, { kind: "consult", companion: "nhatky" }]);
  const events = await (await page.request.get(`${api}/ai/runs/${reply.runId}/events?protocol=2`)).text();
  expect(events.match(/"activity":"consulting"/g)).toHaveLength(2);
  expect(errors).toEqual([]);
  await context.close();
});

test("V3-C: a permitted handoff changes the speaker; the user returns; a denied one is blocked", async ({ browser }) => {
  const context = await browser.newContext({ baseURL: origin });
  const { page, errors } = await open(context, 62);
  await prepare(context, 62, ["dieuphoi_handoff_nhatky"]);
  await controls(page, { delay: 1.2 });
  await sendDirect(page, "dieuphoi", "Điều phối", TRANSFER);
  await expect(page.locator(".ai-status [role=status]")).toHaveText("Điều phối đang mời Nhật ký trò chuyện cùng bạn…", { timeout: 15000 });
  const answer = page.getByRole("group", { name: /Tin nhắn từ Nhật ký/ });
  await expect(answer.getByText(/V3-E2E Chào bạn, mình là Nhật ký/)).toBeVisible({ timeout: 20000 });
  await expect(page.locator(".speaker-tag")).toContainText("Nhật ký");
  await expect(page.locator(".handoff-banner")).toContainText("Bạn đang trò chuyện trực tiếp với Nhật ký");
  // Continue with Nhật ký, then return to Điều phối.
  await page.getByRole("textbox", { name: "Tin nhắn cho Điều phối", exact: true }).fill("Chắc là chuyện thi cử");
  await page.getByRole("button", { name: "Gửi tin cho AI", exact: true }).click();
  await expect(page.getByText("Mình vẫn ở đây cùng bạn nhìn lại nhé.")).toBeVisible({ timeout: 20000 });
  await page.getByRole("button", { name: "Quay lại Điều phối" }).click();
  await expect(page.locator(".handoff-banner")).toHaveCount(0);
  await expect(page.getByRole("textbox", { name: "Tin nhắn cho Điều phối", exact: true })).toBeFocused();

  // Denied: the Hoạt động handoff edge is off, so Điều phối answers itself (no transfer at all).
  await page.getByRole("textbox", { name: "Tin nhắn cho Điều phối", exact: true }).fill("Mình muốn nói chuyện trực tiếp với Hoạt động");
  await page.getByRole("button", { name: "Gửi tin cho AI", exact: true }).click();
  await expect(page.getByText("Điều phối đây, mình nghe bạn nè.").last()).toBeVisible({ timeout: 20000 });
  await expect(page.locator(".handoff-banner")).toHaveCount(0);
  expect(errors).toEqual([]);
  await context.close();
});

test("V3-D: groups — create, mentions, everyone, automatic speakers, reload, removal, a11y", async ({ browser }) => {
  const context = await browser.newContext({ baseURL: origin });
  const { page, errors } = await open(context, 63);
  await prepare(context, 63, []);
  await controls(page, { delay: 0.6 });
  await page.goto("/#/assistants");
  await page.getByRole("link", { name: "Tạo nhóm" }).click();
  await page.getByLabel("Tên nhóm").fill("Kế hoạch cuối tuần");
  await page.getByRole("checkbox", { name: /Điều phối/ }).uncheck();
  await page.getByRole("checkbox", { name: /Nhật ký/ }).uncheck();
  await page.getByRole("button", { name: "Tạo nhóm" }).click();
  await expect(page.getByRole("alert")).toHaveText("Hãy chọn ít nhất hai trợ lý.");
  await page.getByRole("checkbox", { name: /Điều phối/ }).check();
  await page.getByRole("checkbox", { name: /Nhật ký/ }).check();
  await page.getByRole("button", { name: "Tạo nhóm" }).click();
  const composer = page.getByRole("textbox", { name: "Tin nhắn cho nhóm Kế hoạch cuối tuần" });
  await expect(composer).toBeVisible();

  // @Nhật ký through the keyboard picker: only that member answers.
  await composer.pressSequentially("@nh");
  await expect(page.getByRole("option", { name: "Nhật ký" })).toBeVisible();
  await composer.press("Enter");
  await composer.pressSequentially("tuần này mình thế nào?");
  await expect(composer).toHaveValue("@Nhật ký tuần này mình thế nào?");
  await composer.press("Enter");
  await expect(page.getByRole("group", { name: "Tin nhắn từ Nhật ký" })).toHaveCount(1, { timeout: 20000 });
  await expect(page.locator(".group-turn")).toHaveCount(1);

  // @Hoạt động targets that member.
  await composer.fill("@Hoạt động có gợi ý gì không?");
  await composer.press("Enter");
  await expect(page.getByRole("group", { name: "Tin nhắn từ Hoạt động" })).toHaveCount(1, { timeout: 20000 });

  // @mọi người: every member, in order, as distinct speakers; the typing line names the speaker.
  await composer.fill("@mọi người giúp mình lên kế hoạch cuối tuần nhé");
  await composer.press("Enter");
  await expect(page.locator(".group-typing")).toContainText(/đang trả lời/, { timeout: 10000 });
  await expect(page.locator(".group-turn")).toHaveCount(5, { timeout: 30000 });
  await expect(page.locator(".group-turn .group-speaker strong")).toHaveText(["Nhật ký", "Hoạt động", "Nhật ký", "Hoạt động", "Điều phối"]);

  // No mention: the selector chooses (synthetic: Hoạt động then Điều phối gathers).
  await composer.fill("Tối nay mình nên làm gì cho vui?");
  await composer.press("Enter");
  await expect(page.locator(".group-turn")).toHaveCount(7, { timeout: 30000 });

  // Reload: same history, no duplicates.
  await page.reload();
  await expect(page.locator(".group-turn")).toHaveCount(7);
  const groupId = page.url().split("/groups/")[1];
  const view = await (await page.request.get(`${api}/ai/groups/${groupId}`)).json();
  const ids = view.messages.map((m: { id: string }) => m.id);
  expect(new Set(ids).size).toBe(ids.length);

  // Remove Hoạt động: it never speaks again, its old messages keep their name.
  await page.getByRole("button", { name: "Thông tin nhóm" }).click();
  await page.getByRole("button", { name: "Bỏ Hoạt động khỏi nhóm" }).click();
  await expect(page.locator(".group-status")).toHaveText("Đã bỏ Hoạt động khỏi nhóm.");
  expect((await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze()).violations).toEqual([]);
  await page.getByRole("button", { name: "Đóng thông tin nhóm" }).click();
  await expect(page.getByRole("button", { name: "Thông tin nhóm" })).toBeFocused();
  await composer.fill("@mọi người lần nữa nhé");
  await composer.press("Enter");
  await expect(page.locator(".group-turn")).toHaveCount(9, { timeout: 30000 });
  await expect(page.locator(".group-turn .group-speaker strong").last()).toHaveText("Điều phối");
  await expect(page.getByRole("group", { name: "Tin nhắn từ Hoạt động" })).toHaveCount(3);
  await noHorizontalOverflow(page);
  expect(errors).toEqual([]);
  await context.close();
});

for (const [user, width] of [[64, 768], [66, 390], [67, 360]]) {
  test(`V3-E: group chat stays usable at ${width}px`, async ({ browser }) => {
    const context = await browser.newContext({ baseURL: origin });
    const { page, errors } = await open(context, user, width);
    await prepare(context, user, []);
    const created = await call(context, user, "POST", "/ai/groups", { name: `Nhóm ${width}`, members: ["dieuphoi", "nhatky"] });
    expect(created.status).toBe(201);
    await page.goto(`/#/assistants/groups/${created.body.groupId}`);
    const composer = page.getByRole("textbox", { name: `Tin nhắn cho nhóm Nhóm ${width}` });
    await composer.fill("chào cả nhóm");
    await composer.press("Enter");
    await expect(page.getByRole("group", { name: "Tin nhắn từ Điều phối" }).last()).toBeVisible({ timeout: 20000 });
    await noHorizontalOverflow(page);
    const box = await page.locator(".group-composer").boundingBox();
    expect(box && box.x >= 0 && box.x + box.width <= width).toBe(true);
    expect(errors).toEqual([]);
    await context.close();
  });
}

test("V3-F: flags off keep the five Phase 2 companions and hide groups", async ({ browser }) => {
  const context = await browser.newContext({ baseURL: origin });
  const { page, errors } = await open(context, 65);
  await prepare(context, 65, []);
  await controls(page, { ai_three_agent_experience_enabled: false, ai_smart_orchestration_enabled: false, ai_group_chat_enabled: false });
  try {
    await page.goto("/#/assistants");
    await expect(page.locator(".bot-list .bot-row")).toHaveCount(5);
    await expect(page.locator(".group-roster")).toHaveCount(0);
    expect((await call(context, 65, "GET", "/ai/groups")).status).toBe(404);
  } finally {
    await controls(page, { ai_three_agent_experience_enabled: true, ai_smart_orchestration_enabled: true, ai_group_chat_enabled: true });
  }
  expect(errors).toEqual([]);
  await context.close();
});
