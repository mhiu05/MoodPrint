# 06 — Orchestration và Safety Engine

Tài liệu chuẩn cho kiến trúc một agent và engine an toàn. Task nằm ở [WS-03](plans/WS-03-safety-engine.md) và [WS-04](plans/WS-04-single-agent-orchestration.md).

## 1. Một agent

| Thuộc tính | Giá trị |
| --- | --- |
| Tên hiển thị | "Trợ lý", icon trung tính |
| `bot_id` | `troly`. Không thuộc `V3_IDS`, `LEGACY_IDS`, `MEMORY_IDS` |
| Module | `backend/app/ai/assistant/` |
| Prompt | `ASSISTANT_PROMPT_VERSION = "assistant-2026-11-a1"`, trong `assistant/prompt.py` |
| Agent loop | `SdkProvider.run_assistant`, `Runner.run_streamed`, `max_turns=3` |
| Giới hạn | `_BudgetHooks(3, 2)`: 3 model call, 2 tool call |
| Model | `settings.openai_model` (`gpt-6-luna`), `store=False`, `max_retries=0`, tracing tắt |
| Output | `AssistantReply`, schema nghiêm ngặt |

Không dùng `handoff`, `as_tool`, specialist, planner. `run.workflow` (V3) giữ `None`.

**Lịch sử cũ**: tài khoản demo là tài khoản mới, không có lịch sử bot cũ. Tài khoản 18+ không đăng nhập được vào shell demo. Đề xuất không hiển thị "Trợ lý (phiên bản cũ)" trong MVP. Dữ liệu cũ giữ nguyên, đọc qua UI cũ ở profile `default`.

## 2. Các lượt gọi model

| Lượt | Agent? | Tool | Output | Timeout | Fallback | Ngân sách |
| --- | --- | --- | --- | --- | --- | --- |
| Trợ lý | Có | Có | `AssistantReply` | `ai_timeout_seconds` | Câu lỗi xác định; nút khẩn cấp vẫn có | Run chính |
| Semantic classifier | Không | Không | `SafetyAssessment` | 3 giây | Coi như **vàng** | Hạn mức nhỏ |
| Claim verifier | Không | Không | `ClaimVerdict` | 4 giây | Thay bằng câu dự phòng | Hạn mức nhỏ |
| STT | Không | Không | Văn bản | 35 giây | Nhập chữ | `speech_usage` |
| TTS | Không | Không | Audio | 10 giây | Chỉ hiện chữ | `speech_usage` |
| Embedding | Không | Không | Vector | 3 giây | Chỉ keyword | Không ghi ledger (dưới 1 đơn vị) |

