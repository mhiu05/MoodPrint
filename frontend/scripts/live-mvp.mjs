/** Genuine hosted Auth + localhost UI checks. Only manifest synthetic owners. */
import { chromium, expect as baseExpect } from "@playwright/test";
import { readFile, writeFile, mkdir } from "node:fs/promises";
import path from "node:path";

const root = path.resolve(process.cwd(), "..");
const output = path.join(root, ".local/fresh-supabase");
await mkdir(output, { recursive: true });
const browser = await chromium.launch({ headless: true });
if (process.argv.includes("--fixture")) {
  const page = await browser.newPage({
    viewport: { width: 640, height: 480 },
    deviceScaleFactor: 1,
  });
  await page.setContent(
    `<html lang="vi"><meta charset="utf-8"><style>body{font:20px Arial;background:#eff4f7;padding:30px;color:#182b39}h1{font-size:22px}article{background:white;padding:24px;border-radius:16px}small{font-size:15px;color:#445}p{line-height:1.6}b{color:#164355}</style><h1>SYNTHETIC TEST — TÌNH HUỐNG GIẢ</h1><article><small>Nhóm lớp mô phỏng · 09/11/2026 10:00</small><p><b>Bạn A:</b> Đừng cho An vào nhóm học tập.</p><p><b>Bạn B:</b> Mình không đồng ý. Mọi người cùng làm bài nhé.</p><p><b>An:</b> Mình buồn khi đọc tin nhắn này.</p></article><small>Nhân vật, tin nhắn và thời gian đều là dữ liệu tổng hợp.</small></html>`,
  );
  await page.screenshot({ path: path.join(output, "synthetic-chat.png") });
  await browser.close();
  console.log("Synthetic evidence screenshot prepared.");
  process.exit(0);
}
const label =
  process.argv.find((x) => x.startsWith("--label="))?.slice(8) ?? "initial";
const expect = baseExpect.configure({ timeout: 90000 });
const manifest = JSON.parse(
  await readFile(path.join(output, "hosted-users.json"), "utf8"),
);
if (
  manifest.project_ref !== "xhlshihobyxrgfqrdafh" ||
  manifest.users.length !== 2 ||
  manifest.users.some((u) => u.deleted || !u.id)
)
  throw new Error("An active exact synthetic manifest is required");
