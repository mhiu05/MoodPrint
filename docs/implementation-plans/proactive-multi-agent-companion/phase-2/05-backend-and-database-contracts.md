# Phase 2 — 05. Hợp đồng backend và database

> Đặc tả, không phải migration. Tiền đề: M-P1-A và M-P1-B đã áp dụng ([phase-1/04](../phase-1/04-database-and-migrations.md)).

## 1. Migration M-P2-A (`0023_collaboration`, số có thể đổi)

```sql
-- Run con cho specialist
ALTER TABLE moodprint.ai_runs ADD COLUMN parent_run_id uuid REFERENCES moodprint.ai_runs(id) ON DELETE CASCADE;
ALTER TABLE moodprint.ai_runs DROP CONSTRAINT ck_ai_runs_origin;
ALTER TABLE moodprint.ai_runs
  ADD CONSTRAINT ck_ai_runs_origin CHECK (origin IN ('user', 'proactive', 'collaboration')),
  ADD CONSTRAINT ck_ai_runs_parent CHECK ((origin = 'collaboration') = (parent_run_id IS NOT NULL));
CREATE INDEX ix_ai_runs_parent_run_id ON moodprint.ai_runs (parent_run_id) WHERE parent_run_id IS NOT NULL;

-- Quyền chia sẻ theo cạnh (opt-in)
CREATE TABLE moodprint.ai_sharing_permissions (
  user_id uuid NOT NULL REFERENCES moodprint.users(id) ON DELETE CASCADE,
  edge varchar(48) NOT NULL,
  enabled boolean NOT NULL DEFAULT false,
  version integer NOT NULL DEFAULT 1,
  policy_version varchar(32) NOT NULL DEFAULT 'sharing-v1',
  updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  CONSTRAINT pk_ai_sharing_permissions PRIMARY KEY (user_id, edge),
  CONSTRAINT ck_ai_sharing_permissions_edge CHECK (edge IN
    ('nhip_energy_for_rure', 'nhip_habit_for_may', 'rure_activity_for_guong')),
  CONSTRAINT ck_ai_sharing_permissions_version CHECK (version >= 1),
  CONSTRAINT ck_ai_sharing_permissions_policy CHECK (policy_version IN ('sharing-v1'))
);

-- Receipt cộng tác (content-free)
CREATE TABLE moodprint.ai_collaborations (
  id uuid PRIMARY KEY,
  user_id uuid NOT NULL REFERENCES moodprint.users(id) ON DELETE CASCADE,
  primary_run_id uuid NOT NULL REFERENCES moodprint.ai_runs(id) ON DELETE CASCADE,
  specialist_run_id uuid REFERENCES moodprint.ai_runs(id) ON DELETE SET NULL,
  edge varchar(48) NOT NULL,
  rule_id varchar(8) NOT NULL,
  requester_bot varchar(16) NOT NULL,
  specialist_bot varchar(16) NOT NULL,
  status varchar(16) NOT NULL,
  deny_reason varchar(32),
  permission_version integer NOT NULL,
  data_version integer NOT NULL,
  input_schema varchar(32) NOT NULL,
  input_digest char(64) NOT NULL,
  output_digest char(64),
  used_in_reply boolean NOT NULL DEFAULT false,
  started_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  finished_at timestamptz,
  CONSTRAINT uq_ai_collaborations_primary_run_id UNIQUE (primary_run_id, specialist_bot, edge),
  CONSTRAINT ck_ai_collaborations_status CHECK (status IN
    ('authorized','denied','completed','failed','timeout','cancelled','discarded')),
  CONSTRAINT ck_ai_collaborations_edge CHECK (
    (edge = 'nhip_energy_for_rure' AND requester_bot = 'rure' AND specialist_bot = 'nhip')
    OR (edge = 'nhip_habit_for_may' AND requester_bot = 'may' AND specialist_bot = 'nhip')
    OR (edge = 'rure_activity_for_guong' AND requester_bot = 'guong' AND specialist_bot = 'rure')),
  CONSTRAINT ck_ai_collaborations_rule CHECK (rule_id IN ('R1','R2','R3','R4')),
  CONSTRAINT ck_ai_collaborations_deny CHECK ((status = 'denied') = (deny_reason IS NOT NULL)),
  CONSTRAINT ck_ai_collaborations_used CHECK (NOT used_in_reply OR status = 'completed')
);
CREATE INDEX ix_ai_collaborations_user_started ON moodprint.ai_collaborations (user_id, started_at);
```

