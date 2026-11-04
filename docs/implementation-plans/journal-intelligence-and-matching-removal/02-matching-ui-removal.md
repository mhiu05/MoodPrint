# 02 — Xóa giao diện tìm bạn, tin nhắn người–người và hoạt động hai người

Phạm vi: yêu cầu 2 và 3. Task JI-10…JI-13. Backend matching/social/activities và bảng 0011–0013 **giữ nguyên**.

## Bản đồ ảnh hưởng (đã đọc code)

### Xóa hẳn (thư mục/file)

| Đường dẫn | Lý do |
| --- | --- |
| `frontend/src/features/real/social/` (22 file: `Discovery.tsx`, `HumanChat.tsx`, `HumanMessages.tsx`, `ProfileEditor.tsx`, `useSocialSummary.ts`, `useConnectionEvents.ts`, … và 6 file `*.test.ts`) | Toàn bộ UI tìm bạn/kết nối/chat người–người |
| `frontend/src/features/real/activities/` (13 file: `IcebreakerPanel.tsx`, `QuizPanel.tsx`, `FocusPanel.tsx`, `ActivityDock.tsx`, `ActivityCatalog.tsx`, `InviteCard.tsx`, …) | Chỉ được import từ `social/HumanChat.tsx:18-21` và `Safety.tsx:5`; phụ thuộc Connection |
| `frontend/src/features/real/Safety.tsx` | Chỉ export `OwnIdentity` (dùng ở `social/Discovery.tsx:16`) và `ConnectionSafety` (dùng ở `social/HumanChat.tsx:14`) |

### Sửa