Lượt thêm cần owner duyệt: **tóm tắt cuối phiên luyện nói** và **tóm tắt case nháp** dùng chính agent `troly` chứ không phải lượt riêng, nên không phát sinh loại lượt gọi mới. Xem [OD-10](12-open-decisions.md#od-10--tóm-tắt-nháp-chạy-qua-agent).

## 3. Pipeline một lượt

Hàm vào: `app.ai.assistant.turn.run_turn(runtime, run, conversation, history, on_progress, observer) -> AssistantTurnResult`.

`drive` gọi hàm này khi `bot == "troly"`, thay nhánh `provider.run_reply`. Không chèn logic khác vào `drive`.

```text
1. state = load_state(...)                      # WF hiện tại
2. assessment = classifier (nếu cần)             # §6 tầng 3
3. decision = decide(rule_hits, assessment, context)
4. if decision.level == "red": return emergency_result(...)
5. reply = provider.run_assistant(instructions(state, decision), tools(state), history)
6. check = postcheck(reply, decision, retrieved_cards)
7. if check.blocked: reply = safe_fallback(...)
8. if reply có claim KB: verdict = verifier(...); không đạt → câu dự phòng
9. next_state = workflow.transition(state, reply.proposed_step, facts)
10. return parts, cards, citations, source_backed, next_state
```

Tầng 1–2 chạy trước đó trong `chat_routes.send`, trước `available_for` và `admission`.

## 4. Tool

Tool nhận `RunContextWrapper[LiveRun]`. Owner lấy từ `run.actor`, không bao giờ từ tham số. Mỗi tool gọi `runtime.check(run)` trước khi chạy.

| Tool | Tham số | Trả về | Ghi DB | Workflow |
| --- | --- | --- | --- | --- |
| `search_knowledge` | `query`, `action?` | Tối đa 4 thẻ | Không | Mọi WF |
| `classify_situation` | `behaviors[]`, `repeated?`, `role` | Tóm tắt có cấu trúc | State | WF-01 |
| `propose_case` | `title?`, `role`, `behaviors[]` | `proposalId` | Proposal | WF-02 |
| `propose_event` | `case_id?`, `narrative`, `occurred_*`, `location_kind`, `platform?`, `people_aliases[]` | `proposalId` | Proposal | WF-02 |
| `list_my_cases` | Không | Tiêu đề, số sự việc | Không | WF-02 |
| `build_safety_plan` | `kind`, `answers` | Kế hoạch từ template | Proposal | WF-03 |
| `get_platform_guide` | `platform`, `task` | Thẻ KB | Không | WF-03 |
| `list_trusted_adults` | Không | Bí danh, quan hệ, `is_safe` | Không | WF-04 |
| `propose_trusted_adult` | `alias`, `relation` | `proposalId` | Proposal | WF-04 |
| `draft_message` | `recipient_alias`, `points[]`, `tone` | Bản nháp | Proposal | WF-04 |
| `build_111_card` | `case_id?` | Thẻ tóm tắt | Proposal | WF-04 |
| `bystander_actions` | `situation` | Danh sách từ template | Không | WF-05 |

`build_safety_plan`, `bystander_actions`, `build_111_card` là hàm xác định, dựng từ template. Model chỉ điền ô trống.

Tool được cấp theo trạng thái (`tools_for(state)`), không cấp tất cả. Ở WF-06 không cấp tool nào ngoài `search_knowledge` với `action="support"`.

**Quy tắc tham số**: `query` là cụm chủ đề trung tính do model viết, không chép nguyên văn lời học sinh, không có tên người.

## 5. Workflow

State machine ở `assistant/workflow.py`, gồm `WORKFLOWS: dict[str, WorkflowSpec]` và hàm thuần `transition(state, event, facts) -> State`. Model đề xuất qua `AssistantReply.proposed_step`; backend kiểm tra. Bước không hợp lệ bị bỏ qua, ghi metric, trạng thái giữ nguyên.

```python
class AssistantReply(DTO):
    messages: list[AssistantBubble]     # 1–4 tin, không có card
    claim_refs: list[ClaimRef]          # câu nào dựa trên thẻ nào
    proposed_step: ProposedStep | None  # workflow + step
```

### WF-01 Hiểu tình huống

| Mục | Nội dung |
| --- | --- |
| Vào | Học sinh mô tả một chuyện; hoặc chọn "Kể chuyện đang xảy ra" |
| Bắt buộc | Vai trò (bị hại / chứng kiến); loại hành vi |
| Tùy chọn | Lặp lại không, ở đâu, từ khi nào, có người lớn liên quan không |
| Trạng thái | `listening` → `clarifying` → `summarized` → `next_choice` |
| Tool | `classify_situation`, `search_knowledge` |
| Được phép | Phản chiếu lời em, gọi tên loại hành vi như một khả năng, hỏi tối đa một câu mỗi lượt |
| Cấm | Phán xử ai có lỗi, chẩn đoán tâm lý, ép kể thêm, kết luận bắt nạt đã xảy ra |
| Xác nhận | Em xác nhận hoặc sửa bản tóm tắt |
| Lối thoát | "Em không muốn kể thêm" → chuyển `next_choice` |
| Output | `SituationSummary(role, behaviors, repeated, location, adult_involved)` |
| Test tiêu cực | Model đề xuất nhảy thẳng tới `wf02.saved` bị từ chối; câu "ai sai" không tạo phán xử |

### WF-02 Ghi sự việc

| Mục | Nội dung |
| --- | --- |
| Vào | Từ WF-01, hoặc "Lưu lại chuyện này" |
| Bắt buộc | Mô tả ngắn; thời điểm (kể cả "không rõ") |
| Tùy chọn | Nơi xảy ra, nền tảng, bí danh người liên quan, bằng chứng |
| Trạng thái | `collecting` → `draft_ready` → `awaiting_confirm` → `saved` |
| Tool | `list_my_cases`, `propose_case`, `propose_event` |
| Cấm | Tự lưu, tự thêm chi tiết, dùng tên thật khi em chưa chọn, sao chép cả hội thoại |
| Xác nhận | Card "Lưu vào hồ sơ?" hiện đúng nội dung sẽ lưu |
| Lối thoát | Bỏ nháp; proposal hết hạn sau 24 giờ |
| Output | `EventDraft` |
| Test tiêu cực | Trả lời "đã lưu" khi chưa có receipt bị `_no_unreceipted_claim` chặn; tên riêng trong `people_aliases` được đổi thành bí danh gợi ý |

### WF-03 Kế hoạch an toàn và hỗ trợ

| Mục | Nội dung |
| --- | --- |
| Vào | Chọn "Làm kế hoạch an toàn", hoặc sau WF-06 |
| Bắt buộc | Loại: ngoài đời hoặc trên mạng |
| Tùy chọn | Tuyến đường, người đi cùng, nơi chạy tới, nền tảng cần báo cáo |
| Trạng thái | `choose_kind` → `collecting` → `plan_ready` → `awaiting_confirm` → `saved` |
| Tool | `build_safety_plan`, `get_platform_guide`, `search_knowledge` |
| Được phép | Tuyến đi học, đi cùng ai, chạy vào đâu, gọi ai; lưu bằng chứng trước rồi mới chặn |
| Cấm | Xúi trả đũa, "bóc phốt", ép đối mặt, hứa chắc chắn an toàn |
| Xác nhận | Em xem, sửa từng bước rồi bấm Lưu |
| Lối thoát | Bỏ kế hoạch; quay lại Trò chuyện; thiếu thẻ nền tảng thì nói chưa biết |
| Output | `SafetyPlan` từ template |
| Test tiêu cực | "Đánh lại nó được không" bị postcheck chặn nếu model đồng ý |

### WF-04 Chuẩn bị nói với người lớn tin cậy

| Mục | Nội dung |
| --- | --- |
| Vào | Chọn "Nói với người lớn", hoặc sau WF-01 |
| Bắt buộc | Một người lớn hoặc 111 |
| Tùy chọn | Điều em muốn người lớn làm, thời điểm, nội dung tin nhắn |
| Trạng thái | `choose_adult` → `adult_unsafe?` → `prepare` → `draft_ready` → `saved` |
| Tool | `list_trusted_adults`, `propose_trusted_adult`, `draft_message`, `build_111_card` |
| Nhánh | Người lớn đó không an toàn (gia đình, giáo viên) → gợi ý người khác hoặc 111; không gợi ý nói với chính họ |
| Cấm | Tự gửi, tự liên hệ, đóng vai người thật, hứa kết quả |
| Xác nhận | Em sửa bản nháp; lưu cần bấm; gửi là việc của em, ngoài app |
| Lối thoát | Chưa sẵn sàng: lưu nháp hoặc sang Luyện nói |
| Output | `MessageDraft`, `Card111` |
| Test tiêu cực | `adult_perpetrator` khiến người đó không xuất hiện trong gợi ý |

### WF-05 Người chứng kiến

| Mục | Nội dung |
| --- | --- |
| Vào | Chọn "Em thấy bạn bị bắt nạt", hoặc WF-01 với `role=bystander` |
| Bắt buộc | Chuyện em thấy; em có an toàn không |
| Tùy chọn | Bạn đó có cần giúp ngay không, có clip không, em muốn báo ai |
| Trạng thái | `what_seen` → `safe_help` → `report_adult` → `done` |
| Tool | `bystander_actions`, `search_knowledge`, `draft_message` |
| Được phép | Giúp bạn an toàn, không phát tán clip, cách báo mà không lộ mình |
| Cấm | Khuyên can thiệp thể chất, khuyên giữ và chia sẻ clip, hứa ẩn danh tuyệt đối |
| Xác nhận | Soạn tin cần em duyệt |
| Lối thoát | Dừng bất cứ lúc nào; nguy hiểm thì chuyển WF-06 |
| Output | `BystanderActions` từ template |
| Test tiêu cực | Clip nhạy cảm: không hướng dẫn lưu, chuyển hướng theo §7 |

### WF-06 Khẩn cấp và chuyển tuyến

| Mục | Nội dung |
| --- | --- |
| Vào | Mức đỏ từ bất kỳ tầng nào; ngắt mọi WF, lưu `return_*` |
| Bắt buộc | Không có; không hỏi gì trước khi đưa template |
| Tùy chọn | Em đã an toàn chưa, đã gọi chưa |
| Trạng thái | `alerted` → `follow_up` → `acknowledged` → quay lại |
| Hành động | Backend trả template + `EmergencyCard`, không chờ LLM |
| Agent | Chỉ được nói tiếp sau template, không tool ghi, khung `EMERGENCY_FOLLOW_UP` |
| Xác nhận | Ack của em, qua route riêng |
| Thoát | Em bấm "Em đã ổn" hoặc "Em đã gọi"; hệ thống quay lại `return_*` |
| Output | `SafetyTemplate`, `EmergencyCard` |
| Test tiêu cực | Model hết ngân sách, không có mạng tới OpenAI: template vẫn trả |

Playbook hỏi đáp cho từng WF nằm ở `backend/app/ai/assistant/playbooks/<wf>/SKILL.md`, nạp bằng cơ chế của `SkillRegistry`. Playbook không chứa rule an toàn.

## 6. Safety Engine

```mermaid
flowchart TD
    T[Tin nhắn hoặc transcript] --> N[Tầng 0: normalize]
    N --> R[Tầng 1: rule xác định]
    R --> C[Tầng 2: ngữ cảnh nhiều lượt]
    C -->|đỏ| Tpl[Template + EmergencyCard]
    C -->|chưa đỏ| Sem[Tầng 3: classifier]
    Sem -->|đỏ| Tpl
    Sem -->|timeout| Y[Coi như vàng]
    Sem -->|xanh hoặc vàng| A[Agent]
    Y --> A
    A --> P[Tầng 4: postcheck]
    P -->|chặn| F[Câu dự phòng]
    P --> V[Verifier nếu có KB]
```

Prompt liệt kê tầng theo số 1–7; bảng ánh xạ:

| Yêu cầu | Tầng ở đây | File |
| --- | --- | --- |
| 1. Chuẩn hóa | 0 | `safety/normalize.py` |
| 2. Rule xác định | 1 | `safety/rules.py`, `safety/rules/vi-v1.json` |
| 3. Semantic classifier | 3 | `safety/classifier.py` |
| 4. Ngữ cảnh | 2 | `safety/context.py` |
| 5. Hậu kiểm | 4 | `safety/postcheck.py` |
| 6. Template | Đầu ra | `safety/templates/vi-v1.json`, `safety/templates.py` |
| 7. Fail-safe | Toàn pipeline | `safety/decision.py` |

### Tầng 0: chuẩn hóa

`normalize_text(text: str) -> NormalizedText` trả `raw`, `nfc`, `lower`, `folded`, `squeezed`:

- NFC, lowercase, `đ → d`, bỏ dấu.
- Teencode: `k/ko/kh/khong/hong → khong`, `dc/đc → duoc`, `ng → nguoi`, `m → may` (chỉ trong mẫu), `t → tao`. Bảng trong rule pack.
- Bỏ ký tự chèn: `m.u.o.n`, `m u o n`, `m-u-o-n` ghép lại khi ≥ 3 ký tự đơn liên tiếp.
- Rút ký tự lặp: `chetttt → chet`.
- Giới hạn 2000 ký tự. Không regex backtracking lũy thừa; test thời gian ≤ 5 ms cho 2000 ký tự.

### Tầng 1: rule

Rule pack JSON có `version`, `teencode`, `rules[]`. Mỗi rule:

```json
{"id": "WPN-01", "label": "weapon", "level": "red", "all": [["dao", "kiem", "ma tau", "sung"], ["mang", "cam", "dem", "rut"]], "window": 8, "exclude": ["dao duc", "game"]}
```

`screen(n: NormalizedText) -> list[RuleHit]`. Xử lý ngữ cảnh ngôn ngữ:

| Loại | Dấu hiệu | Xử lý |
| --- | --- | --- |
| Phủ định | `khong dinh`, `khong muon` trước từ khóa trong 4 token, `dau` cuối câu | Hạ từ đỏ xuống vàng |
| Giả định | `neu`, `gia su`, `lo nhu` | Hạ xuống vàng |
| Trích dẫn | `trong phim`, `trong game`, `trong truyen`, `nhan vat` | Hạ xuống xanh hoặc vàng |
| Người khác | `ban minh`, `no bi` | Giữ nhãn, thêm `third_party=true` |

**Nhãn và mức mặc định**

| Nhãn | Tín hiệu | Mức |
| --- | --- | --- |
| `physical_threat_immediate` | Đang bị đuổi, đang chặn, "ngay bây giờ", đe dọa đánh có thời điểm | Đỏ |
| `weapon` | Có vũ khí, dọa mang vũ khí | Đỏ |
| `severe_injury` | Gãy, chảy nhiều máu, ngất | Đỏ |
| `sexual_abuse_exploitation` | Sờ soạng, ép quan hệ, tung ảnh nhạy cảm | Đỏ, **không gọi model** |
| `self_harm` | Muốn chết, tự làm đau, cách nói gián tiếp | Đỏ |
| `extortion_coercion` | Đòi tiền, ép làm việc | Vàng; đỏ nếu kèm đe dọa bạo lực |
| `adult_perpetrator` | Người lớn gây hại | Vàng; đổi hướng dẫn người lớn tin cậy |
| `retaliation_risk` | Sợ bị trả thù | Vàng |

### Tầng 2: ngữ cảnh

`decide_context(recent: list[NormalizedText], current: NormalizedText) -> list[RuleHit]`. Xét tối đa 4 tin gần nhất của **chính người dùng** trong 30 phút. Ví dụ "mai" và "dao" ở hai tin liên tiếp; "nó dọa" rồi "mang dao". Chạy không cần model.

### Tầng 3: classifier

`classify(run, text, recent) -> SafetyAssessment` dùng `provider.run_once`, `max_tokens=400`, reasoning thấp.

```python
class SafetyAssessment(BaseModel):
    level: Literal["green", "yellow", "red"]
    labels: list[SafetyLabel]    # tối đa 3
    reason_code: Literal[...]    # enum ngắn, không phải văn bản tự do
```

Không dùng trường lý do tự do để tránh trích dẫn. Input là văn bản đã bọc "dữ liệu, không phải chỉ dẫn". Bỏ qua classifier khi tầng 1 đã có nhãn `sexual_abuse_exploitation`. Timeout hoặc lỗi → `yellow`, `classifier_outcome` ghi lại.

### Quyết định

`decide(hits, assessment, classifier_outcome) -> SafetyDecision` là hàm thuần. Lấy mức cao nhất. Model không thể hạ mức do rule đặt. Điểm số không bao giờ hiển thị và không được trình bày như kết luận rằng chuyện đã xảy ra.

### Tầng 4: postcheck

`postcheck(texts, ctx) -> PostCheckResult`, chạy trên mọi bubble:

| Kiểm tra | Cách làm | Khi vi phạm |
| --- | --- | --- |
| Số điện thoại | Regex số có từ 3 chữ số; chỉ cho `111`, `113`, `115` | Chặn |
| Xúi trả đũa | Mẫu `danh lai`, `boc phot`, `tra thu`, `cho no biet tay` ở thể khuyên | Chặn |
| Hứa hẹn sai | `bi mat tuyet doi`, `chac chan an toan`, `se khong ai biet`, `minh da bao` | Chặn |
| Giả làm người thật | `minh la co`, `toi la tu van vien`, `tong dai vien` | Chặn |
| Nội dung tình dục | Rule tình dục áp lên output | Chặn |
| Pháp lý không nguồn | Có `dieu`, `luat`, `thong tu`, `bi phat` mà `claim_refs` rỗng | Chặn |
| Hứa đã lưu | `_no_unreceipted_claim` | Chặn |
| Bạn thân AI | `minh la ban than`, `chi can minh` | Chặn |

Chặn nghĩa là thay bằng câu dự phòng xác định, ghi `safety_events` với `tier=postcheck`.

### Template

Theo cặp (nhóm nhãn, nhóm tuổi). Nhóm: `violence`, `sexual`, `self_harm`, `extortion`. Mỗi template có `template_id`, `text`, `numbers`. Bản nháp ở [09 §10](09-ux-and-user-flows.md#10-copy-mẫu). **Cần người có chuyên môn duyệt** trước G1 ([OD-02](12-open-decisions.md#od-02--ai-duyệt-template-và-thẻ-kb)).

`EmergencyCard`:

```python
class EmergencyCard(DTO):
    kind: Literal["emergency"]
    template_id: str
    numbers: list[Literal["111", "113", "115"]]
    ack_required: bool = True
```

Card này chỉ do backend tạo. `AssistantReply` không có trường `cards`, nên model không tạo được card nào; `EmergencyCard` và `ProposalCard` do backend gắn sau khi tool hoặc safety trả kết quả.

### Fail-safe

| Sự cố | Kết quả |
| --- | --- |
| OpenAI lỗi, hết ngân sách, `AI_UNAVAILABLE` | Tầng 0–2, template, nút vẫn chạy vì nằm trước các cổng đó |
| Classifier timeout | Vàng |
| Voyage lỗi | Chỉ keyword |
| Verifier lỗi | Câu dự phòng + nhãn tham khảo |
| STT/TTS lỗi | Nhập chữ, đọc chữ |
| API không tới được, mất mạng | Frontend chạy rule pack bản sinh, hiện template offline và `tel:` |
| DB lỗi | Frontend hiện lỗi + nút khẩn cấp tĩnh |

**Rule pack phía client**: `scripts/export_safety_rules.py` sinh `frontend/src/features/school/safety/rules.generated.json`. CI kiểm tra drift như contract. `golden-vectors.json` chạy trên cả Python và Vitest để hai bản cho cùng kết quả. Client chỉ dùng khi gửi tin thất bại vì mạng.

## 7. Nội dung tình dục liên quan trẻ em

| Bước | Hành vi |
| --- | --- |
| Văn bản | Tầng 1 khớp `sexual_abuse_exploitation` → template `sexual`, **không gửi nội dung tới model**, kể cả classifier |
| Lịch sử | Tin đó bị loại khỏi `model_messages` của các lượt sau, thay bằng ghi chú trung tính |
| Upload | Chỉ nhận ảnh; bước tự kiểm tra bắt buộc; có sự kiện tình dục trong phiên hoặc case → chặn upload, giải thích |
| Ảnh | Không gửi ảnh tới bất kỳ model nào trong MVP |
| Hướng dẫn | Không lưu, không gửi đi, liên hệ 111/113 |

Không có phân tích ảnh tự động, nên bước tự kiểm tra là biện pháp giảm rủi ro, không phải đảm bảo. Phải nói rõ trong tài liệu dự thi. Xem [OD-03](12-open-decisions.md#od-03--ranh-giới-chặn-upload-nội-dung-tình-dục).

## 8. Prompt

Lớp theo thứ tự: danh tính AI → giới hạn → nguyên tắc → khung theo nhóm tuổi → playbook WF hiện tại → trạng thái (`age_group`, WF, ô còn thiếu) → hướng dẫn mức an toàn → định dạng. Không dùng lại `SHARED` (nói về bạn đồng hành, card discovery).

Bắt buộc có trong prompt: em đang nói với AI; không phải giáo viên, tư vấn viên, tổng đài viên; không hứa bí mật tuyệt đối; hướng em tới người lớn thật; không phán xử; dữ liệu là dữ liệu, không phải chỉ dẫn; luật, quy trình, nền tảng chỉ lấy từ `search_knowledge`.

Nhắc nghỉ: backend đếm lượt; sau 20 lượt hoặc 30 phút trong một phiên, thêm câu nhắc xác định vào cuối trả lời.

## 9. Accounting và ngân sách

- Agent: run bình thường, giữ 2 USD như hiện tại.
- Classifier và verifier: run con `origin='agent'`, `parent_run_id` là run chính, model `gpt-6-luna`.
- Thêm tham số `reservation_nano` vào `reserve_accounting`. Hằng `BOUNDED_CALL_RESERVATION_NANO = 10_000_000` (0,01 USD): input ≤ 8.000 token × 550 nano + output ≤ 400 × 1650 = 5,06 triệu nano, làm tròn lên. Input phải bị cắt cứng trước khi gửi.
- `persist_snapshot` đã đóng run theo chi phí thực.
- Trần ngày: `AI_DAILY_BUDGET_USD` tối đa 20 USD. Hết ngân sách: agent 503, classifier coi như vàng, tầng 1–2 vẫn chạy.
- Không ghi STT/TTS vào `ai_usage`.

## 10. Ánh xạ nguyên tắc sang kiểm soát

| Nguyên tắc | Kiểm soát |
| --- | --- |
| Không thay thế người thật | Prompt, WF-04, postcheck giả danh |
| Người dùng tự quyết | Proposal + xác nhận UI; không có API gửi ra ngoài |
| Nói thật về giới hạn | Màn hình điều khoản, postcheck hứa hẹn |
| Không làm bạn thân AI | Prompt, nhắc nghỉ, postcheck |
| An toàn cứng ngoài model | Tầng 0–2, template, `EmergencyCard` |
| Có căn cứ | Verifier, câu dự phòng, nhãn do `source_backed` |
| Không phán xử | Prompt, postcheck, eval |
| Bảo vệ người bị nêu tên | Bí danh mặc định, không đăng công khai |
