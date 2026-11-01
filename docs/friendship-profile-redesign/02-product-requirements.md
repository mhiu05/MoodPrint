# Friendship Discovery — product requirements

> Policy update, 2026-10-31: the approved global minimum is now **18+ for all MoodPrint**, including guests and personal features. Earlier 16+/teen statements below are historical audit evidence and are superseded by the [18+ rollout](../release/moodprint-18plus-0020-rollout.md). Friendship functionality and separate publication consent remain preserved.

Status: implementation-ready recommendation for later execution; planning only in this session. Evidence IDs refer to [01 audit](01-current-state-audit.md). Behavioral contracts in [03](03-ux-ui-specification.md) and [04](04-technical-specification.md) are normative defaults, not claims of already-shipped functionality.

## 1. Problem, audience and outcome

Replace the five-step questionnaire with a warm, quick Friendship Discovery builder that makes each answer visible immediately, then asks for deliberate publication. Improve recommendations so members understand concrete common ground and have a usable conversation opener.

MoodPrint serves Vietnamese users aged 16+. The friendship MVP continues to serve registered adults **18+** only because that is the current client and server rule (E02/E15). Teen/guest journeys retain their existing explanation/locked state. Enabling friendship for 16–17-year-olds is outside this project.

Primary users: first-time eligible members creating a public friendship profile; returning members editing drafts or published profiles; members reviewing real suggestions, sending requests or exercising safety controls. Account identity and chat/journal features are adjacent, not redesign targets.

Goals:

- Reduce choices and scrolling before the first meaningful preview.
- Preserve the approved three-question direction and MoodPrint's warm green visual language.
- Explain the difference between featured interests, matching data, a draft and a live snapshot.
- Preserve public-data-only matching, adult eligibility, consent and existing social relationships.
- Ship without an AI request per selection/page load, ranking changes, or a new data-access surface.

## 2. Scope and priority

| Must-have MVP | Nice-to-have after MVP | Future / excluded |
| --- | --- | --- |
| Three questions; eight compact interest entries; max three featured IDs; local preview | Additional curated starter variants after content review | Personality inference, AI profile writing, AI starters on every load |
| Desktop two columns; mobile one-question-at-a-time with accessible preview | Usability-informed refinement of default interest order | Matching-score/retrieval changes, introducing a compatibility percentage |
| Explicit server draft save, restoration, route/reload protection, preview then publish | Anonymous aggregate funnel counters with a separate approved instrumentation change | Direct Supabase browser queries, real-name publication, avatar uploads |
| Lossless existing interests/values/languages/goals/styles/activities/availability/strictGoal | Optional richer motion after measurement | Lowering age boundary, candidate-only reports, new social endpoints |
| Compact required-data review before publication; full public-data disclosure | Profile completion helper text experiments | Removing values/language minimums or changing consent semantics |
| Real recommendation data, truthful reasons, deterministic starter, existing invite/skip/block and chat reporting | More template coverage for niche shared interests | Deployment, migration application, source changes in this planning session |

## 3. User stories

| ID | Story | Success proof |
| --- | --- | --- |
| US01 | As a new adult member, I choose what I want and immediately see how my card changes. | Q1/Q2/Q3 update visible and screen-reader summaries with zero selection-triggered API calls. |
| US02 | As a member, I can save an incomplete profile privately and finish later. | PUT draft accepts partial discovery metadata; reload restores server draft, no publication. |
| US03 | As a returning member with ten interests, I feature three without losing the others. | Full set round-trips unchanged until an explicit full-set deletion. |
| US04 | As a cautious member, I see exactly what is shared and choose publication myself. | Fresh server preview and explicit publish action; old live snapshot remains stable while editing. |
| US05 | As a mobile/keyboard user, I complete the same flow and recover from mistakes. | Single source of state across viewport changes; focus restoration, reachable errors and touch targets. |
| US06 | As a member receiving suggestions, I understand the actual common ground. | Reasons are server-supported facts; no invented person, psychological label or probability. |
| US07 | As a member seeking safety, I can skip/block and still report interaction content through chat. | Existing guarded actions and reporting policy remain operational. |

