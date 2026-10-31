# Friendship Discovery — decisions, risks and handoff

Status: planning recommendation, 2026-10-31 (Asia/Bangkok). Source facts are in [01 audit](01-current-state-audit.md); product acceptance is in [02](02-product-requirements.md); [03 UX](03-ux-ui-specification.md) and [04 technical](04-technical-specification.md) define behavior; [05](05-implementation-plan.md) and [06](06-test-and-validation-plan.md) define execution and evidence. No implementation/deploy authority is implied.

## 1. Verified facts versus recommendations

| ID | Kind | Decision / evidence |
| --- | --- | --- |
| D01 | Verified | Expected branch equals actual `test/local-2026-10-30`; HEAD recorded in 01. Two pre-existing dirty application files must be preserved. |
| D02 | Verified | Profile/publication/matching routes are in backend social/routes.py, while taxonomy endpoint is in profiles/routes.py. Reuse those exact endpoints. |
| D03 | Verified | Publication needs canonical 3–10 interests, 2–4 values, 1–2 languages, current versioned server preview and explicit final operation. Save is not publish. |
| D04 | Verified | Friendship is registered/adult 18+ despite the wider 16+ product audience. Keep current boundary. |
| D05 | Verified | Goals and styles do not exactly describe approved intentions/approaches; creative/sports are categories, not existing interest IDs. |
| D06 | Verified | Public profile is JSONB; strict DTO rejects unknown fields. New metadata requires DTO expansion, not necessarily SQL changes. |
| D07 | Verified | Matching has v1/v2/shadow, default v1; deployment scorer is unknown. No percentages; aliases are pair pseudonyms. |
| D08 | Verified | Existing journal guard provides a HashRouter navigation pattern; social editor currently only confirms its own Close. Reporting requires prior interaction and is available through chat. |
| D09 | Recommended default | Adopt optional discovery v1 object with nullable partial-draft answers and ≤3 featured canonical IDs; no SQL migration, new endpoint, taxonomy version or scorer change. |
| D10 | Recommended default | Three main questions plus local preview; supplemental **missing legacy-required fields only** at prepublication review. No invented values or language. |
| D11 | Recommended default | Existing canonical goal/style/full set are retained. New unsaved goal can initialize from Q1; after save canonical goal is explicit settings-only. Q3 never maps to listening/direct. |
| D12 | Recommended default | Explicit server draft saves only, memory-only unsaved edits, full navigation guard, exact reviewed snapshot and distinct final publication click. |
| D13 | Recommended default | Seed avatar/`Bạn` local owner placeholder; public cards retain pair alias. No real name/avatar/private identity promotion. |
| D14 | Recommended default | Deterministic allowlisted starter templates based on exact server reasons; no new AI dependency/call. Keep existing server reason order and factual qualitative label. |
| D15 | Recommended default | CSS feedback; keep shared Dialog GSAP only. Content-width responsiveness, 44px targets, WCAG 2.2 AA validation target. |

## 2. Alternatives resolved

- **Three featured versus all stored interests:** keep both, preserving full values. A hard three-ID rewrite is unacceptable data loss. Unfeatured full interests are still public/matching inputs; full disclosure is mandatory.
- **Synthetic generic creativity/sports tags versus concrete selection:** bounded child picker is preferred; canonical taxonomy and score matrices remain untouched.
- **Relabel old styles versus new metadata:** separate connection approach is preferred. `direct` does not mean lively, and no demographic/psychological inference is supported.
- **Server request per preview versus derived local preview:** derive locally; call authoritative preview only on deliberate review. This provides instant feedback while preserving consent/versioning.
- **Frontend-only versus API DTO expansion:** DTO expansion is necessary to persist these choices faithfully; existing JSONB and endpoints make SQL unnecessary.
- **AI versus template starters:** templates win MVP on reliability, latency, cost, grounding and testability. AI variety is future scope with independent privacy/cost review.
- **Candidate-only report:** keep existing block and interaction report paths. An unsupported report button is worse than an honest existing policy; redesigning reporting is a separate product/backend decision.

