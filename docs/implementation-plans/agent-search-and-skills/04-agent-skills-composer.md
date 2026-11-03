# Agent Skills & Composer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans hoặc superpowers:subagent-driven-development để triển khai task-by-task. Chỉ viết plan trong phiên hiện tại.

**Goal:** Agent tự chọn workflow phù hợp; người dùng chọn một skill hoặc Web/Maps Search trong dấu `+` cho đúng prompt kế tiếp.

**Architecture:** Registry đóng nạp hai `SKILL.md` ở backend, metadata công khai qua capability endpoint, instruction được thêm vào current-agent run sau policy check. Composer giữ selection trong RAM, đóng băng cùng client message ID và truyền `PromptOptions`; menu chỉ hiển thị capability backend cho phép.

**Tech Stack:** Python/Pydantic/pathlib, React19/TypeScript, lucide-react và UI/Dialog hiện có; không cần framework/plugin skill engine mới.

**Spec:** [00](00-overview.md), [01](01-codebase-audit.md), search contracts [02](02-web-search-citations-accounting.md)/[03](03-maps-search.md).

## Global Constraints

- Skill ở `backend/app/ai/skills/<skill-id>/SKILL.md`; phase đầu chỉ `hangout`, `learn-new-thing`.
- Manual skill dùng một lần, chip gỡ được trước gửi và tự xóa sau accepted send; không thành setting vĩnh viễn.
- Skill là chỉ dẫn/metadata đáng tin cậy do repo vận chuyển; không script/shell/network/import/plugin tự động và không cấp thêm tool.
- Chỉ current effective V3 agent trong direct chat ở phase đầu. Không đổi speaker/active_agent bằng skill selection, không gộp lịch sử; group/proactive/legacy không mở menu mới.
- Giữ composer giới hạn500 ký tự, Enter/Shift+Enter/IME, voice draft insertion, send/stop và recovery/idempotency hiện tại.

## Routing và quyền của skill

Đã cân nhắc: (A) chạy trong agent đang mở; (B) luôn handoff sang Hoạt động; (C) consult Hoạt động như tool. **Chọn A** vì skill là workflow cho một prompt, giữ đúng người đang nói và không cần thay grant/history boundary. B tạo sticky handoff ngoài ý định; C hiện child tool-free nên không thể tự đi search và dễ kéo thêm chi phí/thời gian. Không tự mở rộng consult contracts để giải quyết UI selection.

`effective_agent = run.responder or conversation.bot_id`. Manual skill phải hiện cùng tên agent đang trả lời. Nếu `nhatky` đang phân tích mood scope hoặc lượt vừa dùng dữ liệu journal, instruction skill không được thay evidence schema hoặc mở search. Với mood-analysis chuyên biệt, trả lý do skill không dùng được cho lượt hiện tại trước admission, giữ draft/chip cho người dùng điều chỉnh. Với các prompt thông thường, cả ba agent dùng được hai skill. Khi manual/auto skill được chọn, lượt chạy direct ở effective agent, bỏ smart planner cho lượt đó; các lượt khác giữ orchestration hiện có. Skill không kết thúc sticky handoff và không tạo receipt consult giả.

Auto nhận ý định chỉ từ prompt hiện tại, không scan lịch sử private: reuse `conversation_intent` và thêm resolver thuần `resolve_skill(prompt, manual_id, agent, constraints) -> SkillResolution`. Manual valid thắng auto; hai ý định cùng mạnh thì không đoán workflow kép, hỏi người dùng muốn ưu tiên đi chơi hay học. Phrases tiếng Việt có/không dấu và phủ định (ví dụ “không muốn đi đâu”) phải có test. Không gọi LLM riêng chỉ để chọn skill. Resolved skill có thể được agent bỏ qua nếu người dùng chỉ kể chuyện, không yêu cầu gợi ý; explicit selection vẫn xác định workflow nhưng không ép lấy dữ liệu ngoài.

## Registry và contract

