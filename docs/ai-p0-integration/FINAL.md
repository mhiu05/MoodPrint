# P0 integration — PASS

Verified 26 October 2026, Asia/Bangkok. This verdict covers the requested P0
integration and existing staging release, with the recovery limitations below.

| Deliverable | Observed result |
| --- | --- |
| Final main / merge commit | `5e73a130fd0f081887c3c2ab2093c43674388012` |
| Integration | [PR #17](https://github.com/mhiu05/MoodPrint/pull/17), merged with a merge commit after all integration checks passed |
| Integration CI | [40342985397](https://github.com/mhiu05/MoodPrint/actions/runs/40342985397), PASS on actual PR merge ref |
| Final-main CI | [40344737979](https://github.com/mhiu05/MoodPrint/actions/runs/40344737979), PASS: 600 backend, 54 frontend unit, 68 browser, 28 full-stack; static checks, contracts, migration/load, workflow and packaging checks |
| Publisher | [40346588191](https://github.com/mhiu05/MoodPrint/actions/runs/40346588191), PASS; deployed image identity separately verified on host |
| Hosted migration | `0014_moderation` -> `0015_context_privacy`, committed once, all eight postcondition checks PASS; 485 existing rows / 39 tables preserved |
| Actual running release | Both API and web at final main SHA; healthy, zero restarts |
| API digest | `sha256:ae093f4c0f54e71da456701c8ecfd8c53e737a5c38dfef5c34b7a0d12e87c8ea` |
| Web digest | `sha256:49fd4fa26767e20a0b64c8b1fe68a01d3510482ff08d778e21de547340752ca7` |
| Public availability | Liveness, readiness and homepage HTTP 200; maintenance removed |
| Runtime security | Schema 0015, nullable/no-default policy column, RLS enabled, runtime neither superuser nor RLS bypass |
| Final hosted smoke | 10/10 turns completed; all five bots, memory revocation, saved history, explicit mood re-sharing, 2/7 records with mean 2.5 and five missing days, and empty evidence PASS |
| Usage | 14/14 provider requests/responses settled; 23,501 input / 6,923 cached / 727 output tokens, 4 tool calls, estimated USD 0.00209053 at the repository rate snapshot |
| Synthetic cleanup | All 7 created conversations, 1 memory and 2 moods removed; original fixture preference flags restored; no cleanup failures |
| Logs | Zero AI execution errors / tracebacks in the new API container; private content not printed |
| Release automation | Timer enabled and active; resumed poll completed successfully without another rollout; automatic rollback points to schema-0015-compatible F03 |
| Branch cleanup | Three requested branches deleted locally/remotely after ancestry and exact expected-SHA checks; atomic remote deletion protected against concurrent branch changes |
| Preserved | `dev` remains `779db2a`; unrelated branch/worktrees/untracked files, `.gitignore`, backups and deployment-state archives preserved |

Deleted: `docs/ai-agent-conversation-audit-20261026`,
`feat/evidence-grounded-conversation-p0`, `fix/ai-context-privacy-p0`.

Evidence: [migration](evidence/0015-execution.json),
[protected backup metadata](evidence/backup-pre0015.json),
[schema-only recovery](evidence/schema-recovery.json),
[F03 smoke](evidence/f03-hosted-smoke.json),
[final P0 smoke](evidence/p0-hosted-smoke.json),
[release manifest](evidence/p0-release.json),
[final host inspection](evidence/staging-final.json),
[source review](integration-review.md).

The hosted smoke used only the preconfigured synthetic fixture. Its seven-day
incident window was chosen empty before seeding two new records, preserving all
pre-existing fixture moods. Exact 20–26 October cases also remain in the source
regression suite. Assertions exercise real hosted HTTP/API/PostgreSQL and the live
provider; source-CI browser/full-stack tests use the documented synthetic model.

Recovery remains bounded: the fresh archive was decrypted and listed, and an
isolated schema-only restore/upgrade passed. **Fresh full-data restore and portable
recovery/PITR are unverified**; the encrypted archive requires the original Windows
profile. No hosted private rows were restored into test fixtures. Prior live-model
quality scores remain small-sample estimates with a documented judge dispute and
no independent human adjudication. These limits are not presented as unrestricted
production readiness or statistical proof of conversational quality.

Phase B starts only after this completed gate. Its changes must remain on a new
feature branch and Draft PR; P1 deployment/merge is outside authorization.
