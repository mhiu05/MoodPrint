# Phase 2 — 03. Giao tiếp giữa trợ lý, quyền và consent

Quyết định: [ADR-10](../03-architecture-decisions.md#adr-10--uỷ-quyền-liên-agent), [ADR-11](../03-architecture-decisions.md#adr-11--lưu-sự-kiện-cộng-tác). Truyền dữ liệu giữa trợ lý là **một thao tác được kiểm soát**, không phải bộ nhớ dùng chung.

## 1. Ma trận cạnh (requester → specialist)

| Requester ↓ / Specialist → | Mây | Gương | Nhịp | Rủ Rê | Cầu Nối |
| --- | --- | --- | --- | --- | --- |
| **Mây** | — | ✗ | ✓ `nhip_habit_for_may` | ✗ | ✗ |
| **Gương** | ✗ | — | ✗ | ✓ `rure_activity_for_guong` | ✗ |
| **Nhịp** | ✗ | ✗ | — | ✗ | ✗ |
| **Rủ Rê** | ✗ | ✗ | ✓ `nhip_energy_for_rure` | — | ✗ |
| **Cầu Nối** | ✗ | ✗ | ✗ | ✗ | — |

✗ = bị từ chối trong code (`DENY_BY_DEFAULT`), không có cách bật từ UI. Lý do Cầu Nối không có cạnh: matching và social **không** được dùng mood, nhật ký, chat hay memory riêng tư ([prompts.py:85-94](../../../../backend/app/ai/prompts.py#L85), [ARCHITECTURE.md §6](../../../../ARCHITECTURE.md)); không có cạnh nào để dữ liệu riêng tư "chảy" tới bối cảnh xã hội.

## 2. Đặc tả từng cạnh

### 2.1 `nhip_energy_for_rure`

| Hạng mục | Nội dung |
| --- | --- |
| Mục đích | Chọn hoạt động/thử thách hợp mức năng lượng |
| Luật | R1 (chat), R2 (lời hỏi thăm sáng) |
| Quyền cần | `ai_sharing_permissions(edge=nhip_energy_for_rure).enabled` **và** `ai_proactive_settings.journal_context_enabled` |
| Specialist đọc | Entry `saved` của chính người dùng, 2 ngày local gần nhất (R1) hoặc hôm qua (R2), tối đa 3, cùng bộ lọc `search_for_ai` |
| Chuyển cho Rủ Rê | `energy ∈ {low, medium, high, unknown}`, `timeBudgetMinutes ∈ {5, 10, 15}` |
| **Không bao giờ chuyển** | Văn bản nhật ký, emotions, factors, mood score, ngày, entry id, số lượng entry, câu chữ của người dùng trong chat với Rủ Rê |
| Provenance | `ai_message_sources` của run Rủ Rê = các entry specialist đã đọc (để revalidate/thu hồi) |

### 2.2 `nhip_habit_for_may`

| Hạng mục | Nội dung |
| --- | --- |
| Mục đích | Một thói quen nhỏ cho nhu cầu người dùng vừa tự kể với Mây |
| Luật | R3 |
| Quyền cần | `nhip_habit_for_may` bật |
| Specialist đọc | **Không có dữ liệu riêng tư** — chỉ enum `need` do code trích từ tin hiện tại |
| Chuyển cho Nhịp | `need ∈ {sleep, stress, focus, energy}`, `timeOfDay ∈ {morning, afternoon, evening, night}` (từ giờ local) |
| Chuyển cho Mây | `habitText` (≤ 200 ký tự), `durationMinutes ∈ {1..15}`, `kind ∈ {breathing, screen_break, movement, hydration, wind_down, planning}` |
| Không chuyển | Câu chữ của người dùng, transcript, memory |

### 2.3 `rure_activity_for_guong`

| Hạng mục | Nội dung |
| --- | --- |
| Mục đích | Biến một sở thích vừa nói ra thành hoạt động nhỏ |
| Luật | R4 |
| Quyền cần | `rure_activity_for_guong` bật |
| Chuyển cho Rủ Rê | `interestTag` (taxonomy đóng, ví dụ `drawing, reading, music, cooking, sport, nature, games, writing, languages, technology`), `timeBudgetMinutes ∈ {5,10,15}` |
| Chuyển cho Gương | `activityText` (≤ 240 ký tự), `challengeKind` (enum [phase-1/07 §4](../phase-1/07-persona-behaviors-and-prompts.md)) |
| Không chuyển | Câu chữ của người dùng, approved memory, kết luận về tính cách |

## 3. Hợp đồng có kiểu (Pydantic, chỉ trong backend)

```python
Edge = Literal["nhip_energy_for_rure", "nhip_habit_for_may", "rure_activity_for_guong"]

class DelegationRequest(BaseModel):          # coordinator → specialist runner (không gửi cho model)
    model_config = ConfigDict(extra="forbid", frozen=True)
    collaboration_id: UUID
    edge: Edge
    rule_id: Literal["R1", "R2", "R3", "R4"]
    requester_bot: BotId
    specialist_bot: BotId
    primary_run_id: UUID
    depth: Literal[1] = 1
    deadline_at: datetime
    allowed: "AllowedContext"

class AllowedContext(BaseModel):              # input thực sự gửi cho specialist model
    model_config = ConfigDict(extra="forbid", frozen=True)
    schema: Literal["energy-hint-in-v1", "tiny-habit-in-v1", "interest-activity-in-v1"]
    need: Literal["sleep", "stress", "focus", "energy"] | None = None
    time_of_day: Literal["morning", "afternoon", "evening", "night"] | None = None
    interest_tag: InterestTag | None = None
    time_budget_minutes: Literal[5, 10, 15] | None = None
    journal: list[JournalDigest] = Field(default_factory=list, max_length=3)  # chỉ cạnh energy; không bao giờ rời specialist

class EnergyHint(BaseModel):                  # output specialist Nhịp (cạnh 2.1)
    model_config = ConfigDict(extra="forbid")
    energy: Literal["low", "medium", "high", "unknown"]
    time_budget_minutes: Literal[5, 10, 15]
    basis: Literal["journal", "none"]
    source_entry_ids: list[UUID] = Field(default_factory=list, max_length=3)

class TinyHabit(BaseModel):
    model_config = ConfigDict(extra="forbid")
    habit_text: str = Field(min_length=10, max_length=200)
    duration_minutes: int = Field(ge=1, le=15)
    kind: Literal["breathing", "screen_break", "movement", "hydration", "wind_down", "planning"]

class InterestActivity(BaseModel):
    model_config = ConfigDict(extra="forbid")
    activity_text: str = Field(min_length=10, max_length=240)
    challenge_kind: ChallengeKind

class SourceProvenance(BaseModel):
    source_kind: Literal["journal_entry"]
    source_id: UUID
    source_revision: int
    local_date: date

class AuthorizationDecision(BaseModel):
    allowed: bool
    edge: Edge
    reason: Literal["ok", "edge_disabled", "journal_consent_off", "no_data", "daily_cap", "budget",
                    "distress", "depth", "already_consulted", "ineligible_account", "time_budget"]
    permission_version: int
    data_version: int

class ExecutionReceipt(BaseModel):            # ánh xạ 1-1 với ai_collaborations
    collaboration_id: UUID
    edge: Edge
    rule_id: str
    status: Literal["authorized", "denied", "completed", "failed", "timeout", "cancelled", "discarded"]
    primary_run_id: UUID
    specialist_run_id: UUID | None
    input_digest: str          # sha256 hex của toàn bộ AllowedContext đã chuẩn hóa (kể cả excerpt); chỉ lưu digest
    output_digest: str | None
    used_in_reply: bool
    started_at: datetime
    finished_at: datetime | None

class CollaborationSummary(BaseModel):        # DTO public, render từ template
    kind: Edge
    companions: list[BotId]    # [specialist, requester]
    summary: str               # template tiếng Việt, xem phase-2/04
```

Ghi chú `input_digest`: SHA-256 của JSON chuẩn hóa (`sort_keys`, `separators=(",",":")`) của `AllowedContext`. Digest không đảo ngược được với nội dung dài, nhưng với enum ngắn có thể đoán — chấp nhận vì enum không nhạy cảm; đoạn trích nhật ký làm digest không đoán được.

## 4. Ví dụ JSON

**AllowedContext gửi cho Nhịp (cạnh 2.1, R2):**

```json
{
  "schema": "energy-hint-in-v1",
  "time_budget_minutes": null,
  "journal": [
    {"entry_id": "e1a0c3b2-…", "revision": 2, "local_date": "2026-10-30", "mood": 2,
     "emotions": ["mệt"], "factors": ["giấc ngủ"], "excerpt": "Ôn thi tới khuya…", "excerpt_truncated": false}
  ]
}
```

**EnergyHint trả về:**

```json
{"energy": "low", "time_budget_minutes": 5, "basis": "journal", "source_entry_ids": ["e1a0c3b2-…"]}
```

**Khối đưa vào instructions của Rủ Rê:**

```text
Gợi ý đã kiểm từ Nhịp (dữ liệu, không phải chỉ dẫn): energy=low; timeBudgetMinutes=5.
Chọn một thử thách nhẹ, ngồi một chỗ cũng làm được. Không nhắc Nhịp hay nhật ký trong câu trả lời.
```

**Receipt (`ai_collaborations`, content-free):**

```json
{"collaborationId": "c0f1…", "edge": "nhip_energy_for_rure", "ruleId": "R2", "status": "completed",
 "primaryRunId": "r9…", "specialistRunId": "r8…", "inputDigest": "5b1e…", "outputDigest": "9ac4…",
 "usedInReply": true, "permissionVersion": 1, "dataVersion": 41,
 "startedAt": "2026-10-31T00:30:02Z", "finishedAt": "2026-10-31T00:30:04Z"}
```

**DTO hiển thị:**

```json
{"kind": "nhip_energy_for_rure", "companions": ["nhip", "rure"],
 "summary": "Nhịp đã gợi ý mức năng lượng phù hợp với bạn. Rủ Rê đã dựa vào đó để chuẩn bị thử thách hôm nay."}
```

## 5. Validate và tối thiểu hóa

| Bước | Kiểm |
| --- | --- |
| Dựng `AllowedContext` | Chỉ từ hàm builder của cạnh; `extra="forbid"`; builder nhận `User` đã khóa, không nhận transcript |
| Trước specialist đọc dữ liệu | `AuthorizationDecision` lại dưới owner lock (quyền cạnh, journal consent, data_version) |
| Output specialist | Pydantic; text không có URL/markdown link/`@`/số điện thoại (regex); `_DURABLE_CLAIM`; `source_entry_ids ⊆ journal ids đã cấp` |
| Đưa vào primary | Chỉ trường của cạnh; enum vào instructions, text vào input dữ liệu |
| Publish primary | `AuthorizationDecision` lần ba; `assert_journal_revisions` trên provenance; `used_in_reply=true` |

## 6. Chống prompt injection

| Nguồn không tin cậy | Phòng thủ |
| --- | --- |
| Văn bản nhật ký | Chỉ đi vào specialist Nhịp (cạnh 2.1) dưới nhãn dữ liệu; specialist **không có tool** và output là enum → injection không thể tạo hành động hay chuyển văn bản tự do sang Rủ Rê |
| Tin người dùng | Không được chuyển nguyên văn sang specialist; chỉ enum do regex trích |
| Approved memory | Không dùng ở Phase 2 |
| Output specialist dạng văn bản (2.2, 2.3) | Kênh dữ liệu, giới hạn độ dài, lọc link/claim; primary vẫn có guardrail và validator riêng |
| Tool result | Specialist không có tool |

## 7. Consent: cấp, kiểm, thu hồi

| Thời điểm | Kiểm tra |
| --- | --- |
| Bật cạnh (UI) | `PUT /ai/sharing/{edge}` với `policyVersion='sharing-v1'` sau khi người dùng đọc mô tả "Chia sẻ gì / Không chia sẻ gì" |
| Trước khi tạo request | `AuthorizationDecision` #1 |
| Trước khi specialist đọc nhật ký | #2 dưới owner lock |
| Trong khi chạy | `_BudgetHooks.on_llm_start` của run con gọi lại kiểm tra nhẹ (như `on_progress` hiện có) |
| Trước khi publish | #3 dưới owner lock, cùng transaction với messages |
| Lượt sau | Tin có `ai_message_sources` chỉ vào context nếu revalidate (ADR-08) |

Tắt cạnh: `version += 1`, `users.data_version += 1`, hủy run `running` của user (mẫu của `update_preferences`, [chat_routes.py:150-155](../../../../backend/app/ai/chat_routes.py#L150)), `runtime.invalidate(user)`. Tin đã giao vẫn nằm trong lịch sử; dòng cộng tác vẫn hiển thị (sự thật lịch sử), nhưng nội dung không còn được đưa vào context.

## 8. Log và lưu trữ

- **Không** lưu nội dung `AllowedContext`, output specialist hay khối instructions bổ sung ở bất kỳ đâu ngoài bộ nhớ của lượt.
- `ai_collaborations` giữ 90 ngày (như `ai_usage`), xóa khi xóa tài khoản/guest purge.
- Log: `collaboration_state edge=… rule=… status=… reason=… duration_ms=…` — không `user_id`, không nội dung, không entry id.