CHECK `ck_ai_collaborations_edge` là lớp phòng thủ thứ hai cho ma trận ([03 §1](03-agent-communication-and-consent.md)); nguồn chính là `collaboration/policy.py`.

RLS/grant giống [phase-1/04 §4.1](../phase-1/04-database-and-migrations.md). Inventory: guest `INVENTORY` ("purged"), `process_deletions` xóa tường minh, retention xóa `ai_collaborations` > 90 ngày (như `ai_usage`), `docs/supabase/schema.md`.

`ai_usage` **không đổi**: run con có row riêng, `requests_started ≤ 1` trong thực tế (CHECK ≤ 3 vẫn đúng).

## 2. API

| Method | Path | Mô tả |
| --- | --- | --- |
| GET | `/api/v1/ai/sharing` | Danh sách cạnh + trạng thái + mô tả chia sẻ |
| PUT | `/api/v1/ai/sharing/{edge}` | Bật/tắt một cạnh |

```json
// GET /api/v1/ai/sharing
{
  "available": true,
  "edges": [
    {"edge": "nhip_energy_for_rure", "requester": "rure", "specialist": "nhip", "enabled": false,
     "version": 0, "requires": ["journal_context"], "available": false, "reason": "journal_context_off"},
    {"edge": "nhip_habit_for_may", "requester": "may", "specialist": "nhip", "enabled": true,
     "version": 2, "requires": [], "available": true, "reason": null},
    {"edge": "rure_activity_for_guong", "requester": "guong", "specialist": "rure", "enabled": false,
     "version": 0, "requires": [], "available": true, "reason": null}
  ]
}

// PUT /api/v1/ai/sharing/nhip_habit_for_may
{"enabled": false, "expectedVersion": 2, "policyVersion": "sharing-v1"}
```

`require_registered_actor`, idempotency + version như Phase 1. Tắt: `version += 1`, `users.data_version += 1`, hủy run `running` của user, `runtime.invalidate()`. Văn bản "chia sẻ gì" là hằng frontend theo `edge` (không trả từ server để tránh lệch bản dịch; server trả `requires`/`reason`).

## 3. SSE v2 bổ sung (chỉ khi `AI_COLLABORATION_ENABLED`)

| Event | `data` | Khi |
| --- | --- | --- |
| `progress` | `{"activity": "consulting", "companion": "nhip"}` | Ngay sau commit `ai_collaborations(authorized)` |
| `progress` | `{"activity": "composing"}` | Khi specialist kết thúc (mọi trạng thái) và primary bắt đầu |
| `final` | `{"messages": [...], "partCount": n, "collaboration": CollaborationSummary \| null}` | Như Phase 1 |