| File:dòng | Hiện tại | Thay đổi |
| --- | --- | --- |
| `features/real/RealApp.tsx:80,90-92` | import `Discovery`, `HumanChat`, `HumanMessages`, `badgeText`, `useSocialSummary` | Xóa import |
| `RealApp.tsx:627-645` `GuestLocked` | Copy "Tìm bạn và nhắn tin" nhưng **cũng dùng cho `/check-ins`** (dòng 850) | Đổi thành `RegisteredOnly` trung tính: tiêu đề "Tính năng cần tài khoản", nội dung "Tạo tài khoản để dùng lịch hỏi thăm." |
| `RealApp.tsx:647-672` `SessionNotices` | "Tính năng kết nối của bạn đang tạm bị hạn chế…" | Giữ thông báo hạn chế (moderation còn sống) nhưng đổi copy: "Tài khoản của bạn đang bị hạn chế{đến…}. Bạn vẫn dùng được trợ lý và nhật ký." |
| `RealApp.tsx:696-722` `Navigation` | `useSocialSummary` (polling) + 2 mục "Tìm bạn", "Tin nhắn" | Xóa hook và 2 mục; nav còn Trợ lý, Nhật ký, Tài khoản |
| `RealApp.tsx:844-849` | Route `/connect`, `/messages`, `/chat/:connectionId` | Xóa ba route. Đường cũ rơi vào `path="*"` → `/assistants` (dòng 852). Bản yêu cầu bỏ sót `/chat/:connectionId` |
| `RealApp.tsx:1037` | "và kết nối từ những điểm chung." | "và hiểu mình hơn qua từng trang nhật ký." |
| `RealApp.tsx:1869` | "…Tìm bạn giờ là một mục riêng." | Bỏ vế đó khi `successor` null: "Đây là cuộc trò chuyện cũ với {tên}, chỉ để xem lại. Bạn vẫn có thể đổi tên, tải xuống hoặc xóa." |
| `RealApp.tsx:1928` | Card `discovery` render link `/connect` "Tìm bạn đồng điệu" | Tin nhắn cũ còn chứa card này (schema backend vẫn chấp nhận, `api/stream.ts:77`) → render `null` |
| `RealApp.tsx:2051` | "Không chia sẻ với bạn kết nối" | "Chỉ bạn xem được" |
| `RealApp.tsx:2145` | Nút "Mở Tìm bạn" khi `successor` null (Cầu Nối chỉ đọc) | Không render nút khi không có successor |
| `features/real/AssistantGuide.tsx:20-35` | Mục dẫn tới `/messages`, `/connect?tab=profile` | Xóa 2 mục; copy dòng 25 bỏ "Muốn chơi với người thật?…" |
| `features/real/checkins/AgentCheckInSettings.tsx:55` | Lý do `social_not_enabled` có `<Link to="/connect">` | Chỉ hiện text "Cầu Nối đã ngừng hỏi thăm." cho 3 lý do social |
| `features/real/collaboration/collaborationCopy.ts:89` | `V3_NOTE = "Tìm bạn không bao giờ nhận…"` | "Nhật ký của bạn chỉ dùng cho các trợ lý trong MoodPrint, không chia sẻ với người khác." |
| `features/real/Memory.tsx:261` | "…Hồ sơ tìm bạn…" | Bỏ câu nhắc hồ sơ |
| `features/real/Eligibility.tsx:80` | "Năm sinh không xuất hiện trong hồ sơ tìm bạn của bạn." | "Năm sinh chỉ dùng để kiểm tra độ tuổi." |
| `features/real/Auth.tsx:196,199` | "…và kết nối với người khác qua những điểm chung bạn chọn chia sẻ." | "…và để trợ lý AI giúp bạn hiểu nhật ký của chính mình." *File này nằm trong stash của chủ dự án (OD-09); chỉ sửa trên nhánh mới* |
| `features/guest/GuestEntry.tsx:101` | "Tìm bạn và nhắn tin cần tài khoản đã đăng ký." | Xóa dòng (cũng có trong stash, OD-09) |
| `features/onboarding/tourSteps.ts:4,14,58-66` + `tourSteps.test.ts` | Bước tour `matching` (`includeMatching`) | Xóa bước và tham số; cập nhật test |
| `companions/registry.ts:13` (`{kind:"match"}`), `80-92` (Cầu Nối: role "Tìm bạn đồng điệu", starters) | Dữ liệu trình bày legacy | Giữ entry `caunoi` để gắn nhãn lịch sử; role → "Trợ lý cũ"; xóa starters; xóa variant `match` nếu không còn ai dùng (`tsc` báo) |
| `api/session.ts:32,51` | Validator session đòi purpose `MATCH` và `features.matching` | **Giữ** trong đợt này: backend vẫn gửi (`auth/routes.py:117-121,134`); bỏ sau demo |

Đã grep `frontend/src/features/public/*`: không có chuỗi tìm bạn/kết nối. Copy giới thiệu nằm ở `Auth.tsx` và `RealApp.tsx:1037`.

### Backend liên quan UI (JI-12)

- `app/ai/prompts.py:55-56`: lớp `SHARED` đóng băng nói "discovery mở màn tìm bạn". Mọi V3 agent vẫn có thể trả `DiscoveryCard` (`schemas.py:22-23,57`; `search/schemas.py:30`).
- `app/ai/skills/hangout/SKILL.md`: dòng cuối dẫn "luồng activity hiện có" (activity hai người).
- Proactive Cầu Nối (`proactive/context.py:163-178`, `policy.py:63-77,144-147`): **không cần sửa**. Khi V3 mở cho mọi người (cờ true + cohort rỗng), `v3_reason` trả `legacy_companion` nên job Cầu Nối bị bỏ qua (`policy.py:55-57,142-143`).
- Hoạt động (`hoatdong`): `Capabilities(challenges=True)` (`agents.py:54`), persona `prompts.py` (V3_PERSONAS["hoatdong"]), check-in `recent_challenge_kinds` (`proactive/context.py`). **Không** import `modules.activities` hay đọc `activities_enabled` (đã `rg` toàn bộ `backend/app/ai`). Không cần tách gì; chỉ sửa SKILL.md.

