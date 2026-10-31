# API inventory

Danh mục từ [backend/openapi.json](../../backend/openapi.json). Base path đã có trong từng dòng. DTO, status và authorization chi tiết xem OpenAPI cùng route đang được `main.py` include; danh mục này không cấp quyền gọi endpoint hoặc chứng minh feature flag đang bật.

Để cập nhật: export OpenAPI, đối chiếu method/path/operation ID và cập nhật bảng. Xem [API contract](api.md).

| Method | Path | Operation ID |
| --- | --- | --- |
| GET | `/api/v1/admin/feedback` | `feedback_list_api_v1_admin_feedback_get` |
| GET | `/api/v1/admin/feedback/summary` | `feedback_summary_api_v1_admin_feedback_summary_get` |
| PATCH | `/api/v1/admin/feedback/{id}` | `feedback_review_api_v1_admin_feedback__id__patch` |
| GET | `/api/v1/activities/catalog` | `catalog_api_v1_activities_catalog_get` |
| GET | `/api/v1/activities/{session_id}` | `get_session_api_v1_activities__session_id__get` |
| POST | `/api/v1/activities/{session_id}/accept` | `activity_accept_api_v1_activities__session_id__accept_post` |
| POST | `/api/v1/activities/{session_id}/cancel` | `activity_cancel_api_v1_activities__session_id__cancel_post` |
| POST | `/api/v1/activities/{session_id}/decline` | `activity_decline_api_v1_activities__session_id__decline_post` |
| POST | `/api/v1/activities/{session_id}/end` | `activity_end_api_v1_activities__session_id__end_post` |
| POST | `/api/v1/activities/{session_id}/feedback` | `feedback_api_v1_activities__session_id__feedback_post` |
| POST | `/api/v1/activities/{session_id}/focus/join` | `activity_join_api_v1_activities__session_id__focus_join_post` |
| POST | `/api/v1/activities/{session_id}/focus/leave` | `activity_leave_api_v1_activities__session_id__focus_leave_post` |
| POST | `/api/v1/activities/{session_id}/focus/pause` | `activity_pause_api_v1_activities__session_id__focus_pause_post` |
| POST | `/api/v1/activities/{session_id}/focus/resume` | `activity_resume_api_v1_activities__session_id__focus_resume_post` |
| POST | `/api/v1/activities/{session_id}/ready` | `ready_api_v1_activities__session_id__ready_post` |
| POST | `/api/v1/activities/{session_id}/responses` | `respond_api_v1_activities__session_id__responses_post` |
| GET | `/api/v1/admin/reports` | `queue_api_v1_admin_reports_get` |
| POST | `/api/v1/admin/reports/{report_id}/claim` | `claim_api_v1_admin_reports__report_id__claim_post` |
| POST | `/api/v1/admin/reports/{report_id}/resolve` | `resolve_api_v1_admin_reports__report_id__resolve_post` |
| POST | `/api/v1/admin/users/{ref}/lift` | `lift_api_v1_admin_users__ref__lift_post` |
| GET | `/api/v1/ai/conversations` | `conversations_api_v1_ai_conversations_get` |
| POST | `/api/v1/ai/conversations` | `create_conversation_api_v1_ai_conversations_post` |
| GET | `/api/v1/ai/conversations/{conversation_id}` | `conversation_api_v1_ai_conversations__conversation_id__get` |
| PATCH | `/api/v1/ai/conversations/{conversation_id}` | `rename_conversation_api_v1_ai_conversations__conversation_id__patch` |
| DELETE | `/api/v1/ai/conversations/{conversation_id}` | `delete_conversation_api_v1_ai_conversations__conversation_id__delete` |
| POST | `/api/v1/ai/conversations/{conversation_id}/end` | `end_api_v1_ai_conversations__conversation_id__end_post` |
| GET | `/api/v1/ai/conversations/{conversation_id}/export` | `export_conversation_api_v1_ai_conversations__conversation_id__export_get` |
| PUT | `/api/v1/ai/conversations/{conversation_id}/read` | `mark_read_api_v1_ai_conversations__conversation_id__read_put` |
| POST | `/api/v1/ai/conversations/{conversation_id}/messages` | `send_api_v1_ai_conversations__conversation_id__messages_post` |
| GET | `/api/v1/ai/preferences` | `preferences_api_v1_ai_preferences_get` |
| GET | `/api/v1/ai/inbox` | `inbox_api_v1_ai_inbox_get` |
| POST | `/api/v1/ai/inbox/read-all` | `read_all_api_v1_ai_inbox_read_all_post` |
| PUT | `/api/v1/ai/preferences` | `update_preferences_api_v1_ai_preferences_put` |
| GET | `/api/v1/ai/proactive` | `proactive_api_v1_ai_proactive_get` |
| PUT | `/api/v1/ai/proactive/schedules/{bot_id}/{slot}` | `save_schedule_api_v1_ai_proactive_schedules__bot_id___slot__put` |
| DELETE | `/api/v1/ai/proactive/schedules/{bot_id}/{slot}` | `delete_schedule_api_v1_ai_proactive_schedules__bot_id___slot__delete` |
| PUT | `/api/v1/ai/proactive/settings` | `save_settings_api_v1_ai_proactive_settings_put` |
| GET | `/api/v1/ai/sharing` | `read_sharing_api_v1_ai_sharing_get` |
| GET | `/api/v1/bots/legacy` | `legacy_bots_api_v1_bots_legacy_get` |
| POST | `/api/v1/ai/proactive/schedules/{bot_id}/{slot}/migrate` | `migrate_schedule_api_v1_ai_proactive_schedules__bot_id___slot__migrate_post` |
| PUT | `/api/v1/ai/sharing/{edge}` | `update_sharing_api_v1_ai_sharing__edge__put` |
| POST | `/api/v1/ai/runs/{run_id}/cancel` | `cancel_api_v1_ai_runs__run_id__cancel_post` |
| GET | `/api/v1/ai/runs/{run_id}/events` | `events_api_v1_ai_runs__run_id__events_get` |
| POST | `/api/v1/auth/confirmation` | `resend_confirmation_api_v1_auth_confirmation_post` |
| POST | `/api/v1/auth/guest` | `guest_create_api_v1_auth_guest_post` |
| POST | `/api/v1/auth/guest-intents` | `guest_intents_api_v1_auth_guest_intents_post` |
| POST | `/api/v1/auth/guest/end` | `guest_end_api_v1_auth_guest_end_post` |
| POST | `/api/v1/auth/login` | `login_api_v1_auth_login_post` |
| POST | `/api/v1/auth/logout` | `logout_api_v1_auth_logout_post` |
| POST | `/api/v1/auth/password-recovery` | `request_password_recovery_api_v1_auth_password_recovery_post` |
| POST | `/api/v1/auth/password-reset` | `reset_password_api_v1_auth_password_reset_post` |
| POST | `/api/v1/auth/reauthenticate` | `reauthenticate_api_v1_auth_reauthenticate_post` |
| POST | `/api/v1/auth/signup` | `signup_api_v1_auth_signup_post` |
| POST | `/api/v1/blocks` | `block_api_v1_blocks_post` |
| GET | `/api/v1/bots` | `bots_api_v1_bots_get` |
| GET | `/api/v1/connection-requests` | `list_requests_api_v1_connection_requests_get` |
| POST | `/api/v1/connection-requests` | `send_request_api_v1_connection_requests_post` |
| POST | `/api/v1/connection-requests/{request_id}/accept` | `accept_api_v1_connection_requests__request_id__accept_post` |
| POST | `/api/v1/connection-requests/{request_id}/cancel` | `cancel_api_v1_connection_requests__request_id__cancel_post` |
| POST | `/api/v1/connection-requests/{request_id}/decline` | `decline_api_v1_connection_requests__request_id__decline_post` |
| GET | `/api/v1/connections` | `list_connections_api_v1_connections_get` |
| GET | `/api/v1/connections/{connection_id}` | `get_connection_api_v1_connections__connection_id__get` |
| POST | `/api/v1/connections/{connection_id}/activities` | `invite_api_v1_connections__connection_id__activities_post` |
| GET | `/api/v1/connections/{connection_id}/activities` | `history_api_v1_connections__connection_id__activities_get` |
| GET | `/api/v1/connections/{connection_id}/activities/current` | `current_api_v1_connections__connection_id__activities_current_get` |
| POST | `/api/v1/connections/{connection_id}/block` | `block_connection_api_v1_connections__connection_id__block_post` |
| POST | `/api/v1/connections/{connection_id}/end` | `end_api_v1_connections__connection_id__end_post` |
| GET | `/api/v1/connections/{connection_id}/events` | `events_api_v1_connections__connection_id__events_get` |
| POST | `/api/v1/connections/{connection_id}/messages` | `send_message_api_v1_connections__connection_id__messages_post` |
| GET | `/api/v1/connections/{connection_id}/messages` | `get_messages_api_v1_connections__connection_id__messages_get` |
| POST | `/api/v1/connections/{connection_id}/peer-reference` | `peer_reference_api_v1_connections__connection_id__peer_reference_post` |
| POST | `/api/v1/connections/{connection_id}/read` | `mark_read_api_v1_connections__connection_id__read_post` |
| POST | `/api/v1/connections/{connection_id}/reveal-requests` | `request_reveal_api_v1_connections__connection_id__reveal_requests_post` |
| GET | `/api/v1/connections/{connection_id}/reveal-requests` | `list_reveals_api_v1_connections__connection_id__reveal_requests_get` |
| PUT | `/api/v1/consents/{purpose}` | `update_consent_api_v1_consents__purpose__put` |
| POST | `/api/v1/data-deletions` | `deletion_api_v1_data_deletions_post` |
| GET | `/api/v1/data-deletions/{job_id}` | `deletion_status_api_v1_data_deletions__job_id__get` |
| POST | `/api/v1/exports` | `export_api_v1_exports_post` |
| GET | `/api/v1/exports/{job_id}` | `export_status_api_v1_exports__job_id__get` |
| GET | `/api/v1/exports/{job_id}/download` | `download_api_v1_exports__job_id__download_get` |
| POST | `/api/v1/feedback` | `create_feedback_api_v1_feedback_post` |
| GET | `/api/v1/feedback/submission-state` | `get_submission_state_api_v1_feedback_submission_state_get` |
| GET | `/api/v1/health/live` | `live_api_v1_health_live_get` |
| GET | `/api/v1/health/ready` | `ready_api_v1_health_ready_get` |
| GET | `/api/v1/matching/candidates` | `candidates_api_v1_matching_candidates_get` |
| POST | `/api/v1/matching/skips` | `skip_api_v1_matching_skips_post` |
| GET | `/api/v1/memories` | `memories_api_v1_memories_get` |
| PATCH | `/api/v1/memories/{memory_id}` | `edit_memory_api_v1_memories__memory_id__patch` |
| DELETE | `/api/v1/memories/{memory_id}` | `delete_memory_api_v1_memories__memory_id__delete` |
| GET | `/api/v1/moods` | `list_moods_api_v1_moods_get` |
| GET | `/api/v1/moods/summary` | `summary_api_v1_moods_summary_get` |
| PUT | `/api/v1/moods/{local_date}` | `save_mood_api_v1_moods__local_date__put` |
| DELETE | `/api/v1/moods/{local_date}` | `delete_mood_api_v1_moods__local_date__delete` |
| GET | `/api/v1/profiles/matching-draft` | `get_draft_api_v1_profiles_matching_draft_get` |
| PUT | `/api/v1/profiles/matching-draft` | `save_draft_api_v1_profiles_matching_draft_put` |
| POST | `/api/v1/profiles/matching-draft/preview` | `preview_draft_api_v1_profiles_matching_draft_preview_post` |
| POST | `/api/v1/profiles/published` | `publish_api_v1_profiles_published_post` |
| GET | `/api/v1/profiles/published/current` | `published_current_api_v1_profiles_published_current_get` |
| DELETE | `/api/v1/profiles/published/current` | `withdraw_api_v1_profiles_published_current_delete` |
| GET | `/api/v1/proposals` | `proposals_api_v1_proposals_get` |
| POST | `/api/v1/proposals/{proposal_id}/confirm` | `confirm_api_v1_proposals__proposal_id__confirm_post` |
| POST | `/api/v1/proposals/{proposal_id}/reject` | `reject_proposal_api_v1_proposals__proposal_id__reject_post` |
| GET | `/api/v1/public/experience` | `public_experience_api_v1_public_experience_get` |
| POST | `/api/v1/reports` | `report_api_v1_reports_post` |
| GET | `/api/v1/reports/{report_id}` | `report_status_api_v1_reports__report_id__get` |
| DELETE | `/api/v1/reveal-grants/{reveal_id}` | `revoke_api_v1_reveal_grants__reveal_id__delete` |
| GET | `/api/v1/reveal-grants/{reveal_id}/value` | `revealed_value_api_v1_reveal_grants__reveal_id__value_get` |
| POST | `/api/v1/reveal-requests/{reveal_id}/decline` | `decline_api_v1_reveal_requests__reveal_id__decline_post` |
| POST | `/api/v1/reveal-requests/{reveal_id}/grant` | `grant_api_v1_reveal_requests__reveal_id__grant_post` |
| GET | `/api/v1/session` | `get_session_api_v1_session_get` |
| GET | `/api/v1/social/summary` | `social_summary_api_v1_social_summary_get` |
| GET | `/api/v1/taxonomy` | `taxonomy_api_v1_taxonomy_get` |
| PUT | `/api/v1/users/me/eligibility` | `declare_eligibility_api_v1_users_me_eligibility_put` |
| GET | `/api/v1/users/me/identity` | `own_identity_api_v1_users_me_identity_get` |
| PATCH | `/api/v1/users/me/identity` | `edit_identity_api_v1_users_me_identity_patch` |
| POST | `/api/v1/voice/transcriptions` | `transcribe_api_v1_voice_transcriptions_post` |

