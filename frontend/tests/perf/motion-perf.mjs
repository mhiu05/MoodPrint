// Paired production-build motion/performance protocol (docs/ux-redesign/17 V-MOTION-PERF).
// Usage: node tests/perf/motion-perf.mjs <baselineDist> <candidateDist> <out.json> [runs]
// Serves both builds locally, mocks every API call with synthetic fixtures (no backend,
// no provider, no real data), throttles the CPU 4x at a 390x844 phone viewport, and
// alternates baseline/candidate runs after one warm-up each. Raw samples are written out.
import { chromium } from "@playwright/test";
import { createServer } from "node:http";
import { readFile, writeFile } from "node:fs/promises";
import { extname, join, normalize } from "node:path";

const [baselineDir, candidateDir, outFile, runsArg] = process.argv.slice(2);
if (!baselineDir || !candidateDir || !outFile) throw new Error("usage: motion-perf.mjs <baseline> <candidate> <out.json> [runs]");
const RUNS = Number(runsArg || 7);
const TYPES = { ".html": "text/html", ".js": "text/javascript", ".css": "text/css", ".svg": "image/svg+xml", ".png": "image/png", ".json": "application/json" };

function serve(root, port) {
  return new Promise((resolve) => {
    const server = createServer(async (request, response) => {
      const path = normalize(decodeURIComponent(new URL(request.url, "http://x").pathname)).replace(/^([/\\])+/, "");
      const file = join(root, path || "index.html");
      try {
        const body = await readFile(file.startsWith(normalize(root)) ? file : join(root, "index.html"));
        response.writeHead(200, { "Content-Type": TYPES[extname(file)] || "application/octet-stream" });
        response.end(body);
      } catch {
        response.writeHead(200, { "Content-Type": "text/html" });
        response.end(await readFile(join(root, "index.html")));
      }
    }).listen(port, "127.0.0.1", () => resolve(server));
  });
}

const RUN = "33333333-3333-4333-8333-333333333333";
const CONV = "22222222-2222-4222-8222-222222222222";
const session = {
  userId: "11111111-1111-4111-8111-111111111111", alias: "An", ageBand: "adult", eligible: true, csrfToken: "csrf-perf",
  timezone: "Asia/Bangkok", serverTime: "2026-10-23T08:00:00Z", features: { ai: true, matching: true, voice: false },
  consents: { AI: { enabled: true, version: 1, policyVersion: "v1" }, MEM: { enabled: true, version: 1, policyVersion: "v1" },
    MATCH: { enabled: true, version: 1, policyVersion: "v1" }, VOICE: { enabled: false, version: 1, policyVersion: "v1" } },
};
const thread = { conversationId: CONV, botId: "may", version: 1, persistent: false, expiresAt: "2026-10-24T08:00:00Z", messages: [], hasMoreMessages: false, activeRunId: null, activeRunVersion: null };
const sse = (events) => events.map((event, index) => `id: ${index + 1}\ndata: ${JSON.stringify({ version: "ai-events-v1", seq: String(index + 1), type: event.type, data: event.data ?? {} })}\n\n`).join("");

const INSTRUMENT = () => {
  const perf = { layoutShift: 0, longTasks: [], raf: 0, clickAt: 0, sendingAt: 0, eventsAt: 0, finalChunkAt: 0, bubbleAt: 0, headingAt: 0 };
  window.__perf = perf;
  new PerformanceObserver((list) => { for (const entry of list.getEntries()) if (!entry.hadRecentInput) perf.layoutShift += entry.value; }).observe({ type: "layout-shift", buffered: true });
  perf.longTaskStarts = [];
  new PerformanceObserver((list) => { for (const entry of list.getEntries()) { perf.longTasks.push(Math.round(entry.duration)); perf.longTaskStarts.push(Math.round(entry.startTime)); } }).observe({ type: "longtask", buffered: true });
  const raf = window.requestAnimationFrame.bind(window);
  window.requestAnimationFrame = (callback) => raf((time) => { perf.raf += 1; callback(time); });
  const fetcher = window.fetch.bind(window);
  window.fetch = async (...args) => {
    const response = await fetcher(...args);
    if (String(args[0]).includes("/events")) perf.eventsAt = performance.now();
    return response;
  };
  // The moment the stream chunk carrying the final event is handed to the app.
  const read = ReadableStreamDefaultReader.prototype.read;
  ReadableStreamDefaultReader.prototype.read = function (...args) {
    return read.apply(this, args).then((result) => {
      if (result.value && !perf.finalChunkAt && new TextDecoder().decode(result.value).includes('"type":"final"')) perf.finalChunkAt = performance.now();
      return result;
    });
  };
  document.addEventListener("pointerdown", () => { perf.clickAt = performance.now(); }, true);
  new MutationObserver(() => {
    const now = performance.now();
    if (!perf.sendingAt && document.body.textContent.includes("Đang gửi")) perf.sendingAt = now;
    if (!perf.bubbleAt && document.querySelector(".from-bot .chat-bubble")) perf.bubbleAt = now;
  }).observe(document, { childList: true, subtree: true, characterData: true });
};

