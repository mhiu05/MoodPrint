/** Explicit hosted acceptance. Reuses only the two local manifest accounts. */
import { chromium, expect as baseExpect } from "@playwright/test";
import { randomUUID } from "node:crypto";
import { readFile, mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "../..",
);
const expect = baseExpect.configure({ timeout: 30000 });
const output = path.join(root, ".local/product-completion");
const manifest = JSON.parse(
  await readFile(path.join(output, "hosted-users.json"), "utf8"),
);
const project = "xhlshihobyxrgfqrdafh";
if (
  manifest.project_ref !== project ||
  manifest.users.length !== 2 ||
  manifest.users.some(
    (u) => !u.id || u.deleted || !u.email.endsWith("@example.test"),
  )
)
  throw new Error("A complete, active synthetic hosted manifest is required");
const ownerEnv = await readFile(path.join(root, ".env"), "utf8");
function env(name) {
  const line = ownerEnv.split(/\r?\n/).find((s) => s.startsWith(`${name}=`));
  if (!line) throw new Error(`Missing ${name}`);
  return line
    .slice(name.length + 1)
    .trim()
    .replace(/^(["'])(.*)\1$/, "$2");
}
const supabase = env("SUPABASE_URL").replace(/\/$/, "");
const key = env("SUPABASE_PUBLISHABLE_KEY");
if (supabase !== `https://${project}.supabase.co`)
  throw new Error("Exact audited project required");
const frontend = "http://127.0.0.1:5183";
const api = "http://127.0.0.1:8010";
const storage = `https://${project}.storage.supabase.co`;
const [userA, userB] = manifest.users;
const privateValues = [
  key,
  ...manifest.users.flatMap((u) => [u.email, u.password]),
];
const receipt = {
  started_at: new Date().toISOString(),
  project_ref: project,
  users: manifest.users.map(({ slot, id }) => ({ slot, id })),
  checks: [],
  resources: {},
  screenshots: [],
  forbidden_requests: [],
  page_errors: [],
  browser_http_errors: [],
};
const receiptPath = path.join(output, "hosted-browser-receipt.json");
await mkdir(output, { recursive: true });
try {
  const previous = await readFile(receiptPath, "utf8");
  const previousRun = JSON.parse(previous);
  await writeFile(
    path.join(
      output,
      `hosted-browser-${previousRun.started_at.replace(/[^0-9TZ]/g, "")}.json`,
    ),
    previous,
  );
} catch (error) {
  if (error.code !== "ENOENT") throw error;
}
function clean(error) {
  let message = error instanceof Error ? error.message : String(error);
  for (const secret of privateValues)
    if (secret) message = message.replaceAll(secret, "[redacted]");
  return message
    .replace(/https?:\/\/[^\s]+\?[^\s]+/g, "[URL query redacted]")
    .slice(0, 1500);
}
async function save() {
  await writeFile(receiptPath, JSON.stringify(receipt, null, 2) + "\n");
}
async function check(name, run) {
  try {
    await run();
    receipt.checks.push({ name, status: "passed" });
    console.log(`PASS ${name}`);
  } catch (error) {
    const alerts = await page
      .getByRole("alert")
      .allTextContents()
      .catch(() => []);
    receipt.checks.push({
      name,
      status: "failed",
      detail: clean(error),
      visible_alerts: alerts.map(clean),
    });
    console.log(
      `FAIL ${name}: ${clean(error).split("\n")[0]} ${alerts.map(clean).join("; ")}`,
    );
  }
  await save();
}
function blocked(name, detail) {
  receipt.checks.push({ name, status: "blocked", detail });
  console.log(`BLOCKED ${name}`);
}
async function token(user) {
  const response = await fetch(
    `${supabase}/auth/v1/token?grant_type=password`,
    {
      method: "POST",
      headers: { apikey: key, "Content-Type": "application/json" },
      body: JSON.stringify({ email: user.email, password: user.password }),
    },
  );
  expect(response.status).toBe(200);
  const body = await response.json();
  expect(body.user.id).toBe(user.id);
  privateValues.push(body.access_token, body.refresh_token);
  return body.access_token;
}
async function request(endpoint, auth, method = "GET", body) {
  if (!endpoint.startsWith("/v1/"))
    throw new Error("Only product API endpoints allowed");
  return fetch(api + endpoint, {
    method,
    headers: {
      ...(auth ? { Authorization: `Bearer ${auth}` } : {}),
      "Content-Type": "application/json",
    },
    ...(body ? { body: JSON.stringify(body) } : {}),
  });
}
async function json(endpoint, auth, method = "GET", body) {
  const response = await request(endpoint, auth, method, body);
  expect(response.status, `${method} ${endpoint}`).toBe(200);
  return response.json();
}
const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({
  baseURL: frontend,
  viewport: { width: 1440, height: 1000 },
  reducedMotion: "reduce",
});
await context.route("**/*", async (route) => {
  const url = new URL(route.request().url());
  const permitted =
    ["data:", "blob:"].includes(url.protocol) ||
    url.origin === frontend ||
    url.origin === api ||
    ((url.origin === supabase || url.origin === storage) &&
      /^\/(auth|storage)\/v1\//.test(url.pathname));
  // Never permit signup, OTP, recovery or invitations: this run sends no email.
  const emailOperation = /\/auth\/v1\/(signup|otp|recover|invite|resend)/.test(
    url.pathname,
  );
  if (!permitted || emailOperation) {
    receipt.forbidden_requests.push(`${url.origin}${url.pathname}`);
    await route.abort("blockedbyclient");
  } else await route.continue();
});
const page = await context.newPage();
page.setDefaultTimeout(15000);
page.on("pageerror", (e) => receipt.page_errors.push(clean(e)));
page.on("response", (r) => {
  if (r.status() >= 500)
    receipt.browser_http_errors.push({
      path: new URL(r.url()).pathname,
      status: r.status(),
    });
});
page.on("response", async (r) => {
  const url = new URL(r.url());
  if (url.origin === api && r.status() >= 400) {
    const body = await r.json().catch(() => ({}));
    receipt.api_errors ??= [];
    receipt.api_errors.push({
      path: url.pathname,
      status: r.status(),
      code: body.error?.code,
      details: body.error?.details,
    });
  }
  if (
    url.origin === api &&
    r.status() === 200 &&
    r.request().method() === "POST" &&
    url.pathname === "/v1/cases"
  ) {
    const body = await r.json();
    receipt.resources.created_case_ids ??= [];
    receipt.resources.created_case_ids.push(body.id);
  }
});
async function login(user) {
  await page.goto("/auth");
  await page
    .getByRole("textbox", { name: "Email", exact: true })
    .fill(user.email);
  await page.getByLabel("Mật khẩu", { exact: true }).fill(user.password);
  const signed = page.waitForResponse(
    (r) =>
      r.url().includes("/auth/v1/token") && r.request().method() === "POST",
  );
  await page
    .locator("form")
    .filter({ has: page.getByRole("textbox", { name: "Email", exact: true }) })
    .getByRole("button", { name: "Đăng nhập", exact: true })
    .click();
  expect((await signed).status(), "Hosted password sign-in response").toBe(200);
  await expect(page).toHaveURL(/\/(home|settings)$/);
}
async function logout() {
  await page.goto("/settings");
  await page.getByRole("button", { name: "Đăng xuất", exact: true }).click();
  await expect(page).toHaveURL(/\/auth$/);
}
let authA, authB, caseId, caseDetail, evidence, plan;
const tag = randomUUID().slice(0, 8);
const title = `Hosted synthetic browser ${tag}`;
const summary = `Tình huống tổng hợp ${tag}: một nhóm nhân vật hư cấu trêu chọc trong bài tập mô phỏng.`;
const png = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aHCsAAAAASUVORK5CYII=",
  "base64",
);
try {
  await check("real Auth token and manifest ownership A/B", async () => {
    authA = await token(userA);
    authB = await token(userB);
  });
  await check(
    "invalid login shows an error and retains auth route",
    async () => {
      await page.goto("/auth");
      await page
        .getByRole("textbox", { name: "Email", exact: true })
        .fill(userA.email);
      await page
        .getByLabel("Mật khẩu", { exact: true })
        .fill("Synthetic-wrong-password-1!");
      const response = page.waitForResponse(
        (r) =>
          r.url().includes("/auth/v1/token") && r.request().method() === "POST",
      );
      await page
        .locator("form")
        .filter({
          has: page.getByRole("textbox", { name: "Email", exact: true }),
        })
        .getByRole("button", { name: "Đăng nhập", exact: true })
        .click();
      expect((await response).status()).toBe(400);
      await expect(page.getByRole("alert")).toBeVisible();
      await expect(page).toHaveURL(/\/auth$/);
    },
  );
  await check("normal UI login opens real Home", async () => {
    await login(userA);
    await page.goto("/home");
    await expect(page.getByRole("heading", { level: 1 })).toContainText(/Chào/);
  });
  await check(
    "Home to wizard saves a draft and reloads persisted data",
    async () => {
      await page
        .locator('a[href="/cases/new"]')
        .filter({ hasText: "Ghi lại sự việc" })
        .first()
        .click();
      await expect(page).toHaveURL(/\/cases\/new$/);
      await page.getByRole("textbox", { name: "Đặt tên hồ sơ" }).fill(title);
      await page.getByRole("button", { name: "Tiếp tục", exact: true }).click();
      await page
        .getByRole("textbox", { name: "Chuyện gì đã xảy ra?" })
        .fill(summary);
      const saved = page.waitForResponse(
        (r) =>
          new URL(r.url()).pathname === "/v1/cases" &&
          r.request().method() === "POST",
        { timeout: 40000 },
      );
      await page.getByRole("button", { name: "Lưu nháp", exact: true }).click();
      const savedResponse = await saved;
      expect(
        savedResponse.status(),
        `Case create response: ${clean(await savedResponse.text())}`,
      ).toBe(200);
      await expect(page).toHaveURL(/\/cases\/[0-9a-f-]{36}$/);
      caseId = new URL(page.url()).pathname.split("/").pop();
      receipt.resources.case_id = caseId;
      await save();
      caseDetail = await json(`/v1/cases/${caseId}`, authA);
      expect(caseDetail.status).toBe("draft");
      expect(caseDetail.title).toBe(title);
      await page.reload();
      await expect(page.getByRole("heading", { level: 1 })).toHaveText(title);
    },
  );
  if (caseId) {
    await check(
      "edit draft uploads PNG through real Storage and activates case",
      async () => {
        await page.goto(`/cases/${caseId}`);
        await page
          .getByRole("link", { name: "Bổ sung hồ sơ", exact: true })
          .click();
        await page.getByRole("button", { name: /Chuyện xảy ra/ }).click();
        await expect(
          page.getByRole("textbox", { name: "Chuyện gì đã xảy ra?" }),
        ).toHaveValue(summary);
        await page
          .getByRole("button", { name: "Tiếp tục", exact: true })
          .click();
        await page
          .getByRole("textbox", { name: "Những người liên quan" })
          .fill("Nhân vật A và B hư cấu");
        await page
          .getByRole("button", { name: "Tiếp tục", exact: true })
          .click();
        await page
          .getByRole("checkbox", { name: "Khó tập trung", exact: true })
          .check();
        await page
          .getByRole("button", { name: "Tiếp tục", exact: true })
          .click();
        await page.getByLabel("Chọn tệp bằng chứng").setInputFiles({
          name: `synthetic-${tag}.png`,
          mimeType: "image/png",
          buffer: png,
        });
        await expect(
          page.getByRole("status").filter({ hasText: "Đã tải xong" }),
        ).toBeVisible({ timeout: 45000 });
        await page
          .getByRole("button", { name: "Tiếp tục", exact: true })
          .click();
        await page
          .getByRole("button", { name: "Lưu hồ sơ", exact: true })
          .click();
        await expect(page).toHaveURL(new RegExp(`/cases/${caseId}$`));
        caseDetail = await json(`/v1/cases/${caseId}`, authA);
        expect(caseDetail.status).toBe("active");
        expect(caseDetail.evidenceIds).toHaveLength(1);
        evidence = await json(
          `/v1/evidence/${caseDetail.evidenceIds[0]}`,
          authA,
        );
        receipt.resources.evidence_id = evidence.id;
        expect(evidence.byteSize).toBe(png.length);
        expect(evidence.uploadStatus).toBe("uploaded");
        await save();
      },
    );
    if (evidence)
      await check(
        "signed download returns exact uploaded PNG bytes",
        async () => {
          const signed = await json(
            `/v1/evidence/${evidence.id}/download-url`,
            authA,
          );
          const url = new URL(signed.url);
          expect(url.origin).toBe(supabase);
          expect(url.pathname).toMatch(/^\/storage\/v1\/object\/sign\//);
          const downloaded = await fetch(signed.url);
          expect(downloaded.status).toBe(200);
          expect(Buffer.from(await downloaded.arrayBuffer()).equals(png)).toBe(
            true,
          );
        },
      );
    await check(
      "timeline event add and edit persists after reload",
      async () => {
        await page.goto(`/cases/${caseId}/timeline`);
        await page
          .getByRole("button", { name: "Thêm mốc", exact: true })
          .click();
        await page
          .getByRole("textbox", { name: "Điều đã xảy ra", exact: true })
          .fill(`Mốc tổng hợp ${tag}`);
        await page
          .getByRole("button", { name: "Lưu mốc", exact: true })
          .click();
        await expect(page.locator(".case-timeline")).toContainText(
          `Mốc tổng hợp ${tag}`,
        );
        await page
          .getByRole("button", {
            name: new RegExp(`Sửa mốc Mốc tổng hợp ${tag}`),
          })
          .click();
        await page
          .getByRole("textbox", { name: "Điều đã xảy ra", exact: true })
          .fill(`Mốc tổng hợp đã sửa ${tag}`);
        await page
          .getByRole("button", { name: "Lưu mốc", exact: true })
          .click();
        await expect(page.getByRole("dialog")).toHaveCount(0);
        await page.reload();
        await expect(page.locator(".case-timeline")).toContainText(
          `Mốc tổng hợp đã sửa ${tag}`,
        );
        caseDetail = await json(`/v1/cases/${caseId}`, authA);
        receipt.resources.event_ids = caseDetail.events.map((e) => e.id);
        await save();
      },
    );
    await check(
      "plan save and Home checklist persist after reload",
      async () => {
        await page.goto(`/cases/${caseId}/plan`);
        await page
          .getByRole("button", { name: "Chọn phương án này" })
          .first()
          .click();
        await page
          .getByRole("button", { name: "Lưu kế hoạch", exact: true })
          .filter({ visible: true })
          .first()
          .click();
        await expect(page.locator(".plan-save button")).toBeDisabled();
        plan = await json(`/v1/cases/${caseId}/plan`, authA);
        receipt.resources.plan_id = plan.id;
        receipt.resources.plan_item_ids = plan.items.map((i) => i.id);
        await save();
        await page.goto("/home");
        const checkbox = page
          .locator(".home-check")
          .filter({ hasText: plan.items[0].label })
          .locator("input")
          .first();
        await checkbox.click();
        await expect(checkbox).toBeChecked();
        await page.reload();
        await expect(checkbox).toBeChecked();
        plan = await json(`/v1/cases/${caseId}/plan`, authA);
        expect(plan.items[0].status).toBe("done");
      },
    );
    await check(
      "logout and fresh login preserve case timeline and checklist",
      async () => {
        await logout();
        await login(userA);
        await page.goto("/home");
        await expect(page.getByText(title, { exact: true })).toBeVisible();
        if (plan)
          await expect(
            page
              .locator(".home-check")
              .filter({ hasText: plan.items[0].label })
              .locator("input")
              .first(),
          ).toBeChecked();
        await page.goto(`/cases/${caseId}/timeline`);
        await expect(page.locator(".case-timeline")).toContainText(
          `Mốc tổng hợp đã sửa ${tag}`,
        );
      },
    );
  }
  await check(
    "Support trusted contact persists without external messages",
    async () => {
      await page.goto("/support/find-help");
      await page
        .getByRole("textbox", { name: "Tên gọi dễ nhớ", exact: true })
        .fill(`Cô giáo tổng hợp ${tag}`);
      await page
        .getByRole("button", { name: "Thêm người tin cậy", exact: true })
        .click();
      await page.reload();
      await expect(
        page.getByText(`Cô giáo tổng hợp ${tag}`, { exact: true }),
      ).toBeVisible();
      const contacts = await json("/v1/trusted-contacts", authA);
      receipt.resources.contact_ids = contacts.items
        .filter((c) => JSON.stringify(c).includes(tag))
        .map((c) => c.id);
      await save();
    },
  );
  await check(
    "Support draft is persisted and explicitly not sent",
    async () => {
      const content = `Lời nhắn tổng hợp ${tag}. Mình muốn chuẩn bị nói chuyện với một người lớn đáng tin.`;
      await page.goto("/support/prepare");
      await page
        .getByRole("textbox", { name: "Nội dung xem trước", exact: true })
        .fill(content);
      await page
        .getByRole("button", { name: "Lưu bản nháp", exact: true })
        .click();
      await expect(
        page
          .getByText("Đã lưu bản nháp trong tài khoản. Chưa gửi cho ai.")
          .first(),
      ).toBeVisible();
      const drafts = await json("/v1/support-drafts", authA);
      const draft = drafts.items.find((d) => d.content === content);
      expect(draft).toBeTruthy();
      expect(draft.status).toBe("draft");
      receipt.resources.support_draft_id = draft.id;
      await save();
      await page.goto(`/support/prepare?draftId=${draft.id}`);
      await page.reload();
      await expect(
        page.getByRole("textbox", { name: "Nội dung xem trước", exact: true }),
      ).toHaveValue(content);
    },
  );
  await check("profile nickname update persists after reload", async () => {
    await page.goto("/settings");
    await page
      .getByRole("textbox", { name: "Bí danh", exact: true })
      .fill(`Mây tổng hợp ${tag}`);
    await page
      .getByRole("button", { name: "Lưu thay đổi", exact: true })
      .click();
    await expect(
      page.getByText("Đã cập nhật bí danh và nhóm tuổi."),
    ).toBeVisible();
    await page.reload();
    await expect(
      page.getByRole("textbox", { name: "Bí danh", exact: true }),
    ).toHaveValue(`Mây tổng hợp ${tag}`);
  });
  await check(
    "meaningful desktop Home and mobile case screenshots",
    async () => {
      await page.goto("/home");
      await expect(page.getByRole("heading", { level: 1 })).toContainText(
        `Mây tổng hợp ${tag}`,
      );
      await page.screenshot({
        path: path.join(output, "hosted-home-1440.png"),
        fullPage: true,
      });
      receipt.screenshots.push("hosted-home-1440.png");
      await page.setViewportSize({ width: 390, height: 844 });
      await page.goto(caseId ? `/cases/${caseId}` : "/support");
      await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
      expect(
        await page.evaluate(
          () =>
            globalThis.document.documentElement.scrollWidth <=
            globalThis.innerWidth,
        ),
      ).toBe(true);
      await page.screenshot({
        path: path.join(output, "hosted-case-390.png"),
        fullPage: true,
      });
      receipt.screenshots.push("hosted-case-390.png");
      await page.setViewportSize({ width: 1440, height: 1000 });
    },
  );
  await check("User B cannot read or update A memory", async () => {
    const memory = await json("/v1/memories", authA, "POST", {
      category: "preference",
      content: `Synthetic hosted isolation ${tag}`,
    });
    receipt.resources.memory_id = memory.id;
    await save();
    expect(
      (
        await request(`/v1/memories/${memory.id}`, authB, "PATCH", {
          content: "Forbidden synthetic change",
        })
      ).status,
    ).toBe(404);
    expect(
      (await request(`/v1/memories/${memory.id}`, authB, "DELETE")).status,
    ).toBe(404);
    const memories = await json("/v1/memories", authB);
    expect(memories.items.some((m) => m.id === memory.id)).toBe(false);
  });
  if (caseId)
    await check("User B case read and write return 404", async () => {
      expect((await request(`/v1/cases/${caseId}`, authB)).status).toBe(404);
      expect(
        (
          await request(`/v1/cases/${caseId}`, authB, "PATCH", {
            version: caseDetail.version,
            title: "Forbidden synthetic change",
          })
        ).status,
      ).toBe(404);
    });
  if (plan)
    await check("User B plan read and item write return 404", async () => {
      expect((await request(`/v1/cases/${caseId}/plan`, authB)).status).toBe(
        404,
      );
      expect(
        (
          await request(
            `/v1/plans/${plan.id}/items/${plan.items[0].id}`,
            authB,
            "PATCH",
            { status: "done" },
          )
        ).status,
      ).toBe(404);
    });
  if (evidence)
    await check(
      "User B evidence read signed URL and deletion return 404",
      async () => {
        for (const suffix of ["", "/download-url"])
          expect(
            (await request(`/v1/evidence/${evidence.id}${suffix}`, authB))
              .status,
          ).toBe(404);
        expect(
          (await request(`/v1/evidence/${evidence.id}`, authB, "DELETE"))
            .status,
        ).toBe(404);
      },
    );
  await check("User B conversation read and deletion return 404", async () => {
    const id = randomUUID();
    const response = await request("/v1/conversations", authA, "POST", {
      id,
      title: `Synthetic isolation ${tag}`,
    });
    expect(response.status).toBe(200);
    receipt.resources.conversation_id = id;
    await save();
    expect((await request(`/v1/conversations/${id}`, authB)).status).toBe(404);
    expect(
      (await request(`/v1/conversations/${id}`, authB, "DELETE")).status,
    ).toBe(404);
  });
  await check(
    "missing and invalid tokens cannot access authenticated API",
    async () => {
      for (const endpoint of ["/v1/me", "/v1/cases", "/v1/memories"]) {
        expect((await request(endpoint)).status).toBe(401);
        expect(
          (await request(endpoint, "invalid.synthetic.token")).status,
        ).toBe(401);
      }
    },
  );
  await check("User B UI cannot open A direct case route", async () => {
    await logout();
    await login(userB);
    await page.goto("/home");
    await expect(page.getByText(title, { exact: true })).toHaveCount(0);
    if (caseId) {
      await page.goto(`/cases/${caseId}`);
      await expect(
        page.getByRole("heading", {
          name: "Không tìm thấy hồ sơ",
          exact: true,
        }),
      ).toBeVisible();
    }
    await logout();
    await page.goto("/cases");
    await expect(page).toHaveURL(/\/auth/);
  });
  await check(
    "known-schema preflight exposes blockers without querying user rows",
    async () => {
      const response = await fetch(api + "/hosted-product/preflight");
      expect(response.status).toBe(200);
      const preflight = await response.json();
      receipt.preflight = preflight;
      for (const [relation, present] of Object.entries(preflight.relations))
        if (!present)
          blocked(
            `hosted relation ${relation}`,
            "Missing hosted relation; corresponding journey is not verified. Deployment is outside this run.",
          );
    },
  );
  blocked(
    "genuine expired signed JWT",
    "No genuine expired token fixture is available. Missing/invalid token checks passed separately; no signing keys or Auth settings were changed.",
  );
  await check(
    "browser sends no requests outside audited hosts or email operations",
    async () => {
      expect(receipt.forbidden_requests).toEqual([]);
      expect(receipt.page_errors).toEqual([]);
    },
  );
} finally {
  receipt.finished_at = new Date().toISOString();
  receipt.counts = {
    passed: receipt.checks.filter((c) => c.status === "passed").length,
    failed: receipt.checks.filter((c) => c.status === "failed").length,
    blocked: receipt.checks.filter((c) => c.status === "blocked").length,
  };
  await save();
  await browser.close();
  console.log(JSON.stringify(receipt.counts));
}
if (receipt.counts.failed) process.exitCode = 1;
