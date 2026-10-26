# Architecture and boundaries

The deployed P0 baseline stays on main `5e73a13`. This branch changes the SDK
adapter, a small intent helper, runtime prompt composition/accounting and private
response planning. It adds no dependency, migration, public API field, frontend
flow, agent handoff or model call.

## Intent and tools

`conversation.py` derives a bounded Vietnamese hint from the current user message
already present in F03's filtered model input. It does not read saved transcripts,
assistant prose, discarded context or a separate user profile. Explicit data
requests take the analysis path. Explicit requests to talk, listen, celebrate,
joke or answer a practical question can remove `read_mood_summary`. A refusal of
advice alone does not refuse analysis; ambiguous scoped Nhịp requests retain P0.

This is conservative routing, not a universal intent classifier. It cannot grant
scope, select dates/owners, restore permissions or register another tool. Runtime
tools remain owner/consent/session/version-fenced. Non-data conversation uses the
existing guarded `AiOutput` path; data requests with current scope still require
the private plan and verified read. Without scope, even an analysis hint supplies
no mood tool or reusable snapshot.

The F03 projection, recognized policy stamps, privacy cutoffs, data-version
invalidation and terminal evidence clearing are unchanged. A selected but unused
mood scope still gets the conservative mood-turn stamp. This can lose harmless
continuity on the next turn; it does not expand reuse permission.

## Grounded response planning

`MoodAnalysisPlan` gains only `detail=standard|brief` and `include_mean`. Values,
dates, counts, means, source references and causal/trend claims remain unwritable
by the model. The backend additionally honors an explicit current request for a
short answer or no repeated mean by removing presentation detail; it cannot add
facts. Brief recorded-day descriptions select up to three actual latest records.

The deterministic renderer is retained as the standard/default implementation.
The model selects relevant verified material and a bounded next step; no free-form
analytical prose or new inference capability is promoted. This implements a small
hybrid planning step while retaining backend numerical authority. A fully free
generative analytical renderer needs stronger claim validation and further work.

## Persona, safety and context

Historical `instructions()` variants and their frozen fixtures remain unchanged.
A separate shared conversation layer and five persona-specific runtime layers
handle listening, joy, corrections, rejected activities, topic changes and social
boundaries. Runtime evidence/authorization instructions remain a separate layer.
Mây avoids adding unstated sensory facts; Cầu Nối distinguishes wording intent
from an unknowable recipient reaction. Tool receipts, age eligibility and consent
remain enforced by the existing backend, not by persona text.

Relevant corrections and constraints stay in the already-authorized bounded
context. The model is told to ask a short clarification when the reference is no
longer visible. No extra summary, recovered revoked source, automatic memory or
persistent intent field is introduced. Usage versions append `conversation-intent-v1`;
synthetic evaluation also records full instruction hashes and exact source commits.

## Limits and review

Vietnamese routing can miss indirect, mixed-language or ironic requests; ambiguity
keeps the old analytical path. Free conversational prose is not a general semantic
fact validator. Numerical guarantees apply to the strict analysis path; unrelated
conversation has no supplied mood records/tool, and must not pretend otherwise.
The small development benchmark cannot prove universal hallucination elimination
or statistical improvement. Independent human review is still required before a
P1 release decision. P1 is delivered as a Draft PR and is not deployed or merged.