async function measure(browser, baseURL, scenario, reducedMotion = "no-preference", blockOrb = false) {
  const context = await browser.newContext({ viewport: { width: 390, height: 844 }, reducedMotion });
  const page = await context.newPage();
  const cdp = await context.newCDPSession(page);
  await cdp.send("Emulation.setCPUThrottlingRate", { rate: 4 });
  await page.addInitScript(INSTRUMENT);
  // Arm control: motion allowed but the orb chunk unavailable (static icon fallback).
  if (blockOrb) await page.route(/ThinkingOrbVisual/, (route) => route.abort());
  let release;
  const held = new Promise((resolve) => { release = resolve; });
  await page.route("**/api/v1/**", async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname.replace("/api/v1", "");
    const json = (value, status = 200) => route.fulfill({ status, json: value });
    if (path === "/session") return json(session);
    if (path === "/bots") return json([{ botId: "may", name: "Mây", role: "Lắng nghe", description: "Lắng nghe.", starters: ["Hôm nay mình hơi mệt"], avatarKey: "may" }]);
    if (path === "/ai/preferences") return json({ historyEnabled: false, semanticMemoryEnabled: false, version: 1, policyVersion: "ai-data-v1", retentionDays: 30, historyAvailable: true, semanticMemoryAvailable: false });
    if (path === "/ai/conversations") return request.method() === "GET" ? json([]) : json(thread, 201);
    if (path === `/ai/conversations/${CONV}`) return json(thread);
    if (path === `/ai/conversations/${CONV}/messages`) return json({ runId: RUN, conversationId: CONV, version: 2, runVersion: 1, eventsUrl: `/api/v1/ai/runs/${RUN}/events` }, 202);
    if (path === `/ai/runs/${RUN}/events`) {
      await held;
      return route.fulfill({ contentType: "text/event-stream", body: sse([{ type: "progress" }, { type: "final", data: { text: "Mình nghe bạn đây.", cards: [] } }, { type: "completed" }]) });
    }
    if (["/proposals", "/memories", "/connections", "/connection-requests"].includes(path)) return json([]);
    if (path === "/social/summary") return json({ pendingIncomingRequests: 0, unreadConnections: 0, activityInvites: 0 });
    if (path === "/moods") return json([]);
    if (path === "/moods/summary") return json({ from: "2026-10-17", to: "2026-10-23", count: 0, mean: null, min: null, max: null, insightAvailable: false, buckets: [] });
    return json({ error: { code: "NOT_FOUND", message: "Missing fixture" } }, 404);
  });
  const result = {};
  if (scenario === "ai") {
    await page.goto(`${baseURL}/#/assistants/may?new=1`);
    const box = page.getByRole("textbox", { name: "Tin nhắn cho Mây" });
    await box.waitFor();
    await box.fill("Xin chào");
    await page.waitForTimeout(300);
    await page.evaluate(() => { window.__perf.layoutShift = 0; window.__perf.longTasks = []; });
    await page.getByRole("button", { name: "Gửi tin cho AI" }).click();
    await page.waitForFunction(() => window.__perf.sendingAt > 0);
    await page.waitForTimeout(400); // accepted run, events still held
    const rafStart = await page.evaluate(() => window.__perf.raf);
    await page.waitForTimeout(1000);
    const acceptedWindow = await page.evaluate((start) => ({ raf: window.__perf.raf - start, canvases: document.querySelectorAll("canvas").length }), rafStart);
    release();
    await page.waitForFunction(() => window.__perf.bubbleAt > 0, null, { timeout: 30000 });
    await page.waitForTimeout(500);
    const after = await page.evaluate(() => window.__perf.raf);
    await page.waitForTimeout(1000);
    const perf = await page.evaluate(() => window.__perf);
    // A long task is attributed to the orb when it starts within 150ms after its chunk arrived.
    const orbChunkEnd = await page.evaluate(() => performance.getEntriesByType("resource").find((entry) => entry.name.includes("ThinkingOrbVisual"))?.responseEnd ?? null);
    const orbAttributable = orbChunkEnd === null ? [] : perf.longTasks.filter((_, index) => perf.longTaskStarts[index] >= orbChunkEnd - 5 && perf.longTaskStarts[index] <= orbChunkEnd + 150);
    Object.assign(result, {
      orbChunkEnd: orbChunkEnd === null ? null : Math.round(orbChunkEnd),
      orbAttributableLongTasks: orbAttributable,
      statusCommitMs: +(perf.sendingAt - perf.clickAt).toFixed(1),
      finalRenderMs: +(perf.bubbleAt - perf.eventsAt).toFixed(1),
      finalChunkRenderMs: +(perf.bubbleAt - perf.finalChunkAt).toFixed(1),
      rafPerSecAccepted: acceptedWindow.raf,
      canvasesAccepted: acceptedWindow.canvases,
      rafPerSecAfterFinal: perf.raf - after,
      cls: +perf.layoutShift.toFixed(4),
      longTasks: perf.longTasks,
    });
  } else {
    await page.goto(`${baseURL}/#/messages`);
    await page.getByRole("heading", { level: 1, name: "Tin nhắn" }).waitFor();
    await page.waitForTimeout(300);
    await page.evaluate(() => {
      window.__perf.layoutShift = 0; window.__perf.longTasks = [];
      new MutationObserver(() => {
        const heading = [...document.querySelectorAll("h1")].find((element) => element.getClientRects().length && /chia sẻ|kể gì/.test(element.textContent));
        if (heading && !window.__perf.headingAt) window.__perf.headingAt = performance.now();
      }).observe(document, { childList: true, subtree: true });
    });
    await page.getByRole("navigation", { name: "Điều hướng chính" }).getByRole("link", { name: "Trợ lý" }).click();
    await page.waitForFunction(() => window.__perf.headingAt > 0, null, { timeout: 30000 });
    await page.waitForTimeout(600);
    const perf = await page.evaluate(() => window.__perf);
    Object.assign(result, { routeHeadingMs: +(perf.headingAt - perf.clickAt).toFixed(1), cls: +perf.layoutShift.toFixed(4), longTasks: perf.longTasks });
  }
  await context.close();
  return result;
}

