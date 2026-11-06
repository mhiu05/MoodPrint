# 02 — Kiến trúc hiện tại

Tài liệu này mô tả code tại HEAD đã review, tập trung vào đường đi Grok sẽ chạm tới. Tổng quan chung nằm ở [ARCHITECTURE.md](../../ARCHITECTURE.md). Mọi mục dưới đây là VERIFIED trừ khi ghi khác.

## 1. Thành phần

```mermaid
flowchart LR
    B[SPA React 19] -->|/api/v1 cùng origin| C[Caddy]
    C --> A[FastAPI một worker]
    A --> R[AiRuntime trong RAM]
    A --> P[(PostgreSQL schema moodprint)]
    A --> S[Supabase Auth]
    R --> O[OpenAI qua Agents SDK]
    A --> V[Voyage]
    A --> ST[Supabase Storage]
    B -->|signed URL, tus| ST
    W1[worker proactive] --> P
    W2[worker maps] --> P
```

## 2. Vòng đời một request AI

```mermaid
sequenceDiagram
    participant UI as RealApp
    participant Client as ApiClient
    participant Route as chat_routes.send
    participant Sec as security.transaction
    participant RT as AiRuntime.drive
    participant Turn as search.prepare_turn
    participant WF as Workflow.decide
    participant SDK as SdkProvider
    participant DB as PostgreSQL
    UI->>Client: POST /ai/conversations/{id}/messages
    Client->>Route: Cookie, X-CSRF-Token, Idempotency-Key
    Route->>Sec: lock_actor, verify_session, is_adult_eligible
    Route->>Sec: assert_purpose("AI")
    Route->>DB: owned_conversation, AiTurn trùng?
    Route->>Route: available_for, assert_companion_open
    Route->>Route: validate_options, version, admission
    Route->>DB: AiRun, AiTurn, AiMessageRecord, ai_usage giữ 2 USD
    Route-->>UI: 202 AIRunAccepted(runId, eventsUrl)
    UI->>Route: GET /ai/runs/{id}/events (SSE)
    Route->>RT: asyncio.create_task(drive)
    RT->>Turn: skills, web, Maps (chỉ V3)
    RT->>DB: kiểm tra data_version, MEM, revalidate check-in
    RT->>RT: model_messages, retrieve_memories, build_history
    RT->>RT: monitor_policy mỗi 0,5 giây
    RT->>WF: triage → planner → policy.validate
    alt direct
        RT->>SDK: run_reply(...)
    else consult hoặc handoff
        RT->>SDK: run_agents(...)
    end
    SDK-->>RT: AiReply đã qua guardrail
    RT->>DB: giao dịch: AiRun completed, ai_messages, ai_usage settled
    RT-->>UI: event final, completed
```

Điểm quan trọng cho thiết kế mới:

| Điểm | File, symbol | Ý nghĩa |
| --- | --- | --- |
| Cổng đầu | `chat_routes.send` | `AI_UNAVAILABLE`, `admission`, ngân sách đều chặn trước khi có run. Safety đỏ phải chạy **trước** các cổng này. |
| Không có streaming token | `SdkProvider._stream` | Browser chỉ nhận kết quả đã validate. Hậu kiểm an toàn cắm vào được mà không cần cắt stream. |
| Publish một giao dịch | `drive` | Message, run, usage commit cùng nhau. Template đỏ dùng cùng cách. |
| Sự kiện SSE của run lưu | `persistent_events` | Hàm thuần từ DB, forward-only. Template đỏ không cần `drive`. |
| Giới hạn | `_BudgetHooks(3, 2)`, `MAX_MODEL_CALLS = 7` | 3 model call, 2 tool call mỗi lượt. |
| Thời gian | `ai_timeout_seconds = 30`, `RUN_TIMEOUT_SECONDS = 30` | Thêm classifier và verifier cần nới trong profile demo. |

## 3. Upload attachment

```mermaid
sequenceDiagram
    participant UI as JournalAttachments
    participant API as media_routes
    participant DB as PostgreSQL
    participant S as Supabase Storage
    UI->>API: POST /journal/entries/{id}/media (type, mime, size)
    API->>DB: JournalMedia pending, receipt
    API->>S: POST object/upload/sign (không x-upsert)
    API-->>UI: uploadUrl, token, resumableUrl
    alt file ≤ 6 MiB
        UI->>S: PUT uploadUrl, x-upsert: false
    else file > 6 MiB
        UI->>S: tus, x-signature, chunk 6 MiB
    end
    UI->>API: POST .../media/{id}/complete
    API->>S: object/info
    API->>DB: so size và content-type; đúng thì ready, sai thì xóa
    UI->>API: GET .../media/{id}/access
    API->>S: object/sign, TTL 60 giây
    API-->>UI: signed URL
```

Server không bao giờ thấy byte file và không có hash. Evidence cần thêm bước tải về để băm.

## 4. Voice transcription

```mermaid
sequenceDiagram
    participant UI as VoiceRecorder
    participant API as voice.transcribe
    participant P as OpenAI
    UI->>UI: AudioWorklet 16 kHz, tối đa 30 giây, encodeWav
    UI->>API: POST /voice/transcriptions audio/wav
    API->>API: assert_purpose("VOICE"), giới hạn 6/phút, 60/ngày, slot
    API->>API: validate_audio
    API->>P: audio.transcriptions.create
    API->>API: kiểm tra lại quyền, text ≤ 500
    API-->>UI: TranscriptionPreview
    UI->>UI: người dùng sửa, đưa vào composer
```