## 3. Product decisions to acknowledge before later release

These are not questions blocking the authorized planning deliverables. Recommended defaults are explicit enough for the future coding agent to proceed within the plan. A product owner should acknowledge them during implementation review; changing a default requires updating the affected specifications before code.

| Decision | Recommended default | Why / consequence of changing |
| --- | --- | --- |
| Must onboarding be literally only three answers including publication? | Three **main** questions; small missing-data supplement before first publication. | Today matching requires values/languages and ≥3 full interests. Eliminating those inputs requires a separate scoring/eligibility-policy proposal; do not silently relax requirements. |
| Should new intent/approach change ranking? | No new scorer inputs. Preserve old canonical goal/style; clear helper and settings summary. | Reweighting/using new fields changes discovery, requires evaluation and its own rollout. Experiences maps only to the broad canonical friendship default for a genuinely new profile. |
| Should users 16–17 get friendship? | No; retain 18+ exactly. | Needs separate age-appropriate safety/product work. This is not an approval request to weaken the existing rule. |
| Should the card use real account name/avatar? | No; owner placeholder and pair pseudonyms. | Requires a separately authorized identity-sharing model and consent, not a display lookup. |
| Are full interests beyond three private? | No; current PublicProfile/API expose them. Explain and show them in details/review. | Making them private changes API/redaction/matching contracts and is outside MVP. |

## 4. Remaining verification questions and safe defaults

| Unknown | Evidence to obtain during implementation/release | Default until verified |
| --- | --- | --- |
| Actual deployed scorer and rollout state | Existing approved operational source/settings owner, without printing secrets | Preserve setting; test v1/v2/shadow locally. |
| Hosted schema/ACL parity | Read-only authorized deployment evidence compared to reviewed migrations/SQL | No hosted changes; no client table access; no migration in this plan. |
| Guard behavior across real browser history patterns | T14/T15 using existing journal mechanism as reference | Block release if Back/Forward loses data; no broad router migration without review. |
| Profile creation time and comprehension baseline | Moderated Vietnamese usability sessions and existing aggregate stats | Proposed targets in 02, no invented improvement numbers. |
| Exact visual match to reference screenshots | User-provided reference images if later available, compared with approved textual direction | Text brief + actual global tokens; no dark-theme assumption. |
| Maximum card height at translated/zoomed states | 06 device/accessibility matrix | Auto height and disable sticky when too tall. |
| Unknown taxonomy IDs in future-server payloads | Contract/version compatibility test | Show recoverable incompatibility; no filtering that overwrites stored data. |

No separate screenshot upload, account credentials or product meeting is needed to finish these planning documents.

## 5. Risk register

| Risk / severity | Mitigation / owner / release evidence |
| --- | --- |
| Existing 4–10-interest profiles truncated — critical | P0-02/P2/P3 retained+featured reconciliation and T07/T08/T20. |
| Silent canonical goal/style rewrite — high | Existing saved-profile preservation, disclosed goal/style defaults, T02/T09/T30. |
| Unfeatured fields invisible to owner but public — critical | Full public-data disclosure expanded in server review; T07/T13/T24/T31. |
| Implicit consent/publication or stale token reuse — critical | Existing save/preview/publish protocol, separate final click and T16–T18. |
| Older client wipes metadata / old backend rejects JSONB — high | Omission preservation; backend-first deploy; expanded DTO rollback floor; T21–T23. |
| Dirty exit or delayed response leaks/loses state — high | Profile-scoped guard, version/revision/epoch checks, T11–T19. |
| Eligibility/block/revocation policy bypass — critical | No matching changes; locked recheck tests and bilateral restrictions T28–T31. |
| Unsupported explanation or sensitive AI prompt — high | Unchanged server reasons, exact allowlist templates, no private-data source; T25/T26/T31. |
| Supplemental fields make first publication feel like another survey — medium | Only missing fields in compact review, no extra main steps, usability target/comprehension measurement. |
| Shared PeerCard change breaks requests/reporting — high | Presentation wrapper reuse, heading/action checks and real lifecycle T24/T28/T29. |
| Container width/sticky/mobile navigation obscures action — medium | Scoped container query, normal-flow mobile actions, height fallback, T32–T35. |
| No runtime validation performed in planning — explicit limitation | Future implementation must execute 06; current documentation review proves no application behavior. |

