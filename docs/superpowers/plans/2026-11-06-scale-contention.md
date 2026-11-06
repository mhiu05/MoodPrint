# Scale contention implementation plan

**Goal:** Diagnose P3-I07 with real measurements and retain only changes that improve the unchanged 50-parent workload, followed by resource, accounting and reliability work in priority order.

**Architecture:** One API process, PostgreSQL pool 4+1, fresh authorization on every existing check, fake providers with denied egress. Keep the production transaction and monetary authorities. No cloud operations, production migration, merge, deployment, paid calls or production-budget activation.

**Spec:** User continuation request; `docs/scale-readiness/07-load-testing-and-benchmark-plan.md` and existing runner SLO decisions.

- [x] Verify remote baseline `07486b83` and successful CI attempt 2. Preserve original divergent checkout and all pre-existing edits; use isolated checkout.
- [x] Profile baseline connection holds, SQL/task distribution and Python CPU, then form one measured hypothesis.
- [x] Write focused regression, observe RED, implement one change, observe GREEN and relevant security/privacy regression.
- [ ] Compare short isolated workloads; reject regressions. Run full isolated 900-second acceptance with unchanged pool, deadlines, workload and SLOs.
- [ ] Record 2-CPU local simulation limits, RSS, CPU, loop, pool, throughput and completion distributions; separate actual EC2 evidence.
- [ ] Audit global paid-operation authority, child/retry/concurrent-worker/cancellation/restart coverage. Keep paid tests disabled until campaign safety gates pass.
- [ ] Extend mixed and fault workloads with explicit remaining gaps; preserve revocation, sessions, replay, cancellation, drain and crash guarantees.
- [ ] Run relevant full regression, update engineering appendices in docs 12–16, commit, normal-push HEAD to feat/upgrade-user, verify exact remote SHA and completed CI.

Ruling: original root remains untouched; its branch diverged and cannot fast-forward. Worktree starts at the verified remote commit. Push only the reviewed descendant with an explicit branch ref, never force.

Ruling: app and local PostgreSQL share CPU affinity 0,1. App memory cap 7.5 GiB and database 0.5 GiB; Docker host exposes only 7.61 GiB physical memory, so 8 GiB physical availability cannot be claimed. Local co-located PostgreSQL adds CPU pressure and omits EC2-to-Supabase network latency; this is a constrained local simulation only.

Correction: the 0.5 GiB disposable-DB cap caused a confirmed fixture OOM (exit137, OOMKilled=true) during repeated schema resets. That run is invalid as implementation regression evidence. Replacement configuration gives the app CPU0,1/2CPU quota/8GiB cap and the separate local database CPU2,3/2CPU quota/4GiB cap, reflecting that production database resources are outside the EC2 application envelope. The host still has only7.61GiB physical RAM, so this establishes configured cgroup limits and measured RSS, not8GiB available physical memory or EC2 network proof. No application pool, timeout or SLO changed.


Final retained decision: every runtime performance experiment was rejected and removed.
Only exact lifetime/recent pool measurements, stronger fail-closed SLO gates and new
authority/lease/reconnect regressions remain.112focusedPASS, RuffPASS/mypy195PASS.
A completed variant900s run failed pool thresholds; autocommit failed42/50; the retained
runtime's requested900s stopped209/217 with8timeouts after126.9585s measurement.
All reports remain in docs/scale-readiness/evidence/p3-*.json. P3-I07 remainsFAILED;
P4 is local-only partial; all-provider accounting and mixed/fault coverage remain open.
Full bare backend pytest and final exact-SHA CI are assessed separately.