**Persistent run (mặc định, vì lịch sử được lưu):** route SSE hiện **không** đọc `LiveRun.events` mà poll DB và dựng danh sách cố định seq 1–3 ([chat_routes.py:605-631](../../../../backend/app/ai/chat_routes.py#L605)). Event "consulting" phát qua `runtime.event()` vì thế sẽ không bao giờ tới client. Thiết kế Phase 2: ở v2, danh sách event của persistent run là **hàm xác định của trạng thái DB**, chỉ tiến về phía trước:

```text
[progress {}]                                                    -- luôn có
+ [progress {activity: consulting, companion}]  nếu tồn tại ai_collaborations của run với status ≠ denied
+ [progress {activity: composing}]              nếu collaboration đó đã kết thúc (completed/failed/timeout/cancelled)
+ [final, completed] hoặc [failed|cancelled]    khi run kết thúc
```

Số event tối đa 5 ⇒ `afterSeq ≤ 5` ở v2 (v1 giữ ≤ 3 và không có hai event giữa). Vì mỗi phần tử chỉ xuất hiện sau phần tử trước, prefix ổn định nên reconnect bằng `afterSeq`/`Last-Event-ID` vẫn đúng. Lượt không phối hợp có `final` ở seq 2 như Phase 1. Temporary chat dùng `LiveRun.events` như hiện tại. Client v1 không bao giờ thấy các khóa mới (v1 ghép như cũ, bỏ `collaboration`).

Validator client v2: `progress.data` chỉ nhận `{}` hoặc đúng hai dạng trên với `companion ∈ BotId`; `final.data.collaboration` là `null` hoặc object `{kind, companions, summary}` với `summary` ≤ 200 ký tự, `companions` 2 phần tử.

## 4. DTO

`AIMessage` thêm `collaboration: CollaborationSummary | null` — chỉ trên bubble `partIndex = 0` của run có receipt `completed` + `used_in_reply`. `conversation_view()` join:

```sql
LEFT JOIN moodprint.ai_collaborations col
  ON col.primary_run_id = m.run_id AND col.status = 'completed' AND col.used_in_reply
```

Render `summary` bằng template theo `(edge, rule_id)` ([04 §3](04-collaboration-ui-ux.md)).

## 5. Tích hợp runtime

```python
# AiRuntime.drive(), ngay trước self.provider.run(...)
signals = CollabSignals(bot_id=c.bot_id, intent=conversation_intent(c.bot_id, history, scoped=...),
                        latest_text=current_text(history), local_time=..., depth=0)
consult = await self.coordinator.maybe_consult(run, signals)     # None hoặc ConsultResult
if consult:
    extra_instructions, extra_input = consult.for_primary()
    self.event(run, "progress", {"activity": "composing"})
output = await self.provider.run(..., extra_instructions=extra_instructions, extra_input=extra_input)
# publish transaction: thêm consult.provenance vào ai_message_sources, set used_in_reply
```

- `maybe_consult` không ném lỗi ra ngoài trừ khi do người dùng hủy/quyền bị thu hồi (khi đó run hủy như hiện tại); mọi lỗi khác → `None` + receipt trạng thái lỗi.
- Stamp: run có provenance nhật ký từ specialist → `JOURNAL_TURN_POLICY` (chat) hoặc `proactive-journal-v1` (proactive). Run không có provenance (R3, R4) → stamp bình thường.
- `SdkProvider.run(...)` nhận thêm `extra_instructions: str = ""`, `extra_input: list[dict] = []` (mặc định rỗng → hành vi Phase 1 không đổi).

## 6. Specialist runner

```python
async def run_specialist(self, request: DelegationRequest, *, observer) -> BaseModel:
    spec = EDGES[request.edge]
    agent = Agent[SpecialistContext](
        name=f"MoodPrint:{request.specialist_bot}:specialist:{request.edge}",
        instructions=spec.instructions,              # không dùng persona đầy đủ; mục đích hẹp
        model=self.provider.model(), tools=[], output_type=spec.output_type,
        output_guardrails=[_no_unreceipted_claim_structured],
        model_settings=ModelSettings(store=False, max_tokens=300, timeout=spec.timeout,
                                     retry=ModelRetrySettings(max_retries=0), parallel_tool_calls=False))
    ctx = SpecialistContext(user_id=..., collaboration_id=request.collaboration_id, depth=1)
    async with asyncio.timeout(spec.timeout):
        result = await Runner.run(agent, input=[spec.input_item(request.allowed)], context=ctx, max_turns=1,
                                  hooks=_BudgetHooks(ctx.check, observer, model_limit=1, tool_limit=0),
                                  run_config=RunConfig(tracing_disabled=True, trace_include_sensitive_data=False))
    return spec.validate(result.final_output, request.allowed)
```

`_BudgetHooks` cần tham số `model_limit`/`tool_limit` (hiện hard-code 3/2, [provider.py:83,106](../../../../backend/app/ai/provider.py#L83)) — thay đổi nhỏ, mặc định giữ 3/2.

## 7. Cấu hình

| Biến | Mặc định | Ràng buộc |
| --- | --- | --- |
| `AI_COLLABORATION_ENABLED` | `false` | Yêu cầu `AI_MULTI_MESSAGE_ENABLED` (SSE v2); production yêu cầu `AI_ACCOUNTING_ENABLED` vì run con không có `ai_turns` — phục hồi sau crash dựa vào lease `ai_usage` (`recover_expired`, [accounting.py:78-89](../../../../backend/app/ai/accounting.py#L78)); coordinator luôn đóng run con trong `finally` |
| `AI_COLLABORATION_DAILY_CAP` | 10 | 1–50 |
| `AI_COLLABORATION_TIMEOUT_SECONDS` | 8 | 3–10 |
| `AI_COLLABORATION_BUDGET_SHARE` | 0.7 | 0.1–0.9 |

Thêm vào [configuration.md](../../../backend/configuration.md) và [api-reference.md](../../../backend/api-reference.md) (gate `check_docs.py`).
