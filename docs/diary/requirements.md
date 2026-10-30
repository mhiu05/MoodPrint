
# MoodPrint — Diary Experience V2
## Full Codebase Audit, Implementation Planning, Development and Visual QA

You are a senior full-stack product engineer, UI/UX architect, and accessibility specialist working directly inside the CURRENT GitHub Codespace.

Repository: https://github.com/mhiu05/MoodPrint

Design references:
- https://github.com/pbakaus/impeccable
- https://github.com/greensock/gsap
- https://gsap.com/docs/

This is an implementation task, not just a design review.

You are authorized to inspect the repository, create a feature branch, write documentation, implement code, run local tests, and open a Draft PR.

Do NOT merge into main or deploy to production.

Work autonomously. Do not stop after writing a superficial plan.

---

# 1. Git Workflow — Mandatory First Step

The current Codespace is on `main`.

Create and switch the CURRENT Codespace to:

`feat/diary-experience-v2`

Before any changes:

1. Run `pwd`, `git status --short`, `git branch --show-current`, `git log -1 --oneline`, and inspect remotes.
2. Fetch the latest `origin/main`.
3. Preserve all existing local modifications.
4. Create the feature branch safely from the existing checkout.
5. Integrate the latest upstream main changes if necessary, without losing local work.
6. Verify the active branch and working tree.

CRITICAL:

Six visual references have already been added locally under:

`docs/diary/visual-references/`

They may currently be UNTRACKED.

Do not lose, overwrite, clean, or reset these images.

Never use destructive commands such as `git reset --hard`, `git clean -fd`, or force-push.

Preserve and commit these reference files on the feature branch.

If there are unrelated local changes, preserve them separately. Never silently include unrelated files in commits.

If the branch already exists, inspect it before reusing it. Never overwrite an existing branch.

Do not modify `main`.

---

# 2. Study the Six Visual References

Read:

`docs/diary/visual-references/README.md`

Inspect all six PNGs:

1. `01_nhat_ky_cam_xuc.png`
2. `02_ghi_lai_khoanh_khac.png`
3. `03_kham_pha_them.png`
4. `04_lich_nhat_ky.png`
5. `05_khoanh_khac_cua_ban.png`
6. `06_nhip_dong_hanh.png`

These images are the PRIMARY visual references.

For each screen, document:

- Layout and information hierarchy
- Component inventory
- Typography and colors
- Spacing and visual rhythm
- Interaction behavior
- Navigation behavior
- Responsive adaptations
- Backend/API dependencies
- Missing states and accessibility requirements
- Differences between the visual reference and existing implementation

Do not treat the images as pixel-perfect specifications.

AI-generated reference images may contain inconsistent labels, dates, spacing, or illustrative data.

Correct those problems while preserving the intended visual direction.

The objective is a polished, usable production-quality web application, not a static screenshot clone.

---

# 3. Audit the Existing MoodPrint Codebase

Read existing `AGENTS.md`, project skills, architecture documentation, and relevant source code.

Pay particular attention to:

- `frontend/src/features/real/Mood.tsx`
- `frontend/src/features/real/RealApp.tsx`
- `frontend/src/features/real/real.css`
- `frontend/src/styles/`
- `frontend/src/components/`
- `frontend/src/components/motion/`
- `frontend/src/api/`
- `backend/app/modules/mood/`
- `backend/app/modules/voice/`
- `backend/app/ai/`
- `backend/app/infrastructure/database/`
- Existing Alembic migrations
- Supabase integrations
- Existing privacy, retention, export, and deletion flows
- Existing frontend and backend tests

Discover actual component paths and dependencies rather than assuming everything lives in these locations.

Inspect current:

- Mood CRUD APIs and DTOs
- One-entry-per-day behavior
- Date ranges and timezone handling
- Optimistic concurrency and idempotency
- AI mood context and tool permissions
- Existing Supabase Storage usage
- Media/voice handling
- Mobile navigation
- Existing GSAP integration
- Existing accessibility and motion policies

Identify what can be reused and what must change.

Preserve existing working features, API compatibility where practical, and user data.

Do not rewrite unrelated application modules.

---

# 4. Design Direction — Impeccable

Study:

https://github.com/pbakaus/impeccable

