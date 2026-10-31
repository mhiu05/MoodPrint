# Phase 1 — 05. Backend API và agent runtime

## 1. Bố cục module đề xuất

| File (mới hoặc sửa) | Nội dung |
| --- | --- |
| `backend/app/ai/proactive/__init__.py` (mới) | Package |
| `backend/app/ai/proactive/models.py` (mới) | ORM 5 bảng của [04 §4](04-database-and-migrations.md) |
| `backend/app/ai/proactive/schemas.py` (mới) | DTO API (§2) và output model-facing (`ProactiveReply`, `NhipProactiveReply`) |
| `backend/app/ai/proactive/schedule.py` (mới) | Hàm thuần: `next_occurrence`, `resolve_local`, `in_quiet_hours`, `weekday_allowed`, giới hạn teen |
| `backend/app/ai/proactive/policy.py` (mới) | `authorize_proactive()`, `persona_eligibility()` |
| `backend/app/ai/proactive/context.py` (mới) | Builder dữ liệu theo persona ([07](07-persona-behaviors-and-prompts.md)), truy xuất nhật ký hôm qua |
| `backend/app/ai/proactive/executor.py` (mới) | E1–E5 ([03 §6](03-proactive-scheduler-and-workers.md)) |
| `backend/app/ai/proactive/routes.py` (mới) | Router `/ai/proactive`, `/ai/inbox`, `/ai/conversations/{id}/read` |
| `backend/app/jobs/proactive.py` (mới) | `materialize_due`, `claim_job`, `proactive_tick` |
| [provider.py](../../../../backend/app/ai/provider.py) (sửa) | `CompanionReply` output type; `run_proactive()` |
| [runtime.py](../../../../backend/app/ai/runtime.py) (sửa) | Persist N bubble; revalidate proactive-journal; event v2 |
| [chat_routes.py](../../../../backend/app/ai/chat_routes.py) (sửa) | SSE v1/v2; `durable_run` nhiều row; DTO mới |
| [persistence.py](../../../../backend/app/ai/persistence.py) (sửa) | `admission()`/`daily_turns()` lọc `origin`; `conversation_view()` hoàn thiện nhóm, join `origin`/`proactive_slot` |
| [context.py](../../../../backend/app/ai/context.py) (sửa) | Policy mới, gộp bubble trong `build_history` |
| [prompts.py](../../../../backend/app/ai/prompts.py) (sửa, **không** đổi `instructions()` đã đóng băng) | Lớp `PROACTIVE_SHARED`, `PROACTIVE_PERSONAS` |
| [config.py](../../../../backend/app/core/config.py) (sửa) | Settings §8 |
| [main.py](../../../../backend/app/main.py) (sửa) | Mount router, vòng lặp `proactive_worker` |
| [contracts.py](../../../../backend/app/contracts.py) (sửa) | `FeatureView.proactive` |

## 2. API mới

Mọi route dùng `require_registered_actor` (guest → `403 REGISTERED_REQUIRED`) và `transaction(request, actor)`; ghi dùng `Idempotency-Key` + `expectedVersion` như phần còn lại của codebase. Khi `PROACTIVE_ENABLED=false`: GET trả `available=false`, ghi trả `503 PROACTIVE_UNAVAILABLE`.

### 2.1 `GET /api/v1/ai/proactive`

```json
{
  "available": true,
  "settings": {
    "timezone": "Asia/Ho_Chi_Minh", "quietStart": "22:00", "quietEnd": "07:00",
    "badgesEnabled": true, "journalContextEnabled": false, "version": 3, "policyVersion": "proactive-v1"
  },
  "schedules": [
    {"botId": "nhip", "slot": "morning", "enabled": true, "localTime": "07:30",
     "weekdays": [1,2,3,4,5,6,7], "pausedUntil": null, "autoPaused": false,
     "nextDeliveryAt": "2026-11-01T00:30:00Z", "version": 2,
     "eligibility": {"allowed": true, "reason": null}},
    {"botId": "caunoi", "slot": "evening", "enabled": false, "localTime": "20:00",
     "weekdays": [1,2,3,4,5,6,7], "pausedUntil": null, "autoPaused": false,
     "nextDeliveryAt": null, "version": 0,
     "eligibility": {"allowed": false, "reason": "social_not_enabled"}}
  ],
  "limits": {"dailyCap": 4, "enabledSlots": 1,
             "windows": {"morning": ["05:00", "11:30"], "evening": ["17:00", "22:30"]},
             "stepMinutes": 15}
}
```