Tổng cộng **109 operations** trong snapshot. `POST /feedback` và `GET /feedback/submission-state` chỉ tồn tại khi `FEEDBACK_ENABLED` và `GUEST_ABUSE_HMAC_KEY` đều có; gửi thành công trả 201, cùng key và payload trả 200 cùng receipt, guest chỉ gửi một lần trong trial (409 `FEEDBACK_ALREADY_SUBMITTED`), user đã đăng ký một lần mỗi ngày Asia/Bangkok (429 `FEEDBACK_DAILY_LIMIT`). Production ẩn docs UI; snapshot vẫn được sinh offline cho contract checks.

Admin feedback cần tài khoản đã đăng ký, role admin hiện hành, xác thực lại bằng mật khẩu trong 12 giờ và `FEEDBACK_ADMIN_ENABLED` riêng. List/summary dùng cùng bộ lọc, ngày Asia/Bangkok tối đa 180 ngày, mặc định loại spam; summary dùng một snapshot đọc nhất quán. PATCH cần CSRF, Idempotency-Key và expectedVersion; stale trả 409 `STALE_VERSION`. Audit chỉ lưu resource/version/trạng thái/staff, không sao chép comment hoặc liên kết tới lịch sử riêng. Retention chạy độc lập với các cờ.

## Nh?t k? V2

