# MoodPrint Productization — Design

Date: 2026-10-25 · Status: **proposed, awaiting product-owner approval** · Implementation plan: [2026-10-25-moodprint-productization-implementation.md](2026-10-25-moodprint-productization-implementation.md) · Detailed specs: [docs/productization/](../productization/README.md)

## 1. Intent and why

MoodPrint already has a real, well-tested AI self-discovery pillar (five assistants, history, approved memories, mood insights) and a real but thin human-connection pillar. The goal is a genuine multi-user product for ~50 real users where **both** pillars are complete: users understand themselves with AI, then meet compatible people through explained suggestions, connect by mutual consent, talk, and do small shared activities together, safely.

Why now: the audit ([01](../productization/01-codebase-audit.md)) found that Pillar B is the gap. Republishing a profile silently closes friendships; requests are anonymous; matching still runs the `mock-v1` parity oracle; there are no shared activities in production (only a simulated prototype); and nobody can act on reports.

## 2. Goals, non-goals, anti-goals

**Goals**

1. Remove every prototype/demo path from production.
2. Make connections durable and consent informed (sender cards, aliases, unread state).
3. Ship matching `rules-v2`: richer taxonomy, explainable reasons, fair exposure, versioned rollback, offline evaluation.
4. Ship three server-authoritative shared activities (Icebreaker, Cooperative Quiz, Shared Focus) inside human chat.
5. Ship staff moderation with enforcement, AI cost caps, privacy coverage, and release qualification for 50 users.

**Non-goals (MVP)**: English practice, semantic profile embeddings, notifications beyond in-app badges, multi-worker scaling, group activities, AI-generated activity content, unblock/appeals UI.

**Anti-goals**: fake users or simulated peers; numeric "compatibility %"; using moods/notes/AI conversations/memories for matching; new realtime vendors or microservices; destructive migrations.

## 3. Constraints

React + Vite + TypeScript · Python 3.12 + FastAPI · OpenAI Agents SDK · Supabase PostgreSQL/Auth · SQLAlchemy async + Alembic · existing Voyage/pgvector · existing Docker/AWS/GitHub Actions. Single worker topology. Expand-only migrations applied to hosted only through reviewed offline SQL with approval. Tests only on disposable local `*_test` databases. Vietnamese UI.

## 4. Approaches considered

| Topic | Options | Chosen | Why |
|---|---|---|---|
| Activity sync | (a) extend per-connection SSE watermark · (b) WebSocket · (c) LISTEN/NOTIFY · (d) Supabase Realtime | **(a)** | No new infra, authorization stays in HTTP reads, already load-tested |
| Activity state | (a) server-authoritative rows + pure state machine · (b) client-side with server relay | **(a)** | Integrity, reconnect/resume, no fabricated outcomes |
| Matching | (a) tune v1 · (b) deterministic weighted taxonomy scorer · (c) + embeddings · (d) learned ranking · (e) LLM judge | **(b)**, (c) post-MVP behind flag | Explainable, cheap, fits sparse small pool |
| Republish semantics | (a) keep close-on-republish · (b) connections survive profile edits | **(b)** (DR-03, needs PO confirmation) | Profile edits should change discovery, not consent |
| Moderation | (a) staff role + admin API/screen · (b) DB console only · (c) external tool | **(a)** | Auditable, minimal, within the app's auth model |
| Cost control | (a) per-user daily quota + global ceiling · (b) none | **(a)** | Real users + paid model |

## 5. Decided parts of the how

- **Architecture** — [04](../productization/04-target-architecture.md): new `app/modules/activities` module; `activities/hooks.py` is the only coupling from social → activities; frontend split into `features/real/social/*` and `features/real/activities/*`.
- **Matching** — [05](../productization/05-matching-design.md): taxonomy v2 JSON as single source; formula `I .30, V .20, G .15, P .15, S .10, T .10` with renormalization and coverage factor; threshold 0.30 + one exact shared item; cold-start boost, load penalty, MMR, daily tie-break; `MATCHING_SCORER=v1|v2|shadow`.
- **Activities** — [06](../productization/06-shared-activities-design.md): common state machine; one non-terminal session per connection; reciprocal reveal; hidden quiz answers; focus timer with server timestamps and presence intervals; sweeper with `deadline_at`; invitation quotas.
- **Contracts and migrations** — [07](../productization/07-database-and-api-contracts.md), [11](../productization/11-migration-and-rollback.md): 0011–0014, `READY_REVISIONS` tolerance, feature flags for rollback.
- **UX** — [08](../productization/08-frontend-ux-plan.md): Discovery tabs, request cards, unread badges, activity dock (sheet < 1100 px / side panel ≥ 1100 px), explicit both-screen flows, viewport acceptance criteria.
- **Security/ops** — [09](../productization/09-security-privacy-operations.md): suspension/restriction enforcement, admin re-auth, content-free metrics logs, alarms, backup/restore drill, privacy notice draft.
- **Testing** — [10](../productization/10-testing-evaluation-strategy.md): test catalog T-* mapped to requirements; two-actor race tests on real PostgreSQL; two-browser full-stack specs.

## 6. Left to the builder

- Exact Vietnamese copy beyond the strings given in the specs (keep tone of existing screens).
- Content of the Icebreaker (≥24) and Quiz (≥60) banks, within the validation rules (product-owner review recommended).
- Persona and label datasets for the matching benchmark (team raters).
- Internal helper decomposition inside modules, as long as the interfaces named in the plan exist.
- CSS details within the stated breakpoints and acceptance criteria.

## 7. Questions for the product owner (only material ones)

Q-01 confirm DR-03 · Q-02 provider data processing/legal · Q-03 moderators and escalation · Q-04 Supabase plan/backups · Q-05 SMTP for Auth emails · Q-06 AWS approvals/domain. Defaults and impact: [13 §2](../productization/13-risks-and-decisions.md#2-open-questions-material-only).

## 8. Builder check

A read-only reviewer pass over this design and the plan was run in the planning session; findings and their resolution are recorded in [14 §11](../productization/14-implementation-handoff.md#11-planning-review-record).
