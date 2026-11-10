# DR-INT-02: Restricted internal development merge of Phase 2 and Phase 3

Status: **INTEGRATED_FOR_INTERNAL_DEVELOPMENT.** This is not `G_INTEGRATION = VERIFIED`, and it is not a release decision.

## 1. What the owner asked for, and what it does not waive

The owner asked, in writing on 2026-11-09, for a successful merge into `mhiu05/feat-refactor` for continued
engineering and an internal MVP demonstration, and said explicitly that this does **not** waive the original
full-verification requirements. The original acceptance criteria in `docs/implementation/phase2-3/` and the
runbook `10-INTEGRATION-AND-AUTOMATIC-MERGE-RUNBOOK.md` stay in force for release verification. Nothing in
those documents was edited to make a failed gate pass.

## 2. Original gates that are NOT met

| Gate | State | Why |
|---|---|---|
| `PHASE_2 = VERIFIED` | **NOT_VERIFIED** | D2-07: no-result accuracy 0.556 (10/18) against 0.90 on the single test run. Also unmet: 350-chunk target (74), six usable sources (two). |
| `PHASE_3 = VERIFIED` | **NOT_VERIFIED** | Q3-03 not demonstrated (the urgency dataset and the detector share an author; no independent set exists). Live repeats incomplete: the OpenAI call ceiling (900 of 900) is spent and this mission was not authorised to raise it. |
| `G_INTEGRATION = VERIFIED` | **cannot be claimed** | Depends on both phases being verified and on external safety review. |
| Hosted migration and hosted corpus publish | **excluded** | Not authorised. |
| `baseline/phase-2-3-verified` tag | **not created** | Would be false. |

## 3. Conditions of the restricted policy and their evidence

1. Both feature branches are committed and pushed: see `integration-report.md` for the SHAs.
2. Phase 2's basic retrieval is usable and its security, citation and licence tests pass; the one non-security
   deviation (no-result accuracy) is documented in `phase-2-report.md` and accepted here **only** under this
   development-only exception.
3. All local integration tests pass: recorded with exact commands in `integration-report.md`.
4. Required GitHub CI passes on the exact integration SHA: recorded there.
5. No known exploitable Critical authorization, privacy or data-integrity defect: see the security section.
6. **Live AI Companion is off by default.** The backend only calls the model when `OPENAI_API_KEY` is configured
   and a non-demo workspace is used; CI, test and default development environments have no key, and the
   demo workspace never calls the backend.
7. **Model-assisted safety is off by default.** It requires `MOODPRINT_MODEL_ASSISTED_SAFETY=1` and a model
   client (`backend/app/agent_gateway/wiring.py`).
8. Not deployed to public production. No deployment setting was changed.
9. Only synthetic data was used.
10. Hosted migrations and hosted corpus publication are excluded.
11. The unresolved independent safety assessment and the live-repeat gate stay visible in the Phase 3 report,
    in DR-INT-01 and in section 2 above.
12. This record is the distinct internal-only acceptance record.

## 4. Technical and safety mitigations

- The default knowledge retriever is the real one and fails closed without a Voyage key; the fixture must be
  chosen on purpose, is announced in the log and is refused when `APP_ENV=production`. A turn without a
  retriever fails instead of answering from synthetic data.
- Citations come only from the run's retrieval ledger; a forged marker is dropped and an empty ledger yields no
  citation (vertical-slice test).
- No write happens before a bound approval; the approval binds to the exact payload the user saw.
- Retrieval never returns an unpublished, `reference_only` or `unverified` document.

## 5. Exact limitations

- In-domain questions the corpus cannot answer (penalty amounts, a named school's rules, other countries' law)
  retrieve the nearest cards instead of returning nothing, so the Companion must not treat a retrieved card as
  proof that the corpus answers the question.
- Urgency `immediate` detection recall on an independent set is unknown (Q3-03).
- The legal excerpt is a single-reader transcription and its current legal status is not confirmed from an
  official database.
- No human reviewed card wording, benchmark labels or safety behaviour.

## 6. Why this is acceptable for isolated development, and why it is not release approval

Everything merged is behind defaults that keep real students away from it: no key, no hosted corpus, no hosted
migration, synthetic data only, the demo workspace unchanged. Engineers and the owner can build on a single
integrated branch and demonstrate the product internally. It does **not** authorise any real-user deployment,
live model use with real student content, hosted migration, hosted corpus publication or a verified-baseline
tag. Those need their own authorisation and the original gates.