| Method | Path | Operation ID |
| --- | --- | --- |
| GET | `/api/v1/journal/entries` | `list_entries_api_v1_journal_entries_get` |
| POST | `/api/v1/journal/entries` | `create_entry_api_v1_journal_entries_post` |
| GET | `/api/v1/journal/entries/{entry_id}` | `get_entry_api_v1_journal_entries__entry_id__get` |
| PUT | `/api/v1/journal/entries/{entry_id}` | `update_entry_api_v1_journal_entries__entry_id__put` |
| DELETE | `/api/v1/journal/entries/{entry_id}` | `delete_entry_api_v1_journal_entries__entry_id__delete` |
| POST | `/api/v1/journal/entries/{entry_id}/media` | `reserve_media_api_v1_journal_entries__entry_id__media_post` |
| POST | `/api/v1/journal/entries/{entry_id}/media/{media_id}/complete` | `complete_media_api_v1_journal_entries__entry_id__media__media_id__complete_post` |
| GET | `/api/v1/journal/entries/{entry_id}/media/{media_id}/access` | `access_media_api_v1_journal_entries__entry_id__media__media_id__access_get` |
| DELETE | `/api/v1/journal/entries/{entry_id}/media/{media_id}` | `delete_media_api_v1_journal_entries__entry_id__media__media_id__delete` |

