# Friendship Discovery — current-state audit

> Policy update, 2026-10-31: the approved global minimum is now **18+ for all MoodPrint**, including guests and personal features. Earlier 16+/teen statements below are historical audit evidence and are superseded by the [18+ rollout](../release/moodprint-18plus-0020-rollout.md). Friendship functionality and separate publication consent remain preserved.

Status: planning only. Inspected on 2026-10-31 (Asia/Bangkok). No implementation is authorized by this document.

## 1. Evidence boundary

- Expected and observed branch: `test/local-2026-10-30`; inspected HEAD: `d6eaf71908a13d31b3d9192e59ebf2f52129811e`.
- Pre-existing working-tree changes: `frontend/src/features/real/RealApp.tsx` and `frontend/src/features/real/journal/journal.css`. They were read where relevant and must be preserved. `.gitignore` must not be edited.
- Findings below come from local source, committed migrations/reviewed SQL, tests, and documentation. No hosted database, production settings, real member profiles, running UI, or live matching results were inspected. Code-supported behavior is not a claim of a passing runtime test.
- The approved textual brief is the visual authority: three questions, desktop builder/preview columns, compact choices, and a recommendation card with common ground and a starter. Reference screenshots were not attached to this session; no pixel-level fidelity claim is possible.
- Product problems in the brief are stakeholder observations, not findings from a conducted user study. Excess choices and delayed preview are independently supported by code.

## 2. Verified architecture and code map

Paths are repository-relative; line references describe this inspection snapshot. Proposed files appear only in documents 04–06 and are explicitly marked new.

| Evidence | Existing location | Observed responsibility |
| --- | --- | --- |
| E01 | `frontend/src/features/real/RealApp.tsx:813` | `/connect` renders `Discovery`; guests render `GuestLocked`. `/messages` and `/chat/:connectionId` share the guest restriction. |
| E02 | `frontend/src/features/real/social/Discovery.tsx:32` | Fetches taxonomy, draft, current publication, candidates and requests; URL `?tab=`; saves parent resource results; refreshes session after publication. |
| E03 | `frontend/src/features/real/social/ProfileEditor.tsx:17` | Default profile, five steps, React local state, explicit draft save, server preview and publication; dirty-close confirmation. |
| E04 | `frontend/src/features/real/social/profileRules.ts:14` | Five-step definition, taxonomy limits, validation, immutable tag toggling. |
| E05 | `frontend/src/features/real/social/TagPicker.tsx:5` | Grouped native checkbox chips, counters, max disables unselected controls; the square checkbox remains visible in CSS. |
| E06 | `frontend/src/features/real/social/CandidateCard.tsx:14` | `SeedAvatar`, shared `PeerCard`, `CandidateCard`; candidate invite/skip/block actions. No conversation starter. |
| E07 | `frontend/src/features/real/social/RequestCard.tsx` | Reuses `PeerCard` for pending incoming/outgoing requests; protect this consumer when changing public card markup. |
| E08 | `frontend/src/features/real/social/social.css` | Existing chip/card/tab styles; two-column recommendation grid at 768px; facts stack at 420px. No builder/live-preview layout. |
| E09 | `frontend/src/components/UI.tsx:31` | Shared Button, StatePanel and native Dialog. Dialog owns focus restoration/trapping, Escape, and a reduced-motion-aware GSAP entrance. |
| E10 | `frontend/src/styles/tokens.css` | Global warm light background, green semantic palette, Segoe UI stack, spacing, 44px targets, motion tokens. |
| E11 | `frontend/src/styles/App.module.css:138`; `frontend/src/styles/me2we.css:799` | Reading container capped at 45rem; mobile navigation and page safe-area/bottom padding. A two-column editor needs a scoped width override. |
| E12 | `frontend/src/api/client.ts:24`; `backend/app/contracts.py:19` | Same-origin `/api/v1` BFF transport, cookie credentials, CSRF/idempotency, session epoch/abort; DTO camelCase JSON, snake_case Python, unknown fields forbidden. |
| E13 | `backend/app/modules/social/routes.py:61` | Actual profile, preview, matching, request and block routes. Profile APIs live here, not in `profiles/routes.py`. |
| E14 | `backend/app/modules/social/schemas.py:20` | Validated `PublicProfile`; draft/preview/publish/candidate/request DTOs. |
| E15 | `backend/app/modules/social/service.py:48` | Publishability, payload allowlist, consent/adult/registered eligibility, pair policy, quotas, pseudonyms and explanation dispatch. |
| E16 | `backend/app/modules/social/retrieval.py:45` | SQL exclusions and bounded retrieval; configured v1/v2/shadow ranking; locked recheck in route. |
| E17 | `backend/app/modules/profiles/taxonomy_v2.json`; `taxonomy.py` in the same directory | Canonical 30 interests, 8 values, 3 styles, 4 goals, 2 languages, 4 activities, 6 availability slots; `/taxonomy` in `profiles/routes.py`. |
| E18 | `backend/app/modules/matching/scoring_compat.py`; `scoring_v2.py:15`; `ranking.py:15`; `explain.py` | Legacy-compatible and v2 scoring, diverse ranking, truthful shared-data reasons. |
| E19 | `backend/app/modules/social/models.py:26` | JSONB draft/published payloads, versions/digests, candidate refs, canonical pairs, blocks, requests and rooms. |
| E20 | `deploy/supabase/reviewed-sql/supabase-initialization-review.sql:435`; `backend/alembic/versions/0011_social_stabilization.py`; `0012_matching_v2.py` in the same directory | Runtime role access, RLS and social/matching expansion history. |
| E21 | `frontend/src/features/real/Safety.tsx:371`; `backend/app/modules/moderation/routes.py:384`; `schemas.py` in that directory | Reporting after interaction, private identity grants and moderation. Discovery has blocking, no candidate-only report action. |
| E22 | `frontend/package.json`; `backend/pyproject.toml` | React 19/Vite/TypeScript, custom CSS, GSAP 3.13 range and @gsap/react; FastAPI, SQLAlchemy, Pydantic, Alembic, OpenAI Agents SDK. Vitest, Playwright/axe and pytest already exist. No Tailwind/shadcn dependency in this frontend manifest. |
| E23 | `frontend/src/features/real/RealApp.tsx:1982`; `frontend/src/features/real/journal/useJournalGuard.tsx:6` | Declarative HashRouter; journal guard already intercepts internal anchor clicks, native popstate and beforeunload, with a pending callback. Reuse the pattern, not journal-specific copy or its discard-only dialog. |

