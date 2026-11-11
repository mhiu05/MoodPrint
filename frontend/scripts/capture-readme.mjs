// Captures the connected local product with a synthetic account and no model calls.
// Run from frontend: node scripts/capture-readme.mjs
// Account JSON stays under .local; it is never included in browser traces or output.
import { readFile, mkdir } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { chromium, expect } from "@playwright/test";
/* global document */

const root = fileURLToPath(new URL("../../", import.meta.url));
const origin = process.env.CAPTURE_BASE_URL ?? "http://127.0.0.1:5678";
const api = process.env.CAPTURE_API_URL ?? "http://127.0.0.1:8508";
const auth = process.env.CAPTURE_AUTH_URL ?? "http://127.0.0.1:54821";
for (const endpoint of [origin, api, auth]) {
  if (
    !["127.0.0.1", "localhost", "[::1]"].includes(new URL(endpoint).hostname)
  ) {
    throw new Error("README captures require local loopback services");
  }
}
const accountPath = path.resolve(
  root,
  process.env.CAPTURE_ACCOUNT_FILE ?? ".local/ui-capture/account.json",
);
const local = path.resolve(root, ".local") + path.sep;
if (!accountPath.startsWith(local))
  throw new Error("Synthetic account file must be inside .local");
const account = JSON.parse(await readFile(accountPath, "utf8"));
const output = path.join(root, ".github/assets/readme");
const qa = path.join(root, "frontend/test-results/readme-qa");
await Promise.all([
  mkdir(output, { recursive: true }),
  mkdir(qa, { recursive: true }),
]);
const browser = await chromium.launch();
try {
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    reducedMotion: "reduce",
    locale: "vi-VN",
  });
  const allowed = new Set(
    [origin, api, auth].map((url) => new URL(url).origin),
  );
  // Block external traffic, but never replace any API response or modify the DOM.
  await context.route("**/*", (route) => {
    const url = new URL(route.request().url());
    return allowed.has(url.origin) || ["data:", "blob:"].includes(url.protocol)
      ? route.continue()
      : route.abort("blockedbyclient");
  });
  const page = await context.newPage();
  const errors = [];
  const apiReads = new Set();
  let agentRequests = 0;
  page.on("request", (request) => {
    const url = new URL(request.url());
    if (
      url.origin === api &&
      request.method() === "POST" &&
      /\/(messages|analyses|complete)$/.test(url.pathname)
    )
      agentRequests++;
  });
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("response", (response) => {
    const url = new URL(response.url());
    if (url.origin === api && response.request().method() === "GET")
      apiReads.add(`${response.status()} ${url.pathname}`);
  });
  await page.goto(`${origin}/auth`);
  await page
    .getByRole("textbox", { name: "Email", exact: true })
    .fill(account.email);
  await page.getByLabel("Mật khẩu", { exact: true }).fill(account.password);
  await page
    .locator("form")
    .filter({ has: page.getByRole("textbox", { name: "Email", exact: true }) })
    .getByRole("button", { name: "Đăng nhập", exact: true })
    .click();
  await expect(page).toHaveURL(/\/home$/);
  async function capture(route, name, ready) {
    await page.goto(origin + route);
    await expect(ready()).toBeVisible();
    await expect(page.locator(".skeleton")).toHaveCount(0);
    await page.screenshot({
      path: path.join(output, name),
      animations: "disabled",
    });
  }
  await capture("/home", "dashboard.png", () =>
    page.getByRole("heading", { name: /Chào/ }),
  );
  await capture("/support/knowledge", "knowledge.png", () =>
    page.getByRole("heading", { level: 1 }),
  );
  await capture("/cases", "incidents.png", () =>
    page.getByRole("heading", { level: 1 }),
  );
  await capture(`/cases/${account.caseId}/plan`, "action-plan.png", () =>
    page.getByRole("heading", { level: 1 }),
  );
  await page.setViewportSize({ width: 1280, height: 620 });
  await page.goto(`${origin}/ai/chat/${account.conversationId}`);
  await expect(
    page.getByRole("heading", { name: "SafeVoice", exact: true }),
  ).toBeVisible();
  await expect(page.getByText(/Bạn muốn kể điều gì/)).toBeVisible();
  const input = page.getByRole("textbox", { name: "Điều bạn muốn kể" });
  // This is an unsent draft, not an invented model interaction.
  await input.fill(
    "Mình muốn chuẩn bị cách nói chuyện với cô.\nMình đã ghi lại sự việc và muốn chọn một bước nhỏ để bắt đầu.",
  );
  await page.getByRole("heading", { name: "SafeVoice", exact: true }).click();
  await page.screenshot({
    path: path.join(output, "chat-desktop.png"),
    animations: "disabled",
  });
  for (const width of [360, 390, 430, 768, 1440]) {
    await page.setViewportSize({ width, height: width < 500 ? 800 : 900 });
    await input.focus();
    const box = await input.boundingBox();
    if (!box || box.y + box.height > (width < 500 ? 800 : 900))
      throw new Error("Composer outside viewport");
    if (
      (await page.evaluate(() => document.documentElement.scrollWidth)) > width
    )
      throw new Error("Horizontal overflow");
    await page.screenshot({
      path: path.join(qa, `connected-chat-${width}.png`),
      animations: "disabled",
    });
  }
  if (errors.length) throw new Error(`Browser errors: ${errors.join("; ")}`);
  if (agentRequests)
    throw new Error("README capture must not request model execution");
  console.log(
    JSON.stringify(
      {
        screenshots: 5,
        connectedApiReads: [...apiReads].sort(),
        agentExecutionRequests: agentRequests,
        mobileWidths: [360, 390, 430],
        pageErrors: errors.length,
      },
      null,
      2,
    ),
  );
} finally {
  await browser.close();
}