Apply Impeccable's design philosophy to this feature.

If the Impeccable skill is already installed, use its relevant workflows.

Relevant capabilities include:

- shape
- document
- critique
- audit
- polish
- clarify
- adapt
- harden
- animate
- optimize

Use the documented skill interface supported by the current Codex environment.

Do not overwrite existing project skills or agent configuration.

If unavailable, apply the principles manually and document that choice.

## Visual requirements

Create a bright, welcoming, emotionally supportive UI.

Visual identity:

- Light theme
- Warm off-white backgrounds
- Sage-green accents
- MoodPrint's existing dark green branding
- Friendly, non-technical Vietnamese copy
- Soft borders and restrained shadows
- Rounded but not excessively rounded components
- Meaningful illustrations and emotion icons
- Consistent typography and spacing
- Clear active, hover, focus, loading and error states

Avoid common AI-generated UI problems:

- Excessive nested cards
- Too many colored gradients
- Oversized decorative elements
- Inconsistent icon styles
- Unnecessary whitespace
- Tiny low-contrast text
- Overly dense form layouts
- Repeated headings
- Unnecessary animations
- Technical terminology exposed to non-technical users

Build on the existing MoodPrint brand instead of introducing an unrelated design system.

Use reusable design tokens and components.

---

# 5. Responsive Web App Requirements

This is a responsive WEB APPLICATION, not a native mobile app.

The design must work on desktop, tablet, and mobile.

## Mobile: Primary reference

Use the six supplied screenshots as the main mobile design direction.

The mobile experience should prioritize:

1. Mood selection
2. Detailed emotions
3. Influencing factors
4. Journal composition
5. Media attachments
6. Save actions
7. Explore More
8. Persistent bottom navigation

IMPORTANT PRODUCT DECISION:

"Khám phá thêm" appears BELOW the journaling experience on mobile.

Do not force the desktop right sidebar into the mobile layout.

The mobile page should scroll naturally.

Maintain proper bottom safe-area spacing.

The fixed bottom navigation must never obscure content, form controls, media, or buttons.

## Desktop

Reuse the existing MoodPrint desktop navigation architecture.

Recommended structure:

- Left: Existing application navigation
- Center: Main journaling experience
- Right: Companion, writing prompts, recent memories, and mood insights

The right sidebar should provide contextual value instead of duplicating the main form.

## Tablet

Use a responsive intermediate layout.

Collapse or relocate secondary features where necessary.

Test at minimum:

- 360px
- 390px
- 430px
- 768px
- 1024px
- 1440px

No horizontal page overflow.

Do not use device detection as a substitute for responsive layout.

---

# 6. Functional Scope

Implement the following six experiences.

## Screen 01 — Nhật ký cảm xúc

Allow the user to:

- Select one of five overall mood levels
- Select multiple detailed emotions
- Select multiple influencing factors
- Choose the appropriate journal date
- Move smoothly into writing a journal entry

Use clear Vietnamese descriptions.

Do not force users to complete every optional field.

Support quick emotional check-ins without requiring long-form writing.

## Screen 02 — Ghi lại khoảnh khắc

Support multimodal journal entries:

- Text
- Voice recordings
- Images
- Video

Support combinations of these media within one journal entry.

Required UX:

- Write and edit text
- Record audio
- Pause/stop recording as appropriate
- Preview and replay audio
- Add/remove images
- Preview media
- Upload and preview video
- Remove attachments
- Save draft
- Save journal entry
- Edit existing entry
- Delete entry with confirmation
- Loading, failure, retry and successful-save states

Handle microphone permission denial and unsupported browsers gracefully.

Prevent accidental loss of unsaved work.

Support multiple moments per day.

Do not let the new data model silently overwrite historical daily mood records.

## Screen 03 — Khám phá thêm

Provide four main destinations:

1. Nhịp đồng hành
2. Gợi ý viết
3. Kỷ niệm của bạn
4. Nhìn lại cảm xúc

Also show recent memories when appropriate.

On mobile this is a section BELOW the primary journal workflow.

On desktop these capabilities may appear in the right sidebar.

Cards must lead to real destinations or functional interfaces.

Do not ship decorative, non-functional controls.

## Screen 04 — Lịch nhật ký