`DESIGN.md` is explicitly scoped to AI conversation; its white/charcoal overrides must not become friendship colors. `PRODUCT.md` contains prior chat-task context, not authorization to redesign the chat in this task. Global tokens and actual social CSS take precedence for this surface.

## 3. Current journey

1. Registered eligible user opens `/#/connect`. With a live profile the default tab is suggestions; otherwise profile. Tabs include suggestions, requests, profile and private identity. Tab changes use URL replacement and keyboard arrow/Home/End navigation.
2. Matching UI checks `features.matching`, `ageBand === adult`, and absence of restriction notices. Ineligible accounts only see identity and a truthful restriction explanation. The product as a whole supports 16+, but friendship is **18+ today** (E02/E15). The redesign must retain that boundary.
3. User opens the editor. It hydrates from a versioned draft, otherwise published profile, otherwise defaults. Steps are interests → values → style/goal/languages → optional activities/availability → preview.
4. All interest groups render together. Publishing requires 3–10 interests, 2–4 values and 1–2 languages. Drafts may be incomplete. Style defaults to `balanced`, goal to `friendship`; these defaults are not evidence of a user's personality.
5. Draft save uses version-checked PUT. Last questionnaire action saves and POSTs preview. Only then is a server card available. Ordinary selections do not create a preview request.
6. User reads sharing explanation and clicks `Hiển thị hồ sơ`. Publish uses the reviewed draft version, preview digest and expected publication version. If MATCH consent was off, this explicit operation enables it and records consent (E13).
7. Success refreshes session, resources and suggestions. Publication is a versioned snapshot, so draft changes do not edit the live profile. Withdraw hides the profile; consent withdrawal is a different operation and can invalidate social interactions.

Privacy footer from the approved brief is accurate for a first draft. When editing an already-live profile, it requires an additional explanation that the old published snapshot remains visible until explicitly replaced/withdrawn.

## 4. Current contracts and persistence

All paths below are relative to `/api/v1`; the frontend client adds that prefix.

| Route | Relevant contract / behavior |
| --- | --- |
| GET `/taxonomy` | `TaxonomyDTO`; canonical IDs, labels, categories and limits. |
| GET / PUT `/profiles/matching-draft` | `DraftView {profile, version, publishedVersion}`; PUT `DraftInput` adds `expectedVersion`. Existing save is full replacement, not PATCH. 409 `STALE_VERSION` on conflict. |
| POST `/profiles/matching-draft/preview` | Validates minimums; returns `{profile, draftVersion, previewDigest}`. Stores a random 64-character token with 15-minute expiry. Despite its name this is not a payload hash computed by the client. |
| GET `/profiles/published/current` | Null or snapshot with state `live`, `needs_republish`, `stale`, plus `profileVersion`. |
| POST `/profiles/published` | `{draftVersion, previewDigest, expectedPublishedVersion}`; 201 on publish; 409 `PREVIEW_CHANGED` if version/digest/expiry changed. No implicit publication. |
| DELETE `/profiles/published/current` | `{expectedVersion: profileVersion}`; withdraw snapshot, increment account profile version. |
| GET `/matching/candidates` | Up to 5 `CandidateCardDTO`: opaque `candidateRef`, pair `alias`, `avatarSeed`, permitted `profile`, ≤3 `reasons`, `matchLabel`, `sharedActivities`, `scoringVersion`, profile/peer versions. No percentage. |
| POST `/matching/skips` | `{candidateRef}`; applies pair cooldown. |
| POST / GET `/connection-requests` | Send by `{candidateRef}`; list incoming/outgoing; accept/decline/cancel existing routes use versions. |
| POST `/blocks` | `{peerRef}` using an owned opaque candidate reference. |

