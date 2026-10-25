# 13 — Risks and Decisions

## 1. Decision records

| ID | Decision | Alternatives considered | Rationale | Status |
|---|---|---|---|---|
| DR-01 | Reuse per-connection SSE watermark (`activity_seq`) for activity sync; polling fallback | WebSocket; LISTEN/NOTIFY; Supabase Realtime; client polling only | Zero new infra; authorization stays in HTTP reads; proven under 50-user load | Adopted |
| DR-02 | Delete the legacy prototype from `frontend/src` after migrating UX patterns | Keep behind harness; keep as demo mode | Production must never show fake data; 77 tests guard dead code | Adopted |
| DR-03 | Connections and pending requests survive profile republish/withdraw; MATCH withdrawal, block, end, restriction, deletion still close | Keep current close-on-republish | Current behavior destroys relationships when users edit interests (DEF-01); profile edits change discovery, not consent | **Adopted as default — needs product-owner confirmation (Q-01)** |
| DR-04 | Deterministic taxonomy scorer `rules-v2` (weighted, symmetric, explainable); no runtime LLM/embedding calls | Embeddings, learned ranking, LLM judge | Explainable, cheap, testable; data too sparse for learning | Adopted |
| DR-05 | Show qualitative labels and shared-item reasons, never percentages | Show score % | Avoid implying validated compatibility | Adopted |
| DR-06 | One stable per-pair pseudonymous alias derived from canonical user pair | Per-user public handle; current mixed aliases | Consistency without cross-pair tracking | Adopted |
| DR-07 | Requests carry the counterpart's public card | Anonymous requests (current) | Informed consent to connect | Adopted |
| DR-08 | Three MVP activities (Icebreaker, Quiz, Focus), one non-terminal activity per connection | More kinds; parallel activities | Scope control; simpler UI and invariants | Adopted |
| DR-09 | Static, versioned, server-side content banks | AI-generated content | Predictable, moderated, no cost | Adopted |
| DR-10 | Retire outbox (stop writes, purge, drop post-MVP) | Repurpose as event bus | No consumer; watermark design makes it unnecessary | Adopted |
| DR-11 | Role-gated staff moderation (API + minimal admin screen), manual review | External tool; CLI only; automated classifiers | Smallest safe workflow for 50 users with auditability | Adopted |
| DR-12 | Per-user daily AI turn quota + global daily spend ceiling | Monthly caps; no caps | Bounded cost exposure; uses existing accounting | Adopted |
| DR-13 | Read markers for unread counts; no read receipts to peers | Read receipts | Privacy-preserving engagement signal | Adopted |
| DR-14 | Four expand-only migrations (0011–0014), reviewed offline SQL for hosted | Single big migration | Independent rollout and review per phase | Adopted |
| DR-15 | Keep single worker; no horizontal scaling in MVP | Multi-worker with Redis | Capacity envelope sufficient; avoids rewrite of in-memory limits | Adopted |
| DR-16 | Readiness accepts a small set of heads (`READY_REVISIONS`) | Exact single head | Enables app rollback after expand-only migrations | Adopted |
| DR-17 | English practice is post-MVP | Include in MVP | Needs turn-taking + bilingual content + longer free-text moderation | Adopted |
| DR-18 | Soft goal compatibility with opt-in `strictGoal` | Hard goal equality (current) | Small pool coverage; user control preserved | Adopted |

## 2. Open questions (material only)

| ID | Question | Owner | Default if unanswered | Blocks |
|---|---|---|---|---|
| Q-01 | Confirm DR-03: should profile edits keep existing connections? | Product owner | Keep connections (DR-03) | B-02 merge (implementation may proceed; confirm before release R1) |
| Q-02 | Provider data processing: OpenAI/Voyage retention, region, DPA for private content | Product owner + legal | Keep `SEMANTIC_MEMORY_ENABLED=false`; AI on only with existing synthetic-scope evidence until confirmed | G8 |
| Q-03 | Who moderates, escalation for self-harm/threats, response SLA | Product owner | 48 h triage, founder as admin | G7, I-02 runbook |
| Q-04 | Supabase plan: backups/PITR, leaked-password protection (paid) | Product owner | Weekly logical backups by operator | G10 |
| Q-05 | SMTP provider for Auth emails | Product owner | None — launch blocker | G12 |
| Q-06 | AWS account approvals, region, domain, budget | Product owner | Staging stays BLOCKED | G10, J-04 |

## 3. Risk register

| ID | Priority | Risk | Likelihood | Impact | Mitigation | Owner/task |
|---|---|---|---|---|---|---|
| RK-01 | P0 | Real users without moderation workflow | High | High | Phase I before beta (G7) | I-01…I-03 |
| RK-02 | P0 | Profile edits close friendships (DEF-01) | High | High | DR-03 / B-02 | B-02 |
| RK-03 | P0 | Uncapped AI spend with real users | Medium | High | I-05 + alarms | I-05, I-07 |
| RK-04 | P0 | Auth emails not delivered | Medium | High | Configure SMTP (Q-05) | external |
| RK-05 | P1 | Activity race conditions leak answers or duplicate sessions | Medium | High | Unique index, CAS, projections, race tests | D-03, T-ACT-02, T-ICE-01 |
| RK-06 | P1 | Small pool → empty discovery | High | Medium | Soft goals, cold-start boost, honest empty states, invite-based onboarding | C-03/C-04 |
| RK-07 | P1 | Scorer v2 not better than v1 | Medium | Medium | Offline gate + shadow mode; keep v1 | C-06 |
| RK-08 | P1 | Single-process restart drops SSE/RAM AI context | Medium | Low | Clients reconnect; server state persistent; deploy off-peak | — |
| RK-09 | P1 | Provider privacy not certified | Medium | High | Q-02; keep semantic memory off | I-08 |
| RK-10 | P1 | Self-declared age misuse | Medium | High | Report reason + suspension; invite-only beta | I-03 |
| RK-11 | P2 | Focus timer drift across devices | Low | Low | Server timestamps + offset re-sync | G-03 |
| RK-12 | P2 | Outbox table growth | Certain | Low | A-05 purge | A-05 |
| RK-13 | P2 | No backups/restore drill | Medium | High | I-07 runbook + drill | I-07 |
| RK-14 | P2 | Large `Social.tsx` refactor regressions | Medium | Medium | Barrel re-export; existing mocked + full-stack suites | D-07, H-02 |
| RK-15 | P2 | Hosted apply mistakes | Low | High | Offline SQL + rehearsal + hash approval (existing tooling) | J-03 |

## 4. External prerequisites (unresolved)

SMTP (Q-05) · Supabase plan decisions (Q-04) · AWS resources/domain (Q-06) · Legal privacy notice (Q-02) · Named moderators (Q-03) · Superpowers plugin installation for the implementation session (optional; local skills are sufficient).
