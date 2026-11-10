# Urgency quality closure

Code delivery SHA: `e831a31d935aeb363f9e7689e21b31782e072568`. The exact five-source safety bundle and every dataset hash are in `agent/evals/results/safety-quality-closure-v2.json`; initial and pre-review measurements are preserved.

## Changes and safeguards

Clause-level context splits prevent an earlier denial, media framing or historic event from erasing a later current disclosure. Timed conditional self-harm commitments and explicit third-person overdose are recognized. Multi-turn escalation now requires a danger-related cue rather than any time/pronoun pair. Presence is linked to an earlier aggressor via anaphora/current threat, not a new friend/teacher offering support. Paired tests preserve immediate ongoing danger while avoiding escalation for homework, ordinary medicine, safe location and past completed pushing. Q3-04 present-danger policy is unchanged.

Assessor refusal, empty/malformed output, timeout and connection failures preserve a conservative elevated/watch state and diagnostics; they cannot downgrade deterministic immediate. Provider/overall deadlines, cancellation cleanup and injected instructions are tested offline. Refusal/unreadable responses retain usage, roleplay preflight and early-exit paths meter the classifier, and a main-model failure/cancel does not leak a classifier task. MOODPRINT_MODEL_ASSISTED_SAFETY remains off by default. No real-user data handling or extra OpenAI call was authorized.

## Transparent offline results

| Dataset | n | immediate TP/N | benign FP/N | exact 3-level accuracy | recall 95% CI |
|---|---:|---:|---:|---:|---|
|safety_final_frozen|64|32/32|0/22|0.8906|[0.8928208017449293, 1.0]|
|safety_cross_model_frozen|31|8/14|0/10|0.6129|[0.3259064457965074, 0.7861920109552588]|
|safety_h3_frozen|83|30/32|0/34|0.8193|[0.7985287685584542, 0.982689432968359]|
|safety_h4_frozen|65|23/24|0/32|0.8615|[0.7975819352134406, 0.9926065438344942]|
|safety_validation|40|19/20|0/14|0.9000|[0.763868806553258, 0.9911185511992047]|
|safety_context_regressions|15|8/8|0/2|1.0000|[0.6755924351161198, 1.0]|

Same-author final set improves from 31/32 immediate and 1/22 benign false alarms to 32/32 and 0/22. The previously inspected model-authored cross set improves from 7/14 to 8/14 (.5714), FPR 0/10; six immediate cases still miss. Its exact 3-level accuracy is 0.6129. Final same-author exact 3-level accuracy is 0.890625, so perfect immediate recall does not mean every urgency label is correct. Full 3x3 confusion matrices, per-group rates, elevated over/under-triage, Wilson intervals, level errors and changed outcomes are in the JSON, not hidden by a combined success rate.

Every available set is synthetic and implementer-authored or previously inspected model-authored. None is independent or human-labelled. The small cross sample does not demonstrate target recall >= 0.95 / FPR <= 0.10; zero observed FPR has a wide interval. Offline fake-provider checks measure mechanics only; no new hybrid live metric or current latency quality claim is made.

## Independent review package

`docs/implementation/safety-review/README.vi.md` and `annotation.schema.json` provide Vietnamese policy/temporal/actor labelling, taxonomy, examples/counterexamples, two blind reviewers, third-person adjudication, provenance/licence checks, frozen-cluster workflow, confusion/CI reporting and sign-off fields. All human approvals are PENDING. The package reviews UMD/CLPsych2019, eRisk, OurDataHelps and C-SSRS Vietnamese primary resource pages; restricted social-conversation datasets were not downloaded or scraped. None is silently mapped to school urgency or treated as licensed product data.

`Q3-03 = NOT_DEMONSTRATED`. PHASE_3 = NOT_VERIFIED. External qualified Vietnamese-speaking review, independent labels and enough events for confidence intervals remain required. Prepared examples and another coding-agent review do not independently certify safety or real-student readiness.
