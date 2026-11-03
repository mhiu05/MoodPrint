# Collaboration Defaults Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans hoặc superpowers:subagent-driven-development để triển khai từng task; không xóa runtime khi bỏ trang settings.

**Goal:** Mọi capability từng bị điều khiển bởi “Trợ lý phối hợp với nhau” bật hiệu lực mặc định cho tài khoản đủ điều kiện cũ/mới, không cần vào settings/xác nhận; bỏ UI cấu hình đó.

**Architecture:** Tập trung effective grants vào một module có hai policy modes: legacy opt-in và defaults-v1. Defaults-v1 bỏ ảnh hưởng của hàng preference cũ `false`/missing nhưng giữ eligibility/data gates và operational switches. Receipt mang policy + epoch, kiểm lại trước model/publish/continuation; preference cũ giữ nguyên để rollback.

**Tech Stack:** Python policy, SQLAlchemy/PostgreSQL additive migration, FastAPI settings/API, React routes/copy.

**Spec:** [00](00-overview.md), [01](01-codebase-audit.md); thay yêu cầu mặc định tắt trong các plan Phase2/V3 cũ **chỉ đối với per-edge preference**, không thay giới hạn dữ liệu của chúng.

## Global Constraints

- Áp dụng cả3 legacy edges và4 V3 consult/handoff edges; không chỉ cạnh Hoạt động.
- Không đổi AI consent/history preferences/journal-context opt-in, group journal access hoặc member history để ép account thành eligible.
- Giữ coordinator, orchestration, consult/handoff/tools, receipts và usage; Cầu Nối/social discovery không có đường đọc dữ liệu private mới.
- Giữ server feature/cohort switches, quota/budget/concurrency, distress/refusal/source revision và checks trước dispatch/publish.
- Không ghi preference cũ `false` thành lịch sử “người dùng đã đồng ý”; không có modal yêu cầu bật phối hợp lại.

## Kiểm kê capability/data boundary đang có

Hướng request khác hướng trả kết quả; bảng ghi rõ cả hai. Căn cứ `collaboration/{policy,contracts,coordinator,specialist}.py`, `orchestration/{policy,workflow,specialists}.py` và `runtime.py`.

| Capability | Input được specialist thấy hiện tại | Dữ liệu primary nhận và giới hạn giữ nguyên |
| --- | --- | --- |
| `nhip_energy_for_rure`, R1 chat/R2 sáng | Rủ Rê nhờ Nhịp; tối đa3 saved journal excerpts, mỗi text≤600 ký tự, mood1–5,≤6 emotions/factors, IDs/revisions/date. R1 chỉ hôm nay+hôm qua theo ngày local (`CHAT_JOURNAL_DAYS=2`); R2 chỉ hôm qua. Đòi `journal_context_enabled`, AI và eligibility. | Rủ Rê chỉ nhận energy enum low/medium/high/unknown, time budget và nhãn estimate/basis; source IDs giữ backend, không câu chữ/mood/emotions/factors. |
| `nhip_habit_for_may`, R3 | Mây→Nhịp: need enum sleep/stress/focus/energy, time-of-day. Không transcript, memory hay journal input. | Một habit text≤200 ký tự, duration1–15 phút, habit kind; đó là gợi ý, không phải fact về người dùng. |
| `rure_activity_for_guong`, R4 | Gương→Rủ Rê: interest taxonomy và time budget5/10/15 phút. Không câu chữ gốc/history/memory. | Một activity text≤240 và challenge kind; không tự ghi shared activity hoặc mời người khác. |
| `dieuphoi_consult_nhatky` | Điều phối→Nhật ký: task/focus enum, days1–14. Backend đọc≤5 saved entries, excerpt≤600, mood/emotions/factors/IDs/revisions. Private prose chỉ ở specialist, vẫn đòi journal-context gate và journal-refusal checks. | `for_primary()` chỉ themes≤4, pattern≤240,≤4 observed/inferred observations và entriesConsidered; bỏ source IDs, ngày cụ thể, excerpts. `check_reflection` chặn sao chép dài/nguồn bịa. |
| `dieuphoi_consult_hoatdong` | Goal≤160 ký tự từ yêu cầu hiện tại, time budget, energy enum. Không journal/memory/history. | `ActivityPlan`:1–3 generated options, title≤60,1–3 steps≤120, minutes/effort, note≤160. Guard không hỏi Hoạt động sau khi Nhật ký đã cấp dữ liệu, tránh goal mang nội dung journal. |
| `dieuphoi_handoff_nhatky` | Chỉ latest user message + `HandoffInput.reason` enum, rebuild context, không copy transcript. Nhật ký có journal tool **chỉ khi** approved plan hỏi `journal_entries` và user không từ chối; backend journal tool kiểm quyền riêng. `mood_scores` trong allowlist không phải grant tự chọn mood scope. | Nhật ký trả lời trực tiếp, speaker/active-agent có receipt; các lượt sau chỉ đoạn hội thoại từ handoff. Không gửi raw journal trở lại Điều phối. Không thêm free-text summary/topic vào transfer. |
| `dieuphoi_handoff_hoatdong` | Chỉ latest user message + reason enum; không prior transcript/journal/memory. | Hoạt động trả lời trực tiếp, continuation giới hạn segment và live edge. Giữ nút quay về Điều phối. |

