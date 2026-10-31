# Phase 1 — 02. Hợp đồng nhiều bubble (P1.1)

Quyết định nền: [ADR-01](../03-architecture-decisions.md#adr-01--lưu-nhiều-bubble-cho-một-run), [ADR-02](../03-architecture-decisions.md#adr-02--version-và-sequence-của-hội-thoại), [ADR-03](../03-architecture-decisions.md#adr-03--tiến-hóa-giao-thức-sse). Bật bằng `AI_MULTI_MESSAGE_ENABLED` (mặc định `false`); khi tắt, model vẫn nhận `AiOutput` như hiện nay.

## 1. Output có cấu trúc (Pydantic, chỉ trong backend)

```python
# backend/app/ai/schemas.py (đề xuất) — model-facing, KHÔNG phải DTO public
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

MAX_BUBBLES = 4
MAX_BUBBLE_CHARS = 1500
MAX_REPLY_CHARS = 5900   # v1 ghép bằng "\n\n" phải ≤ 6000 ký tự (stream.ts)

class Bubble(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1, max_length=MAX_BUBBLE_CHARS)
    cards: list[Card] = Field(default_factory=list, max_length=3)

    @field_validator("text")
    @classmethod
    def visible(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("bubble must contain visible text")
        return value.strip()

class CompanionReply(BaseModel):
    """Một lượt trả lời = 1..4 bubble. Mặc định 1."""
    model_config = ConfigDict(extra="forbid")
    messages: list[Bubble] = Field(min_length=1, max_length=MAX_BUBBLES)

    @model_validator(mode="after")
    def bounded(self):
        total = sum(len(b.text) for b in self.messages) + 2 * (len(self.messages) - 1)
        if total > MAX_REPLY_CHARS:
            raise ValueError("reply too long")
        if sum(len(b.cards) for b in self.messages) > 3:
            raise ValueError("at most 3 cards per reply")
        texts = [b.text.casefold() for b in self.messages]
        if len(set(texts)) != len(texts):
            raise ValueError("duplicate bubbles")
        return self

class NhipReply(CompanionReply):
    source_entry_ids: list[UUID] = Field(default_factory=list, max_length=5)
```

Quy tắc validate nghiệp vụ chạy **sau** SDK (backend, không phụ thuộc model):

| Quy tắc | Áp dụng | Hậu quả khi vi phạm |
| --- | --- | --- |
| `_no_unreceipted_claim` trên **mọi** bubble (không chỉ `text` ghép) | Mọi bot | Guardrail tripwire → run `failed` / job `skipped(guardrail)` |
| Không link `/self/entry/`, `http(s)://`, `javascript:`, `data:`, `](` | Nhịp journal | `JOURNAL_CITATION_INVALID` (hiện có) |
| Có entry → phải có `source_entry_ids` thuộc evidence | Nhịp journal | Như trên |
| Card chỉ thuộc union `navigate_bot`/`mood_form`/`discovery` | Mọi bot | Pydantic reject |
| Bubble rỗng sau `strip()`/trùng lặp | Mọi bot | Pydantic reject |

Render đặc biệt:

- `MoodAnalysisPlan` → `render_mood_analysis()` vẫn trả **một** `AiOutput` → bọc thành `CompanionReply(messages=[Bubble(...)])` ([evidence.py](../../../../backend/app/ai/evidence.py)).
- `NhipReply` → `render_journal_output()` mở rộng: dòng "Bài viết đã tham khảo: …" do backend thêm vào **bubble cuối**; cắt độ dài theo ngân sách của bubble đó ([ai/journal.py:115-144](../../../../backend/app/ai/journal.py#L115)).

## 2. Hướng dẫn tách bubble (lớp prompt mới, không sửa prompt đã đóng băng)

Thêm vào `conversation_instructions()` (lớp runtime, [prompts.py:128-150](../../../../backend/app/ai/prompts.py#L128)) — nguyên văn tiếng Việt:

```text
Định dạng trả lời: messages là 1 đến 4 tin ngắn như khi nhắn tin. Mặc định dùng 1 tin.
Chỉ tách khi tự nhiên: một câu đón nhận ngắn rồi một ý chính; hoặc một câu hỏi lại tách
khỏi phần trả lời. Không tách danh sách, các bước, một đoạn giải thích liền mạch hay câu
trả lời ngắn. Không lặp nội dung giữa các tin. Card đặt ở tin cuối.
```

## 3. DTO public (API)

`AIMessage` ([schemas.py:59-66](../../../../backend/app/ai/schemas.py#L59)) thêm trường, tất cả có mặc định để tương thích:

| Trường | Kiểu | Mặc định | Ý nghĩa |
| --- | --- | --- | --- |
| `partIndex` | `int` 0–3 | 0 | Vị trí bubble trong run |
| `partCount` | `int` 1–4 | 1 | Tổng bubble của run (tính từ DB, không tin client) |
| `origin` | `"user" \| "proactive"` | `"user"` | Nguồn run (join `ai_runs.origin`) |
| `proactiveSlot` | `"morning" \| "evening" \| null` | `null` | Khung lời hỏi thăm (từ `ai_runs.proactive_slot`) |

Ví dụ `GET /ai/conversations/{id}` (rút gọn):

```json
{
  "conversationId": "33333333-3333-4333-8333-333333333333",
  "botId": "nhip", "version": 9, "persistent": true,
  "messages": [
    {"id": "…01", "actor": "self", "text": "Hôm nay mình hơi uể oải.", "cards": [],
     "runId": "…r1", "status": "completed", "partIndex": 0, "partCount": 1, "origin": "user", "proactiveSlot": null},
    {"id": "…02", "actor": "bot", "text": "Nghe như mấy ngày qua bạn đã gồng khá nhiều.", "cards": [],
     "runId": "…r1", "status": "completed", "partIndex": 0, "partCount": 2, "origin": "user", "proactiveSlot": null},
    {"id": "…03", "actor": "bot", "text": "Tối nay thử tắt màn hình sớm hơn 15 phút xem sao?", "cards": [{"kind": "mood_form"}],
     "runId": "…r1", "status": "completed", "partIndex": 1, "partCount": 2, "origin": "user", "proactiveSlot": null}
  ],
  "activeRunId": null, "activeRunVersion": null, "hasMoreMessages": false
}
```

## 4. SSE

### 4.1 Hai phiên bản

| | `ai-events-v1` (mặc định) | `ai-events-v2` (`GET …/events?protocol=2`) |
| --- | --- | --- |
| Loại event | `progress, final, completed, failed, cancelled` | Như v1 |
| `final.data` | `{text, cards}` — text là các bubble ghép `"\n\n"`, cards nối theo thứ tự | `{messages: [{messageId, partIndex, text, cards}], partCount}` |
| Persistent replay | seq 1 `progress`, 2 `final`, 3 `completed` | Như v1 (`afterSeq ≤ 3`) |
| `progress.data` | `{}` | `{}` ở Phase 1 (Phase 2 thêm trạng thái cộng tác thật) |

Ví dụ v2:

```text
id: 2
event: final
data: {"version":"ai-events-v2","seq":"2","type":"final","data":{"partCount":2,"messages":[{"messageId":"…02","partIndex":0,"text":"Nghe như mấy ngày qua bạn đã gồng khá nhiều.","cards":[]},{"messageId":"…03","partIndex":1,"text":"Tối nay thử tắt màn hình sớm hơn 15 phút xem sao?","cards":[{"kind":"mood_form"}]}]}}

id: 3
event: completed
data: {"version":"ai-events-v2","seq":"3","type":"completed","data":{}}
```

`messageId` có trong v2 để client không cần ID tạm `${runId}-final` và dedupe chính xác sau reconcile. Temporary chat (RAM) dùng UUID sinh lúc publish.

### 4.2 Thay đổi server

- `AIEvent.version: Literal["ai-events-v1","ai-events-v2"]` ([schemas.py:119-123](../../../../backend/app/ai/schemas.py#L119)).
- `durable_run()` lấy **tất cả** row bot của run `ORDER BY part_index` thay vì `scalar()` một row ([chat_routes.py:522-526](../../../../backend/app/ai/chat_routes.py#L522)).
- `events()` dựng `final` theo version yêu cầu ([chat_routes.py:605-631](../../../../backend/app/ai/chat_routes.py#L605)); `LiveRun.events` lưu payload chuẩn hóa dạng v2 và chuyển sang v1 khi phát.
- OpenAPI: `AIEvent` schema xuất cả hai dạng ([main.py:411-422](../../../../backend/app/main.py#L411)).

### 4.3 Thay đổi client

`consumeAIEvents(eventsUrl + "?protocol=2")` trả `ValidatedReply = {messages: ValidatedBubble[]}`. **Lưu ý:** regex chặn URL hiện tại `^/api/v1/ai/runs/[a-zA-Z0-9-]+/events$` ([stream.ts:52](../../../../frontend/src/api/stream.ts#L52)) sẽ từ chối query — phải nới thành `^/api/v1/ai/runs/[a-zA-Z0-9-]+/events(\?protocol=2)?$` và client tự thêm query (server vẫn trả `eventsUrl` không có query). Parser kiểm: `version === "ai-events-v2"`, 1–4 phần tử, `partIndex` 0..n-1 liên tục, text không rỗng, mỗi bubble ≤1.500 ký tự, tổng card ≤ 3, không khóa lạ ([stream.ts:110-121](../../../../frontend/src/api/stream.ts#L110)).

## 5. Lưu trữ (atomic)

Trong transaction cuối của `drive()` ([runtime.py:682-714](../../../../backend/app/ai/runtime.py#L682)):

```python
durable = await owned_conversation(db, c.id, user.id, lock=True)   # FOR UPDATE
base = durable.version
for i, bubble in enumerate(reply.messages):
    db.add(AiMessageRecord(
        conversation_id=c.id, sequence=base + 1 + i, actor="bot",
        part_index=i, part_count=len(reply.messages),
        text=bubble.text, cards=[card.model_dump(mode="json", by_alias=True) for card in bubble.cards],
        run_id=run.id))
durable.version = base + len(reply.messages)
durable.updated_at = now()
# cùng transaction: ai_runs → completed, ai_usage terminal snapshot
```

- Không có trạng thái "đã hiện một phần": hoặc mọi bubble cùng run `completed`, hoặc không bubble nào.
- Hủy (`cancel`) trước commit → không row nào; sau commit → kết quả cuối là `completed` (giữ ngữ nghĩa hiện tại: "terminal outcome is immutable").
- Bộ nhớ RAM (`Conversation.messages`, [store.py](../../../../backend/app/ai/store.py)) append N `AIMessage` cùng lúc rồi `c.version += N`.
- `check_capacity()` tính theo tổng byte của mọi bubble.

## 6. Lịch sử, phân trang, resume

- `conversation_view(limit, before)` vẫn phân trang theo `sequence` ([persistence.py:59-102](../../../../backend/app/ai/persistence.py#L59)). **Bổ sung:** nếu row cũ nhất của trang có `part_index > 0`, nạp thêm các phần còn thiếu cùng `run_id` (tối đa 3 row) để **không cắt nhóm**; `hasMoreMessages` tính sau bổ sung.
- Client nhóm các row **liền kề** có cùng `runId` và `actor="bot"`.
- Reconnect: không đổi — reload trạng thái (`GET conversation`), nếu `activeRunId` còn thì mở lại events; v2 replay chứa đủ bubble.
- Export ([chat_routes.py:710-739](../../../../backend/app/ai/chat_routes.py#L710)) thêm `partIndex`, `partCount`, `origin`, `proactiveSlot`.

## 7. Dựng context cho model

`build_history()` ([context.py:74-94](../../../../backend/app/ai/context.py#L74)) **gộp** các bubble liền kề cùng `run_id` thành một message `assistant` (nối `"\n\n"`) trước khi áp giới hạn 24 tin / 24.000 byte. Lý do: model thấy lượt trả lời trước như một khối, không bị lệch tỷ lệ user/assistant, và giới hạn 24 tin không bị bubble "ăn" mất.

`model_messages()` không đổi logic stamp: mọi bubble cùng run dùng chung stamp `ai_turns`.

## 8. Tin cũ (legacy)

Row trước migration có `part_index=0, part_count=1` (server default) → hiển thị như hiện tại. Không backfill dữ liệu. Không tách lại tin cũ.

## 9. Trình bày, sao chép, accessibility

| Hạng mục | Quy định |
| --- | --- |
| Cấu trúc DOM | Một `div.message-group` (`role="group"`, `aria-label="Tin nhắn từ Nhịp, 2 phần"`) chứa N `.message-content` |
| Hành động | Giờ + "Sao chép" hiện ở **bubble cuối** của nhóm; mỗi bubble vẫn focus được và có "Sao chép" riêng khi focus |
| Live region | Nhóm mới thêm vào được đọc **một lần** (chèn nguyên nhóm trong một lần cập nhật state) |
| Khoảng cách | Trong nhóm 6 px; giữa các lượt giữ khoảng cách hiện tại (baseline: hai tin bot khác run cách nhau như hai lượt, xem [92](../92-visual-qa-and-agent-browser.md)) |
| Motion (tùy chọn) | Theo [DESIGN.md](../../../../DESIGN.md) "animation must never delay content": mọi bubble render **ngay** với layout đầy đủ; hiệu ứng vào chỉ là opacity 0.6→1 + nâng 4 px (GSAP, `power2.out`), lệch 60 ms/bubble, tổng ≤ 220 ms; tắt hoàn toàn với `prefers-reduced-motion`; **không** hiển thị "đang gõ" giữa các bubble vì run đã kết thúc |
| Khung bubble | Tin của trợ lý **không** có khung/nền (DESIGN.md "Don't add assistant bubble frames"); nhóm được nhận biết bằng khoảng cách hẹp và một dòng metadata chung |
| Chọn chữ | Mỗi bubble là một khối chọn riêng; "Sao chép" nhóm không có ở Phase 1 |

## 10. Hết hạn và xóa

Bubble là `ai_messages` thường → xóa hội thoại/hết hạn/xóa tài khoản đi theo đường hiện có (`ON DELETE CASCADE` từ `ai_conversations`, purge `AiRun` khi xóa tài khoản).

## 11. Bảng kiểm tương thích

| Kết hợp | Kết quả mong đợi |
| --- | --- |
| Server mới + client cũ | v1, một bubble ghép; sau reconcile, client cũ hiện N tin riêng |
| Server cũ (chưa migration) + client mới | Client gửi `?protocol=2`, server cũ bỏ qua query → v1; client mới **phải** chấp nhận v1 (fallback parser) |
| `AI_MULTI_MESSAGE_ENABLED=false` | Model dùng `AiOutput`; persist 1 bubble `part_count=1` |
| Image cũ sau migration | Insert không ghi `part_*` → default; đọc bỏ qua cột mới |