### Có nên vô hiệu hóa route backend social/matching? — Đề xuất

**Giữ mounted trong đợt demo, gỡ sau demo.** Lý do:
1. UI không còn cách cấp purpose `MATCH`. Mọi route social/matching kiểm `assert_purpose(MATCH)` + adult dưới lock, nên người dùng mới không thể dùng. Tài khoản đã bật MATCH trước đây vẫn gọi được API bằng client tự viết (rủi ro thấp, dữ liệu đã do họ tự công khai).
2. Gỡ router (import `main.py:378,387,389-392`, vòng `include_router` `main.py:396-422` cho `profiles`, `social`, `social_summary`, `notifications`, `activities`, `moderation`) làm vỡ ~15 file test backend (`test_social*.py`, `test_matching_*.py`, `test_activit*.py`, `test_moderation*`), các harness tải và benchmark matching ngay trước demo, mà không thêm giá trị demo.
3. Moderation admin còn cần cho báo cáo cũ.

Phương án cứng hơn nếu chủ dự án muốn (OD-03): thêm dependency `social_retired` trả 404 cho mọi route ghi của social/activities (`POST/PUT/DELETE`), để route đọc và xóa dữ liệu vẫn hoạt động. Ước lượng 0,5 ngày + sửa test.

## JI-10 — Gỡ route, nav, polling, thư mục social/activities

**Mục tiêu:** Người dùng không còn thấy hay mở được màn tìm bạn, tin nhắn, hoạt động hai người; không còn polling social.

**Files:** Delete `frontend/src/features/real/social/`, `frontend/src/features/real/activities/`, `frontend/src/features/real/Safety.tsx`. Modify `frontend/src/features/real/RealApp.tsx` (các dòng ở bảng trên). Create `frontend/src/features/real/navigation.ts` + `navigation.test.ts`. Test UI: `frontend/tests/e2e/navigation-retired-social.spec.ts` (JI-13 bước 1, viết **trước** bước 3 của task này).

**Interfaces:** Produces: `NAV_ITEMS: readonly { to: string; label: string }[]` trong `navigation.ts` (`Navigation` render từ hằng này); `RegisteredOnly` component (thay `GuestLocked`) trong `RealApp.tsx`, props `{ title: string; children: ReactNode }`.

Repo **không có** React Testing Library (`frontend/package.json` chỉ có `vitest`), nên test Vitest chỉ phủ logic thuần; render/route kiểm bằng Playwright fixture.

- [ ] **Bước 1: Test đỏ**
  - `navigation.test.ts`: `expect(NAV_ITEMS.map(i => i.label)).toEqual(["Trợ lý","Nhật ký","Tài khoản"])`; `expect(NAV_ITEMS.some(i => /connect|messages/.test(i.to))).toBe(false)`.
  - Spec Playwright `navigation-retired-social.spec.ts` (mô tả ở JI-13 bước 1): redirect 3 route cũ, không request `/api/v1/social/`.
- [ ] **Bước 2:** `npm.cmd test -- navigation` → FAIL (module chưa có); spec Playwright FAIL trên code hiện tại.
- [ ] **Bước 3:** Xóa thư mục và file; sửa `RealApp.tsx`; `npm.cmd run typecheck` phải 0 lỗi. Lỗi `tsc` là danh sách chính xác các chỗ import còn sót.
- [ ] **Bước 4:** `npm.cmd test` → pass (6 file `*.test.ts` trong `social/` và 2 trong `activities/` biến mất cùng thư mục; ghi số test trước/sau vào ledger).
- [ ] **Bước 5:** `rg -n "social/|activities/|/connect|/messages\b|useSocialSummary|Tìm bạn đồng điệu|Mở Tìm bạn" frontend/src --glob "!api/generated/**"` → không còn kết quả, trừ `api/stream.ts` (card kind) và `api/session.ts` (MATCH).
- [ ] **Bước 6:** Commit `feat(web): remove friend finding, human messaging and two-person activities`.

