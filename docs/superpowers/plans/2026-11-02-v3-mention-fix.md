# V3 mention caret repair

**Goal:** Preserve text order when typing immediately after selecting a mention.
**Scope:** Existing `GroupChat` caret handling and browser regression coverage.
**Constraints:** Keep the existing fullstack assertion, CI gates, release provenance,
current branch, user changes and `.gitignore`. No CI architecture refactor.

The hosted 0020 → 0024 migration and baseline main deployment are operational
prerequisites, completed separately with the owner's authorization. V3 remains
limited to the two existing test accounts and the existing $1/day budget.

## Design and evidence

`choose` and `openPicker` defer selection to an animation frame. A key typed before
that frame is inserted correctly, then the delayed callback moves the caret back.
The next key is inserted before the first. A paused browser clock reproduces the
CI value `@Nhật ký uần này mình thế nào?t` with the original assertion unchanged.

Store the requested caret in a ref before changing the controlled value. Consume
it once in a layout effect after React updates the textarea, before another input
event or paint. Apply this to both picker selection and the mention button.

## Execution

- [x] Add `frontend/tests/e2e/group-mentions.spec.ts` to the existing browser suite.
- [x] Observe the regression fail with the same malformed value as branch CI.
- [x] Update `frontend/src/features/real/groups/GroupChat.tsx` to restore selection
  during the DOM commit rather than a later animation frame.
- [x] Verify immediate keyboard typing, mouse selection, insertion in the middle
  of a draft, frontend types/build and 217 unit tests plus the Redocly Node test.
- [ ] Verify the unchanged original fullstack suite in CI.
- [ ] Review, commit, push current branch, open a PR and merge only with green CI.
- [ ] Verify the release artifact, attestations, image digests, hosted readiness,
  registered login/session refresh, journal, direct AI, orchestration and groups.

Proactive scheduling and guest entry remain intentionally disabled unless already
configured and supported by the bounded rollout. Never downgrade the database.

Independent code review: approved with no actionable findings. The four browser
regressions pass; the original fullstack assertion remains unchanged.
