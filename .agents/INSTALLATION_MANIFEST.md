# MoodPrint Codex Toolkit Installation Manifest

Checked: 2026-10-27

Repository: `E:\MoodPrint`
Host: Windows PowerShell; Codex CLI 0.157.0; Node.js 24.13.0; Python 3.12.13; uv 0.11.14.

MoodPrint is a React 19 / Vite / TypeScript frontend and a FastAPI / Python 3.12 backend. It uses the OpenAI Agents SDK and Supabase, so frontend, browser, and AI evaluation tools are applicable.

## Upstream sources

| Source | Selected components | Installation method | Installed location | Version / commit | Verification | Status |
|---|---|---|---|---|---|---|
| [obra/superpowers](https://github.com/obra/superpowers) | `using-superpowers`, `brainstorming`, `writing-plans`, `executing-plans`, `test-driven-development`, `systematic-debugging`, `verification-before-completion`, `requesting-code-review`, `receiving-code-review`, `dispatching-parallel-agents`, `subagent-driven-development`, `writing-skills` | Official `skills@1.7.4` CLI, Codex copy mode | `.agents/skills/<skill>/` | Upstream `2ce8aa15d05bd57213e6f746f953aafb7ded7a8b` | All 12 have `SKILL.md`; Codex skill inventory lists them | PASS |
| [vercel-labs/agent-skills](https://github.com/vercel-labs/agent-skills) | `vercel-react-best-practices` (the official React skill directory; user-facing alias often called `react-best-practices`) and `web-design-guidelines` | Official `skills@1.7.4` CLI, Codex copy mode | `.agents/skills/` | Upstream `063bee94c3f4df8453406c830b0a7df0f2860278` | Both skills discovered by Codex; Vite project does not receive Next.js-only skills | PASS |
| [pbakaus/impeccable](https://github.com/pbakaus/impeccable) | Official Impeccable skill, CLI, and Codex hooks | `impeccable@4.7.0 install --providers=codex --scope=project --yes` | `.agents/skills/impeccable/`; `.codex/hooks.json` | Upstream `989c484c091d26f10fa102767eefc0da2e62ec67`; CLI 4.7.0; engine 0.1.16 | CLI version/help ran; hook manifest contains PostToolUse and Stop hooks. Trust review is pending in Codex `/hooks`. | PARTIAL |
| [nextlevelbuilder/ui-ux-pro-max-skill](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill) | Official design skill, reference data, stack catalogs, and search/design-system scripts | `ui-ux-pro-max-cli@2.15.0 init --ai codex` | `.agents/skills/ui-ux-pro-max/` | Upstream `28b3b8dee8c976df4fa3e94aed4e092ad43fcb03`; CLI 2.15.0 | CLI version/help ran; `SKILL.md`, data catalogs, React stack data, and scripts are present | PASS |
| [vercel-labs/agent-browser](https://github.com/vercel-labs/agent-browser) | Official Codex skill and browser CLI as a frontend development dependency | `skills@1.7.4` plus existing exact `agent-browser@0.39.4` npm pin | `.agents/skills/agent-browser/`; `frontend/node_modules/` | Upstream `04ba5264dade678062c3cdcce0f4f293e748249f`; CLI 0.39.4 | Opened `https://example.com`, read title and accessibility snapshot, captured a 37,918-byte temp screenshot | PASS |
| [confident-ai/deepeval](https://github.com/confident-ai/deepeval) | Official DeepEval skill and Python evaluation dependency | `skills@1.7.4`; pinned in the `eval` dependency group and locked with uv | `.agents/skills/deepeval/`; `backend` virtual environment | Upstream `5410e3822dda5f889d5f35de3325a3738004aeb1`; `deepeval==4.3.1` | Deterministic `LLMTestCase` import/construction passed without invoking a judge or provider | PASS |
| [promptfoo/promptfoo](https://github.com/promptfoo/promptfoo) | Native Codex Promptfoo plugin and skills; local CLI; stdio MCP server | Pinned official plugin marketplace plus `codex mcp add promptfoo -- npx --yes promptfoo@0.125.1 mcp --transport stdio` | Machine Codex plugin cache/config; project verification helper at `.agents/scripts/verify-promptfoo-mcp.mjs` | Upstream `b4c2404a0dee93dcd4d53a323d6f32f87ee27558`; CLI 0.125.1; plugin 0.1.5 | Plugin enabled; MCP tool discovery returned 14 tools; read-only `list_evaluations` call passed with zero records | PASS |
| [openai/plugins](https://github.com/openai/plugins) | Official `build-web-apps` and `openai-developers` Codex plugins; OpenAI developer documentation MCP | Native Codex marketplace/plugin commands; `codex mcp add openaiDeveloperDocs --url https://developers.openai.com/mcp` | Machine Codex plugin cache/config | Marketplace commit `0722921d5542fc593105c27bd52630babd8b8c2a`; plugin manifests: build-web-apps 0.1.2 and openai-developers 1.2.3 | Both plugins enabled; docs MCP search returned official OpenAI documentation | PASS |

The repository versions and commits above were checked against the official sources at installation time. The project bootstrap pins CLI/package versions and marketplace commits where those installers expose a pin. The `skills` CLI has no `add --ref` option in version 1.7.4; its lock file records per-skill content hashes. It installs a missing skill from the upstream default ref when restoring it.

## Active project skills

The 18 selected project skills are the 12 Superpowers skills, the two Vercel skills, Impeccable, UI UX Pro Max, Agent Browser, and DeepEval. Promptfoo skills are supplied by its native plugin (`promptfoo-evals`, `provider-setup`, `redteam-run`, and `redteam-setup`). Existing `supabase` and `supabase-postgres-best-practices` skills and other local custom skills were preserved.

The skills CLI also writes `skills-lock.json` at the repository root. This is the CLI's current project-lock location; it records source names and hashes. Skill contents and supporting data remain under `.agents/skills/`.

## Codex plugins, MCP, and hooks

Newly enabled native plugins:

- `promptfoo@promptfoo` (plugin 0.1.5)
- `build-web-apps@openai-curated`
- `openai-developers@openai-curated`

Newly enabled MCP servers:

- `promptfoo`: `npx --yes promptfoo@0.125.1 mcp --transport stdio`
- `openaiDeveloperDocs`: `https://developers.openai.com/mcp`

The OpenAI documentation MCP is read-only and required no authentication. No credentials were entered or written. Provider-backed Promptfoo or DeepEval runs will require whichever provider credentials that evaluation selects. Codex plugin inventory reports the OpenAI plugin auth policies as `ON_USE` and `ON_INSTALL`; no separate sign-in was requested during this installation.

The non-interactive `codex exec` smoke discovered Promptfoo tools but refused a tool invocation under the existing `approval_policy=never`. The connected MCP tool and the standalone stdio smoke both completed the read-only call successfully. No approval policy was changed.

Impeccable's project hook runs for edits/writes and at the Codex stop event. Codex hook trust was not bypassed. **Recovery action:** open this project in Codex, run `/hooks`, inspect the Impeccable hook entries, and approve them if desired. Restart Codex after reviewing the hook so the project skills and plugins reload.

## Dependencies and verification

The frontend's exact `agent-browser` dev dependency and the backend's exact DeepEval `eval` group are already present in the current committed manifests/lockfiles. The bootstrap synced them without changing application runtime dependencies.

Checks completed:

- `npx --yes skills@1.7.4 list --agent codex --json` — exit 0; selected Codex skills are discoverable alongside existing local skills.
- `& .\\.agents\\skills\\impeccable\\scripts\\impeccable.cmd --version` and `--help` — Impeccable 4.7.0 and commands available.
- `npx --yes ui-ux-pro-max-cli@2.15.0 --version` and `--help` — CLI 2.15.0 available.
- `python .agents/skills/ui-ux-pro-max/scripts/search.py minimal --domain style --max-results 2 --json` — local design search returned a matching style result.
- `& .\\node_modules\\.bin\\agent-browser.cmd --version` — Agent Browser 0.39.4.
- Agent Browser public-page smoke — navigation, title, accessibility snapshot, screenshot, then browser session cleanup.
- `npx --yes promptfoo@0.125.1 --version` — 0.125.1.
- `uv run --locked --group eval python -c "from deepeval.test_case import LLMTestCase; ..."` — deterministic DeepEval test case passed; no network judge call.
- `node .agents/scripts/verify-promptfoo-mcp.mjs` — stdio initialize, 14-tool discovery, and read-only `list_evaluations` passed.
- Codex MCP calls — Promptfoo `list_evaluations` returned success with no saved evaluations; OpenAI docs search returned official documentation.
- `codex plugin list --marketplace openai-curated --json`, `codex plugin list --marketplace promptfoo --json`, and `codex mcp list` — selected plugins/MCP entries enabled.
- Second `powershell -NoProfile -ExecutionPolicy Bypass -File .agents\\scripts\\install-toolkit.ps1` — exit 0; existing skills, plugins and MCP entries were skipped; `npm install` and locked `uv sync` completed.
- Authored integration files pass `git diff --check`. The full check flags 194 trailing-whitespace lines in upstream Impeccable, UI UX Pro Max, and Vercel skill files; those vendor files were kept unchanged.

The browser smoke screenshot was written under the Windows temp directory, not the repository. Cleanup used `close --all`, which also closed a pre-existing session named `claude-smoke`; its page state was unknown and was not restored. The project application itself was not started for this toolkit smoke check.

## Configuration and safety

- Root `AGENTS.md` now describes when to use these skills and how to coordinate design, browser, and AI evaluation workflows while preserving existing project/AWS guidance.
- `.codex/hooks.json` contains the official Impeccable Codex hooks.
- `frontend/package.json` / lock and `backend/pyproject.toml` / `uv.lock` already hold the browser and evaluation pins in the current base commit.
- The bootstrap uses project-local skill copies and does not overwrite existing skill directories. Native plugins, marketplaces, MCP entries, and hook trust are machine-specific Codex state.
- Smoke tests used a public test page, a synthetic DeepEval case, and a read-only Promptfoo tool. No production data, paid model call, API key, or external attack was used.
- The repository's existing `.gitignore` excludes `AGENTS.md`, `.agents/`, `.codex/`, and `skills-lock.json`. It was left unchanged per project instructions. Selected toolkit files are marked intent-to-add for review; force-add their contents if you choose to commit them. The downloaded Impeccable Windows executable is excluded from Git and is recreated by the bootstrap installer.

## Reinstall and updates

From the repository root in Windows PowerShell:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .agents/scripts/install-toolkit.ps1
```

The bootstrap adds missing pieces and preserves existing named configuration. It does not silently update already-installed skills or change Codex trust policy. To update selected components deliberately:

```powershell
npx --yes skills@1.7.4 update using-superpowers brainstorming writing-plans executing-plans test-driven-development systematic-debugging verification-before-completion requesting-code-review receiving-code-review dispatching-parallel-agents subagent-driven-development writing-skills vercel-react-best-practices web-design-guidelines agent-browser deepeval -p -y
npx --yes ui-ux-pro-max-cli@2.15.0 update --ai codex
& .\.agents\skills\impeccable\scripts\impeccable.cmd update
```

For package upgrades, change the exact pins deliberately and refresh their lockfiles: update `agent-browser` in `frontend/package.json` then run `npm install`; update `deepeval` in the backend `eval` group with `uv add --group eval deepeval==<version>` then run `uv sync --locked --group eval`. For native plugins, inspect/update the source marketplace with `codex plugin marketplace upgrade promptfoo` or `codex plugin marketplace upgrade openai-curated`, then review `codex plugin list --json`. Update the Promptfoo MCP package pin in both this bootstrap script and the machine-level `codex mcp` configuration together.

## Uninstallation

Remove only the toolkit's named components; do not remove the whole `.agents/` tree because it contains pre-existing Supabase and custom skills.

```powershell
npx --yes skills@1.7.4 remove using-superpowers brainstorming writing-plans executing-plans test-driven-development systematic-debugging verification-before-completion requesting-code-review receiving-code-review dispatching-parallel-agents subagent-driven-development writing-skills vercel-react-best-practices web-design-guidelines agent-browser deepeval -y
npx --yes ui-ux-pro-max-cli@2.15.0 uninstall --ai codex
npm --prefix frontend uninstall agent-browser
uv --directory backend remove --group eval deepeval
codex plugin remove promptfoo@promptfoo
codex plugin remove build-web-apps@openai-curated
codex plugin remove openai-developers@openai-curated
codex mcp remove promptfoo
codex mcp remove openaiDeveloperDocs
```

Impeccable 4.7.0 has no `uninstall` command. To remove it, manually remove only its hook entries from `.codex/hooks.json` and its `.agents/skills/impeccable/` directory. Remove the `promptfoo` or `openai-curated` marketplace source only if no other installed plugin uses it. Revert only the toolkit paragraphs in `AGENTS.md`; preserve the pre-existing rules and other skills.