**Chấp nhận:** build pass; bundle không còn chunk social (`npm.cmd run build` rồi so `dist/assets` trước/sau, ghi kích thước).
**Rủi ro:** CSS `social.css`/`activities.css` bị import từ nơi khác. `tsc` không bắt lỗi CSS, nên chạy `rg "social.css|activities.css" frontend/src`.
**Rollback:** revert commit (chỉ frontend; backend không đổi).

## JI-11 — Dọn copy và fallback card

**Mục tiêu:** Không còn chuỗi nào gợi ý tìm bạn/kết nối; tin nhắn cũ có card `discovery` hiển thị an toàn.

**Files:** các file ở bảng "Sửa" trừ `RealApp.tsx` route/nav (đã làm ở JI-10). Create `frontend/src/features/real/messageCards.ts` (`renderableCards`) + test. Test: `frontend/src/features/onboarding/tourSteps.test.ts`, `frontend/src/features/real/messageCards.test.ts`, `frontend/src/features/real/checkins/checkinsModel.test.ts`, `frontend/src/features/real/retiredCopy.test.ts` (mới).

**Interfaces:** Produces `renderableCards(cards: Card[]): Card[]` (bỏ `kind === "discovery"`), dùng trong vòng render card `RealApp.tsx:1915-1930`; `socialEligibilityText(reason: string): string | null` trong `checkinsModel.ts`, dùng ở `AgentCheckInSettings.tsx:55`.

- [ ] **Bước 1: Test đỏ**
  - `tourSteps.test.ts`: `expect(tourSteps(...).map(s => s.id)).not.toContain("matching")`.
  - `messageCards.test.ts`: `renderableCards([{kind:"discovery"},{kind:"mood_form"}])` → `[{kind:"mood_form"}]`.
  - `checkinsModel.test.ts`: `socialEligibilityText("social_not_enabled") === "Cầu Nối đã ngừng hỏi thăm."` (tương tự cho `teen_social_unavailable`, `social_restricted`).
  - `retiredCopy.test.ts`: đọc nguồn `frontend/src/**/*.{ts,tsx}` bằng `node:fs` (trừ `api/generated`); regex `/[Tt]ìm bạn|bạn kết nối|hồ sơ tìm bạn|kết nối với người khác|Mở Tìm bạn/` → 0 khớp.
- [ ] **Bước 2:** `npm.cmd test` → FAIL.
- [ ] **Bước 3:** Sửa copy theo bảng (chuỗi mới ghi ở bảng là bản chốt).
- [ ] **Bước 4:** `npm.cmd test; npm.cmd run typecheck` → pass.
- [ ] **Bước 5:** Commit `fix(web): drop matching copy and render retired discovery cards as nothing`.

## JI-12 — Backend: V3 không còn trả card `discovery`; SKILL hangout v2

**Mục tiêu:** Ba agent không còn đề xuất tìm bạn/kết nối; skill hangout không còn dẫn tới activity hai người.

**Files:** Modify `backend/app/ai/prompts.py` (thêm `V3_RETIRED_SOCIAL`, ghép trong `conversation_instructions` chỉ cho `bot_id in V3_IDS`), `backend/app/ai/runtime.py:863-870` (sau `AiReply.model_validate`), `backend/app/ai/groups/turn.py` (đường publish bubble của nhóm), `backend/app/ai/skills/hangout/SKILL.md`, `backend/app/ai/skills/registry.py` (version `"2"` cho hangout). Copy backend người dùng thấy: `backend/app/core/security.py:126` và `backend/app/modules/guests/policy.py:56` ("…Lượt dùng thử không có tìm bạn và nhắn tin." → "Tạo tài khoản để dùng tính năng này."), `backend/app/ai/registry.py:40-42` (Cầu Nối legacy: role "Trợ lý cũ", `starters=[]`). Giữ nguyên chuỗi trong route social còn sống (`consent/routes.py:40`, `users/routes.py:109`). Trước khi sửa: `rg -n "không có tìm bạn|Tìm bạn đồng điệu|Sửa hồ sơ kết nối" backend/tests frontend/tests` để cập nhật test đang assert chuỗi cũ. Test: `backend/tests/test_retired_social.py` (mới), `backend/tests/test_agent_skills.py`.