## Lời hỏi thăm (proactive)

Chỉ tài khoản đã đăng ký (`require_registered_actor`, guest → `403 REGISTERED_REQUIRED`; `age_band` ngoài teen/adult → `403 ELIGIBILITY_REQUIRED`). `GET /ai/proactive` luôn trả đủ 10 cặp trợ lý × buổi (`version: 0` = chưa lưu) cùng `available`, `settings`, `limits` (cap, số khung đang bật, khung giờ theo tuổi, bước 15 phút) và `eligibility.reason` cho từng cặp. Ghi yêu cầu `Idempotency-Key` và `expectedVersion` (0 = tạo mới). `available=false` (cờ `PROACTIVE_ENABLED`, nhóm `PROACTIVE_ROLLOUT_USER_IDS` hoặc AI tắt) → ghi trả `503 PROACTIVE_UNAVAILABLE`.

| Lỗi | HTTP | Khi |
| --- | --- | --- |
| `STALE_VERSION` | 409 | `expectedVersion` lệch |
| `SCHEDULE_WINDOW` | 422 | Ngoài khung sáng 05:00–11:30 / tối 17:00–22:30 (teen ≤ 21:00) hoặc lệch bước 15 phút |
| `SCHEDULE_IN_QUIET_HOURS` | 422 (lịch) / 409 (settings) | Lịch đang bật nằm trong giờ yên lặng |
| `PROACTIVE_DAILY_CAP` | 409 | Bật quá `PROACTIVE_DAILY_CAP_PER_USER` khung |
| `PROACTIVE_INELIGIBLE` | 403 | Cầu Nối khi chưa đủ điều kiện kết nối (adult + MATCH + không hạn chế) hoặc lịch sử trò chuyện không khả dụng |
| `SCHEDULE_PAUSE` | 422 | `pausedUntil` quá 30 ngày |
| `INVALID_TIMEZONE`, `QUIET_HOURS_INVALID` | 422 | Múi giờ IANA không hợp lệ; giờ yên lặng ngoài 4–12 giờ |