**Ngoài setting này:** group chat chỉ chia sẻ group-visible messages theo membership/history_from_sequence; `AiGroupMember.journal_access` vẫn default false và là opt-in riêng, không được defaults-v1 ghi true. Proactive lịch/AI lịch sử cũng không tự bật. Direct journal/mood tools giữ owner authorization/moodScope theo lượt. Attachment ảnh/âm thanh, draft entries và full private histories không được thêm vào bất kỳ cạnh nào.

Một điểm copy hiện lệch source: handoff chỉ chuyển `reason` enum, không “một dòng chủ đề ngắn” tự do như `collaborationCopy.ts`; khi sửa copy phải theo code boundary trên. Không mô tả “bật mặc định” là đã mở mọi dữ liệu.

## Default/backfill và rollback

Có hai cách thực tế: update/upsert7 rows cho mọi eligible user rồi archive old values; hoặc overlay policy toàn hệ thống. **Chọn overlay có epoch**, tránh ghi đè opt-out cũ, không bỏ sót account mới đủ18 sau này và không cần một backfill write khổng lồ. Đây là **logical backfill**: mọi eligible account được cùng effective defaults ngay khi rollout, bất kể row cũ absent/false/true. Không có bước yêu cầu người dùng tự bật lại.

Module mới `collaboration/grants.py`:

```text
GrantToken(policy: 'sharing-v1'|'collaboration-defaults-v1', version: int)
effective_grants(db, settings, user, family: 'legacy'|'v3')
  -> EffectiveGrants(edges: dict[str, GrantToken], eligible: bool,
                     feature_open: bool, journal_context: bool)
```

- `AI_COLLABORATION_DEFAULTS_ENABLED=true` + mode cohort mở: cấp token defaults cho từng edge của family hiện được phép; `version=AI_COLLABORATION_POLICY_EPOCH` (đề xuất2). False/missing row không phủ định defaults. Journal-context vẫn là gate riêng ở edge cần nó, không tự đổi false thành true.
- Feature off/ineligible: không có usable grants. Default flag off: đọc nguyên row `AiSharingPermission`/`sharing-v1` như hiện tại; hàng thiếu vẫn off. Không đổi default false của bảng legacy thành true vì bảng giờ là snapshot rollback, không là authority của defaults-v1.
- Cả legacy `coordinator.live_grants/still_authorized`, V3 `workflow.live_grants/still_authorized/handoff_allowed` và read view phải gọi module chung. Không còn nhánh vô tình query `enabled=True` để quyết runtime defaults.
- Bổ sung receipt `permission_policy` (`String(32)`, default `sharing-v1`) ở `AiCollaboration`/`AiOrchestrationStep`; `permission_version` cũ mang row.version hoặc epoch tùy policy. Plan/group steps không có edge giữ version0/policy cũ, không đổi group grants. In-memory `Consultation/Step` mang token đủ2 trường. Chặn publish nếu policy/epoch hoặc feature thay đổi, kể cả edge bool vẫn true.
- Rollback khẩn cấp tắt `AI_SMART_ORCHESTRATION_ENABLED`/`AI_COLLABORATION_ENABLED` trước, ngừng dispatch; drain/cancel in-flight; sau đó tắt defaults và tăng epoch khi redeploy. Old opt-in values vẫn nguyên. Legacy default-off trở lại chỉ trong rollback có chủ đích, không phải trạng thái release mục tiêu. Không downgrade schema khi receipts defaults còn được đọc; rollback về bản compatibility có cột token trước.

