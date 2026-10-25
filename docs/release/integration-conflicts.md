# MVP integration decisions

Source references fetched on 2026-10-26 (Asia/Bangkok):

| Branch | Source commit | Decision |
|---|---|---|
| main | 2c71135e6c8d08b43fabd6621950bcdd530d92ed | Integration base; retain deployment provenance and readiness window |
| docs/productization-plan | 8297e64b916a1f71939fe399601d2bee528bc1b3 | Merge first, including 16 commits absent from local MVP |
| feat/moodprint-product-experience | e5c8929 | Ancestor of local MVP; integrated through that merge |
| fix/moodprint-local-mvp | 3a6367021b925c7a6e662aaef1b3c5dc043993ea | Merge second; preserves real AI availability, history, memory and social fixes |

Both merges use ordinary Git ort, without global ours/theirs preferences. No textual conflicts were reported. Git automatically combined `frontend/tests/e2e/states.spec.ts`; verify both offline retry determinism and new AI/history behavior. Readiness tests and `app/core/revisions.py` come from the latest productization branch. Historical audit references remain pinned to their original snapshot.

The original three worktrees are unchanged. The integration worktree is outside the repository because `.worktrees` was unignored in the original checkout; no ignore rule was edited. Existing `.gitignore` changes authored on the source branch are imported by Git history, without manual edits.

Release and cleanup remain conditional on fresh CI, backup/restore rehearsal, hosted migration safeguards and live acceptance. PR #9 stays open until successful replacement release.
