# 03 — Product Requirements (MVP for ~50 real users)

Product: MoodPrint / Me2We — "hiểu mình hơn · gần nhau hơn". Two equal pillars: **A. AI self-discovery** and **B. meaningful human connection**.

Requirement IDs are stable and referenced by tasks in the [implementation plan](../plans/2026-10-25-moodprint-productization-implementation.md). The traceability matrix is in [§7](#7-traceability-requirement--tasks--tests).

## 1. Target users and context

- ~50 invited Vietnamese-speaking users, 18+ for social features (16+ for private features), joining a closed beta.
- Device mix assumed mobile-first (390–430 px), with desktop use for longer sessions.
- The pool is small: matching must produce useful candidates for **most** users, not perfect ones for a few.

## 2. End-to-end journey

Signup → age declaration → AI self-discovery (assistants, mood, approved memories) → **publish a matching profile** (explicit preview) → discovery (explained suggestions) → connection request with the sender's public card → mutual acceptance → human chat → **shared activity** inside the chat → continued conversation.

## 3. Scope

### 3.1 MVP — included

| Area | Included |
|---|---|
| Foundation | Remove the legacy prototype; no demo data or fabricated behavior anywhere in production |
| AI pillar | Keep existing assistants, history, approved memories, mood, voice flag; add daily AI quota + global spend ceiling |
| Matching | Taxonomy v2, profile v2 (activities, availability, strict-goal), deterministic explainable scorer v2 with fairness/diversity, rollback flag, offline evaluation, aggregated beta metrics |
| Connections | Sender card on requests, connections survive profile edits, consistent aliases, unread counts and badges |
| Activities | Generic framework + Icebreaker + Cooperative Quiz + Shared Focus, all server-authoritative between two real accounts |
| Safety | Staff moderation queue and actions, suspension/social restriction, activity answers as report evidence, PII advisory |
| Privacy | Export and deletion cover new data; privacy notice and provider disclosure draft |
| Ops | Reviewed migrations 0011–0014, alarms/backup runbook, 50-user load qualification, staging release |

### 3.2 Post-MVP — excluded (explicitly)

- English practice activity (topic cards + turn-taking). Rationale in [06 §9](06-shared-activities-design.md#9-english-practice-post-mvp).
- Semantic free-text profile embeddings (Voyage + pgvector) for matching; design kept in [05 §10](05-matching-design.md#10-embedding-generation-and-invalidation-post-mvp-flag).
- Push/email notifications, per-user global SSE stream, presence/typing indicators, read receipts shown to peers.
- Multi-worker/replica topology, Redis, external realtime service.
- Group (3+) activities, AI-generated activity content, AI moderation classifiers.
- In-app unblock, appeals UI (handled by email in beta), analytics dashboards.
- Dropping the `outbox` table (contract migration after MVP).

## 4. Functional requirements

### 4.1 Foundation

| ID | Requirement | Acceptance |
|---|---|---|
| PR-FND-01 | Production code contains no mocks, fixtures, scripted AI/peer replies or simulated success paths | Guard tests fail on any import of removed modules; built bundle contains no prototype strings |
| PR-FND-02 | Production naming and docs reflect the real product | `package.json` name `moodprint-web`; README updated |

### 4.2 Pillar A — AI self-discovery (mostly existing; preserve)

| ID | Requirement | Acceptance |
|---|---|---|
| PR-AI-01 | Five assistants keep working through the Agents SDK with consent gates | Existing backend/full-stack suites pass unchanged |
| PR-AI-02 | Conversation history stays opt-in with retention controls | Existing tests pass |
| PR-AI-03 | Memories persist only after explicit user approval | Existing tests pass |
| PR-AI-04 | Per-user daily AI turn quota and a global daily estimated-spend ceiling, both configurable; exceeding either fails closed with a friendly, honest message | New tests: quota boundary, ceiling boundary, accounting disabled → quota still enforced |
| PR-MOOD-01 | Mood logging and insights unchanged | Existing tests pass |
| PR-PRIV-01 | Four consents (AI, MEM, MATCH, VOICE) remain independent and versioned | Existing tests pass |

### 4.3 Pillar B — Matching

| ID | Requirement | Acceptance |
|---|---|---|
| PR-M-01 | Only eligible peers are retrievable: adult, active, not deleting, MATCH enabled at the published consent version, live current published profile, not blocked either way, no active cooldown, no open connection, no pending request, seen in the last 30 days, profile published or reconfirmed within 180 days, not socially restricted | Retrieval tests per exclusion rule |
| PR-M-02 | Profile v2: interests (≥3 of ~30), values (≥2 of 8), style, goal (1 of 4), languages (≥1), preferred shared activities (0–4), optional availability windows (0–6), "only same goal" toggle | Validation tests; v1 profiles remain valid and publishable |
| PR-M-03 | Each suggestion shows up to 3 reasons derived only from shared, published items, plus a qualitative label ("Nhiều điểm chung" / "Có vài điểm chung"); no percentages or claims of psychological compatibility | Faithfulness property test: every reason maps to an item both profiles contain |
| PR-M-04 | Exposure is balanced: deterministic daily tie-break, cold-start boost for new profiles, down-weighting of peers with many pending incoming requests, diversity re-rank | Unit tests on ranking; offline Gini ≤ v1 |
| PR-M-05 | Scorer is versioned (`rules-v1`, `rules-v2`); `MATCHING_SCORER=v1|v2|shadow` switches without redeploying code; scoring version recorded per impression | Flag tests; candidate references store version |
| PR-M-06 | Private moods, notes, private items, AI conversations and memories are never matching inputs | Static test: scorer/retrieval modules import no private models; DTO allowlist test |
| PR-M-07 | v2 is enabled only after an offline benchmark beats v1 on the agreed gate | `evals/matching` report committed |
| PR-M-08 | Aggregated, content-free beta metrics (impressions, requests, accepts, first messages, activity starts, blocks/reports) with small-count suppression | Report script output shape test |

### 4.4 Pillar B — Connections and messaging

| ID | Requirement | Acceptance |
|---|---|---|
| PR-C-01 | Pending requests show the counterpart's public card (alias, tags, reasons) while the pair is still eligible | API + UI tests; card hidden once ineligible |
| PR-C-02 | Editing/republishing or withdrawing a matching profile does **not** close existing connections; withdrawing MATCH consent, blocking, ending, suspension or deletion still do | Updated `test_social.py` cases |
| PR-C-03 | One stable pseudonymous alias per pair across candidate card, request, connection list, chat and export | Alias consistency test |
| PR-C-04 | Connections list shows last activity time, last message preview and unread count; navigation shows badges for unread chats and incoming requests/invites | API + UI tests |
| PR-C-05 | Existing realtime messaging, retry idempotency, revocation behavior remain | Existing suites pass |

### 4.5 Pillar B — Shared activities

| ID | Requirement | Acceptance |
|---|---|---|
| PR-ACT-01 | Generic activity lifecycle inside an open connection: invite → accept/decline/cancel/expire → active → completed/ended/aborted; at most one non-terminal activity per connection; all state server-authoritative and persisted | State-machine unit tests; API concurrency tests |
| PR-ACT-02 | Both participants see synchronized state within ~2 s through the existing connection SSE; polling fallback; reload/reconnect resumes exactly | Two-browser full-stack test with stream interruption |
| PR-ACT-03 | Icebreaker: 3 questions, independent answers, optional skip, reciprocal reveal (you see an answer only if you answered), mutual "next", completion summary, optional private feedback | API + two-user E2E |
| PR-ACT-04 | Cooperative Quiz: 5 rounds from a shared bank, both answer, reveal after both, team score (correct answers + sync bonus), summary | API + two-user E2E |
| PR-ACT-05 | Shared Focus: mutual start, server timestamps, synchronized countdown, pause/resume/leave/rejoin/end, factual minutes summary, no fabricated achievements | Timer unit tests with injected clock; two-user E2E |
| PR-ACT-06 | Blocking, ending the connection, MATCH withdrawal, suspension or deletion aborts non-terminal activities immediately and revokes access | Lifecycle tests |
| PR-ACT-07 | Invitation limits: ≤6 per connection per hour, ≤20 per user per day, 10-minute cooldown after a decline for the same kind | Quota tests |
| PR-ACT-08 | Feedback is optional, private to the author, aggregated only | DTO test: peer never sees feedback |

### 4.6 Safety and moderation

| ID | Requirement | Acceptance |
|---|---|---|
| PR-S-01 | Staff (role-gated) can list reports, view the evidence attached by the reporter, and resolve with: dismiss, warn, restrict social features for N days, suspend account | Admin API authorization tests; minimal admin screen |
| PR-S-02 | Suspension revokes sessions and blocks login; social restriction hides the user from discovery and blocks new requests/messages/activities | Enforcement tests |
| PR-S-03 | Reporters may attach up to 2 messages and up to 2 activity answers from the pair as evidence | Report tests |
| PR-S-04 | Composer warns (non-blocking) before sending phone numbers/emails/links in human chat | Unit + E2E |
| PR-S-05 | Existing block/report/reveal behaviors remain | Existing suites pass |

### 4.7 Privacy, UX and operations

| ID | Requirement | Acceptance |
|---|---|---|
| PR-PRIV-02 | Export includes own activity participation, own answers, own feedback and read markers | Export test |
| PR-PRIV-03 | Account deletion removes own answers/feedback/read markers and aborts activities | Deletion test |
| PR-PRIV-04 | Privacy notice and provider disclosure drafted for legal review (OpenAI, Voyage, Supabase, AWS) | Document exists; legal sign-off tracked as external gate |
| PR-UX-01 | Coherent IA: Discovery tabs (Gợi ý / Lời mời / Hồ sơ kết nối), chat with activity dock, badges | Full-stack journey |
| PR-UX-02 | 390, 430, 768, 1280, 1440 px: no horizontal overflow, ≥44 px touch targets, composer + newest message visible with keyboard; axe wcag2a/aa/21aa = 0 violations | Full-stack responsive/a11y spec |
| PR-UX-03 | Every screen has loading, empty, error and offline states with retry; drafts are preserved | Mocked E2E state matrix |
| PR-O-01 | Migrations 0011–0014 are expand-only, ACL/RLS-reviewed, rehearsed on a restored snapshot, applied only with approval | Review SQL + rehearsal report |
| PR-O-02 | Alarms (5xx rate, readiness, AI failure rate, budget 80 %), scheduled logical backup and a restore drill | Runbook + drill evidence |
| PR-O-03 | 50 concurrent users (1 s think time) with chat + activities: p95 < 800 ms for writes, 0 integrity failures | Load report |
| PR-O-04 | Staging deploy + rollback rehearsed | Staging evidence (approval-gated) |
| PR-O-05 | Go/no-go recorded with evidence | Release readiness report |

## 5. Non-functional requirements

- **Privacy by default**: no consent is enabled automatically; publishing is always explicit; minimal data in DTOs.
- **Honesty**: never claim an action succeeded without a backend receipt; never show fake people; never present similarity as validated compatibility.
- **Performance**: see PR-O-03; matching request p95 < 600 ms at 50 users.
- **Accessibility**: WCAG 2.1 AA on all new screens; reduced-motion respected; focus management on dialogs/sheets.
- **Localization**: Vietnamese UI copy; content banks in Vietnamese.

## 6. Beta success metrics (directional; N≈50 so treat qualitatively)

| Metric | Definition | Target signal |
|---|---|---|
| Profile publish rate | Users who published ÷ eligible adults | ≥ 60 % |
| Candidate coverage | Users with ≥1 suggestion ÷ users with live profile | ≥ 80 % |
| Request rate | Requests ÷ candidate impressions | Observe |
| Acceptance rate | Accepted ÷ decided requests | ≥ 40 % |
| First message within 24 h | Connections with a message from both sides in 24 h | ≥ 50 % |
| Activity start rate | Connections with ≥1 accepted activity in 7 days | ≥ 30 % |
| Activity completion | Completed ÷ accepted | ≥ 60 % |
| Continued conversation | Connections with ≥5 messages per side within 7 days | Observe |
| Safety guardrail | Blocks + reports per connection | Investigate any spike; every report triaged within 48 h |

## 7. Traceability (requirement → tasks → tests)

| Requirement | Tasks | Test IDs ([10](10-testing-evaluation-strategy.md)) |
|---|---|---|
| PR-FND-01 | A-02, A-03 | T-CLEAN-01, T-CLEAN-02 |
| PR-FND-02 | A-04 | T-CLEAN-03 |
| PR-AI-01..03, PR-MOOD-01, PR-PRIV-01, PR-C-05, PR-S-05 | J-01 (regression) | T-REG-01 |
| PR-AI-04 | I-05 | T-AIQ-01, T-AIQ-02 |
| PR-M-01 | C-04, I-03 | T-MATCH-01 |
| PR-M-02 | C-01, C-02, C-07 | T-MATCH-02 |
| PR-M-03 | C-03, C-05 | T-MATCH-03 |
| PR-M-04 | C-04 | T-MATCH-04 |
| PR-M-05 | C-02, C-04 | T-MATCH-05 |
| PR-M-06 | C-03, C-04 | T-MATCH-06 |
| PR-M-07 | C-06 | T-EVAL-01 |
| PR-M-08 | C-08 | T-METRIC-01 |
| PR-C-01 | B-03 | T-CONN-01 |
| PR-C-02 | B-02 | T-CONN-02 |
| PR-C-03 | B-01 | T-CONN-03 |
| PR-C-04 | B-04, B-05, H-01 | T-CONN-04 |
| PR-ACT-01 | D-01, D-02, D-03, D-06 | T-ACT-01, T-ACT-02 |
| PR-ACT-02 | D-04, D-07 | T-ACT-03 |
| PR-ACT-03 | E-01, E-02, E-03 | T-ICE-01, T-ICE-02 |
| PR-ACT-04 | F-01, F-02, F-03 | T-QUIZ-01, T-QUIZ-02 |
| PR-ACT-05 | G-01, G-02, G-03 | T-FOCUS-01, T-FOCUS-02 |
| PR-ACT-06 | D-05 | T-ACT-04 |
| PR-ACT-07 | D-03 | T-ACT-05 |
| PR-ACT-08 | D-03, E-03 | T-ACT-06 |
| PR-S-01 | I-01, I-02 | T-MOD-01 |
| PR-S-02 | I-03 | T-MOD-02 |
| PR-S-03 | I-04 | T-MOD-03 |
| PR-S-04 | I-06 | T-SAFE-01 |
| PR-PRIV-02, PR-PRIV-03 | D-05, I-04 | T-PRIV-01 |
| PR-PRIV-04 | I-08 | T-DOC-01 |
| PR-UX-01 | H-01, H-02 | T-UX-01 |
| PR-UX-02 | H-04 | T-UX-02 |
| PR-UX-03 | H-03 | T-UX-03 |
| PR-O-01 | B-04, C-02, D-01, I-01, J-03 | T-MIG-01 |
| PR-O-02 | I-07 | T-OPS-01 |
| PR-O-03 | J-02 | T-PERF-01 |
| PR-O-04 | J-04 | T-OPS-02 |
| PR-O-05 | J-05 | T-REL-01 |