- Trả đủ 10 cặp (bot × slot); cặp chưa lưu có `version: 0`, `enabled: false`, giờ mặc định (sáng 07:30, tối 20:00; teen tối 20:00 và tối đa 21:00).
- `eligibility.reason` (enum): `null`, `teen_social_unavailable`, `social_not_enabled`, `social_restricted`, `history_unavailable`, `ai_unavailable`.
- Không có row settings → trả mặc định với `timezone = users.timezone`, `version: 0`.

### 2.2 `PUT /api/v1/ai/proactive/settings`

```json
{"timezone": "Asia/Ho_Chi_Minh", "quietStart": "22:00", "quietEnd": "07:00",
 "badgesEnabled": true, "journalContextEnabled": true,
 "expectedVersion": 3, "policyVersion": "proactive-v1"}
```

Kiểm: IANA hợp lệ (`ZoneInfo`), giờ yên lặng 4–12 giờ, không làm lịch đang bật rơi vào giờ yên lặng (`409 SCHEDULE_IN_QUIET_HOURS` kèm danh sách cặp xung đột). Bật `journalContextEnabled` lần đầu bắt buộc `policyVersion` hiện hành (consent text đã hiển thị). Tắt `journalContextEnabled` → `journal_context_version += 1`, `users.data_version += 1`, hủy job Nhịp chưa chạy, `request.app.state.ai.invalidate(user)`.

### 2.3 `PUT /api/v1/ai/proactive/schedules/{botId}/{slot}` (upsert)

```json
{"enabled": true, "localTime": "07:30", "weekdays": [1,2,3,4,5],
 "pausedUntil": null, "expectedVersion": 2}
```

Phản hồi: một phần tử `schedules[]` như §2.1. Lỗi:

| Code | HTTP | Khi |
| --- | --- | --- |
| `STALE_VERSION` | 409 | `expectedVersion` lệch (0 = tạo mới) |
| `SCHEDULE_WINDOW` | 422 | Ngoài khung/bước 15 phút/teen sau 21:00 |
| `SCHEDULE_IN_QUIET_HOURS` | 422 | Nằm trong giờ yên lặng |
| `PROACTIVE_DAILY_CAP` | 409 | Bật khung thứ 5 |
| `PROACTIVE_INELIGIBLE` | 403 | Cầu Nối khi không đủ điều kiện xã hội, hoặc không có capability lưu lịch sử |
| `PROACTIVE_UNAVAILABLE` | 503 | Flag tắt |

