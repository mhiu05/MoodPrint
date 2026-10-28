# Synthetic one-worker capacity and recovery

The first results below are historical at b8c7efb; the finish-run section records
subsequent approved11538b2 runtime measurements.

## Finish-run measurements at11538b2

All3 commands from prompt10 ran sequentially after suites/servers stopped,
explicit loopback26432 `moodprint_guest_load_test`, owned ports8017/8018:
registered `load_chat_memory.py --workers 1 --users 50`; guest
`load_guest_experience.py --workers 1 --users 50`; same guest command
`--crash-kill`. All exit0/PASS. Full JSON/log/dump artifacts remain owned temp
`%TEMP%/moodprint-guest-finish`, never committed. Synthetic providers/identities
only; no production SLO, upstream signup burst or50 simultaneous paid-call claim.

| Run | Observed result |
| --- | --- |
| Registered50 |50 AI completions;941 non-AI requests;p95 non-AI1958.53ms/AI10729.77ms;RSS192643072;12 connections/10 checked-out;150 embedding backlog;39.24s wall time. |
| Guest50 normal |50 browse/journal/private reads/conversations,100 consent writes;10 AI202/40 clean429,3 voice200/47 clean429,10 SSE;actual maxAI10/STT3;RSS184958976;12 connections/12 checked-out;pool wait462.63ms;backlog0;cleanup10.375s;detached liability186315 synthetic nano-USD. Canary6 successes,p95/max3138.98ms. |
| Guest50 crash/restore |Same admission statuses,owned kill/restart;provider replay0;physical pg_dump/pg_restore in fresh isolated quarantine;expired/anonymous references0;no network listener;canary6 successes,p95/max2152.27ms. Cleanup+restore16.86s;RSS185262080;12 connections/12 checked-out;pool wait1081.23ms;liability204915 retained. Sampled peaksAI6/STT2 (normal run establishes10/3);no cap assertion relaxed. |

No unexpected5xx/owner mismatch/retry/orphan/incident accumulation. Resource
pressure and latency are measured, not hidden; the crash pool wait exceeds1s.
Owner-approved capacity/budget/cleanup targets remain D01/D02/D04 release holds.

## Historical b8c7efb measurements

Local synthetic proof on 2026-10-28; no external model/STT/embedding calls, billing or hosted mutation. Exactly **50 visitors / 1 worker** per run, isolated from test suites. The normal workload seeds anonymous guests so the source-IP signup bucket does not make all visitors one NAT; upstream signup burst capacity is not measured. Production lifetime is still 7200 seconds and global guest caps stay AI10 / STT3.

| Run | Observed result |
| --- | --- |
| Registered baseline `load_chat_memory.py --workers 1 --users 50 --port 8017` | PASS; 50 AI completions, non-AI p50/p95/max 552/1433/3262ms; AI 8242/9773/9899ms; RSS peak 192856064 bytes, DB connections 13, checked-out 10, embedding backlog 150. |
| Guest `load_guest_experience.py --workers 1 --users 50 --port 8018` | PASS; 50 browse/journal/isolated reads/conversation creations, 100 explicit consent writes; 10 AI admitted / 40 clean429, 3 STT success / 47 clean429, 10 validated SSE finals; no500 or private-owner mismatch. |
| Same guest command with `--crash-kill` | PASS; owned worker killed with an admitted provider call, restarted without another provider call; 50 expired sessions denied, original cohort purged, detached financial liability retained and registered canary live. Physical synthetic dump restored after T into a new quarantined local DB; expired/anonymous references 0, replayed provider calls 0, no listener exposed. |

Final rerun after the independent-review fixes: both guest runs **PASS**. Normal peaks AI10/STT3, connections12, checked-out12, pool-acquisition wait203ms, RSS185020416 bytes, SSE10, backlog0, cleanup lag10.629s and cleanup observed10.547s. Crash peaks AI10/STT3, pool wait201ms, RSS185024512 bytes, cleanup lag14.132s; cleanup-plus-restore observation23.719s. No retry/orphan/incident accumulation. Detached synthetic liability remains186315 nano-USD (normal),204915 (crash). These observations are within the proposed healthy60s/5min escalation windows; they are not an approved production latency SLO.

Final normal guest p50/p95/max (ms): browse1033/1541/1747, journal713/1299/1855, private read667/1211/1542, AI admission2008/3446/3771, admitted SSE4026/4571/4571, STT3103/4381/4500. Registered canary148/1998/1998 (6 samples). Crash canary246/2196/2196 (5 samples) stayed successful; provider replay0 and restored expired/anonymous references0. Pool pressure is measurable, so these figures are not a claim of production headroom or50 simultaneous paid requests.

Final latency distributions/statuses and content-free metrics live in `$TEMP/moodprint-guest/{registered-50,final-guest-50,final-guest-50-crash}.json`. Initial pre-review `guest-50*.json` results remain historical evidence. Synthetic dump/server logs remain in owned `$TEMP/moodprint-guest-load-*` directories. No token, raw IP, comment, transcript or user ID is included in result JSON. No real browser/media/provider latency or sustained production soak is inferred. Registered canary timing under guest load is reported in JSON; shared-pool pressure is visible and must be remeasured on the actual deployment target.

Commands from `backend` require `TEST_DATABASE_URL` explicitly set to loopback `moodprint_guest_load_test`; output paths are distinct temp JSON files. The CLI refuses workers other than1, users other than50, remote/non-test/query-overridden targets and occupied ports; it stops only its own process. Crash/physical restore is pinned to the inspected local `moodprint-guest-impl-db` container on26432, creates a uniquely named empty restore DB and keeps its contents synthetic.

`tests/test_guest_restore.py` separately proves the quarantine gate and unsafe-target refusal; `tests/test_guest_cleanup_recovery.py` covers flags-off cleanup, lease theft/crash/retry/failure and compatible rollback. The [release gates](release-readiness.md) still hold D01/D02/D03/D04 and actual hosted recovery/capacity. See [rollback](rollback.md).