`PublicProfile` currently contains `interests`, `values`, `style`, `goal`, `languages`, `activities`, `availability`, `strictGoal`. All IDs are allowlisted; duplicate multi-select IDs fail validation. There are no featured-interest, four-intention, or three-connection-approach fields. `extra=forbid` means simply posting new UI keys to today's API will fail.

`moodprint.matching_drafts.payload` and `moodprint.published_profiles.payload` are JSONB. Draft row is owner-keyed with version and preview token/expiry. Published rows have unique owner/version and a partial unique active-owner index. Candidate refs bind both parties' profile and consent versions and expire after 15 minutes. `taxonomy_version` is stored per published row; it must stay v2 if canonical taxonomy is unchanged.

Reviewed initialization enables RLS and grants table access only through the backend runtime role (`backend_access` policy). Supabase browser API roles are not the cross-user access layer here. Backend ownership, eligibility and pair checks are essential because the runtime policy permits backend DML broadly. No client-side direct table query is justified. Hosted grants/policies were not verified.

## 5. Taxonomy mismatches that affect the redesign

| Approved choice | Existing compatibility |
| --- | --- |
| Music, coffee, games, movies, reading, travel | Existing IDs `music`, `coffee`, `games`, `movies`, `reading`, `travel`. UI `Xem phim` can label `movies`; do not rename its stored ID. |
| Creativity | A category, not an interest ID. Concrete options include photography/drawing/writing/crafts/singing; music already has its own compact chip. Do not store a fictional `creative` interest. |
| Sports | Existing `active` category contains walking/running/cycling/yoga/football/badminton. A generic `sports` ID does not exist. |
| Talk / shared interests / study / experiences | Existing goals are friendship/shared-interests/study-buddy/language-practice. Experiences has no exact goal; talk is narrower wording than existing friendship. |
| Gradual / lively / activity first | Existing styles balanced/listening/direct describe a different dimension. Listening is not evidence of gradual familiarization; direct does not mean lively. |

Recommendation: add optional validated discovery metadata inside the existing public JSONB payload, preserve legacy canonical fields, and avoid taxonomy/scorer changes. See [technical contract](04-technical-specification.md). A frontend-only label substitution would lose intent fidelity, draft restoration and truthful recommendation explanations.

## 6. Matching behavior that must survive

- `backend/app/core/config.py:46` defaults scorer to `v1`; actual deployment override is unknown. `shadow` serves v1 order while computing v2 aggregate comparisons. Do not assume v2 is active or change its setting in this redesign.
- v1.1 requires identical canonical goals, shared language and score ≥30. Score is rounded from 45% interest Jaccard + 35% value Jaccard + 20% style compatibility. Unknown/incomplete canonical profiles score zero. Tie order is peer UUID.
- v2 weights I/V/G/P/S/T are .30/.20/.15/.15/.10/.10. Available components are normalized, with a coverage multiplier `.9 + .1 * coverage`. Threshold .30 additionally requires an exact shared interest, value or activity. `many` starts at .60; these are internal ranking labels, not probabilities.
- v2 curated interest similarity includes same-category similarity and specific pair overrides; a similar interest is not an exact common interest. Soft goals apply unless either party sets `strictGoal`.
- v2 ranking uses a .03 new-profile boost for 7 days; .05 penalty per pending incoming request above 2; MMR λ=.85 with daily viewer-specific tie breaks. Scan cap 1000, shortlist 10, final cards ≤5.
- SQL excludes self, guests, inactive/deletion-pending/restricted/non-adult accounts, missing or mismatched MATCH consent/current snapshot, stale profiles (>180-day boundary), no common language, strict-goal mismatches, blocks in either direction, cooldowns, open rooms and live/recently lapsed pending requests.
- Peer activity window is 30 days. Null `last_seen_at` has a grace rule until **2026-12-31 00:00 UTC**, after which recently-seen is required. Preserve and test both time branches.
- Candidate output is rechecked under canonically ordered shared account locks; writes retain exclusive gates. New public metadata must not bypass that recheck or expose peer IDs.
- Skip/decline/cancel/end have 30-day cooldown logic; pending invitation lifetime is 7 days. Invitation quotas are 10/day and 10 outstanding; message quota 20/minute. Preserve existing policy rather than recreating it in a card.
- Editing/replacing/withdrawing a publication changes discovery; existing rooms/requests are primarily bound to consent, not publication versions (E15 `room_gate`). Do not close friendships on ordinary profile edits.
- Existing explanations use exact shared interests/values, and v2 adds activities/style/availability. No psychological compatibility claim is supported.