```text
SkillSpec(id, name, description, version, path, preferred_tools, allowed_agents)
SkillResolution(skill_id?, origin: manual|auto|none, version?, body_hash?)
TurnConstraints(origin: user|proactive|group, protocol: int,
                mood_scope: bool, private_sources_read: bool, feature_open: bool)
SkillRegistry.load() -> Mapping[str, SkillSpec]
SkillRegistry.instructions(skill_id: str) -> str
resolve_skill(prompt: str, manual_id: str|None, agent: str,
              constraints: TurnConstraints) -> SkillResolution
GET /ai/prompt-capabilities?botId=<effective-agent>
  -> {skills:[{id,name,description,available,reason?}],
      tools:[{id,available,reason?}], responseProtocols:[2,3]}
```

Endpoint auth/eligibility-aware nhưng không trả instruction body, absolute path, token hoặc provider error. Authoritative permission vẫn kiểm lại khi gửi, gọi tool và publish; capability view không là grant. V3 flag/cohort, account eligibility, provider readiness, search budget, protocol3 cùng tham gia available. Tool unavailable không làm offline skill unavailable nếu workflow vẫn hữu ích.

Registry dùng hai đường dẫn hằng số; `resolve()`/root containment, chặn symlink/traversal, ID không có trong allowlist trả422, body≤16KiB UTF-8. Load/read một lần khi startup; lỗi file trả unavailable cho đúng skill và metric không nội dung, không fallback đọc path từ browser. Metadata định nghĩa trong `registry.py`; `SKILL.md` dùng frontmatter scalar đóng (`id/name/description/version`) được parser tối thiểu kiểm khớp registry, body Markdown. Không dùng YAML loader có object tags, không cần thêm dependency. Hash/version có thể ghi vào run receipt metadata nhưng không ghi nguyên prompt/instructions vào logs.

`preferred_tools` là gợi ý workflow; khả năng thực tế là giao của backend allowlist + effective-agent capability + live permission + origin/protocol + quota/budget. Không cho `SKILL.md` khai `tool: shell` rồi tự đăng ký. Không đọc `.agents/skills` hoặc skill cá nhân trên máy người phát triển khi app chạy.

## Hai workflow đầu và backlog

| Skill | Instruction cần viết | Bằng chứng chấp nhận |
| --- | --- | --- |
| `hangout` — “Đi chơi” | Hỏi khu vực nếu cần địa điểm, hỏi thời gian/chi phí/đi một mình hay cùng người khác khi thiếu; gợi ý2–3 lựa chọn vừa sức. Nếu cần place thật thì Maps; không giả vờ đã tìm. Rating/hours thiếu thì nói chưa rõ. | User chọn skill hoặc hỏi đi chơi → hợp ngữ cảnh, không GPS; có Maps dùng kết quả có link; Maps off vẫn gợi ý hoạt động chung/hỏi vùng. |
| `learn-new-thing` — “Học điều mới” | Hỏi sở thích/thời gian/mức hiện tại khi hữu ích, đưa1–3 ý tưởng và một bước thử5–15 phút. Web khi cần tài nguyên/cập nhật/links thật, nguồn có citation; không nhất thiết search cho gợi ý chung. | User “có10 phút muốn học điều mới” → bước thử cụ thể; course/resource mới có nguồn hoặc nói chưa kiểm chứng. |

Backlog ngoài phase đầu: `mood-reset` (hoạt động ngắn an toàn, không chẩn đoán), `creative-break`, `journal-prompt`, `focus-sprint`. `focus-sprint` nên dẫn đến activity Focus hiện có nếu người dùng muốn cùng bạn: `activities/definitions.py` có plans25/5,15/3,50/10; không dựng timer/session trùng. `icebreaker/coop_quiz` là shared activities, challenge là nội dung proactive/Hoạt động; skill không tự mời người khác hoặc ghi receipt đã hoàn thành.

## UX dấu `+` và state machine

