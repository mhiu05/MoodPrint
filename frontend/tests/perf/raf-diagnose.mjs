// Diagnostic: which code schedules animation frames while an AI run is accepted.
import { chromium } from "@playwright/test";
import { createServer } from "node:http";
import { readFile } from "node:fs/promises";
import { extname, join, normalize } from "node:path";
const root = process.argv[2];
const types = { ".html": "text/html", ".js": "text/javascript", ".css": "text/css" };
const server = createServer(async (q, s) => {
  const p = normalize(decodeURIComponent(new URL(q.url, "http://x").pathname)).replace(/^\/+/, "");
  try { const b = await readFile(join(root, p || "index.html")); s.writeHead(200, { "Content-Type": types[extname(p)] || "text/html" }); s.end(b); }
  catch { s.writeHead(200, { "Content-Type": "text/html" }); s.end(await readFile(join(root, "index.html"))); }
}).listen(4183, "127.0.0.1");
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 390, height: 844 } });
if (process.argv[4]) await (await page.context().newCDPSession(page)).send("Emulation.setCPUThrottlingRate", { rate: Number(process.argv[4]) });
await page.addInitScript(() => {
  const counts = {}; window.__rafCallers = counts;
  const raf = window.requestAnimationFrame.bind(window);
  window.requestAnimationFrame = (cb) => { const line = (new Error().stack || "").split("\n")[2]?.trim() || "?"; counts[line] = (counts[line] || 0) + 1; return raf(cb); };
});
let release; const held = new Promise((r) => { release = r; });
await page.route("**/api/v1/**", async (route) => {
  const path = new URL(route.request().url()).pathname.replace("/api/v1", "");
  const m = route.request().method();
  const ok = (json, status = 200) => route.fulfill({ status, json });
  if (path === "/session") return ok({ userId: "1", alias: "An", ageBand: "adult", eligible: true, csrfToken: "c", timezone: "Asia/Bangkok", serverTime: "2026-10-23T08:00:00Z", features: { ai: true, matching: true, voice: false }, consents: { AI: { enabled: true, version: 1, policyVersion: "v1" }, MEM: { enabled: true, version: 1, policyVersion: "v1" }, MATCH: { enabled: true, version: 1, policyVersion: "v1" }, VOICE: { enabled: false, version: 1, policyVersion: "v1" } } });
  if (path === "/bots") return ok([{ botId: "may", name: "Mây", role: "L", description: "L", starters: [], avatarKey: "may" }]);
  if (path === "/ai/preferences") return ok({ historyEnabled: false, semanticMemoryEnabled: false, version: 1, policyVersion: "ai-data-v1", retentionDays: 30, historyAvailable: true, semanticMemoryAvailable: false });
  const t = { conversationId: "22222222-2222-4222-8222-222222222222", botId: "may", version: 1, persistent: false, messages: [], hasMoreMessages: false, activeRunId: null, activeRunVersion: null };
  if (path === "/ai/conversations") return m === "GET" ? ok([]) : ok(t, 201);
  if (path.endsWith("/messages")) return ok({ runId: "33333333-3333-4333-8333-333333333333", conversationId: t.conversationId, version: 2, runVersion: 1, eventsUrl: "/api/v1/ai/runs/33333333-3333-4333-8333-333333333333/events" }, 202);
  if (path.endsWith("/events")) { await held; return route.fulfill({ status: 500 }); }
  return ok([]);
});
await page.goto("http://127.0.0.1:4183/#/assistants/may?new=1");
await page.getByRole("textbox", { name: "Tin nhắn cho Mây" }).fill("Xin chào");
await page.getByRole("button", { name: "Gửi tin cho AI" }).click();
await page.waitForFunction(() => document.body.textContent.includes("Đang gửi") || document.querySelector("canvas"));
await page.waitForTimeout(Number(process.argv[3] || 400));
await page.evaluate(() => { for (const k of Object.keys(window.__rafCallers)) delete window.__rafCallers[k]; });
await page.waitForTimeout(1000);
console.log(JSON.stringify(await page.evaluate(() => window.__rafCallers), null, 1));
release(); await browser.close(); server.close();
