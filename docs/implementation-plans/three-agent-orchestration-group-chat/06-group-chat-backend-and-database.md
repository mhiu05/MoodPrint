# 06 — Nhóm AI: backend, cơ sở dữ liệu, SSE

## 1. Quyết định: mở rộng `ai_conversations`, không nhân bản runtime

Nhóm là một `ai_conversations` với `kind='group'`, `bot_id='group'`. Lý do: tái dùng `ai_messages` (thứ tự `sequence`, nhiều bubble/run, unique `(run_id, actor, part_index)`), hạn lưu trữ `expires_at` + `purge_chat`, xóa tài khoản, `ai_conversation_reads`, export. Mọi endpoint 1:1 lọc `kind='direct'` nên không nhận ID nhóm.

## 2. Schema (migration `0024_three_agent_groups`, chỉ mở rộng)

| Bảng | Thay đổi |
| --- | --- |
| `ai_conversations` | `kind varchar(8) not null default 'direct'` (`direct|group`); CHECK bot: `(kind='direct' and bot_id in 8 id) or (kind='group' and bot_id='group')`; `active_agent varchar(16) null` + `active_agent_since int null` (handoff dính, chỉ `direct`) |
| `ai_messages` | `mentions jsonb not null default '[]'` (mảng ≤ 4 bot id đã phân giải, chỉ tin `self`) |
| `ai_runs` | origin thêm `'agent'`; CHECK parent: `(origin in ('collaboration','agent')) = (parent_run_id is not null)` |
| `ai_group_members` | mới: `(conversation_id, bot_id)` PK, `user_id`, `status active|removed`, `journal_access bool default false`, `history_from_sequence int ≥ 0`, `joined_at`, `removed_at`, `version` |
| `ai_orchestration_steps` | mới: receipts content-free ([04](04-as-tool-and-handoff-contracts.md) §4) |
| `ai_sharing_permissions` | CHECK edge thêm 4 cạnh V3 |
| `ai_proactive_schedules`, `ai_proactive_jobs`, `memory_*` | CHECK bot thêm `dieuphoi, nhatky, hoatdong` |

RLS bật + policy `backend_access` cho `moodprint_runtime` trên bảng mới; client role không có quyền (như 0023).

Người nói của mọi tin AI = `ai_runs.bot_id` của run sinh ra tin đó (main run, child run handoff, child run phát biểu nhóm). Không có cột speaker tự khai.

## 3. API

| Method | Path | Ghi chú |
| --- | --- | --- |
| GET | `/ai/groups` | danh sách nhóm của chủ sở hữu (`updated_at desc`), thành viên, chưa đọc |
| POST | `/ai/groups` | `{name ≤ 60, members: [2..3 bot id V3 duy nhất]}` + `Idempotency-Key` → 201 |
| GET | `/ai/groups/{id}` | header + trang tin (`limit`, `before`), mỗi tin AI có `speaker`; `activeTurnId` |
| PATCH | `/ai/groups/{id}` | đổi tên `{name, expectedVersion}` |
| POST | `/ai/groups/{id}/members` | `{botId, shareHistory, expectedVersion}` (≤ 3) |
| DELETE | `/ai/groups/{id}/members/{botId}?expectedVersion=` | không cho xuống dưới 2; hủy lượt đang chạy |
| PUT | `/ai/groups/{id}/members/nhatky/journal-access` | `{enabled, expectedVersion}` |
| DELETE | `/ai/groups/{id}` | xóa nhóm (chủ sở hữu) |
| POST | `/ai/groups/{id}/messages` | `{text, clientMessageId, expectedVersion, mentions?: botId[]}` → 202 `{turnId, eventsUrl}` |
| GET | `/ai/groups/{id}/turns/{turnId}/events?afterSeq=` | SSE `ai-group-events-v1` |
| POST | `/ai/groups/{id}/turns/{turnId}/cancel` | |
| POST | `/ai/groups/{id}/read` | `{sequence}` |

Tất cả: `require_registered_actor`, đồng ý AI, 18+, cờ C; chủ sở hữu kiểm bằng `user_id` trong mọi truy vấn (404 cho nhóm người khác, không phân biệt "không tồn tại").

## 4. Một lượt nhóm