## 6. Planning review record

Planning review checklist (completed through source cross-checking and read-only documentation verification):

- [x] All seven requested files exist and cross-links resolve.
- [x] Audit paths and line anchors refer to existing inspected source; proposed files are labeled new.
- [x] FR01–FR19 cover both builder and recommendation cards and map to roadmap/test cases (06 traceability table).
- [x] Mobile/tablet/desktop, input semantics, states/motion, all exact choices and Vietnamese copy are specified.
- [x] Preserve full data, canonical minimums, adult gating, existing matching/reports, explicit consent and profile lifecycle.
- [x] New endpoints/SQL are avoided; optional API metadata, older writers and rollback floor are explicit.
- [x] Forbidden UI strings are absent from the proposed UI inventory; only negative test inputs in 06 enumerate them.
- [x] No implementation, generated-contract regeneration, new test execution, dependency install, branch change, commit/PR/deploy or hosted write occurred.
- [x] Existing non-document changes and `.gitignore` are byte-identical to the recorded planning baseline.

Verification evidence: `python scripts/check_docs.py` passed (135 Markdown files, 597 local links, 114 API operations, 70 settings, 50 tables in that run); `git diff --check` exited 0. Additional read-only checks found all seven deliverables, all 37 test IDs, all seven phases, no missing audit paths or planning links, balanced Markdown fences, and none of the three forbidden UI strings in document 03. Non-doc and .gitignore hashes matched the baseline below. These are documentation checks, not frontend/backend/runtime test results. Re-run the documentation checker after later document edits; link totals may change.

