# P0 integration review

Reviewed comparison: `dc53e05b92af58408740a07b17c23fdf7b1cb59a` to
`66cc3c51ffd8579dfe23fe034f128396bcb0f711`; 37 files. GitHub's PR #17 merge-result
tree `ca0681c9a376a36478aefe64a6291c7dc9869412` matches the verified source tree.

No new actionable P0/P1 correctness or security finding was identified in the
reviewed paths. This is a source review supported by regressions and hosted smoke,
not a claim that all possible language-model responses are proven safe.

| Reviewed boundary | Evidence and assessment |
| --- | --- |
| Authorization | A text follow-up cannot grant mood scope. The re-share UI restores dates only after a click and still requires Send. Its state is bound to the current conversation ID. |
| Evidence ownership | Backend-created immutable envelopes bind owner, run, data version, range and expiry; the model cannot select an owner or widen dates. |
| Numbers and capability | Scoped output uses a strict private plan with no numerical fields or free-form claims. The backend renders recorded values, counts, means, missingness and first/last comparisons. Trend inference remains disabled. |
| Revocation and races | Existing per-tool, per-model and final policy fences remain. Source-version changes cancel active runs; F03's conservative history projection remains intact. |
| Retention | Evidence is cleared on all terminal paths and is not added to saved messages, schemas or memory. Legacy policy stamps are not backfilled. |
| Public contracts | `AiOutput`, SSE ordering/version and generated request/response contracts remain unchanged. Scoped output emits no unreceipted action cards. |
| Hosted compatibility | Migration 0015 was separately authorized and verified before rollout. Only F03-compatible images remain in the automatic rollback path; old state files are archived and preserved. |

The 600-test exact-source suite includes 22 F03 and 39 evidence/evaluation cases:
forged claims, missing evidence, invalid owner/run/range/version/expiry, source
edits/deletion, cancellation, withdrawal/regrant and restored conversations. Both
desktop/mobile explicit-sharing browser paths have source-CI coverage. The live
F03 smoke additionally demonstrated authorized retrieval followed by no revoked
canary in the next output, durable stamps and retained owner transcript access.

Residual limits are separate from new findings: unscoped free-form dialogue is
not a universal semantic claim validator; conservative privacy cutoffs can lose
continuity; real-model quality evidence is small and contains a documented judge
dispute; independent human review, fresh full-data restore and portable/PITR
recovery remain unverified. No test assertion or security fence was weakened.