1. **Admission** (1 giao dịch, khóa owner + khóa nhóm): đồng ý AI, phiên bản nhóm, idempotency `(scope_id=group, client_message_id)`, hạn mức Phase 1 (`admission`), không có lượt đang chạy. Ghi tin `self` (+ `mentions` đã phân giải), run lượt (`origin='user'`, `bot_id='group'`), `ai_turns`.
2. **Chọn người nói** (không giữ kết nối): `mentions` ⇒ đúng các thành viên được nhắc (theo thứ tự nhắc; `@mọi người` ⇒ tất cả). Không nhắc: `triage` ⇒ tin tầm thường: 1 người (Điều phối nếu là thành viên); còn lại: selector LLM (`SpeakerPlan{speakers[1..3]{agent, reason}, summarize}`) trên danh sách thành viên + tin mới + 2 lượt gần nhất. Policy: chỉ thành viên `active`, không trùng, ≤ `AI_GROUP_MAX_SPEAKERS` (3), Điều phối tổng hợp đứng cuối. Lỗi ⇒ 1 người mặc định.
3. **Ghi lựa chọn**: một step `group_select` với `detail = {mode, speakers[]}` (fast path: `completed` ngay, không child run; selector LLM: child run mang usage). Step `group_reply` của từng người nói được tạo **khi người đó bắt đầu** (child run + usage reservation tạo lúc đó để lease usage 45 s không hết hạn trong lúc chờ); người bị bỏ khỏi nhóm giữa lượt được ghi `group_reply` `denied/not_member` để thứ tự event vẫn chỉ tiến.
4. **Lần lượt từng người nói** (tuần tự để người sau thấy người trước): mở child run (`origin='agent'`, `bot_id=speaker`), gọi model không giữ kết nối (persona nhóm, lịch sử nhìn thấy theo `history_from_sequence`, tin của trợ lý khác có nhãn `[Tên]`), publish (khóa owner + nhóm): thành viên vẫn `active`, quyền nhật ký vẫn bật nếu đã đọc, run lượt vẫn `running` ⇒ ghi bubbles dưới child run, step `completed + used_in_reply`. Người nói lỗi ⇒ step `failed`, **không** có tin giả; lượt tiếp tục với người sau.
5. **Kết thúc**: run lượt `completed` nếu ≥ 1 người nói thành công, ngược lại `failed`.

## 5. SSE `ai-group-events-v1`

Danh sách event là hàm thuần của trạng thái DB (chỉ tiến ⇒ nối lại bằng `afterSeq`/`Last-Event-ID` không trùng):

```
turn_started {turnId}
agent_selected {agent, ordinal}           # mọi step, theo ordinal (ghi cùng lúc)
  lặp theo ordinal:
  agent_started {agent, ordinal}          # child run tồn tại
  agent_message {agent, ordinal, messages:[{messageId, partIndex, text}]}   # step completed (đã commit)
  | agent_failed {agent, ordinal, code}   # step failed/timeout/cancelled
turn_completed {} | turn_failed {code} | turn_cancelled {}
```

Không có token tạm thời hay nội dung chưa kiểm. Tối đa 1 + 3 + 3×2 + 1 = 11 event; cursor > độ dài ⇒ 409 `CURSOR_GAP`.

## 6. Quyền riêng tư nhóm

- Ngữ cảnh nhóm chỉ là tin trong nhóm; không gộp lịch sử 1:1 của từng trợ lý.
- Nhật ký trong nhóm chỉ đọc nhật ký khi `journal_access=true` cho nhóm đó (mặc định tắt, bật riêng). Lượt đọc nhật ký được ký `journal-turn-v1` ⇒ các lượt sau cắt ngữ cảnh trước đó (fail-closed như Phase 1).
- Thêm thành viên: mặc định chỉ thấy tin **từ lúc tham gia** (`history_from_sequence = version hiện tại + 1`, tức chỉ tin có sequence lớn hơn tin cuối hiện có); người dùng có thể chọn chia sẻ lịch sử trước đó.
- Bỏ thành viên: `status='removed'` ngay; lượt đang chạy bị hủy; publish kiểm lại thành viên; tin cũ giữ nguyên người nói.
- Xóa nhóm: xóa hội thoại (cascade tin, thành viên); receipts content-free theo vòng đời tài khoản.
