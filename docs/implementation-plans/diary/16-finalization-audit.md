# Diary V2 finalization audit

Branch `feat/diary-experience-v2`. Prior head `2639996dda1eb5777b80c50b0f17bc7202c844ac` matched Draft PR #23 and had a successful `Verify local application` run. This audit records the finalization pass on top of that head. Historical reports [14](14-implementation-progress.md) and [15](15-final-report.md) are unchanged.

| Task | Status | Evidence |
| --- | --- | --- |
| F01 Git and PR preflight | PASS | Workspace `E:\MoodPrint`, branch `feat/diary-experience-v2`, remote `origin` GitHub, PR #23 draft, base `main`, mergeable, prior CI success on `2639996`. Unrelated working-tree files (`.gitignore`, `docs/mvp-validation/`, `frontend/evidence/`) were left unstaged. |
| F02 Supabase project identity | PASS | Management API project `roznanxbiyqybjpvtilq`, name `database`, region `ap-northeast-1`, status `ACTIVE_HEALTHY`, host `db.roznanxbiyqybjpvtilq.supabase.co`, Postgres `17.11`. `backend/.env` contains the same project ref. See [17](17-hosted-migration-verification.md). |
| F03 Hosted migration 0019 | BLOCKED | Hosted `moodprint.alembic_version` is `0018_app_feedback`. Journal tables are absent. `origin/main` `READY_REVISIONS` is only `0018_app_feedback`, and readiness rejects any other revision. Applying 0019 would fail the deployed app. No compatibility release was deployed. |
| F04 90-day retention | PASS | Policy unchanged in `journalDateWindow` (89 days back through today) and existing purge tests. Vietnamese explanation added on the composer, home note, and timeline. Provider backups are not claimed to expire immediately. |
| F05 Export removal | PARTIAL | User-facing download controls removed. Authenticated `/exports` and conversation export routes remain as the owner-scoped data-access path. See [19](19-export-removal-audit.md). |
| F06 Nhịp text only | PASS | Existing `search_for_ai` returns text, mood, emotions, factors, date, and version only. A key-set assertion was added in `test_journal_ai.py`. No image, audio, or video understanding was added. See [20](20-nhip-text-only-contract.md). |
| F07 Personal timeline | PASS | Feed grouping, galleries, lightbox, native audio/video, text expansion, edit/delete, and scroll restoration. See [18](18-personal-timeline-redesign.md). |
| F08 Composer, calendar, discovery | PASS | Existing composer, calendar, and four discovery destinations kept. Prompts updated. “Nhìn lại” opens the Nhịp reflection page, which links to the daily mood chart. |
| F09 Automated UI verification | PASS | `npm run typecheck`, `npm test` (103), `npm run build`, and Playwright `journal`, `auth`, `chat-history`, `ux-redesign` (100 passed). Axe on the journal surfaces in `journal.spec.ts` reported no violations. |
| F10 Backend suite for this delta | PARTIAL | The new Nhịp key-set assertion was not executed against PostgreSQL in this session. Prior CI on `2639996` passed the previous suite. The next CI run on this branch is the complete gate. |

Ruling: hosted migration stays blocked until a release whose readiness accepts `0019_journal` is the deployed application, or until an explicitly authorized compatibility release accepts both `0018_app_feedback` and `0019_journal` before the schema move. Additive tables alone do not make the current production image ready.