Implement:

- Monthly calendar
- Previous/next month navigation
- Mood markers on recorded days
- Neutral empty days
- Selected-day details
- Multiple entries on the same day
- Navigation into individual entries
- Entry creation from a selected valid date

Handle timezone and date boundaries correctly.

Never infer moods for missing dates.

## Screen 05 — Khoảnh khắc của bạn

Implement a chronological journal timeline.

Support:

- Text previews
- Image thumbnails
- Audio playback
- Video previews
- Mood indicators
- Dates and local times
- Search
- Media and mood filtering
- Entry detail navigation
- Edit/delete operations
- Pagination or incremental loading

Do not download all media for all entries immediately.

Use efficient previews and lazy loading.

## Screen 06 — Nhịp đồng hành

Extend the EXISTING Nhịp assistant.

Do not create an unnecessary replacement AI agent.

Nhịp should be able to:

- Read the authenticated owner's journal data
- Reflect on journal entries
- Find past memories
- Connect relevant memories
- Summarize mood patterns
- Explain which entries support a reflection
- Link back to original journal entries

Example queries:

"Nhịp ơi, dạo này tâm trạng của mình thế nào?"

"Lần trước mình vui vì được điểm cao là khi nào?"

"Mình có thường lo lắng trước khi thuyết trình không?"

Only make evidence-supported claims.

Avoid diagnosing mental health conditions.

Avoid inventing memories or causal relationships.

Support insufficient-data responses.

---

# 7. Privacy and AI Product Decisions

The following behavior is a confirmed product requirement:

- Journals are visible only to their authenticated account owner.
- Nhịp can access the owner's journal by default to support the journal companion experience.
- Other users cannot read journal data.
- Journal content must not automatically enter social matching, public profiles, or other users' conversations.
- Other assistants must not automatically gain full journal access merely because Nhịp has access.

This default AI access must be transparently described to users.

Do not add the previously rejected consent-toggle panel to the journaling UI.

However, audit existing consent, privacy notice, retention, export, deletion, and AI memory rules carefully.

Separate:

- Reading journal data for an authorized user request
- Persisting long-term AI memory
- Creating embeddings
- Processing media or transcripts through AI providers
- Sharing content with another user

Do not silently equate these actions.

If existing privacy guarantees or explicit user choices conflict with the new default, document the conflict and implement a safe, compatible transition rather than silently weakening protections.

All AI tools must use backend-validated owner identity.

Never trust an arbitrary `user_id` supplied by the model.

---

# 8. Supabase Storage Architecture

Use Supabase Storage for journal media.

Preferred bucket:

`journal-media`

The bucket MUST be PRIVATE.

Design an owner-scoped path structure, such as:

`users/{user_id}/{entry_id}/{media_type}/{file_id}.{extension}`

Store file metadata in PostgreSQL.

Include:

- Journal entry ID
- Owner ID
- Media type
- Storage object path
- MIME type
- File size
- Duration when applicable
- Created timestamp
- Upload status

Consider thumbnail metadata when needed.

Implement secure upload and download flows.

Requirements:

- Owner-only RLS
- Backend ownership validation
- MIME/type validation
- Size limits
- Safe file names
- Signed uploads or another verified secure flow
- Short-lived access URLs where applicable
- Efficient media delivery
- Upload failure recovery
- Orphaned-file cleanup
- Deletion synchronization
- No public media bucket
- No leaked service-role credentials

Proposed MVP limits to evaluate:

- Image: 10 MB/file
- Audio: 20 MB/file
- Video: 50 MB/file

Confirm these limits against the actual user experience, provider configuration, and current Supabase documentation.

Prefer resilient upload techniques for larger files.

Avoid unnecessarily routing large media through FastAPI memory.

Create bucket provisioning instructions or reproducible migrations/configuration where supported.

Do not directly mutate the production bucket or production database.

---

# 9. Database and Migration Planning

Audit the current mood schema first.

The existing implementation may impose:

- One mood record per day
- Limited note length
- A historical date range
- Daily summary assumptions
- Existing mood data dependencies in AI tools

Design a backward-compatible transition to a richer journal system.

Support multiple journal entries per day.

Decide explicitly whether daily mood tracking and journal entries remain separate concepts.