**Interfaces:** Produces `app.ai.schemas.drop_retired_cards(parts: list[AiOutput], bot_id: str) -> list[AiOutput]`: với `bot_id in V3_IDS` bỏ mọi card `kind == "discovery"`; legacy giữ nguyên.

- [ ] **Bước 1: Test đỏ**
  - `test_v3_reply_never_persists_a_discovery_card` (fixture `clients`, bật V3 + multi_message, fake model trả card discovery cho `dieuphoi`): message lưu có `cards == []`.
  - `test_legacy_prompt_bytes_unchanged`: sha256 `instructions('may')`/`('nhip')` bằng giá trị ghi trong `docs/implementation-plans/three-agent-orchestration-group-chat/12-execution-evidence.md` (`697a0b191c2a…`/`2c102b424cba…`, implementer lấy đủ 64 ký tự bằng lệnh trên `origin/main`).
  - `test_v3_conversation_instructions_retire_social`: `"discovery" in conversation_instructions("hoatdong","activity")` và câu cấm có mặt; không có với `"may"`.
  - `test_agent_skills.py`: `"activity hiện có" not in registry.instructions("hangout")`; `registry.load()["hangout"].version == "2"`.
- [ ] **Bước 2:** `uv run --locked pytest -q tests/test_retired_social.py tests/test_agent_skills.py` → FAIL.
- [ ] **Bước 3:** Cài đặt. `V3_RETIRED_SOCIAL = "MoodPrint không còn tính năng tìm bạn hay nhắn tin với người khác. Không dùng card discovery, không gợi ý mời hay kết nối với người dùng khác; nếu cần hoạt động cùng người thân, gợi ý để người dùng tự liên hệ họ."`. Câu cuối SKILL.md hangout đổi thành: "Nếu người dùng muốn làm cùng người khác, gợi ý để họ tự rủ; MoodPrint không gửi lời mời." Frontmatter `version: 2` và `SPECS["hangout"]` version `"2"` (registry so khớp chặt, `registry.py:44-45`).
- [ ] **Bước 4:** chạy lại + `tests/test_prompt_options.py tests/test_three_agents.py tests/test_orchestration_sdk.py tests/test_groups_turn.py`.
- [ ] **Bước 5:** Commit `fix(ai): retire discovery cards for the three agents`.

**Rủi ro:** eval V3 có thể so khớp prompt version (`prompt_version(...)` ghi vào `ai_usage.prompt_version`, `runtime.py:388-392`). Đây là runtime layer nên không đổi `VERSIONS`. Nếu `tests/test_v3_live_eval.py` pin chuỗi, cập nhật có ghi lý do. **Rollback:** revert.

## JI-13 — Spec e2e/fullstack/visual

**Mục tiêu:** Bộ e2e/fullstack phản ánh sản phẩm mới mà không nới assertion không liên quan.

Phân loại sau khi `rg` các chuỗi `/connect`, `#/messages`, `/chat/`, `Tìm bạn`, `icebreaker`, `coop_quiz`, `Cùng tập trung`, `discovery` trong `frontend/tests`:

