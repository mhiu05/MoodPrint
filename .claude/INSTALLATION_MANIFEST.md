# Claude Code Toolkit — Installation Manifest

Generated 2026-10-27 on Windows 11 (Git Bash + PowerShell), Claude Code 2.1.310, Node 24.13.0, npm 11.6.2, Python 3.12.13, uv 0.11.14.

## Detected project stack
- Frontend: React 19 + Vite 7 + TypeScript 5.9 (`frontend/`), Vitest, Playwright (+ axe), GSAP. No Tailwind.
- Backend: FastAPI + SQLAlchemy/Alembic + PostgreSQL (`backend/`, uv-managed, Python 3.12), `openai-agents==0.24.0`.
- Database: Supabase/PostgreSQL (Supabase MCP already in `.mcp.json`).
- AI: OpenAI Agents SDK, existing eval harness in `backend/evals/`.
- CI: `.github/workflows/verify.yml`, `deploy-staging.yml`.
- Pre-existing, untouched: `AGENTS.md`, `.agents/`, `.codex/`, `skills-lock.json` (Codex side).

## Sources
| Source | Components | Integration type | Location | Version | Verification | Status |
|---|---|---|---|---|---|---|
| 1 Superpowers | 15 skills, SessionStart hook | Native plugin (project scope) | `superpowers@anthropic-plugin-directory`; declared in `.claude/settings.json` | 6.4.2 | `claude plugin list` enabled; `claude plugin details` lists brainstorming, writing-plans, executing-plans, test-driven-development, systematic-debugging, requesting-code-review, dispatching-parallel-agents, verification-before-completion, finishing-a-development-branch. Not yet invoked in a live session (plugins load on next session start). | PARTIAL |
| 2 Vercel Agent Skills | `vercel-react-best-practices` (upstream rename of react-best-practices), `vercel-composition-patterns`, `web-design-guidelines` | Project skills, copied | `.claude/skills/` | upstream main @ 2026-10-14 (hashes in `skills-lock.json`) | frontmatter/name/duplicate check passed (`verify-toolkit.mjs`). Deploy, React Native, view-transitions, optimize skills skipped as not applicable. | PASS |
| 3 Impeccable | skill, 4 `impeccable-*` agents, engine binary, 3 hooks | `npx impeccable install --providers=claude --scope=project` | `.claude/skills/impeccable/`, `.claude/agents/impeccable-*.md`, hooks in `.claude/settings.json` | skill 4.7.0, engine 0.1.16 | files, launcher, settings JSON and hook uniqueness verified. The launcher was **not executed**: the auto-mode classifier denied the run, so `detect`/`hook` behavior is unverified. | PARTIAL |
| 4 UI UX Pro Max | design knowledge base + search scripts | `npx ui-ux-pro-max-cli@2.15.0 init --ai claude --offline` (deprecated `uipro-cli` not used) | `.claude/skills/ui-ux-pro-max/` | 2.15.0 | `scripts/search.py --design-system` and `--domain style` returned results. Extra skills the CLI added (banner-design, brand, design, design-system, slides, ui-styling) removed as unrelated. | PASS |
| 5 Agent Browser | discovery skill + global CLI | Skill via `skills add vercel-labs/agent-browser`; CLI reused | `.claude/skills/agent-browser/`; CLI global | CLI 0.39.2 installed (0.39.4 is latest and what the manifest pins); Chrome 156.0.8078.47 | open, snapshot -i, fill, click, get text, screenshot, close all succeeded on a local HTML page. Skill is a stub that loads live docs via `agent-browser skills get core`; its upstream frontmatter has `hidden: true`, so check it is auto-discoverable in a fresh session. | PASS |
| 6 DeepEval | upstream-maintained `deepeval` skill + library | Skill copied from `confident-ai/deepeval`; library via uv, not added to app manifests | `.claude/skills/deepeval/` | deepeval 4.3.1 | `deepeval-smoke.py` ran ExactMatchMetric pass/fail cases (no network/LLM). `deepeval-otel`/`deepeval-tracing` skills not installed (Confident AI cloud tracing, not needed). | PASS |
| 7 Promptfoo | plugin (4 skills), CLI, MCP server | Native plugin + pinned npx CLI + project MCP | plugin `promptfoo@promptfoo`; `.mcp.json` server `promptfoo` | plugin 0.1.5, CLI 0.125.1 | `--version`, `validate config`, local `eval` with `echo` provider (1/1 pass). MCP stdio handshake: 14 tools listed. Claude's own `claude mcp list` shows the server as pending approval (see Blockers). | PARTIAL |
| 8 OpenAI Plugins | `openai-developers` plugin (6 skills + bundled docs MCP) | Native plugin | `openai-developers@openai-developers` | commit 3c5c0debdec2 | `claude mcp list`: `plugin:openai-developers:openaiDeveloperDocs` Connected; tools/list returned 5 tools; `search_openai_docs` returned hits. | PASS |