## 4. Functional requirements and acceptance

| ID / priority | Requirement | MVP acceptance criterion |
| --- | --- | --- |
| FR01 P0 | Use title `Tìm một người bạn hợp gu 🌷`; remove all three forbidden elements from proposed UI. | No obsolete badge/subtitle/disclaimer in discovery render or microcopy inventory; no fabricated profiles. Exact omission checks are in document 06. |
| FR02 P0 | Q1 four options, native radio single selection. | Choosing one replaces only intention; mapping/preservation of canonical goal follows 04; no confirmation dialog or lost Q2/Q3. |
| FR03 P0 | Q2 eight compact entries and visible `n/3` featured counter. | Six direct IDs plus two category launchers; group choice is resolved to a real taxonomy ID. No generic sports/creative stored IDs. |
| FR04 P0 | Fourth featured interest is rejected kindly. | No silent replacement/deletion; one inline polite limit message; selection and focus remain stable. |
| FR05 P0 | Secondary interest expansion is bounded and optional. | Selected tray ≤3; one category at a time, ≤8 options/page, local search; full taxonomy is never dumped into the main form. |
| FR06 P0 | Preserve all existing interests separately from featured selection. | A 4–10-interest profile round-trips full IDs/order; de-featuring a saved interest does not remove it from matching. Explicit full-set management is available. |
| FR07 P0 | Q3 three connection-approach cards, native radio. | Immediate local update; existing style is not relabeled or overwritten. |
| FR08 P0 | Local preview has avatar/name placeholder, neutral status and three labeled sections. | Unanswered text is explicit; preview derives from reducer; no private identity/mood/journal/memory source. |
| FR09 P0 | Desktop sticky preview, structural mobile adaptation. | Grid follows available content width, not only viewport; mobile question navigation and `Xem hồ sơ` dialog work with existing bottom navigation and 200% zoom. |
| FR10 P0 | Explicit private draft save and restoration. | Save announces success only after response; uses newest server version; partial drafts persist; unsaved edits remain memory-only. |
| FR11 P0 | Navigation guard covers close, discovery tabs, internal routes, Back and reload. | Dirty exits offer continue/save-and-leave/discard; save failure retains edits and location. Native unload warning for reload/close; no hidden publish. |
| FR12 P0 | Preserve preview-and-publish protocol. | Review full shared data → save → POST preview → show returned snapshot → explicit `Hiển thị hồ sơ` / `Cập nhật hồ sơ hiển thị`. Changed answers invalidate consent readiness/digest. |
| FR13 P0 | Preserve legacy publication requirements. | 3–10 full interests, 2–4 values, 1–2 languages; no invented selections. Missing values/languages collected only in compact prepublication review. |
| FR14 P0 | Maintain truthful live/draft distinction. | First draft privacy footer retained; existing-live notice explains old snapshot remains public; hidden/stale/needs_republish never auto-reactivate. |
| FR15 P0 | Recommendation card uses actual `CandidateCardDTO`. | Pair alias/avatar seed preserved; short public intent or legacy goal, ≤3 server reasons, one deterministic grounded starter; no account-name lookup. |
| FR16 P0 | Recommendation actions and safety survive. | Invite/skip/block remain version/reference guarded; pending requests/rooms and interaction reporting have no lifecycle regression. No dead candidate-report button. |
| FR17 P0 | No-match/failed/loading/expired states are distinct. | Empty state contains no invented people; retry retains context; expired refs reload without replaying a stale action against a new person. |
| FR18 P0 | Backward-compatible additive metadata. | Old payloads without discovery still validate/read/render; omission by an older writer preserves existing metadata as specified in 04. API deployed before new payload writers. |
| FR19 P0 | No unintended matching-policy change. | Same canonical profile yields same ranking/reasons in v1/v2/shadow regardless of discovery metadata. Full-set edits and deliberate canonical goal changes may alter suggestions and are explained. |