Document:

- Target schema
- Constraints and indexes
- Foreign keys
- RLS policies
- API contracts
- Migration and backfill strategy
- Compatibility with existing records
- Daily aggregation semantics
- Export and deletion behavior
- Retention compatibility
- Rollback strategy
- Concurrency and idempotency

Never delete or overwrite existing user journals during migration.

Use Alembic and existing project migration conventions.

Keep migrations reproducible and testable.

---

# 10. Motion Design — GSAP

Study:

https://github.com/greensock/gsap

Reuse GSAP and `@gsap/react` if already installed.

Follow existing motion conventions, including `useMotionPolicy`.

Use animation only when it improves comprehension or feedback.

Suggested interactions:

### Mood selection
Subtle scale and color transitions.

### Emotion chips
Smooth selected-state feedback.

### Journal editor
Gentle entrance when expanded.

### Media attachments
Smooth thumbnail addition/removal transitions.

### Save action
Clear, restrained save feedback.

### Calendar
Subtle month transitions.

### Timeline
Lightweight entrance transitions for newly revealed entries.

### Nhịp companion
Subtle panel transitions and message presentation.

Requirements:

- Respect `prefers-reduced-motion`
- Avoid animations that prevent interaction
- Avoid unnecessary animation on every re-render
- Prevent memory leaks
- Use React-compatible GSAP lifecycle and cleanup
- Keep form state independent from animation state
- Avoid heavy scroll animations and layout shifts

Do not animate everything merely because GSAP is available.

---

# 11. Accessibility and Localization

Target WCAG 2.2 AA where applicable.

Requirements:

- Semantic HTML
- Keyboard navigation
- Visible focus states
- Accessible labels
- Screen-reader announcements
- Suitable color contrast
- Touch targets around 44px or larger where practical
- Reduced-motion support
- Accessible audio controls
- Error messages linked to fields
- Safe handling of long text
- Responsive text scaling

Use natural Vietnamese throughout the interface.

Avoid technical words such as "bucket", "embedding", "vector", or "RLS" in user-facing copy.

Do not penalize users for missing journal days.

Avoid guilt-inducing streak mechanics.

Do not frame emotional well-being as a score to maximize.

---

# 12. Implementation Plans — Required Deliverables

Create:

`docs/implementation-plans/diary/`

Write the implementation documentation BEFORE making significant application-code changes.

Required files:

- `00-executive-summary.md`
- `01-current-codebase-audit.md`
- `02-visual-reference-analysis.md`
- `03-product-requirements.md`
- `04-frontend-architecture.md`
- `05-backend-and-api-design.md`
- `06-database-and-migrations.md`
- `07-supabase-storage-design.md`
- `08-nhip-ai-integration.md`
- `09-design-system-and-gsap.md`
- `10-testing-and-visual-qa.md`
- `11-implementation-roadmap.md`
- `12-security-privacy-and-risks.md`
- `13-release-and-rollback.md`
- `14-implementation-progress.md`

Each document must contain concrete, repository-specific details.

Reference actual file paths and implementation evidence.

Avoid generic advice.

For implementation tasks, include:

- Task ID
- Priority
- Dependencies
- Target files/modules
- Required changes
- Acceptance criteria
- Testing requirements
- Estimated complexity
- Status

Use explicit statuses:

PASS / PARTIAL / BLOCKED / NOT_STARTED

Include a visual-reference-to-component mapping.

Document any deliberate deviations from the images.

---

# 13. Implementation Workflow

Use the following order.

## Phase A — Audit and Planning

1. Create and switch to the feature branch.
2. Preserve the six reference images.
3. Audit the existing architecture.
4. Analyze the screenshots.
5. Study Impeccable and GSAP.
6. Write the implementation plans.
7. Identify breaking-change risks.
8. Commit the planning documents separately.

## Phase B — Core Journal Backend

Implement the required data model and APIs.

Include migration and storage integration.

Preserve existing functionality.

Implement owner-level authorization.

## Phase C — Frontend

Implement screens according to the reference mapping.

Reuse existing design tokens and components.

Make mobile and desktop responsive.

Prioritize functional correctness before decorative polish.

## Phase D — Nhịp Integration

Extend existing Nhịp tools and context retrieval.