**Substitution:** `openai/plugins` is a Codex plugin collection. It was replaced by the Claude-compatible `openai/openai-developers-for-claude`.

## Configuration summary
- Native plugins: superpowers, promptfoo, openai-developers (scope `project`, in `.claude/settings.json`; marketplaces `promptfoo`, `openai-developers` under `extraKnownMarketplaces`).
- MCP (`.mcp.json`): `supabase` (pre-existing, HTTP, OAuth), `promptfoo` (`npx --yes promptfoo@0.125.1 mcp --transport stdio`). OpenAI Docs MCP comes from the plugin, not duplicated.
- Hooks (`.claude/settings.json`): Impeccable `SessionStart`, `PostToolUse` (`Edit|Write`), `Stop`. The Superpowers plugin registers its own `SessionStart`. The installer wrote the hooks into `settings.local.json` in plugin-hooks format; they were moved into the shared `settings.json` and the local file removed.
- Subagents: `browser-qa`, `ai-evaluator` (new), 4 `impeccable-*` (from installer).
- Scripts: `.claude/scripts/bootstrap/bootstrap.{mjs,ps1,sh}`, `.claude/scripts/verification/{verify-toolkit.mjs,mcp-stdio-smoke.mjs,deepeval-smoke.py}`; pins in `.claude/config/toolkit.json`.

## Verification evidence
- `node .claude/scripts/verification/verify-toolkit.mjs` → all static checks passed (9 skills, no duplicates, no broken symlinks, settings valid, no inline secrets, 3 plugins enabled).
- `bootstrap.mjs --check` (also via `.ps1` and `.sh`) → 26 OK, 0 missing, exit 0.
- `mcp-stdio-smoke.mjs promptfoo` → `Promptfoo MCP 1.0.0`, 14 tools.
- `uv run --no-project --python 3.12 --with deepeval==4.3.1 python .claude/scripts/verification/deepeval-smoke.py` → OK.
- Not run: Impeccable `detect`/`hook` (execution denied), live invocation of plugin skills (needs a new session), Promptfoo MCP via Claude itself (needs `/mcp` approval), any LLM-judge or red-team run (no budget given).

## Blockers / environment notes
- Project MCP servers (`supabase`, `promptfoo`) are `Pending approval` in `claude mcp list`; approve once via `claude` → `/mcp`. Supabase also needs OAuth.
- `.gitignore` ignores `.claude/`, `.mcp.json`, `CLAUDE.md`, `AGENTS.md`, `skills-lock.json`, so none of this toolkit is tracked by git. Copy them manually or change `.gitignore`.
- Promptfoo MCP exposes `run_evaluation`, `redteam_run`, `share_evaluation` (uploads results). Treat those as billable/outbound and use only with explicit approval.
- Another process modified `backend/pyproject.toml` (`deepeval==4.3.1` in an `eval` group), `frontend/package.json` (`agent-browser 0.39.4`) and their lockfiles, and `.codex/`, `.gitignore` during this install. Those are not from this toolkit and were not touched here.
- The `.claude/skills/` list in `CLAUDE.md`'s original kit section (accessible-web-testing, etc.) does not exist in the folder.

## Reinstall
`powershell -ExecutionPolicy Bypass -File .claude/scripts/bootstrap/bootstrap.ps1` (Windows) or `bash .claude/scripts/bootstrap/bootstrap.sh`. Idempotent; `--check`/`-Check` only reports. Requires Node ≥ 22.22 (promptfoo), `claude`, `git`; `uv` + Python 3.12 for DeepEval. Plugin cache, Chrome binary and OAuth sessions are machine-local and are reinstalled, not copied.

## Update
- Plugins: `claude plugin update <name>@<marketplace>`.
- Skills: `npx skills update`, or delete the folder and rerun bootstrap after bumping `.claude/config/toolkit.json`.
- CLIs: bump versions in `toolkit.json` and `.mcp.json` together, then rerun the verification scripts.

## Uninstall
`claude plugin uninstall <id> --scope project`; `claude mcp remove promptfoo --scope project`; delete the skill folders and `impeccable-*` agents; remove the `hooks` block from `.claude/settings.json`; `npm uninstall -g agent-browser`.