const median = (values) => { const sorted = [...values].sort((a, b) => a - b); const mid = sorted.length >> 1; return sorted.length % 2 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2; };
const summarize = (samples, key) => {
  const values = samples.map((sample) => (Array.isArray(sample[key]) ? sample[key].length : sample[key]));
  return { median: median(values), min: Math.min(...values), max: Math.max(...values), samples: values };
};

const [baseline, candidate] = await Promise.all([serve(baselineDir, 4181), serve(candidateDir, 4182)]);
const browser = await chromium.launch(process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH ? { executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH } : {});
// "candidateReduced" is the same candidate build under prefers-reduced-motion (no orb),
// isolating what the animated status itself costs.
const builds = {
  baseline: ["http://127.0.0.1:4181", "no-preference"],
  candidate: ["http://127.0.0.1:4182", "no-preference"],
  candidateReduced: ["http://127.0.0.1:4182", "reduce"],
  candidateNoOrb: ["http://127.0.0.1:4182", "no-preference", true],
};
const LABELS = Object.keys(builds);
const raw = Object.fromEntries(LABELS.map((label) => [label, { ai: [], route: [] }]));
for (const scenario of ["ai", "route"]) {
  for (const label of LABELS) await measure(browser, builds[label][0], scenario, builds[label][1], builds[label][2]); // warm-up, discarded
  for (let run = 0; run < RUNS; run += 1) {
    const order = run % 2 ? [...LABELS].reverse() : LABELS;
    for (const label of order) raw[label][scenario].push(await measure(browser, builds[label][0], scenario, builds[label][1], builds[label][2]));
  }
}
await browser.close();
baseline.close();
candidate.close();
const report = { protocol: { viewport: "390x844", cpuThrottle: 4, runsPerBuild: RUNS, warmUp: 1, order: "alternating", browser: "Playwright Chromium headless", fixtures: "synthetic API, no backend/provider", arms: builds }, summary: {}, raw };
for (const build of LABELS) {
  report.summary[build] = {
    ai: Object.fromEntries(["statusCommitMs", "finalRenderMs", "finalChunkRenderMs", "rafPerSecAccepted", "canvasesAccepted", "rafPerSecAfterFinal", "cls", "longTasks", "orbAttributableLongTasks"].map((key) => [key, summarize(raw[build].ai, key)])),
    route: Object.fromEntries(["routeHeadingMs", "cls", "longTasks"].map((key) => [key, summarize(raw[build].route, key)])),
  };
}
await writeFile(outFile, JSON.stringify(report, null, 1));
console.log(JSON.stringify(report.summary, (key, value) => (key === "samples" ? value.join(",") : value), 1));