Giữ thế giới thiết kế chat hiện có trong `DESIGN.md`/`agent-chat.css`: dấu `+` bên trái textarea “Nhắn cho Điều phối…”; gửi/dừng tiếp tục bên phải, voice còn dễ truy cập. Tối thiểu hit area44px, nhãn “Thêm kỹ năng hoặc công cụ”, `aria-expanded/controls`. Không đặt tool ở menu Tài khoản.

Popover có Web Search, Maps Search và mục “Kỹ năng” mở danh sách2 skill. Mỗi item có tên và mô tả một dòng; unavailable có lý do từ backend. Không thêm công cụ giả/attachment chưa hỗ trợ. Sau chọn skill/tool, chip trên cùng composer và nút bỏ có nhãn rõ. Tối đa1 skill + mỗi tool một chip; thay skill không xóa text/tools, chọn lại không duplicate. Maps chọn mở ô nhập “Khu vực” gắn chip; chọn skill Đi chơi không tự bắt người dùng nhập khu vực cho mọi gợi ý.

Keyboard: Enter/Space mở, Arrow/Home/End điều hướng nếu dùng menu role, Escape đóng rồi trả focus về `+`; submenu “Kỹ năng” có back bằng bàn phím. Chọn item trả focus textarea; remove chip trả focus tới chip còn lại hoặc textarea. Nếu popover dùng button list/dialog thay ARIA menu thì phải giữ Tab order tự nhiên, không trộn hai mô hình. Mobile menu không che textarea/send hoặc tràn viewport320px; giữ safe-area/virtual keyboard; reduced motion theo policy hiện có.

State: `draftSelection → submittingSnapshot → accepted → nextDraftSelection`. Đóng băng normalized options cùng text/client ID **trước** network call. Sau202 chỉ xóa selection revision đã gửi; chip của prompt mới người dùng vừa chọn không bị xóa nhầm. 4xx chưa accepted giữ draft/options với lỗi; network/5xx unknown giữ snapshot riêng để reconcile/retry cùng ID/options, không tự phát search lại. Sau accepted rồi cancel/fail không tự gắn chip cũ lại. Đổi conversation/agent, New, logout/expiry xóa selection; back/forward không mang chip sang scope khác. Không URL/query-string/localStorage cho khu vực hoặc skill selection.

Manual tools đều được thử đúng1 lần nếu available: backend preflight chuẩn bị result hoặc status trước compose; agent không được bỏ qua lựa chọn chỉ bằng quyết định model. `SearchAllowance` dùng chung cho preflight và function-tool invocation để cached operation không bị gọi/đếm lần hai. Chọn cả Web/Maps: Maps start trước, Web chỉ chạy khi deadline còn đủ≥20 giây; nếu không báo tool chưa kịp dùng. Không tool nào vượt shared quota/remaining budget; trả lý do thay vì thay provider.

## Files dự kiến

Tạo `backend/app/ai/skills/{__init__,registry,resolver,schemas,routes}.py`, `skills/hangout/SKILL.md`, `skills/learn-new-thing/SKILL.md`; tạo `frontend/src/features/real/composer/{ComposerOptions,PromptChips}.tsx`, `promptOptions.ts`, `promptOptions.test.ts`, `composer.css`. Sửa `backend/app/ai/{schemas,runtime,provider,chat_routes}.py`, `orchestration/workflow.py` chỉ ở lựa chọn direct/continuation, `core/config.py`, `contracts.py`, auth feature view và `main.py`; frontend `RealApp.tsx`, API contracts/generated types, CSS. Tạo tests `backend/tests/test_agent_skills.py`, `test_prompt_options.py`, E2E `frontend/tests/e2e/agent-skills.spec.ts`. Generated contracts là output build, không sửa tay.

## Tasks và kiểm chứng tương lai

### S1 — Registry và instructions tin cậy

**Interfaces:** `SkillRegistry`, `SkillSpec` và capability view ở trên; feature mới `AI_AGENT_SKILLS_ENABLED=false`.