Với operator cần rollback một cohort, dùng server rollout/cohort hiện có; khi defaults đã rollout cho toàn bộ eligible account thì empty allowlist có nghĩa mở cho tất cả theo semantics repo. Không lấy old opt-out làm denylist mặc định. Không mở guest hoặc account chưa có age declaration hợp lệ. Không tự mở history để làm một temporary chat thành persistent: các gate persistent vẫn giữ.

## API, UI và config production

`GET /ai/sharing` có thể giữ cho compatibility/diagnostics, phản ánh effective enabled + available/reason; thêm `policyMode/policyEpoch` optional. Khi defaults mode active, `PUT /ai/sharing/{edge}` trả410 `SHARING_SETTINGS_RETIRED` và không sửa hidden preference; client cũ cần refresh. Khi rollback mode, API legacy hoạt động lại để quản lý opt-in. Không để UI cũ ghi một toggle mà runtime cố tình bỏ qua.

Xóa `CollaborationSummaryCard` khỏi AccountPage, lazy import/route settings `/companion-sharing` và `SharingPage.tsx`/CSS phần settings không còn dùng. URL cũ redirect `/assistants` bằng replace, không render toggle. **Giữ** `CollaborationLine`, `AgentLines/HandoffBanner`, backend summary templates, receipts và “Vì sao?” thông tin. Bỏ link “Đổi cài đặt phối hợp” từ receipt dialog, thay bằng mô tả dữ liệu đang dùng; có link info Nhật ký nếu người dùng cần quản lý journal-context. Copy không nói “bạn đã bật quyền cạnh” khi receipt là defaults policy; cũng không nói “trợ lý đã phối hợp” nếu chưa có completed/used receipt.

Flags/config cần operator kiểm ở staging, không được suy runtime từ env example:

| Cờ có sẵn | Giá trị/điều kiện mục tiêu |
| --- | --- |
| `AI_ENABLED`, `AI_MULTI_MESSAGE_ENABLED`, `AI_ACCOUNTING_ENABLED`, `CHAT_HISTORY_ENABLED` | true ở deployment đủ điều kiện; AI consent và lịch sử cá nhân vẫn do quyền hiện có |
| `AI_THREE_AGENT_EXPERIENCE_ENABLED`, `AI_SMART_ORCHESTRATION_ENABLED` | true cho V3 cohort để4 edges thực sự dùng được |
| `AI_V3_ROLLOUT_USER_IDS` | Review cohort; để `[]` khi mở toàn bộ eligible accounts |
| `AI_COLLABORATION_ENABLED`, `AI_COLLABORATION_ROLLOUT_USER_IDS` | Giữ/bật nếu còn phục vụ legacy; defaults cả3 edges khi legacy family hợp lệ |
| `AI_DAILY_BUDGET_USD`, orchestration/collaboration caps và budget shares | Positive verified global budget; giữ quota/cost fences hiện có |
| `AI_GROUP_CHAT_ENABLED` | Giữ giá trị rollout hiện tại; không cần bật để4 direct edges hoạt động |
| **Mới** `AI_COLLABORATION_DEFAULTS_ENABLED`, `AI_COLLABORATION_POLICY_EPOCH` | true/2 sau compatibility migration, fake proof và cohort validation |

Đưa các cờ thiếu vào `deploy/runtime.env.example` khi triển khai. Không mặc định đổi code `Settings` mọi runtime flags thành true, vì cần kill switches fail closed. Việc active defaults trong production cần cả epoch policy lẫn existing runtime flags, không chỉ xóa UI.

## Files và tasks

Tạo `backend/app/ai/collaboration/grants.py`, migration `backend/alembic/versions/<next>_collaboration_default_policy.py`, `backend/tests/test_collaboration_defaults.py`. Sửa collaboration `{models,contracts,coordinator,schemas,routes}.py`, orchestration `{models,policy,workflow}.py`, `core/config.py`, proactive executor checks qua coordinator; frontend `RealApp.tsx`, `collaboration/SharingPage.tsx`, `collaboration/CollaborationLine.tsx`, `collaboration/collaborationCopy.ts`, CSS liên quan. Không xóa cả thư mục collaboration. Generated contracts cập nhật khi API đổi.

### C1 — Shared grants và migration compatibility

**Interfaces:** `GrantToken`, `effective_grants`; receipt token như trên.