Implement journal access with owner authorization.

Add evidence references and appropriate error handling.

## Phase E — Visual Polish

Apply the Impeccable review philosophy.

Refine typography, layout, spacing and hierarchy.

Integrate appropriate GSAP transitions.

Do not introduce unnecessary motion.

## Phase F — Verification

Run all relevant tests and browser checks.

Fix defects.

Update documentation with actual verification results.

---

# 14. Testing and Visual QA

Use the repository's existing tooling.

Include:

- Backend unit tests
- API integration tests
- Frontend component tests
- TypeScript typecheck
- Production build
- Playwright E2E tests
- Visual regression checks
- Accessibility checks
- Responsive testing

Test at:

360, 390, 430, 768, 1024 and 1440 pixels.

Capture screenshots of each implemented experience.

Compare the implementation against the six reference images.

Do not rely solely on screenshot similarity.

Verify actual interactions.

Critical test scenarios:

- Save a text entry
- Save image attachments
- Record and replay audio
- Upload and preview video
- Create multiple entries in one day
- Edit and delete entries
- Reload and recover saved content
- Navigate the calendar and timeline
- Search and filter entries
- Handle upload failures
- Handle permission-denied microphone
- Handle network interruption
- Handle stale writes and duplicate submissions
- Verify one user cannot access another user's files
- Verify private Storage URLs do not become permanently public
- Verify Nhịp retrieves only owner-scoped journal data
- Verify Nhịp cites real journal entries
- Verify empty states and limited-data states
- Verify reduced-motion behavior
- Verify mobile navigation does not cover input controls
- Verify existing mood and AI features remain functional

Use safe synthetic test data.

Do not run destructive tests against production.

If real Supabase integration is unavailable, complete mock/local verification and mark hosted integration as unverified.

Do not fabricate PASS results.

---

# 15. Performance and Reliability

Target a practical MVP of approximately 50 concurrent users.

Avoid unnecessary complexity.

Evaluate:

- Media upload concurrency
- Large file handling
- Lazy loading
- Query efficiency
- Indexed journal searches
- Timeline pagination
- Storage bandwidth
- Backend memory usage
- AI token usage and retrieval size
- Mobile rendering performance

Do not load entire historical journals into each AI prompt.

Use bounded retrieval.

Prefer simple, maintainable architecture over premature microservices.

---

# 16. Git Commits and Draft PR

Keep commits logically separated.

Suggested commit groups:

1. Visual references and implementation plans
2. Database and backend journal model
3. Private Storage integration
4. Responsive journal UI
5. Calendar, timeline and discovery
6. Nhịp integration
7. GSAP polish and visual QA
8. Tests, documentation and final fixes

After verification:

- Commit all intended changes.
- Push the feature branch.
- Open a Draft PR targeting `main`.
- Include implementation summary, migration risks, screenshots and test evidence.
- Do not merge.
- Do not deploy.
- Do not modify production user data.

---

# 17. Final Report

At the end, provide:

## A. Git Status
- Active Codespace branch
- Base commit
- Final commit
- Draft PR URL

## B. Implementation
- Features completed
- Files changed
- Migrations added
- Storage configuration
- Nhịp integration

## C. Design and UX
- Visual reference mapping
- Mobile behavior
- Desktop behavior
- GSAP animations
- Impeccable review findings

## D. Verification
- Tests executed
- Passed/failed counts
- Browser screenshots
- Accessibility findings
- Known limitations

## E. Outstanding Work
- Remaining tasks
- Blockers
- Production prerequisites
- Rollback considerations

## F. Final Verdict

Choose one:

- READY_FOR_REVIEW
- PARTIAL
- BLOCKED

Never claim a feature is complete if it has not been implemented and tested.

---

# 18. Execution Principles

You have permission to operate autonomously within the new feature branch.

Do not ask for confirmation for ordinary local development work.

If a task requires missing credentials or privileged production access, document the blocker and continue with independently testable tasks.

Do not hardcode secrets.

Do not expose user media publicly.

Do not modify unrelated product features.

Do not merge into main.

Do not deploy production.

Begin immediately with the Git safety audit, branch creation, and six-image inspection.

Then produce the implementation plans and proceed through implementation, testing, and the Draft PR.