## 7. Identity, report and private-data boundaries

The card name is a **pair pseudonym**, generated in `service.py:291`, with a decorative seed avatar. It is not the session alias or a real name. Owner preview currently uses `Bạn` and seed `00`. The approved request permits a clearly defined placeholder; retain that privacy-preserving option and explain that the pair alias varies by viewer. Do not promote private identity fields or an account avatar to a public card.

Candidate card supports invite, skip and block. Report UI exists in `Safety.tsx` around human chat, including after closing/blocking. The report API requires an owned unexpired reference **and an existing interaction room**; no candidate-only reporting is currently supported (`INTERACTION_REQUIRED`). Keep chat reporting reachable; a new candidate-report feature is outside MVP and would need its own policy.

Scorers/retrieval consume explicit public snapshots only; journal, mood, AI memory and transcript content are not inputs. OpenAI Agents SDK exists elsewhere in backend, but no AI inference is needed or currently used for the matching card audited here. Supabase Storage is used elsewhere; the existing friendship avatar is generated in CSS, not fetched from Storage.

## 8. UX findings and constraints

| Finding | Evidence / confidence | Design implication |
| --- | --- | --- |
| Up-front taxonomy density | E03/E05/E17: all 30 interests and category headings render together; verified code | Show eight entry choices; category picker is secondary and bounded. |
| Delayed reward | E03: card only after server preview at step five; verified | Derive live preview locally from one reducer. |
| Survey-like sequence | E03/E04: five gates with radio/checkbox facets; verified | Three main questions; retain only missing legacy-required metadata at prepublication review. |
| Existing useful accessibility | E05/E09: native inputs, fieldsets, counters, dialog focus; verified | Keep semantics while hiding checkbox glyphs; do not replace them with clickable divs. |
| No unsaved-route guard | E03: close-button confirmation only; no beforeunload/router guard in editor; verified inspection | Cover tab/route changes, Back and reload explicitly. |
| Narrow content wrapper | E11: 45rem reading width; verified | Scoped discovery container up to 70rem and container-aware grid. |
| Potential broad shared-card regression | E06/E07 | Share presentation model, preserve request actions and heading levels. |
| Completion/time/frustration rates | No analytics or new study inspected | Set proposed metrics; establish a baseline later, do not invent results. |

## 9. Existing verification assets

- Unit rules: `frontend/src/features/real/social/profileRules.test.ts`; transport/session tests in `frontend/src/api/`.
- Browser mocks: `frontend/tests/e2e/discovery.spec.ts`, `social.spec.ts`, `states.spec.ts`, `motion.spec.ts`; Playwright config explicitly enumerates test filenames. Add scenarios to existing registered files by default.
- Real local stack: `frontend/tests/fullstack/matching-v2.spec.ts`, `moderation.spec.ts`, `local-mvp.spec.ts`, `responsive.spec.ts`; `scripts/test_fullstack.py` owns disposable servers. Do not treat mocked browser tests as evidence for server consent/RLS.
- Backend: `backend/tests/test_profile_v2.py`, `test_social.py`, `test_matching_compatibility.py`, `test_matching_privacy.py`, `test_matching_retrieval_v2.py`, `test_scoring_v2.py`, `test_ranking.py`, `test_explain.py`, `test_pair_alias.py`, `test_privacy_lifecycle.py`, `test_enforcement.py`, `test_moderation_admin.py`.
- DB fixtures in `backend/tests/conftest.py` reset schema and require an explicitly guarded local disposable `_test` PostgreSQL DB. They were not run for this planning task.

## 10. Risk conclusion and unknowns

The smallest faithful redesign needs an additive API DTO change, but no new endpoint, SQL column, migration, index or RLS policy is currently justified. Keep existing publication minimums and scorer modes. The remaining onboarding cost is a compact review panel for missing values/languages; removing that cost would be a separate matching-policy decision, not a cosmetic change.

Unverified: hosted schema parity, active scorer, available live candidate population, actual UI contrast/rendering and user completion time. These become release preflight/validation items, with conservative defaults in [decision log](07-open-questions-and-decisions.md).
