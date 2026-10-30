# Export removal audit

Status: **PARTIAL**.

## Removed from the product UI

| Surface | Change |
| --- | --- |
| Settings data section | Heading is “Xóa dữ liệu”. The download button, guest download dialog, and “file is ready” notice are gone. Deletion of selected data and account deletion stay. |
| Conversation info | “Tải xuống cuộc trò chuyện” is gone. Rename and delete stay. |
| `downloadConversation` | Removed from `AIData.tsx` and `RealApp.tsx`. |

Copy states that people view their journal, moods, memories, and conversations in MoodPrint, and that the app does not create a downloadable file. It does not say that a legal right of access has been extinguished. Provider backup retention is still disclosed on account deletion.

## Preserved on purpose

The authenticated routes remain:

- `POST /api/v1/exports`
- `GET /api/v1/exports/{job_id}`
- `GET /api/v1/exports/{job_id}/download`
- `GET /api/v1/ai/conversations/{conversation_id}/export`

Ruling: these routes are the existing owner-scoped copy of account, consent, mood, journal text/metadata, memory, and social data. The privacy tests use them to prove isolation, expiry, and one-time download. Removing them in this pass would delete that proof and the only complete copy without a replacement access mechanism. Account deletion, guest expiry, and retention cleanup do not depend on the buttons and were left in place.

This is a product conflict, not a claim that every legal obligation is gone. If counsel later requires the routes to disappear, replace the privacy tests with direct owner reads before deleting the handlers.

## Regression checks

Playwright now expects the download buttons to be absent and deletion to remain:

- `tests/e2e/auth.spec.ts`
- `tests/e2e/ux-redesign.spec.ts`
- `tests/e2e/chat-history.spec.ts`
- `tests/fullstack/journeys.spec.ts`
- `tests/fullstack/mvp.spec.ts`
- `tests/fullstack/guest-experience.spec.ts`
- `tests/fullstack/chat-history.spec.ts`

The e2e files above passed in this session (100 tests across journal, auth, chat-history, and ux-redesign). The fullstack files were updated and not re-run here because they need the disposable HTTP and PostgreSQL harness.
