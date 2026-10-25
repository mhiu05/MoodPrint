# 00 — Executive Summary

**Audience:** product owner and the engineer/agent who will implement the plan. **Revision audited:** `5689dd9` (main), 2026-10-25.

## Where MoodPrint stands

- **Pillar A (AI self-discovery) is real and verified**: five assistants on the OpenAI Agents SDK, opt-in persistent history, explicitly approved memories, mood tracking with insights, privacy controls, export and deletion. 278 backend tests pass on real PostgreSQL (re-run in this session); prior full-stack, hosted and live-AI runs passed.
- **Pillar B (human connection) is real but not yet a product**:
  - matching still runs the `mock-v1` frontend-parity oracle on a 7-interest taxonomy;
  - **editing your matching profile closes all your friendships** (DEF-01);
  - connection requests are anonymous (DEF-02);
  - the same person appears under two different aliases (DEF-03);
  - there are no unread indicators;
  - **shared activities exist only as a simulated prototype**;
  - **reports are never reviewed**.
- **The legacy prototype** (`App.tsx`, `pages/`, `state/`, `mocks/`, `domain/`) is no longer reachable in production but still carries 77 of the 89 frontend unit tests.
- **Operations:** CI is strong. Staging on AWS is scripted but blocked on resources. There is no AI spend cap, no moderation workflow and no restore drill.

## What we will build (MVP for ~50 users)

1. **Cleanup** — delete the prototype; guard tests make demo data impossible in production.
2. **Stabilize connections** — profile edits no longer close rooms (decision DR-03, needs owner confirmation), requests show the sender's public card, one alias per pair, unread counts and navigation badges.
3. **Matching v2** — 30 interests in 6 categories, 8 values, 4 goals, shared-activity preferences, optional availability. Deterministic, symmetric, explainable scoring with honest reason chips (no percentages), fair exposure, and a rollback flag. It is enabled only after an offline benchmark beats v1.
4. **Shared activities in chat** — Icebreaker (reciprocal reveal), Cooperative Quiz (team score), Shared Focus (server-timed Pomodoro). All are server-authoritative, synchronized through the existing chat event stream, and resumable after reload.
5. **Safety and operations** — staff moderation queue with warn/restrict/suspend, a daily AI quota and spend ceiling, a privacy notice draft, alarms and backup runbooks, and a 50-user load qualification.

No new services or vendors. Four expand-only migrations (0011–0014). All new behavior is behind flags.

## Roadmap at a glance

| Phase | Theme | Size |
|---|---|---|
| A | Prototype removal, baseline | S–M |
| B | Durable, informed connections + unread | M |
| C | Matching v2 + evaluation | L |
| D | Activity framework | L |
| E/F/G | Icebreaker / Quiz / Focus | M each |
| H | UX integration, responsive/a11y | M |
| I | Moderation, enforcement, AI cost, privacy, ops | L |
| J | Full-stack, load, hosted migration (approval), staging (approval), go/no-go | M–L |

Release trains R1 (A+B) → R2 (C) → R3 (D–H) → R4 (I+J). **A real-user beta requires R4**: moderation is a launch blocker.

## Decisions needed from the product owner

- **Q-01** — confirm that profile edits keep existing connections.
- **Q-02** — provider data processing and legal privacy notice.
- **Q-03** — who moderates, and the escalation path.
- **Q-04** — Supabase plan: backups and leaked-password protection.
- **Q-05** — SMTP for signup and recovery emails.
- **Q-06** — AWS resources and domain.

## Where to start

Read [14 — Implementation handoff](14-implementation-handoff.md), then execute the [implementation plan](../plans/2026-10-25-moodprint-productization-implementation.md) from task A-01.
