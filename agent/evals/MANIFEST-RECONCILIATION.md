# Live manifest: documented 72 vs authored cases, and the repeat protocol

Source of the 72: `docs/implementation/phase2-3/07-PHASE-3-EVALUATION-AND-QUALITY-GATES.md` §3
(12 + 8 + 6 + 20 + 8 + 6 + 8 + 4). Reconciled 2026-11-09. Historical run records are not rewritten.

| Suite | Plan | Authored (before → after closure) | Reconciliation |
|---|---|---|---|
| chat | 12 | 12 → 12 | complete; includes the four high-risk scenarios `chat-07..10` (SC-04/07/09/24) |
| screenshot | 8 | 8 → 8 | complete (8 rendered synthetic messenger images) |
| roleplay | 6 | 6 → 6 | complete (6 scenarios × 6 turns) |
| knowledge | 20 (12 lookup / 4 no-tool / 4 no_results) | 12 → **20** | had 6 lookup / 3 no-tool / 3 no_results; added `know-13..18` (lookup over the three fixture topics), `know-19` (no-tool small talk), `know-20` (no_results must not invent a phone number) |
| approval | 8 | 6 → **7** | added `app-07` (ambiguous save question must not become a save). The plan's *expired*, *edited-mid-flow* and *version-conflict* variants cannot be expressed in a single live chat; they are pinned deterministically (`test_tool_incident`, `test_tool_plan`, PostgreSQL `I-AG` approval tests), not as live cases |
| memory | 6 | 4 → **6** | added `mem-05` (contradiction → new candidate, nothing overwritten) and `mem-06` (a deleted memory is not recalled or invented); "two conversations" and "deleted next turn" are PostgreSQL lifecycle tests |
| injection | 8 | 8 → 8 | complete |
| urgency live | 4 | counted inside chat | the four live urgency cases are `chat-07..10`; not a separate suite, so 72 − 4 = 68 distinct live contents |
| **total** | **72** | **56 → 67** | 67 + the 4 shared with chat = 71 counting as the plan counts; the 1 missing is the approval variant above |

No filler cases were added: every new case targets a behaviour category the plan lists and the fixture corpus can support.
All ten new cases were written and their expectations fixed **before** any model saw them. They are **NOT_RUN**.

## Repeat protocol (plan §5.4: every live case 3 times in the final round)

| Suite | cases | repeats executed | status |
|---|---|---|---|
| chat | 12 | 3 (`final2-a`) | protocol met (prompt `companion_v3`; not re-run on `companion_v4`) |
| injection | 8 | 3 (`final2-a`) | protocol met (v3) |
| approval | app-01..06 | 3 (`final2-a`) | protocol met (v3) |
| approval | app-03, app-07 | 3 (`closure-a03`, `companion_v4`) | met for these two |
| knowledge | 12 old + 8 new | 1 (old), 0 (new) | **3× UNVERIFIED** |
| memory | 4 old + 2 new | 1 (old), 0 (new) | **3× UNVERIFIED** |
| screenshot | 8 | 1 | **3× UNVERIFIED** |
| roleplay | 6 | 1 | **3× UNVERIFIED** |
| any suite on `companion_v4` / `roleplay_partner_v2` other than the two approval cases | | 0 | **UNVERIFIED** (prompts changed after the final live round) |

## Why it stopped, and what it would take

The owner's cumulative cap is hard: `max_calls_total = 900`. The ledger read 784 calls at the start of this round;
the S-06 comparison (76 classification calls + 3 authoring calls) and the A-03 regression (37 calls) used the remaining
116, and the ledger now reads **900 / 900** (US$0.163 of 2.90). The budget gate refuses any further paid request, as
designed; nothing was raised or rewritten.

Estimated further need, from measured calls per output (2.2 for chat/injection/approval, 2.6 for the others) and about 7
calls per roleplay session: the missing repeats and the new cases are 78 outputs (≈ 195 calls) plus 12 roleplay sessions
(≈ 84 calls); a 3× re-run of chat, injection and approval on `companion_v4` is 78 outputs (≈ 172 calls). Total
**≈ 450 more paid calls (≈ US$0.15)**. The binding limit is the call count, not dollars. Owner action: raise
`max_calls_total` to about 1,400 and extend `expires_on` (now 2026-11-12) if this should be run.
