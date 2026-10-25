# 05 — Matching System Design (`rules-v2`)

Goal: useful, explainable, privacy-preserving suggestions for a ~50-user pool, with fair exposure and a safe rollback. Similarity of self-selected public tags is **not** a validated psychological compatibility measure, and the product must never say it is.

## 1. Audit of the current implementation (`mock-v1`)

| Aspect | Today | Evidence | Problem |
|---|---|---|---|
| Scorer | `45·Jaccard(interests) + 35·Jaccard(values) + 20·style`, half-up rounding, threshold 30 | [scoring.py:92](../../backend/app/modules/matching/scoring.py#L92) | Jaccard penalizes users who select more tags; values have only 4 options so value overlap is near-random |
| Version label | `mock-v1` in scorer, `rules-v1-id` in DTO | [scoring.py:11](../../backend/app/modules/matching/scoring.py#L11), [social/schemas.py:75](../../backend/app/modules/social/schemas.py#L75) | Wrong telemetry |
| Taxonomy | 7 interests, 4 values, 3 styles, 2 goals, 2 languages | [taxonomy.py](../../backend/app/modules/profiles/taxonomy.py) | Too coarse for meaningful reasons |
| Hard filters | goal equality, language overlap | `base_eligibility` in [service.py](../../backend/app/modules/social/service.py) | Goal equality halves a 50-user pool |
| Retrieval | ORM scan ordered by `User.id` (≤1000), then Python filtering with several follow-up queries | [retrieval.py:45](../../backend/app/modules/social/retrieval.py#L45) | Acceptable at 50 users; exclusion logic duplicated in route recheck |
| Tie-break | peer UUID string | [retrieval.py:117](../../backend/app/modules/social/retrieval.py#L117) | Same users always first |
| Explanations | shared interests, shared values, same style (≤3) | `reasons()` in [service.py](../../backend/app/modules/social/service.py) | Good principle (derived from shared items); keep |
| Privacy | only published payloads; `CandidateReference` binds versions | [social/models.py:47](../../backend/app/modules/social/models.py#L47) | Correct; keep |

The locked two-transaction recheck in the candidates route (shortlist → lock users in canonical order → re-verify → mint 15-minute references) is sound and is **kept**.

## 2. Selected architecture and alternatives

**Selected: hybrid "SQL eligibility retrieval → deterministic taxonomy scorer → fairness/diversity re-rank → locked recheck".** No runtime LLM or embedding calls.

| Option | Pros | Cons | Verdict |
|---|---|---|---|
| A. Keep v1, add tags | Trivial | Keeps Jaccard flaws, hard goal split | Rejected |
| **B. Deterministic weighted taxonomy similarity (rules-v2)** | Explainable, symmetric, fast, testable, zero provider cost, works with sparse data | Needs curated similarity matrix; weights are hypotheses | **Selected for MVP** |
| C. B + Voyage embeddings of published free text | Captures nuance beyond tags | Requires free text (moderation burden), provider disclosure, embedding pipeline; little benefit at 50 users | Post-MVP behind flag ([§10](#10-embedding-generation-and-invalidation-post-mvp-flag)) |
| D. Learned ranking from engagement | Optimizes real outcomes | No data at N≈50; feedback loops; opaque | Rejected for MVP |
| E. LLM judging pairs | Rich explanations | Cost per request, non-determinism, privacy risk, hallucinated reasons | Rejected (explicit constraint) |

**Use of Voyage/pgvector:** infrastructure exists and is sound (job leasing, version-bound vectors). For matching it is *appropriate later* for free-text "what I'd like to talk about" fields, *not* for a ~40-tag controlled vocabulary, where a curated similarity matrix is more accurate and explainable. Voyage may optionally be used **offline, once** to propose tag-to-tag similarities that a human then curates into the committed matrix (no runtime calls).

## 3. Taxonomy v2 (single source of truth)

File: `backend/app/modules/profiles/taxonomy_v2.json`, loaded by `backend/app/modules/profiles/taxonomy.py`. Keys are stable ASCII; labels Vietnamese. All v1 keys remain valid (backward compatible).

| Facet | Keys (v2) | Rules |
|---|---|---|
| interests (30, 6 categories) | learning: `reading`, `english`, `languages`, `science`, `history`, `tech` · creative: `photography`, `drawing`, `music`, `writing`, `crafts`, `singing` · active: `walking`, `running`, `cycling`, `yoga`, `football`, `badminton` · mind: `puzzles`, `chess`, `boardgames`, `meditation` · media: `movies`, `anime`, `podcasts`, `games` · lifestyle: `cooking`, `coffee`, `travel`, `plants` | 3–10 selections |
| values (8) | `respect`, `sincerity`, `curiosity`, `kindness`, `humor`, `growth`, `calm`, `reliability` | 2–4 selections |
| styles (3) | `balanced`, `listening`, `direct` | exactly 1 |
| goals (4) | `friendship`, `shared-interests`, `study-buddy`, `language-practice` | exactly 1 |
| languages (2) | `vi`, `en` | ≥1 |
| activities (4 in MVP) | `icebreaker`, `coop_quiz`, `focus`, `chat_only` | 0–4 |
| availability (6) | `weekday_morning`, `weekday_afternoon`, `weekday_evening`, `weekend_morning`, `weekend_afternoon`, `weekend_evening` | 0–6 (optional) |
| strict_goal | boolean | default `false` |

Similarity data in the same JSON:

- `interestSimilarity`: same tag 1.0; same category 0.5 by default; curated overrides (e.g. `english`↔`languages` 0.8, `running`↔`walking` 0.7, `boardgames`↔`chess` 0.7, `drawing`↔`crafts` 0.6, `podcasts`↔`reading` 0.4); otherwise 0.
- `goalCompatibility`: same 1.0; `friendship`↔`shared-interests` 0.7; `shared-interests`↔`study-buddy` 0.7; `study-buddy`↔`language-practice` 0.7; all other pairs 0.4.
- `styleCompatibility`: same 1.0; `balanced` with any 0.75; `listening`↔`direct` 0.5.

Migration of stored payloads: none required. v1 payloads lack `activities`, `availability`, `strictGoal`; they validate as v2 with empty/default values. `published_profiles.taxonomy_version` records `v1` or `v2`.

## 4. Explainable scoring formula

All components are in [0, 1] and **symmetric** (s(A,B) = s(B,A)).

```
I (interests)    = ( Σ_{a∈A} max_{b∈B} sim(a,b) + Σ_{b∈B} max_{a∈A} sim(a,b) ) / (|A| + |B|)
V (values)       = |A∩B| / min(|A|,|B|)
G (goal)         = goalCompatibility[gA][gB]
S (style)        = styleCompatibility[sA][sB]
P (activities)   = |A∩B| / min(|A|,|B|)          -- only if both non-empty, else MISSING
T (availability) = |A∩B| / min(|A|,|B|)          -- only if both non-empty, else MISSING

weights w = {I:0.30, V:0.20, G:0.15, P:0.15, S:0.10, T:0.10}
present  = components not MISSING
raw      = Σ_{k∈present} w_k·c_k / Σ_{k∈present} w_k
coverage = Σ_{k∈present} w_k                      -- in [0.75, 1.0]
score    = raw · (0.9 + 0.1·coverage)             -- mild preference for complete profiles
```

Eligible to show iff `score ≥ 0.30` **and** at least one exact shared item among interests, values or activities (guarantees a truthful reason). If either side has `strictGoal = true`, require `gA == gB` (applied as a hard filter, reciprocal by construction).

Displayed label: `score ≥ 0.60` → "Nhiều điểm chung", else "Có vài điểm chung". Numeric score is never shown.

### 4.1 Weight-selection rationale

- **Interests 0.30**: most observable, directly fuels first messages, has the richest vocabulary.
- **Values 0.20**: meaningful but coarse (8 options) and self-presentational; lower than interests.
- **Goal 0.15**: intent alignment matters, but a soft matrix keeps the small pool connected; users who care can set `strictGoal`.
- **Activities 0.15**: ties directly to Pillar B's in-app activities; shared preference predicts a first activity.
- **Style 0.10**: self-reported and complementary styles can work well; low weight.
- **Availability 0.10**: optional, weak signal; only matters when both provide it.

Weights are hypotheses, versioned with the scorer, and change only through the offline evaluation gate ([§12](#12-evaluation-datasets-and-benchmark-methodology)).

### 4.2 Worked example

A: interests {reading, english, coffee}, values {curiosity, kindness}, goal study-buddy, style balanced, activities {focus, coop_quiz}. B: interests {languages, reading, movies, cooking}, values {curiosity, humor}, goal language-practice, style listening, activities {focus}. Availability missing for B.

- I: A→B best = reading 1.0, english↔languages 0.8, coffee↔cooking 0.5 → 2.3; B→A best = languages 0.8, reading 1.0, movies 0, cooking↔coffee 0.5 → 2.3; I = 4.6/7 = 0.657
- V = 1/2 = 0.5 · G = 0.7 · S = 0.75 · P = 1/1 = 1.0 · T = MISSING
- raw = (0.30·0.657 + 0.20·0.5 + 0.15·0.7 + 0.15·1.0 + 0.10·0.75)/0.90 = 0.627/0.90 = 0.697; coverage 0.90 → score = 0.697·0.99 = **0.690** → "Nhiều điểm chung"
- Reasons: "Cùng thích đọc sách", "Cả hai muốn thử Tập trung cùng nhau", "Cùng coi trọng sự ham học hỏi".

## 5. Missing and sparse data

- Optional facets (activities, availability) are dropped from both numerator and denominator (no imputation).
- Required facets are enforced at publish, so they are always present.
- v1 profiles score with I, V, G, S only (coverage 0.75 → factor 0.975) — slightly below equal v2 profiles, which nudges users to update without hiding them.
- Stale profiles: hidden from discovery if published > 180 days ago without reconfirmation, or if the owner was not seen for 30 days (`users.last_seen_at`). The owner sees "Hồ sơ tạm ẩn vì lâu chưa cập nhật" with a one-click reconfirm (re-publish same draft through the normal preview).

## 6. Cold-start strategy

- New user: onboarding nudges to publish after the first AI conversation ends or after 3 days; the profile editor offers **examples**, never pre-filled values derived from private data. Cầu Nối can explain choices but cannot set them.
- New profile boost: +0.03 to ranking (not eligibility) for 7 days after first publish.
- Empty pool: honest empty state ("Chưa có ai phù hợp lúc này") with actions: widen goal (turn off strictGoal), add a language, add interests; never fabricate or show ineligible people. No pool-size disclosure.

## 7. Diversity and fairness

1. **Deterministic daily tie-break**: `tiebreak = sha256(viewer_id ‖ peer_id ‖ local_date)`; replaces UUID ordering.
2. **Load balancing**: ranking penalty `0.05 × max(0, pending_incoming(peer) − 2)`, so popular profiles are not flooded.
3. **Diversity re-rank** (MMR, λ = 0.85): pick 5 greedily maximizing `λ·rank_score − (1−λ)·max_sim_to_selected`, where similarity between candidates is their interest component I.
4. **No protected attributes** exist in the profile (gender is only an optional reveal field and is never used).
5. Fairness monitoring (offline + beta): exposure Gini across eligible users, share of users never shown in 7 days.

Final ordering key: `rank_score = score + cold_start_boost − load_penalty`, then MMR, then tie-break.

## 8. Versioning and rollback

- `SCORING_VERSION` constants: `rules-v1` (renamed from `mock-v1`) and `rules-v2`.
- Setting `MATCHING_SCORER` ∈ {`v1`, `v2`, `shadow`}; default `v1` until the evaluation gate passes, then `v2`.
  - `shadow`: serve v1; compute v2 in-process and log content-free comparison (`matching_shadow overlap_at5=<0..1> v1_count=<n> v2_count=<n>`); no IDs.
- `candidate_references.scoring_version` and `rank` recorded per impression; `CandidateCardDTO.scoringVersion` reflects the real scorer.
- Rollback = flip the setting and restart (no schema change). v2-only profile fields are ignored by v1 (v1 validates only its subset).

## 9. SQL retrieval design

One query returns eligible peers; scoring happens in Python (deterministic, unit-tested). Parameters: `:me`, `:my_languages text[]`, `:my_goal`, `:my_strict bool`, `:now`.

```sql
SELECT u.id, p.version, p.payload, p.created_at AS published_at, c.version AS consent_version,
       (SELECT count(*) FROM moodprint.connection_requests r
         WHERE r.recipient_id = u.id AND r.status = 'pending' AND r.expires_at > :now) AS pending_incoming
FROM moodprint.users u
JOIN moodprint.published_profiles p
  ON p.user_id = u.id AND p.valid AND p.version = u.profile_version
JOIN moodprint.consents c
  ON c.user_id = u.id AND c.purpose = 'MATCH' AND c.enabled AND c.version = p.consent_version
WHERE u.id <> :me
  AND u.status = 'active' AND u.age_band = 'adult' AND NOT u.deletion_pending
  AND (u.social_restricted_until IS NULL OR u.social_restricted_until <= :now)   -- added by I-03
  AND u.last_seen_at > :now - interval '30 days'
  AND p.created_at > :now - interval '180 days'
  AND (p.payload -> 'languages') ?| :my_languages
  AND (NOT :my_strict OR p.payload ->> 'goal' = :my_goal)
  AND (coalesce((p.payload ->> 'strictGoal')::boolean, false) = false OR p.payload ->> 'goal' = :my_goal)
  AND NOT EXISTS (SELECT 1 FROM moodprint.blocks b
                  WHERE (b.blocker_id = :me AND b.blocked_id = u.id)
                     OR (b.blocker_id = u.id AND b.blocked_id = :me))
  AND NOT EXISTS (SELECT 1 FROM moodprint.pairs pr
                  WHERE pr.low_user_id = least(:me, u.id) AND pr.high_user_id = greatest(:me, u.id)
                    AND (pr.cooldown_until > :now
                         OR EXISTS (SELECT 1 FROM moodprint.connections cn
                                    WHERE cn.pair_id = pr.id AND cn.status = 'open')
                         OR EXISTS (SELECT 1 FROM moodprint.connection_requests r
                                    WHERE r.pair_id = pr.id AND r.status = 'pending' AND r.expires_at > :now)))
ORDER BY u.id
LIMIT 1000;
```

Binding note: build this with the SQLAlchemy expression API (`PublishedProfile.payload["languages"].has_any(array(langs))`, `func.least/greatest`, `exists()`), not raw `text()`, so the JSONB `?|` operator and array parameters bind correctly with psycopg 3. The existing locked recheck in the route remains the authority (it re-validates eligibility under row locks before minting references). Implementation: SQLAlchemy Core `text()` or expression API in `backend/app/modules/social/retrieval.py` (`eligible_peers()`), returning typed rows.

## 10. Embedding generation and invalidation (post-MVP, flag)

Only if a free-text published field (`talkAbout`, ≤160 chars) is introduced:

- Table `published_profile_embeddings(profile_id FK published_profiles ON DELETE CASCADE, model, dimensions, embedding extensions.vector, created_at)`, unique `(profile_id, model, dimensions)`, plus a job table modeled on `memory_embedding_jobs` (lease, attempts, consent-version snapshot).
- Enqueue on publish when `MATCHING_SEMANTIC_ENABLED=true`; Voyage `input_type=document`; validate with `validate_vector`.
- Invalidation: new publish creates a new profile row (old row `valid=false` → embedding ignored; purge daily); withdraw, MATCH withdrawal and deletion purge immediately.
- Retrieval: exact cosine `1 − (e1 <=> e2)` over ≤1000 rows; **no ANN index** below ~10k profiles.
- New component `E` weight 0.10, taken proportionally from I and V; explanation uses only tags (free text is never quoted as a reason).
- Disclosure: editor states that this text is sent to Voyage AI to compute similarity.

## 11. Privacy and consent boundaries

- Inputs: only the current, valid, consented published profile row plus counters derived from social tables (pending incoming count). **Never** moods, notes, private items, AI conversations, proposals, memories, embeddings of memories, identity fields or activity answers.
- Enforced by: module import allowlist test (`tests/test_matching_privacy.py`), DTO `extra="forbid"`, and the existing `CandidateReference` version binding.
- Explanations reference only items present in **both** published profiles.
- Logs contain no IDs or tags; shadow logs only aggregate numbers.

## 12. Evaluation datasets and benchmark methodology

Location: `backend/evals/matching/`.

- `personas_v2.json`: 60 synthetic personas (no real data) spanning all goals/languages; 20 % v1-shaped, 30 % without availability, 10 % "sparse" (minimum selections).
- `pair_labels.json`: 300 persona pairs, each labeled by 3 team raters on "would plausibly enjoy a first conversation" (0 = no, 1 = maybe, 2 = yes); store the per-rater labels and report Krippendorff's α (target ≥ 0.4; otherwise refine guidelines).
- `benchmark.py`: for each persona as viewer, rank all others with v1 and v2 (eligibility applied), compute NDCG@5 against mean labels, Precision@5 (label ≥ 1.5), coverage (viewers with ≥1 candidate), mean candidates/viewer, exposure Gini, reason faithfulness (must be 100 %), symmetry violations (must be 0), runtime per viewer at 60 and 600 personas (replicated).
- Gate to switch `MATCHING_SCORER=v2`: NDCG@5(v2) ≥ NDCG@5(v1) + 0.05, coverage(v2) ≥ coverage(v1), Gini(v2) ≤ Gini(v1), faithfulness 100 %, p95 scoring time for 600 personas < 50 ms per viewer.
- Output: `backend/evals/matching/report.json` and a Markdown summary committed with the switch.

## 13. Real-user beta metrics

Computed weekly by `scripts/report_beta_metrics.py` (read-only, aggregated, cells < 5 suppressed): candidate coverage, impressions → request rate, acceptance rate, time to first message, both-sides-replied-in-24h, activity start/completion, 7-day continuation, skip rate, block/report per connection, per-scorer version split. Source: `matching_stats_daily` (counts only) plus aggregate queries over existing tables. Qualitative: short interviews with 5–10 users about suggestion relevance and reason usefulness.

## 14. API and database changes

| Change | Where |
|---|---|
| `PublicProfile` adds `activities: list[str]`, `availability: list[str]`, `strictGoal: bool`; validators read taxonomy v2 | `backend/app/modules/social/schemas.py` |
| `TaxonomyDTO` adds `activities`, `availability`, `categories`, `version: "v2"` | `backend/app/modules/profiles/taxonomy.py` |
| `CandidateCardDTO`: `scoringVersion: Literal["rules-v1","rules-v2"]`, `matchLabel: Literal["many","some"]`, `reasons` (≤3), `sharedActivities: list[str]` | `backend/app/modules/social/schemas.py` |
| `published_profiles.taxonomy_version varchar(8) not null default 'v1'` | migration `0012_matching_v2` |
| `candidate_references.scoring_version varchar(16) not null default 'rules-v1'`, `rank smallint null` | `0012` |
| `matching_stats_daily(day date, scoring_version varchar(16), impressions int, requests int, accepts int, primary key(day, scoring_version))` | `0012` |
| `users.last_seen_at timestamptz` (from B-04 `0011`) | `0011` |
| Setting `MATCHING_SCORER` | `backend/app/core/config.py` |

Full contracts: [07](07-database-and-api-contracts.md).

## 15. Implementation tasks

C-01 taxonomy v2 · C-02 migration 0012 + profile v2 schema · C-03 scorer v2 (pure) · C-04 retrieval/ranking/flag · C-05 explanations + DTO · C-06 offline evaluation · C-07 profile editor + candidate card UI · C-08 beta metrics. Details, tests and verification: [implementation plan, Phase C](../plans/2026-10-25-moodprint-productization-implementation.md#phase-c--matching-improvements).

## 16. Index and performance recommendations

- Add `ix_blocks_blocked_id`, `ix_candidate_references_peer_id`, `ix_connection_requests_recipient_status (recipient_id, status)` in `0011` (advisor INFO + pending-incoming count).
- Existing indexes cover the rest: `uq_published_active_owner`, consents PK, `uq_pairs` (low, high), `uq_open_pair`, `uq_pending_pair`.
- Expected cost at 50 users: one retrieval query (< 10 ms) + Python scoring of ≤ 50 peers (< 2 ms) + locked recheck of ≤ 10 peers (existing p95 ≈ 0.8–1.6 s under burst is dominated by the recheck; reduce the shortlist from 10 to 8 if needed).
- Do not add GIN/vector indexes until profiles > 10k.