## 5. Non-functional requirements

- **NFR01 Accessibility:** target WCAG 2.2 AA. Native inputs, fieldsets, accessible dialogs, visible 3px focus rings, 4.5:1 normal-text contrast and 3:1 control/focus contrast; ≥44px project touch targets. No claim of conformance before manual and automated validation.
- **NFR02 Responsiveness:** 320px reflow, text wrapping and 200% text/zoom; no page horizontal overflow. Content-width breakpoints and safe-area behavior in 03.
- **NFR03 Performance:** render selection feedback on the next React commit, target ≤100ms on representative mobile hardware. No network in selection reducer or starter selection. No new package or custom GSAP timeline needed for MVP.
- **NFR04 Reliability:** versioned saves, idempotent retry of identical uncertain writes, no optimistic publication; stale responses/session epochs cannot restore another user's state.
- **NFR05 Maintainability:** one canonical editor state; pure derived preview; shared public-card presentation; generated OpenAPI types remain authoritative.
- **NFR06 Localization:** natural Vietnamese copy, correct diacritics, readable system fonts, no unnecessary jargon in product UI. Taxonomy IDs remain stable.

## 6. Privacy requirements

- PRE01: only explicitly selected public profile fields enter drafts/public snapshots. Never read journal, mood, chat memory, private identity or AI transcript to fill/recommend/explain.
- PRE02: saving or completing questions does not publish or enable MATCH consent. The final button explains the existing consent-enabling behavior.
- PRE03: public header uses pair pseudonyms and decorative seed avatars. Owner placeholder is `Bạn`; explain why the exact pair alias cannot be previewed globally.
- PRE04: preserve adult/registered/account-status/deletion/restriction gates, shared language, strict goals, bilateral blocks, references, cooldowns and quotas at the server.
- PRE05: no profile choices or personal names in analytics/logs; no browser storage of profile drafts. Clear memory on logout/account change and honor transport cancellation/epoch.
- PRE06: do not weaken RLS or expose `moodprint` tables to browser roles. API DTO expansion is not authorization expansion.
- PRE07: all stored interests remain public profile data under today's API; featuring does **not** make other stored interests private. Review and card detail must disclose the complete set and other public facets.

## 7. Success metrics (proposed, not measured)

| Metric | Definition | Initial target / collection |
| --- | --- | --- |
| Time to meaningful preview | First intentional selection → visible correct preview | ≤100ms feedback target; instrument locally/test timing without recording choices. |
| Builder completion | Adults starting builder who reach ready-to-review in a session | Establish old baseline; target +15 percentage points after controlled pilot. |
| First publication effort | Active interaction time including missing-data review, excluding idle/network wait | Proposed median ≤120 seconds, p90 ≤240 seconds in moderated usability sessions. |
| Consent comprehension | Participant correctly distinguishes draft, local preview, live snapshot | ≥90% in small usability study; any accidental-publication report blocks release. |
| Legacy preservation | Full interests and other canonical fields surviving unchanged edits | 100% test fixtures; zero silent truncation. |
| Grounding | Displayed reasons/starters trace to allowed public facts | 100% fixture review; no fabricated matches. |
| Accessibility / regressions | Critical accessibility defects, eligibility/privacy regressions | Zero unresolved release-blocking defects; all required 06 scenarios pass. |

Existing aggregate `matching_stats_daily` impressions/requests/accepts can contextualize recommendation health, but do not measure this funnel or prove causation. Do not add tracking, identifiers or a schema merely to hit the proposed metrics. Usability testing is a sufficient MVP measurement route; wider analytics needs a separately reviewed content-free design.

## 8. Release gate

All FR01–FR19 and NFR/PRE requirements must have evidence in the future implementation report. Deliver frontend plus additive API contract together; retain current scorer setting and publication rules. Release waits on 06 validation and the narrowly scoped product acknowledgment in 07 about first-publication supplemental fields. This planning task ends with documents and a handoff; it does not authorize deployment.
