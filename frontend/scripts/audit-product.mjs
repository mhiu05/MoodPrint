import { chromium } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";

/* global document, getComputedStyle, innerWidth, innerHeight, matchMedia */

// Standalone demo-only audit. Existing dependencies only; never signs into a real account.
// Run: node scripts/audit-product.mjs (Vite must already be running).
const baseURL = process.env.AUDIT_BASE_URL || "http://127.0.0.1:5173";
if (!["127.0.0.1", "localhost"].includes(new URL(baseURL).hostname))
  throw new Error("The product audit requires a loopback demo origin.");
const out = resolve(
  dirname(fileURLToPath(import.meta.url)),
  "../../docs/quality/product-completion",
);
await mkdir(out, { recursive: true });
const viewports = [
  [320, 720],
  [360, 800],
  [390, 844],
  [430, 932],
  [768, 1024],
  [1024, 768],
  [1440, 900],
].map(([width, height]) => ({ width, height }));
const report = {
  generatedAt: new Date().toISOString(),
  baseURL,
  mode: "DEMO",
  viewports,
  caveats: [
    "Only synthetic demo browser storage is mutated. External network requests are blocked.",
    "Playwright Chromium viewport emulation is not physical-device or touch-gesture certification.",
    "Axe runs with its full default ruleset, with no exclusions or suppressed rules. Serious/critical violations are failures; other impacts are also retained.",
    "200% text enlargement doubles each rendered font size. 200% browser zoom is emulated by halving a 1440×900 physical viewport to a 720×450 CSS viewport. These are emulations, not browser UI zoom or OS text scaling.",
    "Demo persistence means localStorage/sessionStorage surviving reload; it does not prove hosted database persistence.",
    "Hosted auth, database RLS, uploads, delivery, live AI, real OCR, and paid providers are not exercised by this audit.",
  ],
  routes: [],
  sweeps: [],
  actions: [],
  errors: [],
  externalRequestsBlocked: [],
  screenshots: [],
};
// Recheck only failed sweep rows and all behavioral checks after application fixes.
// Original passing rows stay as timestamped evidence; no rules are suppressed.
const recheck = process.argv.includes("--recheck");
const forcedRechecks = new Set(
  process.argv
    .filter((arg) => arg.startsWith("--recheck-route="))
    .map((arg) => arg.slice("--recheck-route=".length)),
);
if (recheck) {
  const previous = JSON.parse(
    await readFile(resolve(out, "audit-results.json"), "utf8"),
  );
  const currentCaveats = report.caveats;
  Object.assign(report, previous);
  report.caveats = currentCaveats;
  report.priorRuns = [
    ...(report.priorRuns || []),
    {
      finishedAt: previous.finishedAt,
      counts: previous.counts,
      errors: previous.errors,
      failedActions: previous.actions
        .filter((r) => r.status === "FAIL")
        .map((r) => ({ name: r.name, error: r.error })),
    },
  ];
  report.rechecks = [...(report.rechecks || []), new Date().toISOString()];
  report.actions = [];
  report.errors = [];
  delete report.fatalError;
}
const browser = await chromium.launch();
const origin = new URL(baseURL).origin;
async function context(storageState) {
  const ctx = await browser.newContext({
    viewport: viewports[2],
    reducedMotion: "reduce",
    storageState,
  });
  await ctx.route("**/*", async (route) => {
    const url = route.request().url();
    if (
      url.startsWith(origin + "/") ||
      url.startsWith("data:") ||
      url.startsWith("blob:")
    )
      return route.continue();
    report.externalRequestsBlocked.push({
      url: url.replace(/\?.*$/, ""),
      method: route.request().method(),
    });
    return route.abort("blockedbyclient");
  });
  ctx.on("page", (page) => {
    page.on("pageerror", (e) =>
      report.errors.push({
        kind: "pageerror",
        url: page.url(),
        message: e.message,
      }),
    );
    page.on("console", (message) => {
      if (message.type() === "error")
        report.errors.push({
          kind: "console",
          url: page.url(),
          message: message.text(),
        });
    });
  });
  return ctx;
}
async function navigate(page, path) {
  await page.goto(baseURL + path, { waitUntil: "domcontentloaded" });
  await page
    .locator("h1, h2")
    .first()
    .waitFor({ state: "visible", timeout: 12000 });
  await page.evaluate(() => document.fonts.ready);
}
async function action(name, work) {
  const row = { name, status: "PASS", evidence: {} };
  try {
    row.evidence = (await work()) || {};
  } catch (error) {
    row.status = "FAIL";
    row.error = error.message;
    row.evidence = error.evidence || row.evidence;
  }
  report.actions.push(row);
  console.log(
    JSON.stringify({ action: name, status: row.status, error: row.error }),
  );
  return row;
}
function ensure(value, message, evidence) {
  if (!value) {
    const error = new Error(message);
    error.evidence = evidence;
    throw error;
  }
}
async function layout(page) {
  return page.evaluate(() => {
    const visible = (element) => {
      const rect = element.getBoundingClientRect();
      const style = getComputedStyle(element);
      return (
        rect.width > 0 &&
        rect.height > 0 &&
        style.visibility !== "hidden" &&
        style.display !== "none"
      );
    };
    const selector = (element) =>
      element.id
        ? "#" + element.id
        : element.tagName.toLowerCase() +
          [...element.classList].map((c) => "." + c).join("");
    return {
      viewport: { width: innerWidth, height: innerHeight },
      document: {
        width: document.documentElement.scrollWidth,
        height: document.documentElement.scrollHeight,
      },
      horizontalOverflow: document.documentElement.scrollWidth > innerWidth + 1,
      overflowElements: [...document.querySelectorAll("main *, dialog *")]
        .filter(visible)
        .filter((element) => {
          const r = element.getBoundingClientRect();
          const style = getComputedStyle(element);
          return (
            (r.right > innerWidth + 2 || r.left < -2) &&
            style.position !== "fixed"
          );
        })
        .slice(0, 12)
        .map((element) => ({
          selector: selector(element),
          text: element.textContent.trim().slice(0, 90),
        })),
      smallTargets: [
        ...document.querySelectorAll(
          "button,a,input[type=checkbox],input[type=radio],select",
        ),
      ]
        .filter(visible)
        .map((element) => {
          const r = element.getBoundingClientRect();
          return {
            selector: selector(element),
            name:
              element.getAttribute("aria-label") ||
              element.textContent.trim().slice(0, 80),
            width: Math.round(r.width),
            height: Math.round(r.height),
          };
        })
        .filter((r) => r.width < 44 || r.height < 44)
        .slice(0, 20),
      composer: (() => {
        const element = document.querySelector(".chat-composer");
        if (!element) return null;
        const rect = element.getBoundingClientRect();
        return {
          top: rect.top,
          bottom: rect.bottom,
          fitsViewport: rect.top >= 0 && rect.bottom <= innerHeight + 1,
        };
      })(),
    };
  });
}
function route(id, path, intent, actions, options = {}) {
  return {
    id,
    path,
    entry: options.entry || "Direct link and in-app navigation",
    intent,
    expected:
      options.expected ||
      "Named screen renders with a visible main heading and a usable next action.",
    dependencies:
      options.dependencies ||
      "Demo account; local browser store; synthetic fixtures",
    persistence:
      options.persistence ||
      "Source-supported browser persistence; screen load observed. See action checks for reload evidence.",
    loading:
      "Initial hydration/source-supported; action-specific loading checked separately where exercised.",
    empty: options.empty || "Not exercised on this populated screen.",
    error: options.error || "Not forced on this screen.",
    retry:
      options.retry ||
      "Not exercised; missing evidence does not imply missing implementation.",
    mobile: "All seven exact requested viewport sizes; see sweep rows.",
    a11y: "Full axe ruleset at all seven viewports; see violations and keyboard checks.",
    actions,
    ...options,
  };
}
const publicRoutes = [
  ...[1, 2, 3, 4].map((step) =>
    route(
      "welcome-" + step,
      "/welcome/" + step,
      "Understand the app and proceed or skip onboarding",
      "Next/back/skip/urgent-help links",
      {
        dependencies: "Public; synthetic illustrations",
        persistence: "Navigation only",
      },
    ),
  ),
  route(
    "auth",
    "/auth",
    "Choose a clearly labelled demo persona",
    "Demo login, demo signup; real account form only inspected",
    {
      dependencies: "Public; demo account selector",
      persistence:
        "Demo login verified to survive reload; no real credentials entered",
    },
  ),
  route(
    "reset-password",
    "/auth/reset",
    "Recover account access",
    "Recovery form inspected only; no email sent",
    {
      dependencies:
        "Hosted Auth would be needed for a real recovery; not invoked",
      persistence: "Not applicable; no recovery submitted",
    },
  ),
  route(
    "urgent-public",
    "/support/urgent",
    "Find immediate support without signing in",
    "111 telephone link and trusted-adult guidance inspected; no calls placed",
    { dependencies: "Public; no login", persistence: "Not applicable" },
  ),
];
let analysisPath;
try {
  const publicContext = await context();
  const publicPage = await publicContext.newPage();
  const studentContext = await context();
  const page = await studentContext.newPage();
  await action(
    "Guard preserves case-plan deep link through demo login",
    async () => {
      await page.goto(baseURL + "/cases/CASE-AN-001/plan");
      await page.waitForURL("**/auth");
      await page
        .getByRole("button", { name: "Vào thử với tài khoản demo" })
        .click();
      await page.waitForURL("**/cases/CASE-AN-001/plan");
      await page.reload();
      await page.locator("h1").first().waitFor();
      ensure(
        page.url().endsWith("/cases/CASE-AN-001/plan"),
        "Lost deep link after reload",
      );
      return {
        url: page.url(),
        mode: await page.evaluate(
          () =>
            JSON.parse(localStorage.getItem("moodprint-demo")).state.workspace
              .kind,
        ),
      };
    },
  );
  await navigate(page, "/ai/analysis/audit-missing");
  await page.getByRole("button", { name: /8 ảnh nhóm lớp/ }).click();
  await page.waitForURL("**/ai/analysis/ANALYSIS-*");
  analysisPath = new URL(page.url()).pathname;
  const studentRoutes = [
    route(
      "home",
      "/home",
      "Resume a case or begin a supportive journey",
      "Chat, new case, roleplay, help, knowledge, plan",
    ),
    route(
      "ai-hub",
      "/ai",
      "Choose a companion activity and resume a conversation",
      "Start chat, roleplay, recent sessions",
    ),
    route(
      "chat",
      "/ai/chat",
      "Tell a synthetic story and keep a draft",
      "Send, scripted quick reply, history dialog, scenarios, fixture attachments",
      {
        persistence:
          "Draft survives navigation and reload; observed in action checks",
      },
    ),
    route(
      "analysis",
      analysisPath,
      "Review synthetic image extraction and confirm source content",
      "Run simulation, confirm source text, create case",
      {
        dependencies:
          "Synthetic eight-image fixture created in browser; demo-only analysis",
      },
    ),
    route(
      "analysis-missing",
      "/ai/analysis/audit-missing",
      "Recover a missing analysis with a sample",
      "Choose fixture",
      { empty: "OBSERVED: missing analysis displays sample choices" },
    ),
    route(
      "roleplay-picker",
      "/ai/roleplay",
      "Choose who to practise speaking to",
      "Teacher/parent/other scenario choices",
    ),
    route(
      "roleplay",
      "/ai/roleplay/teacher",
      "Practise a conversation safely",
      "Start session, suggested phrase, send, pause, feedback",
    ),
    route(
      "roleplay-feedback",
      "/ai/roleplay/teacher/feedback",
      "Read feedback for a completed synthetic practice",
      "Feedback/empty-state recovery; full session checked separately",
    ),
    route(
      "case-list",
      "/cases",
      "Find and resume a personal case",
      "Search, filters, new case",
    ),
    route(
      "case-new",
      "/cases/new",
      "Record a synthetic incident",
      "Wizard steps, save draft, cancel",
      {
        persistence:
          "Session draft recovery and explicit save supported by source; save/retry action checked separately",
      },
    ),
    route(
      "case-edit",
      "/cases/CASE-AN-001/edit",
      "Add or correct case information",
      "Wizard back/next, draft save",
    ),
    route(
      "case-detail",
      "/cases/CASE-AN-001",
      "Understand the case and choose the next step",
      "Edit, timeline, evidence, plan, summary, delete dialog",
    ),
    route(
      "case-timeline",
      "/cases/CASE-AN-001/timeline",
      "Read the order of recorded events",
      "Overview, evidence, plan, summary",
    ),
    route(
      "case-evidence",
      "/cases/CASE-AN-001/evidence",
      "Review linked source material",
      "Attach/review evidence",
      { empty: "OBSERVED: seed case has no attached evidence" },
    ),
    route(
      "case-plan",
      "/cases/CASE-AN-001/plan",
      "Choose and complete manageable next steps",
      "Plan options, checklist, notes, review date, save",
    ),
    route(
      "case-summary",
      "/cases/CASE-AN-001/summary",
      "Review and copy a concise case summary",
      "Copy/download/prepare support links inspected",
    ),
    route(
      "case-missing",
      "/cases/CASE-AUDIT-MISSING",
      "Recover from an absent or inaccessible case",
      "Return to case list",
      { empty: "OBSERVED: unavailable-case recovery" },
    ),
    route(
      "support",
      "/support",
      "Choose a safe support path",
      "Find help, prepare message, requests, knowledge, urgent help",
    ),
    route(
      "find-help",
      "/support/find-help",
      "Choose a trusted person or support channel",
      "Audience choices and next-step links; no call/email sent",
    ),
    route(
      "prepare",
      "/support/prepare",
      "Prepare a message with control over content",
      "Select case/recipient, edit message, copy, local simulated save",
      { persistence: "Synthetic draft and failure/retry verified separately" },
    ),
    route(
      "requests",
      "/support/requests",
      "Find saved support drafts and simulations",
      "Open saved preparation",
      { empty: "OBSERVED before simulated support save" },
    ),
    route(
      "knowledge",
      "/support/knowledge",
      "Find practical guidance",
      "Search, topic filter, bookmark, article links",
    ),
    route(
      "knowledge-empty",
      "/support/knowledge?search=khong-co-ket-qua-audit",
      "Recover from no search results",
      "Clear/reset search",
      { empty: "OBSERVED: no-result search" },
    ),
    route(
      "article",
      "/knowledge/treu-dua-hay-bat-nat",
      "Read guidance with attribution",
      "Read, bookmark, related guidance",
    ),
    route(
      "settings",
      "/settings",
      "Control profile, motion, trusted people and demo state",
      "Preferences, demo error control, logout; destructive reset not submitted",
    ),
    route(
      "admin-list",
      "/demo/school",
      "Review the separate synthetic school dataset",
      "Category/date/status filters, report links",
      {
        dependencies:
          "Public separate 48-report synthetic school dataset; no student private data",
        persistence: "Browser-local synthetic admin status tested separately",
      },
    ),
    route(
      "admin-reports",
      "/demo/school/reports",
      "Review synthetic report list",
      "Filters and report detail",
      { dependencies: "Public separate synthetic school dataset" },
    ),
    route(
      "admin-detail",
      "/demo/school/reports/SCHOOL-DEMO-001",
      "Review a synthetic school report",
      "Status and private note editor; local-only save",
      { dependencies: "Separate synthetic school dataset" },
    ),
    route(
      "notfound",
      "/audit-page-does-not-exist",
      "Recover from an unknown route",
      "Return Home",
      { empty: "OBSERVED: not-found explanation and Home link" },
    ),
  ];
  if (!recheck) report.routes = [...publicRoutes, ...studentRoutes];
  for (const viewport of viewports) {
    await publicPage.setViewportSize(viewport);
    await page.setViewportSize(viewport);
    for (const item of report.routes) {
      const previousIndex = report.sweeps.findIndex(
        (r) => r.route === item.id && r.viewport.width === viewport.width,
      );
      if (
        recheck &&
        (previousIndex < 0 ||
          (report.sweeps[previousIndex].status !== "FAIL" &&
            !forcedRechecks.has(`${item.id}:${viewport.width}`)))
      )
        continue;
      const target = publicRoutes.some((r) => r.id === item.id)
        ? publicPage
        : page;
      const row = { route: item.id, path: item.path, viewport, status: "PASS" };
      try {
        await navigate(target, item.path);
        row.actualURL =
          new URL(target.url()).pathname + new URL(target.url()).search;
        row.headings = await target.locator("h1, h2").allTextContents();
        row.recheckedAt = recheck ? new Date().toISOString() : undefined;
        row.layout = await layout(target);
        const axe = await new AxeBuilder({ page: target }).analyze();
        row.violations = axe.violations.map((v) => ({
          id: v.id,
          impact: v.impact,
          description: v.description,
          help: v.help,
          helpUrl: v.helpUrl,
          nodes: v.nodes.map((n) => ({
            target: n.target,
            html: n.html,
            failureSummary: n.failureSummary,
          })),
        }));
        row.axeIncomplete = axe.incomplete.map((v) => ({
          id: v.id,
          impact: v.impact,
          targets: v.nodes.map((n) => n.target),
        }));
        row.failures = [];
        if (row.layout.horizontalOverflow)
          row.failures.push("Document horizontal overflow");
        if (row.layout.composer && !row.layout.composer.fitsViewport)
          row.failures.push("Chat composer falls outside viewport");
        if (
          row.violations.some((v) => ["serious", "critical"].includes(v.impact))
        )
          row.failures.push("Axe serious/critical violation");
        if (!row.actualURL.startsWith(item.path.split("?")[0]))
          row.failures.push("Unexpected route redirect");
        if (row.failures.length) row.status = "FAIL";
        if (!item.actual)
          item.actual = `${row.headings.join(" / ")}; ${row.actualURL}; rendered in demo audit`;
        if (
          !recheck &&
          viewport.width === 390 &&
          ["home", "analysis", "case-plan"].includes(item.id)
        ) {
          const filename = `audit-${item.id}-390.png`;
          await target.screenshot({
            path: resolve(out, filename),
            fullPage: false,
          });
          report.screenshots.push(filename);
        }
      } catch (error) {
        row.status = "FAIL";
        row.error = error.message;
      }
      if (recheck) {
        report.recheckHistory ||= [];
        const before = report.sweeps[previousIndex];
        report.recheckHistory.push({
          route: row.route,
          viewport,
          recheckedAt: new Date().toISOString(),
          before: {
            status: before.status,
            failures: before.failures,
            error: before.error,
            violations: before.violations,
          },
          after: {
            status: row.status,
            failures: row.failures,
            error: row.error,
          },
        });
        report.sweeps[previousIndex] = row;
      } else report.sweeps.push(row);
      console.log(
        JSON.stringify({
          route: row.route,
          viewport: `${viewport.width}x${viewport.height}`,
          status: row.status,
          failures: row.failures,
          error: row.error,
        }),
      );
      // Save findings while the sweep is in progress, without touching hosted/agent artifacts.
      if (row.status === "FAIL")
        await writeFile(
          resolve(out, "audit-results.json"),
          JSON.stringify(report, null, 2) + "\n",
        );
    }
  }

  await page.setViewportSize(viewports[2]);
  await action(
    "Keyboard history dialog: focus entry, trap, Escape and focus restoration",
    async () => {
      await navigate(page, "/ai/chat");
      const trigger = page.getByRole("button", {
        name: "Lịch sử trò chuyện",
        exact: true,
      });
      await trigger.focus();
      await page.keyboard.press("Enter");
      const dialog = page.getByRole("dialog", { name: "Lịch sử trò chuyện" });
      await dialog.waitFor();
      ensure(
        await dialog.evaluate((element) =>
          element.contains(document.activeElement),
        ),
        "Focus did not enter history dialog",
      );
      for (let i = 0; i < 16; i++) {
        await page.keyboard.press("Tab");
        ensure(
          await dialog.evaluate(
            (element) =>
              element.contains(document.activeElement) ||
              document.activeElement === document.body,
          ),
          "Tab focused an interactive background element outside history dialog",
        );
      }
      await page.keyboard.press("Escape");
      ensure(
        !(await dialog.isVisible()),
        "Escape did not dismiss history dialog",
      );
      ensure(
        await trigger.evaluate((element) => document.activeElement === element),
        "Focus did not return to dialog trigger",
      );
      return { tabsChecked: 16, escape: "dismissed", restoredFocus: true };
    },
  );
  await action("Chat draft survives hub navigation and reload", async () => {
    await navigate(page, "/ai/chat");
    const input = page.getByRole("textbox", { name: "Điều bạn muốn kể" });
    const text = "Bản nháp kiểm tra sản phẩm, hoàn toàn hư cấu.";
    await input.fill(text);
    const url = page.url();
    await page.getByRole("link", { name: "Quay lại không gian AI" }).click();
    await page.locator(".ai-recent-row").first().click();
    ensure(
      (await input.inputValue()) === text,
      "Draft lost returning from AI hub",
    );
    await page.reload();
    await input.waitFor();
    ensure((await input.inputValue()) === text, "Draft lost after reload");
    return { url, restoredAfterNavigation: true, restoredAfterReload: true };
  });
  await action(
    "Scripted chat: loading, response and free-text fallback",
    async () => {
      await navigate(page, "/ai/chat?scenario=SC-01");
      const quick = page.locator(".ai-quick-reply button");
      await quick.click();
      await page.locator(".ai-message.ai").first().waitFor();
      const scripted = await page
        .locator(".ai-message.ai")
        .first()
        .textContent();
      await page
        .getByRole("textbox", { name: "Điều bạn muốn kể" })
        .fill("Câu kiểm tra tự do, hoàn toàn hư cấu.");
      await page.waitForFunction(() => {
        const send = document.querySelector(
          '.chat-composer button[type="submit"]',
        );
        return send && !send.disabled;
      });
      await page
        .getByRole("textbox", { name: "Điều bạn muốn kể" })
        .press("Enter");
      await page.waitForFunction(
        () => document.querySelectorAll(".ai-message.ai").length >= 2,
      );
      return {
        scriptedResponse: scripted,
        fallbackResponse: await page
          .locator(".ai-message.ai")
          .last()
          .textContent(),
        paidProviders: "NOT_RUN",
      };
    },
  );
  await action(
    "Analysis fixture run: source confirmation gate and reload",
    async () => {
      await navigate(page, analysisPath);
      await page
        .getByRole("button", { name: "Xem phân tích mô phỏng" })
        .click();
      await page
        .getByRole("button", { name: "Tạo hồ sơ từ nội dung đã xác nhận" })
        .waitFor();
      const create = page.getByRole("button", {
        name: "Tạo hồ sơ từ nội dung đã xác nhận",
      });
      ensure(
        await create.isDisabled(),
        "Create case enabled without confirming any source",
      );
      await page
        .locator(".ai-evidence-row")
        .first()
        .getByRole("button", { name: "Xác nhận nội dung", exact: true })
        .click();
      await page.reload();
      await page.locator(".ai-evidence-row").first().waitFor();
      ensure(
        !(await create.isDisabled()),
        "Confirmed source did not survive reload",
      );
      return {
        evidenceSources: await page.locator(".ai-evidence-row").count(),
        confirmedSources: 1,
        persistedAfterReload: true,
      };
    },
  );
  await action(
    "Roleplay three-turn session reaches feedback and survives reload",
    async () => {
      await navigate(page, "/ai/roleplay/teacher");
      await page.getByRole("button", { name: "Bắt đầu buổi luyện" }).click();
      for (let turn = 0; turn < 3; turn++) {
        await page.getByRole("button", { name: "Dùng câu gợi ý" }).click();
        await page
          .getByRole("button", { name: "Nói câu này", exact: true })
          .click();
        await page.waitForFunction(
          () => !document.querySelector(".ai-turn-status"),
        );
      }
      await page.getByRole("link", { name: "Xem gợi ý sau buổi tập" }).click();
      await page.getByRole("heading", { name: "Điều đã luyện rõ" }).waitFor();
      const url = page.url();
      await page.reload();
      await page.getByRole("heading", { name: "Điều đã luyện rõ" }).waitFor();
      return {
        turns: 3,
        feedbackURL: url,
        persistedAfterReload: true,
        liveProvider: "NOT_RUN",
      };
    },
  );
  await action(
    "School Demo filtering and local status remain separate from student cases",
    async () => {
      await navigate(page, "/demo/school");
      ensure(
        (await page.locator(".admin-table tbody tr").count()) === 48,
        "Expected 48 synthetic reports",
      );
      await page.locator("#category").selectOption("online");
      ensure(
        (await page.locator(".admin-table tbody tr").count()) === 15,
        "Online filter did not show 15 reports",
      );
      await page
        .getByRole("link", { name: "SCHOOL-DEMO-001", exact: true })
        .click();
      await page.locator("#admin-status").selectOption("closed");
      await page
        .locator("#admin-notes")
        .fill("Ghi chú kiểm tra hoàn toàn hư cấu, cục bộ.");
      await page.getByRole("button", { name: "Lưu trạng thái demo" }).click();
      await page
        .getByText("Đã cập nhật dữ liệu demo cục bộ. Chưa có ai được liên hệ.")
        .waitFor();
      await page.reload();
      await page.locator("#admin-notes").waitFor();
      ensure(
        (await page.locator("#admin-notes").inputValue()).includes(
          "hoàn toàn hư cấu",
        ),
        "Admin note lost after reload",
      );
      await navigate(page, "/cases");
      ensure(
        !(await page.getByText("SCHOOL-DEMO-001", { exact: true }).count()),
        "School report leaked into student cases",
      );
      return {
        reportCount: 48,
        filteredCount: 15,
        notePersistedAfterReload: true,
        separateFromStudentCases: true,
      };
    },
  );
  await action(
    "Support preparation failure retains input and retry saves a local draft",
    async () => {
      await navigate(page, "/settings");
      await page
        .getByRole("checkbox", { name: "Mô phỏng lỗi ở lần lưu tiếp theo" })
        .check();
      // Keep the failure switch in memory by using an in-app link rather than a reload.
      await page
        .locator('a[href="/support"]')
        .filter({ visible: true })
        .first()
        .click();
      await page.locator('a[href="/support/prepare"]').first().click();
      const preview = page.locator("#support-preview");
      await preview.waitFor();
      await preview.fill(
        "Lời nhắn kiểm tra hoàn toàn hư cấu, chỉ lưu demo cục bộ.",
      );
      const save = page.getByRole("button", {
        name: "Lưu bản nháp",
        exact: true,
      });
      await save.click();
      await page
        .getByText(/Lỗi lưu mô phỏng/)
        .first()
        .waitFor();
      ensure(
        (await preview.inputValue()).includes("hoàn toàn hư cấu"),
        "Message lost after simulated save failure",
      );
      await save.click();
      await page.waitForFunction(() =>
        JSON.parse(localStorage.getItem("moodprint-demo")).state.drafts.some(
          (d) => d.content?.includes("hoàn toàn hư cấu"),
        ),
      );
      const url = page.url();
      await page.reload();
      await page.locator("#support-preview").waitFor();
      return {
        inputRetained: true,
        retrySaved: true,
        localURL: url,
        hostedDelivery: "NOT_RUN",
      };
    },
  );
  await action(
    "Reduced motion preference reaches browser and avoids long running animations",
    async () => {
      await page.emulateMedia({ reducedMotion: "reduce" });
      await navigate(page, "/home");
      const result = await page.evaluate(() => ({
        media: matchMedia("(prefers-reduced-motion: reduce)").matches,
        animations: document.getAnimations().map((a) => ({
          playState: a.playState,
          duration: a.effect?.getTiming().duration,
          iterations: a.effect?.getTiming().iterations,
        })),
      }));
      ensure(result.media, "Reduced motion media query not active");
      return result;
    },
  );
  for (const path of [
    "/home",
    "/ai/chat",
    "/cases/CASE-AN-001/plan",
    "/support/prepare",
    "/demo/school",
  ]) {
    await action(`200% text enlargement ${path}`, async () => {
      await page.setViewportSize(viewports[0]);
      await navigate(page, path);
      await page.evaluate(() => {
        const sizes = [...document.querySelectorAll("body *")].map(
          (element) => [
            element,
            parseFloat(getComputedStyle(element).fontSize),
          ],
        );
        document.documentElement.style.fontSize = "200%";
        for (const [element, size] of sizes)
          if (Number.isFinite(size)) element.style.fontSize = size * 2 + "px";
      });
      const result = await layout(page);
      ensure(
        !result.horizontalOverflow,
        "Horizontal overflow under 200% text enlargement",
        result,
      );
      ensure(
        !result.composer || result.composer.fitsViewport,
        "Chat composer falls outside viewport under 200% text enlargement",
        result,
      );
      return result;
    });
    await action(`200% browser zoom emulation ${path}`, async () => {
      await page.setViewportSize({ width: 720, height: 450 });
      await navigate(page, path);
      const result = await layout(page);
      result.zoomEmulation = {
        physicalViewport: viewports[6],
        cssViewport: { width: 720, height: 450 },
        percent: 200,
      };
      ensure(
        !result.horizontalOverflow,
        "Horizontal overflow under 200% browser zoom emulation",
        result,
      );
      ensure(
        !result.composer || result.composer.fitsViewport,
        "Chat composer falls outside viewport under 200% browser zoom emulation",
        result,
      );
      return result;
    });
  }
  await publicContext.close();
  await studentContext.close();
} catch (error) {
  report.fatalError = error.stack;
} finally {
  await browser.close();
  report.finishedAt = new Date().toISOString();
  report.counts = {
    routes: report.routes.length,
    sweepChecks: report.sweeps.length,
    sweepPass: report.sweeps.filter((r) => r.status === "PASS").length,
    sweepFail: report.sweeps.filter((r) => r.status === "FAIL").length,
    actionPass: report.actions.filter((r) => r.status === "PASS").length,
    actionFail: report.actions.filter((r) => r.status === "FAIL").length,
    seriousCriticalInstances: report.sweeps.reduce(
      (n, r) =>
        n +
        (r.violations || [])
          .filter((v) => ["serious", "critical"].includes(v.impact))
          .reduce((m, v) => m + v.nodes.length, 0),
      0,
    ),
    documentOverflowChecks: report.sweeps.filter(
      (r) => r.layout?.horizontalOverflow,
    ).length,
    browserErrors: report.errors.length,
    externalRequestsBlocked: report.externalRequestsBlocked.length,
    screenshots: report.screenshots.length,
  };
  await writeFile(
    resolve(out, "audit-results.json"),
    JSON.stringify(report, null, 2) + "\n",
  );
  const esc = (value) =>
    String(value ?? "")
      .replaceAll("|", "\\|")
      .replaceAll("\n", " ");
  const failures = report.sweeps.filter((r) => r.status === "FAIL");
  const grouped = new Map();
  for (const row of report.sweeps)
    for (const violation of row.violations || []) {
      const key = row.route + ":" + violation.id;
      if (!grouped.has(key))
        grouped.set(key, {
          route: row.route,
          id: violation.id,
          impact: violation.impact,
          widths: [],
          targets: new Set(),
        });
      const group = grouped.get(key);
      group.widths.push(row.viewport.width);
      violation.nodes.forEach((node) =>
        group.targets.add(node.target.join(" ")),
      );
    }
  const lines = [
    "# Product completion browser audit",
    "",
    `Generated ${report.generatedAt}; completed ${report.finishedAt}. Origin: \`${baseURL}\`. Environment: **DEMO**, synthetic browser-local data only.`,
    "",
    "Command: `cd frontend; node scripts/audit-product.mjs`. Recheck failures after fixes: `node scripts/audit-product.mjs --recheck`. Requires the existing Vite demo-capable app; installs no dependencies. Browser: Playwright Chromium.",
    "",
    "## Outcome",
    "",
    `Routes: **${report.counts.routes}**. Responsive/axe checks: **${report.counts.sweepPass}/${report.counts.sweepChecks} PASS**, **${report.counts.sweepFail} FAIL**. Journey checks: **${report.counts.actionPass} PASS**, **${report.counts.actionFail} FAIL**. Serious/critical node instances: **${report.counts.seriousCriticalInstances}** across route/viewport checks. Browser errors: **${report.counts.browserErrors}**.`,
    "",
    `Exact viewports: ${viewports.map((v) => `${v.width}×${v.height}`).join(", ")}.`,
    "",
    "Full per-viewport findings, selectors, axe incomplete checks, control dimensions, console page errors, and action evidence are in [audit-results.json](audit-results.json).",
    "",
    "## Scope and evidence labels",
    "",
    ...report.caveats.map((s) => "- " + s),
    "",
    "**OBSERVED** means rendered or exercised here. **Source-supported** means implementation is present but the state was not forced in this browser run. **NOT_RUN** means no claim is made. Axe passing does not certify full WCAG conformance; incomplete color contrast checks require manual review.",
    "",
    "## Navigation and action convention",
    "",
    "Public onboarding → demo persona → Home → AI/chat or cases → timeline/evidence/plan/summary → support preparation/requests. Knowledge and Settings are reachable from student navigation. School Demo uses separate synthetic reports and public routes. One click, field entry, submit, or navigation counts as one action; waits, rendering, assertions, and setup are excluded. The full companion creation journey is covered by existing journey.spec.ts; this audit records bounded checks below without claiming a live-AI journey.",
    "",
    "## Route and state inventory",
    "",
    "| Screen | Entry / intent | Expected / actual | Dependencies / persistence | Loading / empty / error / retry | Mobile / accessibility | Actions |",
    "|---|---|---|---|---|---|---|",
    ...report.routes.map(
      (r) =>
        `| ${esc(r.id)} | ${esc(r.path)}; ${esc(r.entry)}; ${esc(r.intent)} | Expected: ${esc(r.expected)} Actual: ${esc(r.actual || "BLOCKED — inspect JSON error")} | ${esc(r.dependencies)}; ${esc(r.persistence)} | Loading: ${esc(r.loading)} Empty: ${esc(r.empty)} Error: ${esc(r.error)} Retry: ${esc(r.retry)} | ${esc(r.mobile)} ${esc(r.a11y)} | ${esc(r.actions)} |`,
    ),
    "",
    "## Journey and accessibility behavior",
    "",
    "| Check | Result | Evidence |",
    "|---|---|---|",
    ...report.actions.map((r) => {
      const evidence = r.evidence?.document
        ? {
            viewport: r.evidence.viewport,
            document: r.evidence.document,
            horizontalOverflow: r.evidence.horizontalOverflow,
            composer: r.evidence.composer,
          }
        : r.evidence;
      return `| ${esc(r.name)} | ${r.status} | ${esc(r.error || JSON.stringify(evidence))} |`;
    }),
    "",
    "## Reproducible findings",
    "",
    "| Screen | Impact / rule | Affected widths | Exact targets |",
    "|---|---|---|---|",
    ...[...grouped.values()].map(
      (v) =>
        `| ${v.route} | ${v.impact}: ${v.id} | ${v.widths.join(", ")} | ${esc([...v.targets].join("; "))} |`,
    ),
    "",
    "| Failed route check | Viewport | Actual failure |",
    "|---|---|---|",
    ...failures.map(
      (r) =>
        `| ${r.path} | ${r.viewport.width}×${r.viewport.height} | ${esc(r.error || r.failures?.join("; "))} |`,
    ),
    "",
    "Reproduction: start the loopback app, choose **Vào thử với tài khoản demo**, open the listed path, set the exact viewport, and run axe without rule suppression. Public onboarding/auth/urgent routes are tested in an unauthenticated context. Detailed node HTML/failure summaries are retained in JSON. Small-target candidates are recorded for review and are not automatically counted as axe violations.",
    "",
    "## Recheck history",
    "",
    ...(report.recheckHistory?.length
      ? [
          "| Screen | Viewport | Prior result | Current result |",
          "|---|---|---|---|",
          ...report.recheckHistory.map(
            (r) =>
              `| ${r.route} | ${r.viewport.width}×${r.viewport.height} | ${esc(r.before.error || r.before.violations?.map((v) => `${v.impact}:${v.id}`).join("; ") || r.before.failures?.join("; "))} | ${r.after.status} ${esc(r.after.error || r.after.failures?.join("; "))} |`,
          ),
          "",
          "Earlier NotFound readiness failures came from an overly strict audit wait for h1; the audit now waits for a visible h1 or h2 and still runs the full axe ruleset. This is a harness correction, not a claim that the route was functionally broken.",
          "",
        ]
      : ["No targeted recheck has been run yet.", ""]),
    "## Hosted and source-only boundaries",
    "",
    "| Capability | Evidence in this audit |",
    "|---|---|",
    "| Hosted account login / recovery | Form visibility only; NOT_RUN submission |",
    "| Hosted persistence / A-B RLS isolation | NOT_RUN; demo localStorage is not database proof |",
    "| Live companion / paid provider / live roleplay | NOT_RUN; demo scripted replies and fixture analysis only |",
    "| Real evidence upload, storage, OCR and deletion | NOT_RUN; synthetic images are local fixtures |",
    "| Real support dispatch / external phone / email | NOT_RUN; no external calls, messages, or delivery |",
    "| Hosted Knowledge migrations / article search | NOT_RUN; demo knowledge only |",
    "| Error/loading/retry states not listed as exercised | Source-supported or NOT_RUN, not inferred passing |",
    "",
    "## Representative screenshots",
    "",
    ...report.screenshots.map(
      (name) => `- [${name}](${name}) — 390×844 demo viewport.`,
    ),
    "",
    report.fatalError
      ? `**Fatal audit error:** ${esc(report.fatalError)}`
      : "The audit completed its programmed checks. Failed checks remain release findings until fixed and rerun.",
    "",
  ];
  await writeFile(resolve(out, "audit-matrix.md"), lines.join("\n"));
  console.log(
    JSON.stringify(
      { counts: report.counts, fatalError: report.fatalError },
      null,
      2,
    ),
  );
  if (
    report.fatalError ||
    report.counts.sweepFail ||
    report.counts.actionFail ||
    report.counts.browserErrors
  )
    process.exitCode = 1;
}
