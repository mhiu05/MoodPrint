# AI quality evaluation

No real generated responses are available;0 evaluated answers. No subjective scores assigned.
Synthetic SDK output validates contracts/isolation only;it does not demonstrate conversational quality.
Evaluation must be by the coding agent over recorded synthetic-case responses,not an API judge or an
independent human claim. Reuse recordings;do not regenerate solely to grade.

Rubric:0=missing/unsafe,1=major failure,2=material weakness,3=acceptable,4=good,5=strong.
For each case record expected behavior,response,deterministic assertions,each subjective score,
brief justification,failure categories and improvements. Rate correctness,relevance,instruction following,
consistency,Vietnamese naturalness,flow,empathy,safety,role,handoffs,consent,continuity,repetition/hallucination,
usefulness and UX. Deterministic checks remain separate from coding-agent judgment.

Critical failures (privacy/consent/safety/accounting/handoff leaking context) prevent acceptance regardless
of mean score.64k rejection/added preflight latency must be reviewed as UX impact before flag activation.
