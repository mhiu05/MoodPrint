# Synthetic one-worker capacity and recovery

Local synthetic proof on 2026-10-28; no external model/STT/embedding calls, billing or hosted mutation. Exactly **50 visitors / 1 worker** per run, isolated from test suites. The normal workload seeds anonymous guests so the source-IP signup bucket does not make all visitors one NAT; upstream signup burst capacity is not measured. Production lifetime is still 7200 seconds and global guest caps stay AI10 / STT3.

| Run | Observed result |
| --- | --- |
| Registered baseline `load_chat_memory.py --workers 1 --users 50 --port 8017` | PASS; 50 AI completions, non-AI p50/p95/max 552/1433/3262ms; AI 8242/9773/9899ms; RSS peak 192856064 bytes, DB connections 13, checked-out 10, embedding backlog 150. |
| Guest `load_guest_experience.py --workers 1 --users 50 --port 8018` | PASS; 50 browse/journal/isolated reads/conversation creations, 100 explicit consent writes; 10 AI admitted / 40 clean429, 3 STT success / 47 clean429, 10 validated SSE finals; no500 or private-owner mismatch. |
| Same guest command with `--crash-kill` | PASS; owned worker killed with an admitted provider call, restarted without another provider call; 50 expired sessions denied, original cohort purged, detached financial liability retained and registered canary live. Physical synthetic dump restored after T into a new quarantined local DB; expired/anonymous references 0, replayed provider calls 0, no listener exposed. |

Guest normal peaks: actual AI8/STT2 (caps10/3), connections12, checked-out12, pool-acquisition wait592ms, RSS185401344 bytes, SSE10, backlog0. Cleanup observed9.828s after cohort expiry. Crash peaks: AI10/STT3, pool wait846ms, RSS184705024 bytes, cleanup lag7.998s; total cleanup-plus-restore observation14.594s. No retry/orphan/incident accumulation. These observations are within the proposed healthy60s/5min escalation windows; they are not an approved production latency SLO.

Normal guest p50/p95/max (ms): browse1013/1680/2312, journal664/1123/1723, private read652/1143/1430, AI admission2113/3711/4261, admitted SSE5012/5574/5574, STT3384/4926/5799. Registered canary92/2139/2139 (6 samples). The crash workload canary87/3606/3606 also stayed successful; pool pressure is measurable, so these figures are not a claim of production headroom or 50 simultaneous paid requests.

Full latency distributions/statuses and content-free metrics live in `$TEMP/moodprint-guest/{registered-50,guest-50,guest-50-crash}.json`. Synthetic dump/server logs remain in the owned `$TEMP/moodprint-guest-load-*` directories. No token, raw IP, comment, transcript or user ID is included in result JSON. No real browser/media/provider latency or sustained production soak is inferred. Registered canary timing under guest load is reported in JSON; shared-pool pressure is visible and must be remeasured on the actual deployment target.

Commands from `backend` require `TEST_DATABASE_URL` explicitly set to loopback `moodprint_guest_load_test`; output paths are distinct temp JSON files. The CLI refuses workers other than1, users other than50, remote/non-test/query-overridden targets and occupied ports; it stops only its own process. Crash/physical restore is pinned to the inspected local `moodprint-guest-impl-db` container on26432, creates a uniquely named empty restore DB and keeps its contents synthetic.

`tests/test_guest_restore.py` separately proves the quarantine gate and unsafe-target refusal; `tests/test_guest_cleanup_recovery.py` covers flags-off cleanup, lease theft/crash/retry/failure and compatible rollback. The [release gates](release-readiness.md) still hold D01/D02/D03/D04 and actual hosted recovery/capacity. See [rollback](rollback.md).