Không lưu audio. Không có `language`, `prompt`. Không vào ledger chi phí của tài khoản đăng ký.

## 5. Proactive job

```mermaid
sequenceDiagram
    participant W as app.jobs.proactive
    participant DB as PostgreSQL
    participant E as proactive.executor
    participant SDK as SdkProvider.run_proactive
    W->>DB: materialize lịch thành ai_proactive_jobs
    W->>DB: claim job có lease
    W->>E: E1 kiểm tra, E2 context
    E->>E: distress_screen(digests)
    alt khớp
        E->>E: SAFETY_TEMPLATE, không gọi model
    else
        E->>SDK: một lượt không tool
        E->>E: validate_output
    end
    E->>DB: publish ai_messages, ai_message_sources
```

Bị tắt hoàn toàn trong profile demo. Worker vẫn chạy heartbeat để `deploy.sh` báo healthy.

## 6. Guest turn

```mermaid
sequenceDiagram
    participant UI as GuestEntry
    participant API as guests.routes
    participant S as Supabase Auth
    participant DB as PostgreSQL
    UI->>API: POST /auth/guest-intents
    UI->>API: POST /auth/guest (tuổi 18+, CAPTCHA, disclosure)
    API->>DB: GuestProvisioningAttempt, signup_started
    API->>S: anonymous signup
    API->>DB: User guest, T0 theo đồng hồ DB, hạn 2 giờ
    API-->>UI: SessionView, cookie
    UI->>API: POST conversation (persistent theo historyAvailable)
    UI->>API: POST messages
    API->>DB: reserve_guest_quota, reserve_guest_operation
    Note over API: drive như lượt thường, thêm deadline và GuestGuardedModel
    API->>DB: guest_cleanup_jobs xóa sau hạn
```

## 7. Danh tính và eligibility

```mermaid
flowchart TD
    Req[Request] --> RA[require_actor → load_actor]
    RA --> VS[verify_session: revoke, hạn, auth.sessions]
    RA --> CSRF[CSRF, Origin cho ghi]
    RA --> T[transaction → lock_actor]
    T --> VA[verify_actor]
    VA --> EA{eligible=True?}
    EA -->|có| IA[is_adult_eligible]
    IA -->|sai| E403[403 ELIGIBILITY_REQUIRED]
    EA --> Del[deletion_pending]
```

`transaction(..., eligible=False)` dành cho session, export, xóa dữ liệu. `_session_view` tự tính `eligible = adult_eligible(user, declaration)`.

## 8. Dữ liệu liên quan

| Nhóm | Bảng | Migration | Ghi chú |
| --- | --- | --- | --- |
| Danh tính | `users`, `auth_sessions`, `age_declarations`, `consents`, `consent_events` | 0001, 0004 | `age_band` có CHECK |
| Hội thoại | `ai_conversations`, `ai_messages`, `ai_turns`, `ai_runs`, `ai_usage` | 0006, 0007, 0021, 0024, 0025 | `citations`, `source_backed` trên message |
| Memory | `memories`, `memory_proposals`, `memory_embedding_jobs`, `memory_embeddings` | 0007–0009, 0029 | |
| Journal | `journal_entries`, `journal_media`, `journal_storage_deletions`, `journal_ai_settings`, `journal_entry_embeddings`, `journal_ai_jobs` | 0019, 0029 | |
| Chi phí ngoài | `ai_search_usage`, `ai_maps_searches` | 0026, 0027 | Mẫu ledger ngoài |
| Consent | `consents` | 0001 | `consent_enabled` luôn true với `AI`, `MEM`, `VOICE` nếu có hàng |

**Quyền**: schema `moodprint` riêng, nằm ngoài Data API. Migration mới gọi `protect(table)`: bật RLS, thu hồi khỏi `anon`, `authenticated`, `service_role`, cấp DML cho `moodprint_runtime`, tạo policy `backend_access`. Đây là phòng thủ sâu; quyền theo user do backend kiểm tra.

**Storage**: bucket `journal-media` private, giới hạn 50 MiB, signed read 60 giây, upload token 2 giờ, không upsert. `SupabaseJournalStorage._private_bucket` kiểm tra bucket vẫn private trước mỗi lần ký.

**Frontend**: `AppEntry` chọn cây public hoặc `RealApp`. `classifyEntry` chỉ nhận `/`, `/login`, hash route. App dùng `HashRouter`. Trạng thái dùng `useResource`, `resourceCache` và context, không có thư viện state. Token ở `tokens.css`, chat có thế giới riêng ở `agent-chat.css`. Chuyển động qua `useMotionPolicy`.

## 9. Release hiện tại

Chi tiết ở [release-runbook](grok-handoff/release-runbook.md).

```mermaid
flowchart LR
    M[Merge vào main] --> CI[Verify local application, ~35 phút]
    CI -->|workflow_run| V[validate: hold, SHA, CI]
    V --> Bd[build image]
    Bd --> Pub[publish GHCR, attest, prerelease staging-sha]
    Pub --> Poll[EC2 poller mỗi 5 phút]
    Poll --> Dep[deploy.sh: SSM runtime, up, health]
    Dep -->|lỗi| Back[Khôi phục image trước]
```
