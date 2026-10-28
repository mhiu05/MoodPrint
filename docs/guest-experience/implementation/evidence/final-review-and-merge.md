# Guest experience — final review and merge evidence

Status: **PARTIAL / merge pending; release HOLD**. This live report follows
[prompt10](../10-codex-finish-pr-merge-prompt.md). No hosted migration, deployment,
paid call or public enablement is authorized by source integration.

Base/main verified `984753389aa8bd4b3112b19a8beceb1e538fd659`; original finish
start `b8c7efb990447d329599b3bf038430b12aa14084`. Fixes through
`26ca93d141b38f8c963a8c2ec0279280eb830594` implement REL1/F1–F6/UX1. Complete
[independent review](independent-review-26ca93d.md) requests three additional P2
fixes; their regression and later-SHA re-review are in progress. Merge is gated.

Follow-up at862e036 resolved R1–R3 but [scoped review](independent-review-862e036.md)
identified provider-start/admission-clock coupling. The correction keeps bucket
time request-local for refunds and restores fresh post-admission provider time;
54 targeted tests pass including actual orphan deletion. Later-SHA verdict and
remaining integrated/load/CI evidence are still required.

| Scope | Actual command / observed result at26ca93d | Limit |
| --- | --- | --- |
| Backend | `uv sync --locked`; full CI Ruff list; mypy114 clean; `uv run --locked pytest -q -rs`:1042 pass/1 skip,1141.01s | Only D04 hosted-target skip; must refresh after review fixes |
| Frontend | npm ci/audit0/contracts generation/typecheck/91 units/build exit0; generated drift empty | Node24 local; separate Node22/Linux91 units pass |
| Browser | Full owned264 pass/8.0m; default CI command264 pass/7.5m | First default run competed with builds/servers and hit600s after256; unchanged sequential rerun passed |
| Fullstack | New signup/five-bot guest journeys2 pass; first full run31 pass/1 fail | Trace proves504 Outdated Optimize Dep on react-markdown with concurrent Vite cache; isolated registered-history rerun1 pass; complete sequential rerun required |
| Migration | Distinct local DB upgrade/current/check:0018_app_feedback/no drift | No hosted SQL applied; historical9 approvals unchanged |
| Oracles | All21 backend and4 browser exact commands exit0; browser selected1/3/11/18 tests | Fresh results in owned temp; affected backend selectors refreshed after fixes |
| Linux/package | API/web/combined builds;18 deployment tests; pinned actionlint; Compose/Caddy/UID10001/no.env/no maps/no test entrypoint/proxy/CSP/callback/SSE pass | Rebuild changed backend after review fixes |
| Docs/flags |61 Markdown/420 links/109 operations/68 settings/48 tables;9 SQL pins pass;6 defaults/examples false;budget unset; .gitignore no diff | Latest docs counts will change with this report |
| Load/recovery | Pending new50 registered/50 guest/50 crash sequential run | Prior b8c7efb workloads are historical |
| GitHub | CLI push/merge rights verified; all merge methods allowed; no branch protection/rulesets; no existing PR found | Push/PR/CI/merge/post-merge observations pending |

Raw logs, screenshots and JSON stay at `%TEMP%/moodprint-guest-finish`; no dumps,
browser profiles, secrets or private output are committed. Tools: Python3.12.13,
uv0.11.14, Node24.13.0/npm11.6.2 local, Node22.16.0 in Linux build, gh2.97.0,
Docker29.8.2. All database targets are explicit loopback26432 `_test` databases
in owned pgvector0.8.2/PG17 container. No `.env` fallback.

Docker Desktop stopped during a rerun: only owned blocked test processes stopped;
the original exited container was inspected and restarted with its databases
preserved. Interrupted runs are not passes. A recreate attempt failed on the
existing container name and changed nothing.

## Preserved release boundaries

Tracked `deploy/guest-experience.release-hold` remains. Both workflow events
fail closed before eligibility/publication; normal CI remains active. D01 cleanup/
provider/log/backup facts, D02 approved paid budget, D03 proposed180-day retention,
D04 approved hosted target and manual device checks remain unresolved. Driver
spotlight remains deferred; optional inline guidance is the accepted fallback.
The review's nonblocking forced-token-tampering hardening concern is recorded,
not represented as a confirmed production defect or silently omitted.

Original workspace remains untouched on local main with its untracked guest docs;
feature worktree retains unrelated `docs/plans/` and `frontend/evidence/`. No
reset/clean/force push, branch deletion, `.gitignore` change or original-workspace
pull is permitted. Remote-main integration and post-merge verification remain
required before this report can state PASS.