Bật lại một lịch đang `autoPaused` → xóa `auto_paused_at`. Lần lưu lịch đầu tiên tạo `ai_proactive_settings` mặc định trong cùng transaction (không bao giờ có lịch mà thiếu settings). Mọi lần lưu lịch/settings đặt `users.last_seen_at = now()` vì cột này chỉ được ghi khi trượt session sau ≥ 15 phút ([security.py:84-96](../../../../backend/app/core/security.py#L84)) — người dùng mới bật lịch rồi rời đi vẫn được coi là đang hoạt động.

### 2.4 `DELETE /api/v1/ai/proactive/schedules/{botId}/{slot}`

Body `{"expectedVersion": 2}` → xóa row, hủy job chưa chạy, trả `ActionReceipt`.

### 2.5 `GET /api/v1/ai/inbox`

Poll khi tab hiển thị (30 s), khi focus, và sau khi một run kết thúc. Không khóa row (`transaction(..., lock=False)` như `/social/summary`).

```json
{
  "badgesEnabled": true,
  "unreadTotal": 2,
  "bots": [
    {"botId": "nhip", "unread": 1, "latest": {"conversationId": "…", "runId": "…", "slot": "morning",
      "deliveredAt": "2026-10-31T00:31:04Z", "firstSequence": 12}},
    {"botId": "rure", "unread": 1, "latest": {"conversationId": "…", "runId": "…", "slot": "morning",
      "deliveredAt": "2026-10-31T00:45:10Z", "firstSequence": 4}}
  ]
}
```

Truy vấn (một lần, nhóm):

```sql
SELECT r.bot_id, r.id AS run_id, c.id AS conversation_id, r.proactive_slot,
       min(m.sequence) AS first_sequence, max(m.created_at) AS delivered_at
FROM moodprint.ai_runs r
JOIN moodprint.ai_messages m ON m.run_id = r.id AND m.actor = 'bot'
JOIN moodprint.ai_conversations c ON c.id = m.conversation_id
LEFT JOIN moodprint.ai_conversation_reads cr ON cr.conversation_id = c.id
WHERE r.user_id = :uid AND r.origin = 'proactive' AND r.status = 'completed'
  AND c.user_id = :uid AND c.expires_at > now()
  AND r.created_at > now() - interval '30 days'
GROUP BY r.bot_id, r.id, c.id, r.proactive_slot, cr.last_read_sequence
HAVING min(m.sequence) > coalesce(cr.last_read_sequence, 0);
```

Không trả `text`, không preview. `badgesEnabled=false` → client ẩn chấm nhưng mục "Lời nhắn mới" vẫn liệt kê.

### 2.6 `PUT /api/v1/ai/conversations/{conversationId}/read`

```json
{"lastReadSequence": 14}
```

`UPDATE … SET last_read_sequence = GREATEST(last_read_sequence, :seq)` (upsert); `:seq` bị cắt về `conversation.version`. Idempotent tự nhiên; vẫn chấp nhận `Idempotency-Key` do `ApiClient` gửi. Trả `{"conversationId": "…", "lastReadSequence": 14}`. `POST /api/v1/ai/inbox/read-all` đánh dấu mọi hội thoại có unread.

### 2.7 Thay đổi API hiện có

| Route | Thay đổi |
| --- | --- |
| `GET /ai/conversations/{id}` | `AIMessage` thêm `partIndex`, `partCount`, `origin`, `proactiveSlot`; trang không cắt nhóm |
| `GET /ai/runs/{id}/events` | `?protocol=2` → `ai-events-v2` ([02 §4](02-multi-message-contract.md)) |
| `GET /ai/conversations/{id}/export` | Thêm các trường như trên |
| `GET /session` | `features.proactive: bool` (flag + registered + AI khả dụng + history capability) |
| `POST /ai/conversations/{id}/messages` | Không đổi contract; lỗi `STALE_VERSION` thêm `retryable: true` để client tự tải lại |

Mọi route mới phải được thêm vào [api-reference.md](../../../backend/api-reference.md) (gate `check_docs.py`).

## 3. Ủy quyền cho run chủ động

```python
async def authorize_proactive(db, settings, job) -> tuple[User, ProactiveSettings, Schedule] | Skip:
    user = await db.scalar(select(User).where(User.id == job.user_id).with_for_update())
    if user is None or user.status != "active" or user.account_kind != "registered":
        return Skip("ineligible_account")
    if user.deletion_pending or (user.suspended_until and user.suspended_until > now()):
        return Skip("ineligible_account")
    if user.age_band not in ("teen", "adult"):
        return Skip("ineligible_account")
    if not settings.ai_available_for(user.id):
        return Skip("ai_unavailable")
    if not settings.chat_history_enabled:
        return Skip("no_history_capability")
    prefs = await db.get(ProactiveSettings, user.id)
    schedule = await db.get(Schedule, job.schedule_id) if job.schedule_id else None
    seen = max(filter(None, (user.last_seen_at, schedule.updated_at if schedule else None)), default=None)
    if seen is None or seen < now() - timedelta(days=settings.proactive_inactive_days):
        return Skip("inactive_user")
    if prefs is None or schedule is None or not schedule.enabled:
        return Skip("disabled")
    if (schedule.version, prefs.version) != (job.schedule_version, job.settings_version):
        return Cancel("version_changed")
    if schedule.paused_until and job.local_date <= schedule.paused_until:
        return Skip("paused")
    if schedule.auto_paused_at:
        return Skip("auto_paused")
    if job.bot_id == "caunoi":
        try:
            await assert_purpose(db, user, "MATCH")      # adult + MATCH + không hạn chế
        except DomainError:
            return Skip("ineligible_social")
    return user, prefs, schedule
```

Gọi ở E1 và **lại** ở E5 (publish). Không có `Actor`, không gọi `verify_session`. Không có tool nào được cấp.

## 4. Thay đổi runtime hiện có

### 4.1 Admission và quota

- `admission()` ([persistence.py:220-268](../../../../backend/app/ai/persistence.py#L220)): `active` (global) đếm mọi origin; `own` và `recent` thêm `AiRun.origin == "user"`.
- `daily_turns()` ([persistence.py:190-198](../../../../backend/app/ai/persistence.py#L190)): thêm `AiRun.origin == "user"` → `features.aiQuotaRemaining` không bị lời hỏi thăm trừ.
- `recover_turns()` không đổi (run proactive có `ai_turns.lease_until`).
- `durable_run()` / `authorized_run()`: run `origin='proactive'` không có events cho client → `404 NOT_FOUND` (tin xuất hiện qua GET hội thoại).

### 4.2 Context policy (ADR-08)

```python
TEXT_POLICIES = {TEXT_POLICY, "proactive-text-v1"}
EVIDENCE_POLICIES = {MOOD_TURN_POLICY, JOURNAL_TURN_POLICY}       # chỉ run hiện tại
REVALIDATED_POLICIES = {"proactive-journal-v1"}                    # cần run_id ∈ revalidated

def model_messages(messages, stamps, *, current_run, data_version, revalidated=frozenset()):
    ...
    allowed = (stamp.policy in TEXT_POLICIES
               or (stamp.policy in EVIDENCE_POLICIES and message.run_id == current_run)
               or (stamp.policy in REVALIDATED_POLICIES and message.run_id in revalidated))
```

Trong `drive()`, trước projection: nếu tin bot mới nhất thuộc run `proactive-journal-v1` trong 36 giờ → dưới owner lock gọi `revalidate_sources(db, user, run_id)`:

```python
rows = select(MessageSource).where(MessageSource.run_id == run_id, MessageSource.user_id == user.id)
ok = (prefs.journal_context_enabled
      and all(row.policy == f"proactive-journal-v1@{prefs.journal_context_version}" for row in rows)
      and stamp.data_version == user.data_version
      and all(current_revision(row.source_id) == row.source_revision and saved and within_90_days))
```

Nếu `ok`: thêm vào `revalidated`, và **trước khi gọi model** ghi `ai_turns.context_policy = JOURNAL_TURN_POLICY` cho lượt hiện tại cùng `c.context_stamps[run.id]` — đúng mẫu "persist provenance before any retrieved prose can reach the model" của `search_journal_entries` ([runtime.py:447-453](../../../../backend/app/ai/runtime.py#L447)). Nếu không: tin đó và mọi tin cũ hơn bị cắt (fail closed, hành vi hiện tại). `ai_turns.context_policy` (varchar 32) chỉ chứa tên policy; version consent tại thời điểm sinh tin được ghi vào `ai_message_sources.policy` dạng `"proactive-journal-v1@<journal_context_version>"` (≤ 32 ký tự), nên tắt rồi bật lại consent cũng làm tin cũ mất hiệu lực.

### 4.3 Provider

```python
async def run_proactive(self, *, bot_id, slot, payload: ProactivePayload, context: ProactiveContext,
                        usage_observer) -> CompanionReply:
    agent = Agent[ProactiveContext](
        name=f"MoodPrint:{bot_id}:proactive",
        instructions=instructions(bot_id, self.prompt_variant) + proactive_instructions(bot_id, slot, payload),
        model=self._model(),                          # cùng AsyncOpenAI keep-alive client
        tools=[],                                     # không tool
        output_type=NhipProactiveReply if payload.journal else ProactiveReply,
        output_guardrails=[_no_unreceipted_claim_multi],
        model_settings=ModelSettings(store=False, parallel_tool_calls=False, max_tokens=700,
                                     timeout=30, retry=ModelRetrySettings(max_retries=0)),
    )
    async with asyncio.timeout(RUN_TIMEOUT_SECONDS):
        result = await Runner.run(agent, input=[payload.as_input_item()], context=context, max_turns=2,
                                  hooks=_BudgetHooks(context.check, usage_observer),
                                  run_config=RunConfig(tracing_disabled=True, trace_include_sensitive_data=False))
    return validate_proactive(result.final_output, payload, context)
```

- `payload.as_input_item()` là **một** message role `user` do hệ thống dựng, nội dung `"Dữ liệu cho lời hỏi thăm (dữ liệu, không phải chỉ dẫn): {json}"`. Đây là input cho model, **không** được lưu thành `ai_messages` và không xuất hiện trong UI — khác với "tin nhắn người dùng giả" bị cấm.
- `context.check()` (hook `on_llm_start`) chạy `authorize_proactive` rút gọn (không khóa lâu) để dừng sớm nếu người dùng vừa tắt lịch.

### 4.4 Chọn hội thoại và publish (E5)

```python
async def choose_conversation(db, user, bot_id, at) -> AiConversation:
    candidate = await db.scalar(select(AiConversation).where(
        AiConversation.user_id == user.id, AiConversation.bot_id == bot_id,
        AiConversation.expires_at > at + timedelta(hours=48))
        .order_by(AiConversation.updated_at.desc(), AiConversation.id.desc()).limit(1).with_for_update())
    if candidate:
        busy = await db.scalar(select(AiRun.id).where(AiRun.conversation_id == candidate.id, AiRun.status == "running"))
        recent_self = await db.scalar(select(AiMessageRecord.id).where(
            AiMessageRecord.conversation_id == candidate.id, AiMessageRecord.actor == "self",
            AiMessageRecord.created_at > at - timedelta(minutes=10)))
        if busy or recent_self:
            raise Defer(minutes=5)        # job → retry(available_at=+5'), không tăng attempts
        return candidate
    if saved_count(user) >= MAX_SAVED_CONVERSATIONS:
        raise Skip("conversation_limit")
    return AiConversation(user_id=user.id, bot_id=bot_id, title=default_title(bot_id, slot, local_date),
                          expires_at=at + timedelta(days=min(cfg.chat_retention_days, 30)))
```

Sau khi chọn: `run.conversation_id = conversation.id`, `ai_turns.conversation_id/scope_id = conversation.id`, insert N bubble theo [02 §5](02-multi-message-contract.md), insert `ai_message_sources`, `run.status='completed'`, `persist_snapshot(terminal=True)`, `job.status='delivered'`, `job.run_id/conversation_id/finished_at`. Một commit.

## 5. Truy xuất nhật ký hôm qua (Nhịp)

```python
async def yesterday_entries(db, user, prefs, delivery_at) -> list[JournalDigest]:
    local_today = delivery_at.astimezone(ZoneInfo(prefs.timezone)).date()
    yesterday = local_today - timedelta(days=1)
    account_today = datetime.now(ZoneInfo(user.timezone)).date()
    if not (account_today - timedelta(days=89) <= yesterday <= account_today):
        return []
    rows = await db.scalars(select(JournalEntry).where(
        JournalEntry.user_id == user.id, JournalEntry.status == "saved",
        JournalEntry.local_date == yesterday)
        .order_by(JournalEntry.created_at.desc(), JournalEntry.id.desc()).limit(3))
    return [JournalDigest(entry_id=r.id, revision=r.version, local_date=r.local_date, mood=r.mood,
                          emotions=r.emotions[:6], factors=r.factors[:6], excerpt=r.text[:600],
                          excerpt_truncated=len(r.text) > 600) for r in rows]
```

- Cùng bộ lọc với `search_for_ai` ([journal/ai.py:32-88](../../../../backend/app/modules/journal/ai.py#L32)): chỉ owner, `saved`, cửa sổ 90 ngày; không media, không draft, không mood note cũ.
- "Hôm qua" theo **múi giờ lịch** (settings), nhãn `local_date` của entry theo múi giờ tài khoản lúc viết; vì timezone tài khoản hiện không đổi được, hai giá trị trùng trong thực tế (cả hai mặc định `Asia/Bangkok` ≡ UTC+7 như `Asia/Ho_Chi_Minh`). Ghi chú giới hạn này trong UI timezone.
- Tối đa 3 entry mới nhất; nếu có nhiều hơn, payload ghi `{"entriesTotal": 5, "entriesIncluded": 3}` (số do backend đếm).

## 6. Validate output chủ động

| Kiểm tra | Áp dụng |
| --- | --- |
| `CompanionReply` constraints (1–3 bubble cho proactive, tổng ≤ 1.200 ký tự) | Mọi bot |
| Guardrail claim hành động (`_DURABLE_CLAIM`) trên từng bubble | Mọi bot |
| Không có entry → không `source_entry_ids`, không câu "đã đọc nhật ký" (`_JOURNAL_CLAIM`, [ai/journal.py:19-23](../../../../backend/app/ai/journal.py#L19)), không nhắc "hôm qua bạn…" (regex `\bhôm qua\b` khi không có entry) | Nhịp |
| Có entry → ≥ 1 `source_entry_ids` ∈ digest; backend thêm dòng tham khảo vào bubble cuối | Nhịp |
| Tối đa 1 câu hỏi (`?` ≤ 1 trên toàn reply) | Mọi bot |
| Không chứa tên người, "đã kết nối", "lời mời đã gửi", phần trăm phù hợp | Cầu Nối |
| `challenge_kind` ∈ enum đóng | Rủ Rê |

## 7. Mã lỗi công khai mới

Thêm vào [availability.py](../../../../backend/app/ai/availability.py) chỉ khi cần cho client: `PROACTIVE_UNAVAILABLE`, `PROACTIVE_DAILY_CAP`, `PROACTIVE_INELIGIBLE`, `SCHEDULE_WINDOW`, `SCHEDULE_IN_QUIET_HOURS` (thông điệp tiếng Việt trong [06 §10](06-frontend-ux-and-notifications.md)).

## 8. Cấu hình mới

| Biến | Kiểu / mặc định | Ràng buộc |
| --- | --- | --- |
| `AI_MULTI_MESSAGE_ENABLED` | bool / `false` | — |
| `PROACTIVE_ENABLED` | bool / `false` | API + UI |
| `PROACTIVE_WORKER_ENABLED` | bool / `false` | Production: yêu cầu `PROACTIVE_ENABLED`, `AI_ENABLED`, `AI_ACCOUNTING_ENABLED`, `AI_DAILY_BUDGET_USD > 0` |
| `PROACTIVE_WORKER_CONCURRENCY` | int / 1 | 1–4 |
| `PROACTIVE_DAILY_CAP_PER_USER` | int / 4 | 1–6 |
| `PROACTIVE_BUDGET_SHARE` | float / 0.5 | 0.1–0.9 |
| `PROACTIVE_GRACE_MINUTES` | int / 90 | 15–180 |
| `PROACTIVE_MAX_ATTEMPTS` | int / 3 | 1–5 |
| `PROACTIVE_INACTIVE_DAYS` | int / 14 | 1–60 |
| `PROACTIVE_ROLLOUT_USER_IDS` | list[UUID] / `[]` | Khác rỗng → chỉ các tài khoản này có `features.proactive` và được worker xử lý (rollout theo nhóm thử nghiệm đã đồng ý); rỗng → mọi tài khoản đủ điều kiện |

Phải thêm vào [configuration.md](../../../backend/configuration.md) (gate `check_docs.py` so khớp mọi field của `Settings`) và `backend/.env.example`.

## 9. Log

Giữ mẫu `logging.getLogger("moodprint")` với key/value content-free (như `ai_execution_end`, [runtime.py:762](../../../../backend/app/ai/runtime.py#L762)): `proactive_job_state job_id=… state=… reason=… bot=… slot=… attempt=… duration_ms=… input_tokens=… output_tokens=…`. Không log `user_id`, giờ hẹn, tiêu đề hay nội dung.