const envText = await readFile(path.join(root, ".env"), "utf8");
function env(name) {
  const line = envText.split(/\r?\n/).find((x) => x.startsWith(`${name}=`));
  if (!line) throw new Error(`Missing ${name}`);
  return line
    .slice(name.length + 1)
    .trim()
    .replace(/^(["'])(.*)\1$/, "$2");
}
const supabase = env("SUPABASE_URL");
if (supabase !== "https://xhlshihobyxrgfqrdafh.supabase.co")
  throw new Error("Exact audited project required");
const api = "http://127.0.0.1:8000";
const frontend = "http://127.0.0.1:5173";
const key = env("SUPABASE_PUBLISHABLE_KEY");
const user = manifest.users[0];
const receipt = {
  model: "gpt-6-luna",
  mode: "GENUINE_LOCAL_RUNTIME_HOSTED_SUPABASE",
  started_at: new Date().toISOString(),
  checks: [],
  outputs: [],
  screenshots: [],
  page_errors: [],
  forbidden_requests: [],
};
const context = await browser.newContext({
  baseURL: frontend,
  viewport: { width: 1440, height: 1000 },
  reducedMotion: "reduce",
});
await context.addInitScript(() =>
  localStorage.setItem("moodprint:ai-companion", "live"),
);
await context.route("**/*", async (route) => {
  const url = new URL(route.request().url());
  const allowed =
    ["data:", "blob:"].includes(url.protocol) ||
    url.origin === frontend ||
    url.origin === api ||
    ((url.origin === supabase ||
      url.origin === "https://xhlshihobyxrgfqrdafh.storage.supabase.co") &&
      /^\/(auth|storage)\/v1\//.test(url.pathname));
  if (
    !allowed ||
    /\/auth\/v1\/(signup|otp|recover|invite|resend)/.test(url.pathname)
  ) {
    receipt.forbidden_requests.push(url.origin + url.pathname);
    await route.abort("blockedbyclient");
  } else await route.continue();
});
const page = await context.newPage();
page.on("pageerror", (e) => receipt.page_errors.push(e.name));
async function save() {
  await writeFile(
    path.join(output, `browser-live-${label}.json`),
    JSON.stringify(receipt, null, 2),
  );
}
async function check(name, run) {
  try {
    await run();
    receipt.checks.push({ name, passed: true });
    console.log(`PASS ${name}`);
  } catch (e) {
    receipt.checks.push({
      name,
      passed: false,
      error_type: e.name,
      detail: String(e.message).split("\n")[0].slice(0, 300),
    });
    console.log(`FAIL ${name}: ${e.name}`);
  }
  await save();
}
async function login() {
  await page.goto("/auth");
  await page
    .getByRole("textbox", { name: "Email", exact: true })
    .fill(user.email);
  await page.getByLabel("Mật khẩu", { exact: true }).fill(user.password);
  await page
    .locator("form")
    .filter({ has: page.getByRole("textbox", { name: "Email", exact: true }) })
    .getByRole("button", { name: "Đăng nhập", exact: true })
    .click();
  await expect(page).toHaveURL(/\/(home|settings)$/);
}
let token;
async function apiJson(endpoint, method = "GET", body) {
  const response = await fetch(api + endpoint, {
    method,
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    ...(body ? { body: JSON.stringify(body) } : {}),
  });
  expect(response.status, `${method} ${endpoint}`).toBe(200);
  return response.json();
}
async function say(id, prompt) {
  const response = page.waitForResponse(
    (r) =>
      new URL(r.url()).origin === api &&
      r.request().method() === "POST" &&
      new URL(r.url()).pathname.endsWith("/messages"),
    { timeout: 90000 },
  );
  const input = page.getByRole("textbox", { name: "Điều bạn muốn kể" });
  await input.fill(prompt);
  await input.press("Enter");
  const stream = await response;
  const raw = await stream.text();
  const events = raw
    .split(/\r?\n/)
    .filter((line) => line.startsWith("data:"))
    .map((line) => JSON.parse(line.slice(5).trim()));
  const answer = events
    .filter((event) => event.event === "message.completed")
    .at(-1)?.data;
  receipt.outputs.push({
    scenario_id: id,
    prompt_version: "companion_v4",
    model: "gpt-6-luna",
    user_message: prompt,
    response: answer?.content ?? null,
    structured: answer?.structured ?? null,
    citations: answer?.citations ?? [],
    events: events.filter(
      (e) => e.event !== "message.delta" && e.event !== "heartbeat",
    ),
  });
  await save();
  return { events, answer };
}
try {
  await check("UI real Supabase login and Home", async () => {
    await login();
    await page.goto("/home");
    await expect(page.getByRole("heading", { level: 1 })).toContainText(/Chào/);
    const response = await fetch(
      supabase + "/auth/v1/token?grant_type=password",
      {
        method: "POST",
        headers: { apikey: key, "Content-Type": "application/json" },
        body: JSON.stringify({ email: user.email, password: user.password }),
      },
    );
    expect(response.status).toBe(200);
    token = (await response.json()).access_token;
  });
  await check(
    "UI new conversation, actual model, follow-up and reload",
    async () => {
      await page.goto("/ai/chat");
      await page.getByRole("button", { name: /Cuộc trò chuyện mới/ }).click();
      await expect(page.getByTestId("chat-live")).toBeVisible();
      const first = await say(
        "UI-A-first",
        "Mình đang ở nhà an toàn. Hôm qua bạn cùng nhóm giấu cặp của mình. Mình chưa muốn báo ngay; bạn nghe mình một chút được không?",
      );
      expect(first.answer?.content).toBeTruthy();
      const second = await say(
        "UI-B-follow-up",
        "Mình nói rõ thêm: chuyện xảy ra đúng một lần thôi. Cho mình một bước nhỏ để nói ranh giới với bạn, không cần đối chất với cả nhóm.",
      );
      expect(second.answer?.content).toBeTruthy();
      receipt.conversation_url = page.url();
      await page.reload();
      await expect(page.getByTestId("live-assistant")).toHaveCount(2);
      await expect(
        page.getByText(second.answer.content, { exact: true }),
      ).toBeVisible();
      await page.setViewportSize({ width: 390, height: 844 });
      const file = `live-chat-390-${label}.png`;
      await page.screenshot({ path: path.join(output, file) });
      receipt.screenshots.push(file);
      expect(
        await page.evaluate(
          () =>
            globalThis.document.documentElement.scrollWidth <=
            globalThis.innerWidth,
        ),
      ).toBe(true);
      await page.setViewportSize({ width: 1440, height: 1000 });
    },
  );
  await check("UI incident and Action Plan restoration", async () => {
    const cases = await apiJson("/v1/cases");
    const selected = cases.items[0];
    expect(selected).toBeTruthy();
    await page.goto(`/cases/${selected.id}`);
    await expect(
      page.getByText(selected.title, { exact: true }).first(),
    ).toBeVisible();
    await page.goto(`/cases/${selected.id}/plan`);
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  });
  await check("UI evidence and analysis restoration", async () => {
    const saved = JSON.parse(
      await readFile(path.join(output, "evidence-initial.json"), "utf8"),
    );
    const analysis = saved.records.find(
      (r) => r.scenario_id === "D03-real-image-analysis",
    );
    expect(analysis.analysis.status).toBe("succeeded");
    await page.goto(`/cases/${analysis.case_id}/evidence`);
    await expect(
      page.getByText("synthetic-chat.png", { exact: true }).first(),
    ).toBeVisible();
    await page.goto(
      `/ai/analysis/${analysis.analysis.id}?caseId=${analysis.case_id}`,
    );
    for (const name of [
      "Chữ đọc được",
      "Quan sát",
      "AI suy đoán (chưa xác minh)",
      "Điều chưa chắc và hạn chế",
    ])
      await expect(
        page.getByRole("heading", { name, exact: true }),
      ).toBeVisible();
    await page.reload();
    await expect(
      page.getByRole("heading", { name: "Chữ đọc được", exact: true }),
    ).toBeVisible();
  });
  await check("UI roleplay saved feedback and exit", async () => {
    const sessions = await apiJson("/v1/roleplay/sessions");
    const selected = sessions.items.find((s) => s.status === "completed");
    expect(selected).toBeTruthy();
    await page.goto(`/ai/roleplay?session=${selected.id}`);
    await expect(
      page.getByRole("region", { name: "Phản hồi buổi luyện" }),
    ).toBeVisible();
    await page.reload();
    await expect(
      page.getByRole("region", { name: "Phản hồi buổi luyện" }),
    ).toBeVisible();
  });
  await check("UI Knowledge Hub, Support and Profile", async () => {
    for (const route of ["/knowledge", "/support", "/settings"]) {
      await page.goto(route);
      await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    }
    await page.goto("/support/urgent");
    await expect(page.locator('a[href="tel:111"]').first()).toBeVisible();
  });
  await check("UI logout/login retains persisted conversation", async () => {
    await page.goto("/settings");
    await page.getByRole("button", { name: "Đăng xuất", exact: true }).click();
    await expect(page).toHaveURL(/\/auth$/);
    await login();
    await page.goto(receipt.conversation_url);
    await expect(page.getByTestId("live-assistant")).toHaveCount(2);
  });
  await check(
    "UI no forbidden network traffic or page exceptions",
    async () => {
      expect(receipt.forbidden_requests).toEqual([]);
      expect(receipt.page_errors).toEqual([]);
    },
  );
} finally {
  receipt.finished_at = new Date().toISOString();
  await save();
  await browser.close();
}
console.log(
  JSON.stringify({
    passed: receipt.checks.filter((c) => c.passed).length,
    failed: receipt.checks.filter((c) => !c.passed).length,
  }),
);
if (receipt.checks.some((c) => !c.passed)) process.exitCode = 1;
