#!/usr/bin/env node
// Idempotent restore of the Claude Code toolkit described in .claude/config/toolkit.json.
// Usage (from the project root): node .claude/scripts/bootstrap/bootstrap.mjs [--check]
//   --check  report only, change nothing.
import { spawnSync } from "node:child_process";
import { existsSync, readFileSync, rmSync } from "node:fs";
import { join, resolve } from "node:path";

const check = process.argv.includes("--check");
const root = resolve(process.cwd());
const cfg = JSON.parse(readFileSync(join(root, ".claude/config/toolkit.json"), "utf8"));
const win = process.platform === "win32";
const results = [];
const note = (status, what, detail = "") => {
  results.push(status);
  console.log(`[${status}] ${what}${detail ? ` - ${detail}` : ""}`);
};
const run = (cmd, args) =>
  spawnSync(cmd, args, { cwd: root, encoding: "utf8", shell: win, stdio: ["ignore", "pipe", "pipe"] });
const has = (cmd) => run(cmd, ["--version"]).status === 0;

// 1. prerequisites
const [maj, min] = process.versions.node.split(".").map(Number);
maj > 22 || (maj === 22 && min >= 22)
  ? note("OK", "node", process.versions.node)
  : note("FAIL", "node >= 22.22 required (promptfoo)", process.versions.node);
for (const [cmd, required] of [["claude", true], ["git", true], ["npx", true], ["uv", false], ["python", false]]) {
  has(cmd) ? note("OK", cmd) : note(required ? "FAIL" : "WARN", `${cmd} not found`, required ? "required" : "needed for DeepEval/backend");
}
if (results.includes("FAIL")) process.exit(1);

// 2. native plugins (declared in .claude/settings.json; installed explicitly so no trust prompt is needed later)
const installed = run("claude", ["plugin", "list"]).stdout ?? "";
const marketplaces = run("claude", ["plugin", "marketplace", "list"]).stdout ?? "";
for (const [name, src] of Object.entries(cfg.plugins.marketplaces)) {
  if (marketplaces.includes(`❯ ${name}`)) note("OK", `marketplace ${name}`);
  else if (check) note("MISSING", `marketplace ${name}`);
  else {
    const r = run("claude", ["plugin", "marketplace", "add", src.repo, "--scope", cfg.plugins.scope]);
    note(r.status === 0 ? "INSTALLED" : "FAIL", `marketplace ${name}`, r.status === 0 ? "" : r.stderr.trim());
  }
}
for (const id of cfg.plugins.install) {
  if (installed.includes(`❯ ${id}`)) note("OK", `plugin ${id}`);
  else if (check) note("MISSING", `plugin ${id}`);
  else {
    const r = run("claude", ["plugin", "install", id, "--scope", cfg.plugins.scope]);
    note(r.status === 0 ? "INSTALLED" : "FAIL", `plugin ${id}`, r.status === 0 ? "" : (r.stdout + r.stderr).trim());
  }
}

// 3. project-local skills under .claude/skills/
for (const [name, s] of Object.entries(cfg.skills)) {
  const dir = join(root, ".claude/skills", name);
  if (existsSync(join(dir, "SKILL.md"))) { note("OK", `skill ${name}`); continue; }
  if (check) { note("MISSING", `skill ${name}`); continue; }
  let r;
  if (s.installer === "skills") {
    r = run("npx", ["--yes", "skills", "add", s.source, "-s", s.skill, "-a", "claude-code", "--copy", "-y"]);
  } else {
    const c = cfg.cli[s.cli];
    r = run("npx", ["--yes", `${c.npm}@${c.version}`, ...c.installArgs.split(" ")]);
    for (const extra of s.removeExtras ?? []) rmSync(join(root, ".claude/skills", extra), { recursive: true, force: true });
  }
  note(existsSync(join(dir, "SKILL.md")) ? "INSTALLED" : "FAIL", `skill ${name}`, r.status === 0 ? "" : (r.stderr ?? "").trim().slice(0, 200));
}

// 4. CLI tools
const ab = cfg.cli["agent-browser"];
if (has("agent-browser")) note("OK", "agent-browser CLI", run("agent-browser", ["--version"]).stdout.trim());
else if (check) note("MISSING", "agent-browser CLI");
else {
  const r = run("npm", ["install", "-g", `${ab.npm}@${ab.version}`]);
  note(r.status === 0 ? "INSTALLED" : "FAIL", "agent-browser CLI", r.status === 0 ? "" : r.stderr.trim().slice(0, 200));
}
if (!check && has("agent-browser")) {
  const r = run("agent-browser", ["install"]);
  note(r.status === 0 ? "OK" : "WARN", "agent-browser browser runtime (agent-browser install)");
}
note("OK", `promptfoo ${cfg.cli.promptfoo.version}`, "resolved on demand through the pinned npx command in .mcp.json");
note("OK", `deepeval ${cfg.cli.deepeval.version}`, "run with: uv run --no-project --python 3.12 --with deepeval==" + cfg.cli.deepeval.version);

// 5. MCP + hooks configuration
const mcp = JSON.parse(readFileSync(join(root, ".mcp.json"), "utf8")).mcpServers ?? {};
for (const s of cfg.mcpServers) note(mcp[s] ? "OK" : "FAIL", `.mcp.json server ${s}`);
const settings = JSON.parse(readFileSync(join(root, ".claude/settings.json"), "utf8"));
note(settings.hooks?.PostToolUse ? "OK" : "FAIL", "hooks in .claude/settings.json", Object.keys(settings.hooks ?? {}).join(","));

console.log("\nManual steps bootstrap cannot do:");
console.log("- Run `claude` in this folder once; approve the project MCP servers (/mcp) and plugin trust prompts.");
console.log("- Supabase MCP needs browser OAuth; providers/judges need keys such as OPENAI_API_KEY in your environment (never committed).");
process.exit(results.includes("FAIL") ? 1 : 0);
