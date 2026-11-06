# MoodPrint Cursor Toolkit Installation Manifest

Checked: 2026-10-29

Repository: `E:\MoodPrint`
Host: Windows PowerShell; Cursor Agent; Node.js 24.13.0; Python 3.12; uv available.

This mirrors the Codex (`.agents` / `~/.codex`) and Claude (`.claude` / `.mcp.json`) toolkits so Cursor Agent can use the same skills and MCP servers.

## Sources mapped into Cursor

| Source | Components | Cursor integration | Location | Status |
|---|---|---|---|---|
| Codex / Claude skills | Superpowers (12), Vercel skills, Agent Browser, DeepEval, UI UX Pro Max, Supabase skills | Junctions from `.agents/skills` / `.claude/skills` | `.cursor/skills/<name>/` | PASS |
| Claude-only skill | `vercel-composition-patterns` | Junction (+ shared junction under `.agents/skills`) | `.cursor/skills/vercel-composition-patterns/` | PASS |
| Impeccable | skill, engine, 4 agents | `impeccable@4.7.0 install --providers=cursor --scope=project` (engine/CLI reports 4.8.0) | `.cursor/skills/impeccable/`, `.cursor/agents/impeccable-*.md` | PASS |
| Claude agents | `browser-qa`, `ai-evaluator` | Copied | `.cursor/agents/` | PASS |
| Claude `.mcp.json` + Codex `mcp_servers` | supabase, promptfoo, openaiDeveloperDocs, playwright, github, aws-mcp | Project MCP config | `.cursor/mcp.json` | PASS |

Skipped (Codex-only / disabled): `node_repl`, `mongodb-atlas` (disabled), `supabase-warehouse` (disabled).

## MCP servers (`.cursor/mcp.json`)

| Server | Transport | Notes |
|---|---|---|
| `supabase` | HTTP | Same MoodPrint project_ref as Claude/Codex; approve OAuth in Cursor Customize → MCP |
| `promptfoo` | stdio | `npx --yes promptfoo@0.125.1 mcp --transport stdio` |
| `openaiDeveloperDocs` | HTTP | `https://developers.openai.com/mcp` (no auth) |
| `playwright` | stdio | `npx @playwright/mcp@latest` (from Codex user MCP) |
| `github` | HTTP | Needs `GITHUB_PERSONAL_ACCESS_TOKEN` in the environment |
| `aws-mcp` | stdio | `uvx mcp-proxy-for-aws@latest …`; `AWS_MCP_PROXY_PROFILES=moodprint` |

## Skills already discoverable

Cursor also auto-loads `.agents/skills/` and `.claude/skills/`. The `.cursor/skills` junctions make the selected toolkit explicit for Cursor-native discovery and Cloud/project scoping.

## Reinstall / check

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .cursor/scripts/install-toolkit.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .cursor/scripts/install-toolkit.ps1 -Check
node .agents/scripts/verify-promptfoo-mcp.mjs
```

After changing MCP config: reload Cursor MCP (Customize → MCP) or restart Cursor, then approve OAuth / confirm env tokens.

## Uninstall

Delete `.cursor/` (gitignored). Junctions do not delete the underlying `.agents` / `.claude` skill trees.