Research was limited to official upstream design/motion/license/WCAG/Supabase RLS pages linked in 03 and the [Supabase RLS guide](https://supabase.com/docs/guides/database/postgres/row-level-security). The lightweight Supabase changelog Markdown fetch was attempted but the web tool rejected its content type; no current Supabase feature behavior is assumed from that failed fetch. Local schema/reviewed SQL remain the audit authority; no hosted parity claim is made.

Baseline non-doc tracked-file SHA-256: `58494ec45967cb974e5a495d3b306b8a513c14ea6a018aa70e3cf29e176b50f0`. Baseline `.gitignore` SHA-256: `21c9ed300b8608c64991df618b22279e4763a4f65f85b4d4c3b8893577102cc6`. Hashes cover the inspected worktree, including the two pre-existing modifications, not a clean HEAD assumption.

## 7. Standalone implementation handoff prompt

The following prompt is for a separate future session. **Do not execute it in this planning session.**

```text
Bạn là coding agent triển khai Friendship Discovery cho MoodPrint tại E:\MoodPrint.

Đọc toàn bộ docs/friendship-profile-redesign/01-current-state-audit.md,
02-product-requirements.md, 03-ux-ui-specification.md,
04-technical-specification.md, 05-implementation-plan.md,
06-test-and-validation-plan.md và 07-open-questions-and-decisions.md trước khi sửa code.
Đọc AGENTS.md/hướng dẫn workspace và kiểm tra lại source thật; audit là snapshot,
không được ghi đè thay đổi mới của người dùng. Branch dự kiến test/local-2026-10-30;
nếu khác, báo chênh lệch và không tự chuyển/reset/rebase branch.
Không sửa .gitignore. Giữ nguyên mọi thay đổi ngoài phạm vi.

Triển khai đúng hướng đã duyệt: title “Tìm một người bạn hợp gu 🌷”, ba câu hỏi,
tám lựa chọn sở thích ban đầu, tối đa ba sở thích nổi bật, desktop builder trái /
preview phải, mobile theo từng câu hỏi với Xem hồ sơ truy cập được. Tuân thủ toàn bộ
copy, trạng thái, kích thước, accessibility và animation trong 03. Không tự thiết kế lại.

Thực hiện task/checklist của 05 theo thứ tự phụ thuộc:
Phase 0 xác minh baseline, mapping lossless và navigation guard;
Phase 3 bổ sung DTO metadata trước khi kết nối frontend ghi dữ liệu mới;
Phase 1 builder và picker giới hạn;
Phase 2 preview cục bộ, lưu/khôi phục draft, review và publish có consent;
Phase 4 thẻ gợi ý thật + câu mở đầu template có căn cứ;
Phase 5 responsive/accessibility/motion;
Phase 6 kiểm thử, regression và review.

Dùng lại kiến trúc và endpoints hiện có. PublicProfile.discovery là extension có
validation theo 04; lưu trong JSONB sẵn có. Không thêm endpoint, SQL migration/RLS,
thay taxonomy/scorer, cài dependency, hoặc sửa hạ tầng khi chưa có lý do/ủy quyền.
Giữ đủ interests/values/languages/goal/style/activities/availability/strictGoal cũ.
Phân biệt full interests và featured; không cắt dữ liệu đã lưu xuống ba mục.
Không ánh xạ gradual/lively sang listening/direct. Dùng quy tắc goalMode trong 04.
Giữ minimum 3 interests, 2 values, 1 language; bổ sung phần thiếu ở review, không tự đoán.

Preview cập nhật từ một reducer, không request/AI theo từng click. Draft chỉ lưu
server khi người dùng yêu cầu; không browser storage. Bảo vệ Close/tab/route/Back/
Forward/reload; session expiry/logout phải xóa state. Giữ luồng save -> server preview
-> xem toàn bộ public snapshot -> click publish riêng với version/digest hiện hành.
Không tự công khai, không tự bật MATCH khi chọn câu trả lời hoặc lưu draft.

Giữ matching 18+ registered và mọi filter/block/quota/consent/version/recheck hiện có.
Chỉ dùng public data do người dùng chọn; không journal, mood, chat, AI memory,
private identity hoặc real account name/avatar. Giữ pair alias/seed; không giả người
ghép bạn, không phần trăm tương hợp. Starter dùng exact server reasons + allowlist
template trong 04, không gọi AI và không tự gửi. Giữ invite/skip/block và báo cáo qua
chat; không thêm candidate-only report sai policy.

Với mỗi task, viết test có ý nghĩa cho hành vi thay đổi, xác nhận fail phù hợp,
triển khai tối thiểu rồi chạy lại. Chạy Vitest/typecheck/build, pytest và Playwright
fixture/fullstack theo 06; integration chỉ trên local disposable *_test DB và
synthetic users. Không dùng production/staging/live-provider/paid AI. Không chạy
đồng thời các harness reset cùng DB. Không coi skipped test là pass.
Regenerate OpenAPI/types bằng script hiện có khi DTO đổi; review generated diff.

Lập bảng FR01-FR19/NFR/PRE -> T01-T37 -> kết quả thực tế. Xác minh mobile, keyboard,
screen reader, contrast, reduced motion, navigation history, older writer omission,
10-interest compatibility, stale preview và consent. Review source diff, privacy và
mọi acceptance criterion trước khi tuyên bố xong. Báo riêng lỗi sẵn có ngoài phạm vi.

Rollback phải giữ backend đọc được discovery mới; không quay về DTO từ chối metadata
đã lưu, không xóa dữ liệu để rollback. Backend mới phải sẵn sàng trước frontend mới.
Nếu gặp mâu thuẫn an toàn/compatibility cần đổi chính sách, dừng phần phụ thuộc và
trình bày bằng chứng + đề xuất; không âm thầm thay rule.

Kết thúc bằng báo cáo tiếng Việt: thay đổi, file, acceptance evidence, test đã chạy/
chưa chạy, rủi ro còn lại và readiness. Không commit/push/tạo PR/merge/deploy hay
thay đổi hosted data nếu chưa được người dùng yêu cầu rõ trong phiên triển khai.
```