- [x] Viết failing matrix: old rowfalse/true/missing và user mới → defaults on khi eligible; old-policy flagoff khôi phục đúng old values; guest/under18/unknown age/suspended/deleting/AI off/cohort off/history gate không được lách.
- [x] Additive receipt migration, shared resolver và revalidation tất cả call sites; giữ `AiSharingPermission` không ghi lại. Test defaults token version2 khác old row.version2, policy flip/epoch change chặn output in-flight và handoff continuation.
- [x] Chạy `uv run --locked pytest tests/test_collaboration_defaults.py tests/test_sharing_api.py tests/test_collaboration_migration.py -q`; pass với DB disposable; migration không thay schedule/preference/raw content. Test `test_new_account_has_every_edge_off_and_no_caunoi_edge` giữ case old mode, thêm case defaultsmode riêng.

### C2 — Chứng minh runtime thực chạy và không tăng scope

**Files:** coordinator/workflow/proactive checks và tests liên quan trong01.

- [x] Legacy fake chat R1/R3/R4, proactive R2 và V3 consult/handoff chạy được không cần PUT sharing; journal-context false vẫn chặn edge cần journal và không tự bật setting đó.
- [x] Assert snapshot dữ liệu đúng từng hàng bảng boundary; handoff không free-text topic/priorhistory; source edits/revoke cancel; Nhật ký→Hoạt động taint guard, group journal opt-in unchanged, matching không thấy private content.
- [x] Chạy `uv run --locked pytest tests/test_collaboration_chat.py tests/test_collaboration_proactive.py tests/test_collaboration_privacy.py tests/test_collaboration_review_fixes.py tests/test_orchestration_policy.py tests/test_orchestration_sdk.py tests/test_v3_review_fixes.py tests/test_v3_proactive.py -q`; pass fake và receipts/usage chỉ cho bước thật sự chạy.

### C3 — Bỏ settings UI, giữ explanation/runtime

- [x] Fixture E2E account không có mục “Trợ lý phối hợp với nhau”, old route redirect; prompt hợp lệ vẫn có real receipt line và handoff banner/return. Case legacy và V3 đều có kiểm tra.
- [x] Xóa settings component/dead CSS/import/API calls, sửa explanation copy/link, giữ `CollaborationLine` và `AgentLines`; không xóa backend runtime/API diagnostics theo tên settings.
- [x] Chạy `npx.cmd playwright test tests/e2e/collaboration.spec.ts tests/e2e/multi-message.spec.ts tests/e2e/group-mentions.spec.ts` sau update fixtures và `npx.cmd vitest run src/api/streamCollaboration.test.ts src/api/streamOrchestration.test.ts`; pass offline. Không thay tests receipt bằng assertion UI biến mất đơn thuần.

### C4 — Rollout và phục hồi

- [ ] Read-only preflight khi được triển khai: đếm old missing/true/false theo family, không export identities/content; record config names/modes, không ghi secret. Không cần sửa từng row làm backfill.
- [ ] Compatibility schema+code trước; bật defaults cho cohort rồi toàn eligible accounts; kiểm metrics calls/timeout/deny/cost/token mismatch. Không yêu cầu người dùng xác nhận bật.
- [ ] Diễn tập fake rollback off→on→off/epoch bump khi có in-flight child; không publish receipt sai hoặc revive output cũ. AWS credential/config steps ở [07](07-rollout-credentials-and-coverage.md), không gọi AWS trong phiên plan.

## Review Focus, chi phí và acceptance

Oldfalse vẫn chặn runtime → C1 old-row matrix; chỉ sửa V3 bỏ sót proactivelegacy → C2 R2 case; defaults mở raw journal/group grant → C2 projection snapshots; epoch change publish stale → C1 race tests; UI removal làm mất runtime receipt/links → C3 full journey.

Chi phí sẽ tăng do nhiều eligible prompt có thể chạy planner/child hơn. Giữ legacy cap10/ngày/timeout8s và V3 cap20 steps/ngày/max2 specialists/planner8s/specialist10s, global30s và budgetshare0,7 mặc định nguồn; có thể operator giảm bằng config, không nới mặc định. Optional failure giữ fallback direct, không giả receipt. Không có credential mới, không cần IAM mới. Acceptance: mọi eligible old/new account có effective defaults không cần PUT, runtime vẫn được gọi đúng điều kiện, UI setting bị bỏ, private boundaries/quota/rollback đều có fake proof; journal opt-in/history không tự bật.