- [x] Failing tests: hai IDs duy nhất, schema khớp file, unknown ID/traversal/symlink/oversize/invalid UTF-8 bị chặn; metadata không tạo arbitrary tool; missing Maps/Web vẫn dùng skill offline.
- [x] Viết hai SKILL.md và registry/startup load/capability route; chỉ public metadata. Test payload skill giả có lệnh thực thi không được chạy hoặc cấp quyền.
- [x] Chạy `uv run --locked pytest tests/test_agent_skills.py -q`; pass, không network. Đây là deliverable độc lập search providers.

### S2 — Resolver và per-turn runtime contract

**Interfaces:** `PromptOptions`, `SkillResolution`, `resolve_skill`, run-local selection; digest/protocol dùng W1.

- [x] Tests manual>auto, phủ định/ambiguous intent, agent hiện tại/active handoff không đổi, Nhật ký mood-analysis constraint, 1skill/2tools/area limits; same ID khác options conflict, cùng options không lặp tool. Kiểm nguồn private không vào search child.
- [x] Nối skill instruction vào đúng direct provider run, không thêm model router, không reconfigure consult children/group/proactive. Backend validate cả manual/auto; tool intersection và preflight không lách quota/checks.
- [x] Chạy `uv run --locked pytest tests/test_prompt_options.py tests/test_agent_skills.py tests/test_orchestration_sdk.py tests/test_v3_review_fixes.py -q`; pass fake, các luồng không chọn skill giữ hành vi cũ.

### S3 — Menu/chip và request snapshot

**Interfaces:** `normalizePromptOptions`, `selectionKey(options)`, composer state cùng request intent hiện có.

- [x] Vitest bảng state: add/replace/remove/dedupe, accepted clear, rejected giữ, unknown giữ snapshot, selection mới không bị clear, agent/thread/New/logout reset. Không lưu selection/location vào browser storage.
- [x] Nối `+`/submenu/chips vào `BotConversation`; payload typed `StartRunInput`; manual search item đọc capability view. Giữ voice/send/stop/IME/focus và500-char draft.
- [x] Chạy `npx.cmd vitest run src/features/real/composer/promptOptions.test.ts`, `npm.cmd run typecheck`; pass. Test keyboard bằng Playwright fixture, không dùng API thật.

### S4 — Journey và rollout riêng

- [ ] Fixture E2E auto/manual hangout/learn, chip xóa sau gửi, search selected một lần, reload/retry/cancel, unsupported account/provider, responsive320/390/768/1280 và keyboard/screen-reader names.
- [x] Chạy `npx.cmd playwright test tests/e2e/agent-skills.spec.ts tests/e2e/search.spec.ts tests/e2e/maps-search.spec.ts` sau khi fixtures đã có; pass offline. Bổ sung assertion Focus/icebreaker/quiz không tự tạo session khi chỉ chọn skill; regression `activities.spec.ts` ở gate chung.
- [ ] Mở skill cohort độc lập Web/Maps; feature off không lộ menu đã chết. Bật search item khi backend protocol3/accounting/provider ready. Không đổi global AI consent hoặc auto bật location.

## Review Focus và acceptance

Skill metadata giả cấp tool → S1 allowlist test; unknown send outcome mất lựa chọn → S3 frozen-snapshot test; đổi thread mang location sang người/agent khác → S3 scope reset; implicit handoff mở thêm dữ liệu → S2 unchanged-agent assertions; menu/subpanel keyboard/mobile → S4 focus/viewport journeys.

Chấp nhận khi hai skill auto/manual đều hoạt động ở agent hiện tại, menu/chip đúng một lượt và tools vẫn bị backend kiểm soát. Privacy/security giữ registry nội bộ, minimized search input và không browser storage. Chi phí: load/resolver/menu không gọi model; workflow chỉ dùng số call hiện có, search thêm usage theo02/03. Failure: unavailable skill không chạy code lạ, thông báo giữ draft và cho bỏ chip; capability fetch lỗi không chặn chat thường. AWS/credential: skill riêng không có credential mới; đưa `AI_AGENT_SKILLS_ENABLED` và cohort vào runtime parameter ở phiên rollout, Web dùng key cũ, Maps cần token theo [07](07-rollout-credentials-and-coverage.md).