Mọi lần lưu hủy job chưa chạy của lịch liên quan; đổi múi giờ/giờ yên lặng tính lại `nextDeliveryAt` cho mọi lịch; tắt `journalContextEnabled` tăng `journal_context_version` và `users.data_version`, hủy job Nhịp chưa chạy và lượt chat đang chạy.

**Lời nhắn mới (inbox).** `GET /ai/inbox` (không khóa hàng tài khoản, poll 30 s) trả `badgesEnabled`, `unreadTotal` và mỗi trợ lý một dòng `{botId, unread, latest:{conversationId, runId, slot, deliveredAt, firstSequence}}` — **không** có nội dung hay preview. Đếm theo lượt giao (3 bubble = 1), chỉ hội thoại còn hạn, run trong 30 ngày; trả lời sau lời hỏi thăm được tính là đã đọc. Guest, cờ tắt hoặc ngoài nhóm rollout → `{badgesEnabled:false, unreadTotal:0, bots:[]}`. `PUT /ai/conversations/{id}/read` `{lastReadSequence}` upsert đơn điệu (`GREATEST`), cắt về `conversation.version`, hội thoại người khác → 404. `POST /ai/inbox/read-all` đánh dấu mọi hội thoại có lời nhắn mới và trả lại inbox.

## Trợ lý phối hợp (Phase 2)

Chỉ tài khoản đã đăng ký (`require_registered_actor`, guest → `403 REGISTERED_REQUIRED`). `GET /ai/sharing` trả `{available, edges:[{edge, requester, specialist, enabled, version, requires, available, reason}]}` cho đúng ba cạnh `nhip_energy_for_rure`, `nhip_habit_for_may`, `rure_activity_for_guong` (Cầu Nối không có cạnh). Tài khoản mới: mọi cạnh `enabled:false, version:0`. `reason ∈ {feature_unavailable, ineligible_account, journal_context_off}`; văn bản "chia sẻ gì / không chia sẻ gì" là hằng frontend theo `edge`.

`PUT /ai/sharing/{edge}` `{enabled, expectedVersion, policyVersion:"sharing-v1"}` (bắt buộc `Idempotency-Key`). Bật: version +1. **Tắt luôn được phép** (kể cả khi cờ tắt): version +1, `users.data_version` +1, mọi run `running` của tài khoản → `cancelled`, `runtime.invalidate()` — lượt đang chạy không dùng hay lưu được kết quả phối hợp.

| Lỗi | HTTP | Khi |
| --- | --- | --- |
| `NOT_FOUND` | 404 | Cạnh ngoài allowlist (mọi cạnh có Cầu Nối, mọi cặp không khai báo) |
| `STALE_VERSION` | 409 | `expectedVersion` lệch |
| `SHARING_REQUIRES_JOURNAL_CONTEXT` | 409 | Bật `nhip_energy_for_rure` khi chưa bật "Dùng khoảnh khắc đã lưu hôm qua" |
| `COLLABORATION_UNAVAILABLE` | 503 | Bật khi `AI_COLLABORATION_ENABLED=false`, ngoài nhóm rollout hoặc chưa bật `AI_MULTI_MESSAGE_ENABLED` |
| `ADULT_REQUIRED` | 403 | Bật khi tài khoản chưa đủ 18 tuổi, bị tạm khóa hoặc đang chờ xóa |

