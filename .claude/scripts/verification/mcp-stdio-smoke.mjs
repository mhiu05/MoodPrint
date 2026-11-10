#!/usr/bin/env node
// Read-only MCP stdio smoke test: initialize + tools/list against a server declared in .mcp.json.
// Usage: node .claude/scripts/verification/mcp-stdio-smoke.mjs <server-name> [timeout-seconds]
import { spawn } from "node:child_process";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const [name, timeoutArg] = process.argv.slice(2);
const timeoutMs = Number(timeoutArg || 240) * 1000;
if (!name) {
  console.error("usage: mcp-stdio-smoke.mjs <server-name> [timeout-seconds]");
  process.exit(2);
}
const cfg = JSON.parse(readFileSync(resolve(".mcp.json"), "utf8")).mcpServers?.[name];
if (!cfg || (cfg.type && cfg.type !== "stdio")) {
  console.error(`server "${name}" not found or not a stdio server in .mcp.json`);
  process.exit(2);
}
const child = spawn(cfg.command, cfg.args ?? [], {
  stdio: ["pipe", "pipe", "inherit"],
  shell: process.platform === "win32",
  env: { ...process.env, ...(cfg.env ?? {}) },
});
let buf = "";
const pending = new Map();
child.stdout.on("data", (d) => {
  buf += d;
  let i;
  while ((i = buf.indexOf("\n")) >= 0) {
    const line = buf.slice(0, i).trim();
    buf = buf.slice(i + 1);
    if (!line.startsWith("{")) continue;
    try {
      const m = JSON.parse(line);
      pending.get(m.id)?.(m);
    } catch {}
  }
});
const send = (id, method, params) =>
  new Promise((res) => {
    pending.set(id, res);
    child.stdin.write(JSON.stringify({ jsonrpc: "2.0", id, method, params }) + "\n");
  });
const timer = setTimeout(() => {
  console.error("TIMEOUT waiting for MCP server");
  child.kill();
  process.exit(1);
}, timeoutMs);

const init = await send(1, "initialize", {
  protocolVersion: "2025-06-18",
  capabilities: {},
  clientInfo: { name: "toolkit-smoke", version: "1.0.0" },
});
child.stdin.write(JSON.stringify({ jsonrpc: "2.0", method: "notifications/initialized" }) + "\n");
const tools = await send(2, "tools/list", {});
clearTimeout(timer);
const list = tools.result?.tools ?? [];
console.log(`server: ${init.result?.serverInfo?.name} ${init.result?.serverInfo?.version}`);
console.log(`tools (${list.length}): ${list.map((t) => t.name).join(", ")}`);
child.kill();
process.exit(list.length > 0 ? 0 : 1);
