# Guest experience ? final review and merge evidence

Status: **final activity-race delta awaiting exact-SHA review/CI; release HOLD**.
This pre-merge report follows [prompt10](../10-codex-finish-pr-merge-prompt.md).
Actual final head/review verdict, PR merge/main SHAs and post-merge run results
will be recorded in [PR20](https://github.com/mhiu05/MoodPrint/pull/20) and the
final response. No post-merge evidence commit is needed.

Base/main: `984753389aa8bd4b3112b19a8beceb1e538fd659`. Finish start:
`b8c7efb990447d329599b3bf038430b12aa14084`. REL1/F1?F6/UX1 code through
`26ca93d141b38f8c963a8c2ec0279280eb830594`; review corrections through
`11538b233c9ae9e127df7d133a73e01e0e242ec2`; deadline test/evidence refinement
`b49e1094939e4a44732fa5cf08c21f2deec10b24`; browser-history guard
`6316f824ccc6d9df87de730de170e2c7e0f595c1`. New activity source/test delta is
identified by the commit containing this report; latest-head CI remains mandatory.

| Scope | Commands actually run / observed results | Coverage / limit |
| --- | --- | --- |
| REL1 | `python -m unittest discover -s deploy/aws/tests -v`:18 Linux tests; pinned actionlint PASS; tracked marker and fail-closed hold helper inspected | Both workflow events fence eligibility/build/publish/release; post-merge workflow must be observed |
| F1/F2 | Actual PostgreSQL final-lock/consent, document-job token/lease/source and funded query tests RED?GREEN;54 review correction tests PASS | No provider call after rejected final admission; source/semantic publication fencing retained |
| F3 | Budget/audio/route regressions RED?GREEN at sample boundaries across8/16/44.1/48kHz | Fractional15s reserves210 synthetic nano-USD/15001ms; replay/limits preserved |
| F4/F5 | Three grant/recovery output barriers and guest DB-clock tests RED?GREEN | Final private bytes/cookies fenced; registered sliding behavior retained |
| F6/UX1 | Guest log privacy and one-action end?signup regressions RED?GREEN; actual HTTP guest journeys2 PASS | No guest identifier logs; end failure stays retryable; private tree unmounted before signup |
| Independent review | [Whole branch](independent-review-26ca93d.md), [interaction](independent-review-862e036.md), [11538b2 approval](independent-review-11538b2.md), [b49 approval](independent-review-b49e109.md), [6316 approval](independent-review-6316f82.md) | Three P2 findings and clock coupling fixed; newest activity delta needs scoped approval |
| Backend | `uv sync --locked`; exact CI Ruff list; mypy114 clean; b49 full local `pytest -q -rs`:1047 PASS/1 D04 skip923.47s | Backend unchanged by subsequent frontend fixes; latest full Linux CI below |
| Frontend | Locked npm install/audit0/contracts drift empty; typecheck/91 units/build PASS after activity fix | Build19.69s; Linux/Node22 packaging must pass at final head |
| History guard | Controlled delayed-router Back regression RED1; native popstate guard GREEN57 onboarding/3rounds, final mutation assertion1 PASS; negative-oracle21 refreshed19 PASS50.2s | Historical CI Back failure's precise cause unproven; controlled gap independently reproduced |
| Activity race | Held-refresh regression RED1; room-local terminal-ID dismissal fence GREEN32 activity tests/2rounds1.1m; original phone geometry test8 repeats PASS20.4s; actual-HTTP activity fullstack5 PASS1.6m | Different new invitation accepted; no POST; geometry waits for actual GSAP transform removal, original bounds unchanged; no transient-animation-overlap claim |
| Full browser/fullstack | Prior complete local264 owned/264 default/32 actual-HTTP fullstack PASS;6316 Linux265 browser/32 fullstack PASS | Final activity head full owned/fullstack and CI still pending; failures below remain visible |
| Negative matrix | All25 exact plan07 commands exit0;21 backend/4 browser commands; affected backend rows2/8/9/10/13/15/24/25 refreshed with1 selected each | Browser rows3/19/20/21 select1/3/11/19 after history regression |
|50 registered/1worker | `load_chat_memory.py --workers 1 --users 50 --port 8017`:PASS;50 AI completions/941 non-AI;p95 non-AI1958.53ms/AI10729.77ms;RSS192643072;12 connections/10 pool slots | Synthetic SDK only; no production SLO/headroom inference |
|50 guest normal/1worker | `load_guest_experience.py --workers 1 --users 50 --port 8018`:PASS;AI10 admitted40 clean429/STT3 success47 clean429;10 SSE;peak10/3;cleanup10.375s | Detached synthetic liability186315 retained; registered canary successful |
|50 guest crash/1worker | Same command plus `--crash-kill`:PASS;owned kill/restart,provider replay0;physical quarantine restore expired/anonymous references0,no listener;cleanup+restore16.86s | Detached liability204915 retained; canary successful; no hosted restore |
| Schema/SQL | Local upgrade/current/check0018_app_feedback/no drift;9 historical approval pins PASS; pending0015?0018 hash4a5abfbfc6ab09d0ba7ab01dd65bcacea2598abcb07fa12a7da1ffcbbba47606 transaction rehearsal PASS/DDL rolled back/remoteExecuted=false | Distinct loopback test databases; no hosted mutation |
| Packaging | Prior API/web/combined Linux images,UID10001/no.env/no test entrypoint/no web maps;Node22 91units;Compose/Caddy/proxy/CSP/callback/SSE PASS | Latest frontend runtime must rebuild via final-head Linux CI; no image publication |
|6316 CI | [Push40733052335](https://github.com/mhiu05/MoodPrint/actions/runs/40733052335) SUCCESS:1047 backend/1 skip403.72s;91 units;265 browser5.8m;32 fullstack3.8m;18deploy;remaining workflow/package/load gates PASS | Parallel PR run40733063405 failed phone geometry sampled mid-animation; no timeout/assertion/threshold relaxed |

## Retained failures and diagnosis

Earlier default browser run hit600s while competing with builds; unchanged
sequential rerun passed. Shared Vite cache caused504 Outdated Optimize Dep;
sequential actual-HTTP rerun32 passed. Docker Desktop stopped during a backend
rerun; only owned blocked processes were stopped and original container restarted
with databases preserved. Interrupted runs are not passes.

862e036 backend1044 PASS/1 fail/1 skip confused financial settlement completion
with provider cancellation. Deterministic blocked-settlement RED proved the
assertion error; corrected oracle still enforces provider cancellation<=T+150ms
and no late final while awaiting financial terminal state separately. b49 local
full1047/1skip and CI passed. Earlier social-session load samples539.5/516.3ms
failed the unchanged500ms limit; other complete unchanged runs passed. No
threshold or workload was weakened.

6316 local owned264 PASS/1 environment failure (`ERR_NO_BUFFER_SPACE` at page.goto
before app assertions), and fullstack31 PASS/1 failure at icebreaker Continue are
not full passes. The latter revealed late current-session refresh reopening a
terminal summary; new controlled regression reproduces it and the dismissal
fence fixes it. A first activity fullstack launch used an incompatible URL driver
prefix and never reached tests; rerun uses standard PostgreSQL URL. All raw logs
remain outside Git under `%TEMP%/moodprint-guest-finish`.

## Preserved boundaries

All six defaults/examples remain false; paid daily budget is unset; tracked
`deploy/guest-experience.release-hold` remains. D01 provider/log/backup/deletion
facts and cleanup target, D02 approved numerical budget, D03 proposed180-day
unlinked-feedback retention and D04 hosted Auth/CAPTCHA/DB approval remain
unresolved. Driver spotlight remains deferred with inline guidance fallback.
Manual assistive technology, physical keyboard/microphone and actual target
checks remain gaps. The review's forced out-of-band token-replacement concern
is deferred hardening: no normal takeover path found; five-second heartbeat and
expiry cancellation retained. No paid calls, hosted migration or AWS changes.

Original `E:/MoodPrint` stays on its original local main; overlapping untracked
docs are preserved. Feature worktree/branch and pre-existing untracked
`docs/plans/` and `frontend/evidence/` stay. `.gitignore` has no branch diff.
Tools:Python3.12.13,uv0.11.14,Node24.13/npm11.6.2 local,Node22.16 Linux,
gh2.97,Docker29.8.2. Synthetic DB container pgvector0.8.2/PG17 on loopback26432.
