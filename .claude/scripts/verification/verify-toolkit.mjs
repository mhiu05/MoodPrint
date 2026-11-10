#!/usr/bin/env node
// Static toolkit verification: skills, settings, hooks, MCP config, symlinks, plugins.
// Usage (from the project root): node .claude/scripts/verification/verify-toolkit.mjs
import { spawnSync } from "node:child_process";
import { existsSync, lstatSync, readdirSync, readFileSync, realpathSync } from "node:fs";
import { join, resolve } from "node:path";

const root = resolve(process.cwd());
let fails = 0;
const ok = (cond, msg) => {
  console.log(`${cond ? "PASS" : "FAIL"} ${msg}`);
  if (!cond) fails++;
};

const skillsDir = join(root, ".claude/skills");
const names = new Map();
for (const d of readdirSync(skillsDir)) {
  const p = join(skillsDir, d);
  try {
    realpathSync(p);
  } catch {
    ok(false, `skill ${d}: broken symlink`);
    continue;
  }
  if (lstatSync(p).isSymbolicLink()) console.log(`WARN skill ${d} is a symlink (not self-contained)`);
  const f = join(p, "SKILL.md");
  if (!existsSync(f)) {
    ok(false, `skill ${d}: SKILL.md missing`);
    continue;
  }
  const fm = readFileSync(f, "utf8").replace(/\r/g, "").match(/^---\n([\s\S]*?)\n---/);
  const name = fm?.[1].match(/^name:\s*(.+)$/m)?.[1].trim();
  ok(Boolean(fm && name && /^description:/m.test(fm[1])), `skill ${d}: frontmatter has name + description`);
  ok(name === d, `skill ${d}: folder name matches frontmatter name`);
  ok(!names.has(name), `skill name unique: ${name}`);
  names.set(name, d);
}

const settings = JSON.parse(readFileSync(join(root, ".claude/settings.json"), "utf8"));
ok(true, ".claude/settings.json parses");
const cmds = Object.values(settings.hooks ?? {}).flatMap((groups) =>
  groups.flatMap((g) => g.hooks.map((h) => `${g.matcher ?? ""}|${h.command}`)),
);
const eventCmds = Object.entries(settings.hooks ?? {}).flatMap(([ev, groups]) =>
  groups.flatMap((g) => g.hooks.map((h) => `${ev}|${g.matcher ?? ""}|${h.command}`)),
);
ok(new Set(eventCmds).size === eventCmds.length, `no duplicate hooks (${cmds.length} registered)`);
ok(existsSync(join(root, ".claude/skills/impeccable/scripts/impeccable")), "impeccable launcher exists");

const mcpText = readFileSync(join(root, ".mcp.json"), "utf8");
const mcp = JSON.parse(mcpText);
ok(Boolean(mcp.mcpServers?.promptfoo), ".mcp.json declares promptfoo");
ok(!/(sk-[A-Za-z0-9]{20,}|Bearer [A-Za-z0-9]{20,})/.test(mcpText), ".mcp.json has no inline secrets");

const pl = spawnSync("claude", ["plugin", "list"], { encoding: "utf8", shell: process.platform === "win32" }).stdout ?? "";
for (const id of ["superpowers@anthropic-plugin-directory", "promptfoo@promptfoo", "openai-developers@openai-developers"]) {
  const i = pl.indexOf(`❯ ${id}`);
  ok(i >= 0 && pl.slice(i, i + 200).includes("enabled"), `plugin enabled: ${id}`);
}
console.log(fails ? `\n${fails} check(s) failed` : "\nAll static checks passed");
process.exit(fails ? 1 : 0);