| Spec | Hành động |
| --- | --- |
| `tests/e2e/discovery.spec.ts` (25 test), `tests/e2e/social.spec.ts` (8), `tests/e2e/activities.spec.ts` (16), `tests/e2e/friendship-fixture.ts` (chỉ `discovery.spec.ts` dùng) | **Xóa** |
| `tests/fullstack/matching-v2.spec.ts` (4), `tests/fullstack/activities.spec.ts` (5) | **Xóa**; backend vẫn được bảo vệ bởi `backend/tests/test_matching_*.py`, `test_activit*.py` |
| `tests/fullstack/responsive.spec.ts:35` "social screens are responsive…" | **Thay** bằng "journal and assistant screens are responsive and pass axe at every acceptance size" (cùng kích thước 1440/1280/430/390) |
| `tests/fullstack/mvp.spec.ts:202` Journey B/C, `:333` Journey D, `:426` Journey F (phần matching/chat) | **Xóa** B/C/D; F giữ phần mood + composer, bỏ matching/chat |
| `tests/fullstack/journeys.spec.ts:90` ("…connects two users"), `:162` (reveal/report/block) | `:90` giữ phần mood + SDK stream, bỏ phần kết nối; `:162` **xóa** |
| `tests/fullstack/moderation.spec.ts` | Report sinh từ chat người–người. **Viết lại**: seed report qua endpoint test của `e2e_server.py` (thêm `/__test/moderation/seed-report`, chỉ `APP_ENV=test`), giữ queue → restriction |
| `tests/e2e/real.spec.ts`, `ux-redesign.spec.ts`, `merge-readiness.spec.ts`, `states.spec.ts`, `motion.spec.ts`, `guest*.spec.ts`, `eligibility.spec.ts`, `onboarding.spec.ts`, `collaboration.spec.ts`, `proactive.spec.ts`, `multi-message.spec.ts`, `agent-check-in-settings.spec.ts`, `auth.spec.ts`, `chat-history.spec.ts`, `session-reliability.spec.ts`; fixtures `ux-fixtures.ts`, `search-fixtures.ts` | **Sửa từng test**: bỏ mock `/social/summary`, `/connections`; assert nav 3 mục; assert copy mới. Không nới assertion không liên quan |
| `tests/fullstack/v3.spec.ts`, `collaboration.spec.ts`, `product-experience.spec.ts`, `guest-*.spec.ts`, `mood-evidence.spec.ts`, `helpers.ts` | Sửa các tham chiếu nav/copy (1–6 chỗ mỗi file) |
| `tests/visual/capture.spec.ts:42,61-63` | Bỏ ảnh `messages`; thêm ảnh `memory` và `profile` (Tài khoản có công tắc mới). Không có baseline ảnh được theo dõi trong git (`git ls-files` không có snapshot), chỉ là evidence |

- [ ] **Bước 1:** Thêm spec mới trước: `tests/e2e/navigation-retired-social.spec.ts`: nav 3 mục ở 1440 và 390; `/#/connect`, `/#/messages`, `/#/chat/x` → URL `/#/assistants`; không request `/api/v1/social/`; legacy Cầu Nối read-only không có nút "Mở Tìm bạn". Chạy → đỏ trước JI-10 (chạy trên commit trước JI-10) hoặc xanh sau. Ghi cả hai vào ledger.
- [ ] **Bước 2:** Xóa/sửa theo bảng.
- [ ] **Bước 3:** `npx.cmd playwright test --config playwright.owned.config.ts --reporter=list --output "$env:TEMP\ji13-e2e"` → pass. Fullstack: lệnh mục 6 của `docs/development.md` với DB `moodprint_ji_fullstack_test`.
- [ ] **Bước 4:** Commit `test(web): retire social journeys; keep moderation via a seeded report`.

**Chấp nhận:** không còn spec nào điều hướng tới route đã xóa; tổng số test e2e/fullstack trước/sau ghi vào ledger, kèm danh sách test bị xóa (không ghi chung chung).
**Rủi ro:** CI `verify.yml` có thể liệt kê spec theo tên. Kiểm `rg "matching-v2|activities.spec|discovery.spec|social.spec" .github`. **Rollback:** revert commit test cùng với JI-10/11.
