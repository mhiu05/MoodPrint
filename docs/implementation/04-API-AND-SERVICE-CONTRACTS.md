# 04 — API and Service Contracts

> Tất cả là 📐 PLANNED. Phần đánh dấu 🔒 phải đóng băng trước khi Phase 2/3 rẽ nhánh (`06` §3).

## 1. Traceability map

Cột **Hiện tại** đã đối chiếu với code. Quy tắc phân quyền viết tắt: **O** = owner qua RLS và service. Test ID xem `07`.

| Tính năng | Mock contract hiện tại | API đích | Thực thể DB | Phân quyền | Test |
|---|---|---|---|---|---|
| Onboarding | `WelcomePage`, tĩnh | Không có | Không | Công khai | `E-ONB` |
| Đăng ký | `AuthPage.enter(true)`, `login()` | Supabase `signUp`, `GET /v1/me` | `auth.users`, `profiles` | Supabase Auth | `E-AUTH-01`, `I-AUTH-*` |
| Đăng nhập, khôi phục phiên | `useDemoStore.user`, `Guard` | Supabase `signInWithPassword`, `onAuthStateChange` | `auth.sessions` | Supabase Auth | `E-AUTH-02..04` |
| Vào demo | `AuthPage.enter(false)`, `personas` | Không có, chỉ local | `moodprint-demo` local | Không | `E-DEMO-01` |
| Cài đặt | `SettingsPage`, `updateUser`, `setPreferences` | `GET/PATCH /v1/me` | `profiles` | O | `I-ME-*` |
| Danh sách hồ sơ | `CaseList` lọc client | `GET /v1/cases` | `cases`, `action_plans` | O | `I-CASE-02` |
| Tạo hồ sơ, nháp | `CaseWizard.save`, `demoService.saveCase`, sessionStorage | `POST /v1/cases` | `cases`, `case_events` | O | `I-CASE-01`, `E-CASE-01` |
| Sửa hồ sơ, trạng thái | `CaseDetail.persist` | `PATCH /v1/cases/{id}` | `cases` | O + version | `I-CASE-03` |
| Xóa hồ sơ | `deleteCase` | `DELETE /v1/cases/{id}` | `cases`, cascade, evidence purge | O | `I-CASE-04` |
| Timeline | `saveEvent` qua `persist` | `POST/PATCH/DELETE /v1/cases/{id}/events[/{eventId}]` | `case_events`, `case_event_evidence` | O | `I-EVENT-*` |
| Hồ sơ liên quan | `CaseDetail.related` (3 hồ sơ khác của owner) | `GET /v1/cases/{id}/related` | `cases` | O | `I-CASE-05` |
| Evidence | `EvidencePicker`, `putEvidence` | `/v1/evidence/*` | `evidence_items`, Storage | O + signed URL | `I-EV-*`, `E-EV-*` |
| Rà soát evidence | `EvidenceCard.onSave` | `PATCH /v1/evidence/{id}` | Cột `user_edited_text`, `review_status` | O | `I-EV-05` |
| Tóm tắt, xuất | Tạo client-side, `copyText`, `downloadText` | Không đổi, chạy trên dữ liệu thật | Không | Client | `E-CASE-02` |
| Kế hoạch | `PlanPage.save`, `savePlan`, `mergePlanDraft` | `GET/PUT /v1/cases/{id}/plan` | `action_plans`, `plan_items` | O + version | `I-PLAN-*` |
| Tick ở Home | `HomePage` `putPlan` | `PATCH /v1/plans/{id}/items/{itemId}` | `plan_items` | O | `I-PLAN-04`, `E-PLAN-02` |
| Người tin cậy | `addTrustedPerson`, `removeTrustedPerson` | `/v1/trusted-contacts` | `trusted_contacts` | O | `I-TC-*` |
| Soạn hỗ trợ | `SupportPreparePage`, `saveDraft` | `/v1/support-drafts` | `support_drafts` | O | `I-SD-*` |
| Chia sẻ cho trường | `demo_submitted` chỉ mô phỏng | `/v1/shares`, `/v1/schools` | `case_shares`, `case_share_evidence` | O; staff theo trường | `I-SHARE-*` |
| Bookmark, đã đọc | `toggleBookmark`, `markRead` | `/v1/knowledge/article-states` | `knowledge_article_states` | O | `I-KS-*` |
| Knowledge Hub | `mocks/data/knowledge.ts` | Giữ local tới Phase 2 | Không | Công khai sau đăng nhập | `U-KB` |
| AI Chat | `chat.tsx`, script | Giữ mock, Phase 3 dùng `/v1/conversations/*` | `conversations`, `messages`, `agent_runs` | O | `I-CONV-*` (Phase 0) |
| Phân tích ảnh | `analysis.tsx`, fixture | Giữ mock tới Phase 3 | `evidence_derivatives` | O | Phase 3 |
| Roleplay | `roleplay.tsx`, script | Giữ mock tới Phase 3 | Phase 3 | O | Phase 3 |
| Hỗ trợ khẩn cấp | `UrgentPage`, tĩnh, công khai | **Không có API.** Phải chạy khi backend chết | Không | Công khai | `E-URG-01` |
| School Admin Demo | `school-store.ts` độc lập | Giữ mock, không nối DB | `moodprint-school-demo` local | Không | `E-SCH-01` |
| Long-term memory | Chưa có UI | `/v1/memories`, `/v1/memory-candidates` | `user_memories`, `memory_candidates` | O | `I-MEM-*` |

## 2. Quy ước REST

- Base path `/v1`. `/health`, `/ready` không version.
- Body dùng camelCase qua Pydantic `alias_generator=to_camel`, Python dùng snake_case.
- Xác thực: `Authorization: Bearer <access_token>` trên mọi route `/v1`, trừ khi ghi khác.
- ID là UUID. Tạo mới nhận `id` do client sinh: gọi lại cùng `id` cùng owner trả **200** với bản ghi hiện có, đây là cơ chế idempotency.
- Danh sách: `?limit=` (mặc định 50, tối đa 100), `?cursor=` opaque, trả `{ "items": [...], "nextCursor": null }`.
- Concurrency: tài nguyên có `version` yêu cầu gửi `version`. Sai version trả 409 kèm bản mới nhất.
- Mọi response có header `X-Request-ID`.
- OpenAPI sinh ra `backend/openapi.json`.

### Error envelope 🔒

```json
{ "error": { "code": "version_conflict", "message": "Dữ liệu đã thay đổi.", "requestId": "...", "details": { "latest": {} } } }
```

| HTTP | `code` | Khi nào |
|---|---|---|
| 400 | `invalid_request` | Sai định dạng |
| 401 | `unauthenticated` | Thiếu, sai, hết hạn token |
| 403 | `forbidden` | Đã xác thực nhưng không được phép, ví dụ `fixture_not_allowed` trong `details` |
| 404 | `not_found` | Không tồn tại **hoặc không thuộc về người dùng**. Không phân biệt, để tránh lộ sự tồn tại |
| 409 | `version_conflict` | Sai version |
| 409 | `run_in_progress` | Conversation đang có run |
| 409 | `conflict` | Trùng khác |
| 413 | `object_too_large` | Vượt giới hạn ứng dụng |
| 422 | `validation_failed` | `details.fields` theo từng trường |
| 429 | `rate_limited` | Kèm `Retry-After` |
| 429 | `quota_exceeded` | Vượt quota evidence |
| 502 | `upstream_error` | Storage, Auth lỗi |
| 503 | `not_ready` | `/ready` lỗi |
| 500 | `internal_error` | Không lộ chi tiết |

## 3. Endpoints

### Vận hành

| Method | Path | Auth | Mô tả |
|---|---|---|---|
| GET | `/health` | Không | Process sống. Không chạm dependency |
| GET | `/ready` | Không | Kiểm DB, JWKS. Trả tên thành phần lỗi, không trả chi tiết |

### Profile

| Method | Path | Mô tả |
|---|---|---|
| GET | `/v1/me` | Lazy-create profile từ JWT, trả `Profile`. `user_metadata` chỉ dùng làm giá trị khởi tạo cho `nickname`, `age_band` sau khi validate |
| PATCH | `/v1/me` | `{ nickname?, ageBand?, reducedMotion? }` |
| DELETE | `/v1/me` | P1. Xóa tài khoản, cần `{ "confirm": "DELETE" }`, kiểm tra thêm với Auth server |

```jsonc
// Profile
{ "userId": "uuid", "nickname": "An", "ageBand": "11-13", "locale": "vi", "reducedMotion": false }
```

### Cases

| Method | Path | Mô tả |
|---|---|---|
| GET | `/v1/cases` | Lọc `status`, `q`, `sort=updated\|title`. Trả `CaseSummary` gồm `planProgress` |
| POST | `/v1/cases` | Tạo. `status` chỉ `draft\|active`. Có thể kèm `firstEvent`, `evidenceIds` |
| GET | `/v1/cases/{id}` | `CaseDetail`: gồm `events[]`, `evidenceIds[]`, `linkedPlanId` |
| PATCH | `/v1/cases/{id}` | Trường scalar + `version` |
| DELETE | `/v1/cases/{id}` | Theo `03` §6 |
| GET | `/v1/cases/{id}/related` | Tối đa 3 hồ sơ khác của owner, ưu tiên trùng `categoryTags` |
| POST | `/v1/cases/{id}/events` | Thêm mốc |
| PATCH | `/v1/cases/{id}/events/{eventId}` | Sửa |
| DELETE | `/v1/cases/{id}/events/{eventId}` | Xóa, không đụng evidence |

```jsonc
// CaseDetail
{
  "id": "uuid", "ownerId": "uuid", "title": "Nhóm chat lớp", "template": "TPL-THREAT",
  "perspective": "self", "summary": "...", "categoryTags": ["Trên mạng"], "impactTags": [],
  "status": "active", "people": "", "place": "", "occurredAt": "2026-11-04", "tried": "",
  "trustedPerson": "", "events": [ /* TimelineEvent */ ], "evidenceIds": ["uuid"],
  "linkedPlanId": null, "version": 3, "createdAt": "...", "updatedAt": "..."
}
// TimelineEvent
{ "id": "uuid", "caseId": "uuid", "when": "2026-11-04", "timePrecision": "day", "place": "",
  "description": "...", "provenance": "user_entered", "evidenceIds": [], "needsReview": false }
```

Quy tắc `when`: `exact` là ISO datetime, `day`/`week` là ISO date, `unknown` là chuỗi rỗng. Tương thích kiểu TypeScript hiện có.

Client **không** gửi được `provenance = user_confirmed` với `ai_extracted`, và không gửi `mock_extracted` (trả `403 fixture_not_allowed`).

### Evidence

| Method | Path | Mô tả |
|---|---|---|
| POST | `/v1/evidence/uploads` | Khởi tạo file. Body `{ id, caseId?, filename, mimeType, byteSize, sha256?, shownTimestamp?, capturedAtLabel? }`. Trả `{ evidence, upload: { url, token, chunkSize, objectName, bucketName, expiresAt } }` |
| POST | `/v1/evidence/{id}/upload-token` | Cấp lại token khi `pending` |
| POST | `/v1/evidence/{id}/complete` | Xác minh object tồn tại, chốt metadata |
| POST | `/v1/evidence/notes` | Tạo `text_note`, không có file |
| GET | `/v1/evidence` | `?caseId=` hoặc `?unlinked=true` |
| GET | `/v1/evidence/{id}` | Metadata |
| PATCH | `/v1/evidence/{id}` | Chỉ `userEditedText`, `reviewStatus`, `limitations`. Cột bất biến bị bỏ qua với 422 |
| GET | `/v1/evidence/{id}/download-url` | `{ url, expiresAt }`, có audit |
| POST | `/v1/cases/{id}/evidence/{evidenceId}/link` | Gắn vào hồ sơ |
| DELETE | `/v1/cases/{id}/evidence/{evidenceId}/link` | Bỏ khỏi hồ sơ và mọi mốc, giữ file |
| DELETE | `/v1/evidence/{id}` | Xóa vĩnh viễn |

### Plans

| Method | Path | Mô tả |
|---|---|---|
| GET | `/v1/cases/{id}/plan` | 404 khi chưa có. Trả `ActionPlan` |
| PUT | `/v1/cases/{id}/plan` | Upsert toàn bộ plan và items theo thứ tự mảng. Cần `version` khi đã tồn tại |
| PATCH | `/v1/plans/{planId}/items/{itemId}` | `{ status?, notes? }`, tăng version plan, dùng cho Home |
| GET | `/v1/plans/active` | Plan chưa hoàn tất gần nhất, cho Home |

`PUT` giữ đúng mô hình hiện tại của `PlanPage`. `409 version_conflict` kết nối với thông báo "Kế hoạch đã có cập nhật mới" và `mergePlanDraft` đang có sẵn.

Nguyên tắc nghiệp vụ: `completed` đòi mọi item `done`. Không có trường nào gợi ý MoodPrint đã liên hệ ai.

### Trusted contacts, support drafts, article states

| Method | Path |
|---|---|
| GET, POST | `/v1/trusted-contacts` |
| PATCH, DELETE | `/v1/trusted-contacts/{id}` |
| GET, POST | `/v1/support-drafts` |
| GET, PATCH, DELETE | `/v1/support-drafts/{id}` |
| GET | `/v1/knowledge/article-states` |
| PUT | `/v1/knowledge/article-states/{articleId}` |

### Sharing

| Method | Path | Mô tả |
|---|---|---|
| GET | `/v1/schools` | Trường `verified`. Có thể rỗng |
| POST | `/v1/shares` | Tạo `draft`: `{ id, caseId, schoolId, identityMode, sharedFields[], evidenceIds[] }` |
| GET | `/v1/shares`, `/v1/shares/{id}` | Của học sinh |
| PATCH | `/v1/shares/{id}` | Chỉ khi `draft` |
| GET | `/v1/shares/{id}/preview` | Chính xác nội dung sẽ gửi, gồm metadata định danh |
| POST | `/v1/shares/{id}/submit` | `{ confirmed: true, confirmationVersion, previewHash }`. Sai hash trả 409. Tạo snapshot bất biến |
| POST | `/v1/shares/{id}/withdraw` | Xóa snapshot |
| GET | `/v1/school/{schoolId}/shares[/{id}]` | Chỉ staff của trường đó. Hợp đồng ổn định, UI ở phase sau |
| GET | `/v1/school/{schoolId}/shares/{id}/evidence/{evidenceId}/download-url` | Chỉ evidence đã chọn, audit |

`sharedFields` allow-list: `title, summary, occurredAt, place, events, people, impactTags, tried`. Mặc định **rỗng**, học sinh tự chọn. `previewHash` chống trường hợp nội dung đổi giữa lúc xem và lúc xác nhận.

### Conversations

| Method | Path | Mô tả |
|---|---|---|
| POST | `/v1/conversations` | `{ id, title?, linkedCaseId?, sourceArticleId? }` |
| GET | `/v1/conversations`, `/v1/conversations/{id}` | |
| DELETE | `/v1/conversations/{id}` | Xóa transcript và SDK session |
| GET | `/v1/conversations/{id}/messages` | Transcript |
| POST | `/v1/conversations/{id}/messages` | `{ clientMessageId, content }`, trả `text/event-stream` |
| GET | `/v1/runs/{id}` | Trạng thái, usage |
| POST | `/v1/runs/{id}/cancel` | Dừng |
| POST | `/v1/runs/{id}/approvals/{approvalId}` | `{ decision: "approve"\|"reject" }`, trả SSE tiếp tục |

Gửi lại cùng `clientMessageId`: nếu run đã xong, trả event replay `message.completed`; đang chạy trả `409 run_in_progress`.

### Memory

| Method | Path | Mô tả |
|---|---|---|
| GET, POST | `/v1/memories` | Liệt kê, người dùng tự tạo |
| PATCH | `/v1/memories/{id}` | Tạo bản mới, bản cũ thành `superseded` |
| DELETE | `/v1/memories/{id}` | Xóa cả chuỗi |
| GET | `/v1/memory-candidates` | `pending` |
| POST | `/v1/memory-candidates/{id}/decision` | `{ decision, editedContent? }` |

## 4. Service contracts 🔒

Vị trí: `shared/src/moodprint_shared/contracts/`. Chỉ định nghĩa interface có consumer thực tế. DTO là Pydantic `frozen=True`.

```python
# contracts/auth.py
@dataclass(frozen=True, slots=True)
class AuthContext:
    user_id: UUID
    session_id: str | None
    aal: str | None
    claims_json: str = field(repr=False)   # chỉ để set_config, không log
```

`AuthContext` không chứa JWT gốc. Backend dựng nó từ token đã verify, không ai khác được tạo trong code production. Test helper nằm ở `moodprint_shared.testing`.

```python
# contracts/incidents.py  — consumer: Incident Tool, Context Builder
class IncidentService(Protocol):
    async def list_cases(self, auth: AuthContext, query: CaseQuery) -> Page[CaseSummary]: ...
    async def get_case(self, auth: AuthContext, case_id: UUID) -> CaseDetail: ...
    async def add_event(self, auth: AuthContext, case_id: UUID, data: EventCreate) -> TimelineEvent: ...

# contracts/evidence.py  — consumer: Evidence Analysis
class EvidenceService(Protocol):
    async def list_for_case(self, auth: AuthContext, case_id: UUID) -> list[EvidenceMeta]: ...
    async def get(self, auth: AuthContext, evidence_id: UUID) -> EvidenceMeta: ...
    async def open_read_url(self, auth: AuthContext, evidence_id: UUID, purpose: ReadPurpose) -> SignedRead: ...
    async def add_derivative(self, auth: AuthContext, evidence_id: UUID, data: DerivativeCreate) -> EvidenceDerivative: ...

# contracts/plans.py  — consumer: Action Plan Tool
class ActionPlanService(Protocol):
    async def get_for_case(self, auth: AuthContext, case_id: UUID) -> ActionPlan | None: ...
    async def upsert(self, auth: AuthContext, case_id: UUID, data: PlanUpsert, *, expected_version: int | None) -> ActionPlan: ...
    async def set_item_status(self, auth: AuthContext, plan_id: UUID, item_id: UUID, status: ItemStatus) -> ActionPlan: ...

# contracts/memory.py  — consumer: Context Builder, memory API
class MemoryService(Protocol):
    async def list(self, auth: AuthContext, *, status: MemoryStatus = "active") -> list[Memory]: ...
    async def create(self, auth: AuthContext, data: MemoryCreate) -> Memory: ...
    async def update(self, auth: AuthContext, memory_id: UUID, content: str) -> Memory: ...
    async def delete(self, auth: AuthContext, memory_id: UUID) -> None: ...
    async def propose(self, auth: AuthContext, data: MemoryCandidateCreate) -> MemoryCandidate: ...
    async def decide(self, auth: AuthContext, candidate_id: UUID, decision: CandidateDecision) -> Memory | None: ...
    async def search(self, auth: AuthContext, query: MemoryQuery) -> list[MemoryHit]: ...

# contracts/conversations.py  — consumer: agent_gateway
class ConversationService(Protocol):
    async def begin_turn(self, auth: AuthContext, conversation_id: UUID, client_message_id: UUID, content: str) -> TurnHandle: ...
    async def finish_turn(self, auth: AuthContext, turn: TurnHandle, result: TurnResult) -> None: ...
    async def open_session(self, auth: AuthContext, conversation_id: UUID) -> Session: ...
    async def recent_messages(self, auth: AuthContext, conversation_id: UUID, limit: int) -> list[ChatMessage]: ...

# contracts/context.py  — consumer: runtime
class ContextBuilder(Protocol):
    async def build(self, request: ContextRequest) -> ContextBundle: ...
```

`list_for_case`, `get`... đều raise `NotFound` khi không thuộc về `auth.user_id`.

### `KnowledgeRetriever` 🔒

```python
# contracts/knowledge.py
class KnowledgeFilters(BaseModel):
    age_band: Literal["11-13", "14-17"] | None = None
    topics: list[str] = []
    country_scope: list[str] = []     # ví dụ ["VN", "GLOBAL"]
    languages: list[str] = ["vi"]

class KnowledgeQuery(BaseModel):
    text: str = Field(min_length=1, max_length=1000)
    filters: KnowledgeFilters = KnowledgeFilters()
    top_k: int = Field(default=5, ge=1, le=20)

class RetrievalScope(BaseModel):
    """Không chứa định danh người dùng: corpus là công khai."""
    request_id: str
    corpus_version: str | None = None

class SourceCitation(BaseModel):
    source_id: str
    document_id: str
    title: str
    publisher: str
    url: HttpUrl | None
    section: str | None
    published_at: date | None
    last_reviewed: date | None
    applicability: str
    country_scope: list[str]

class KnowledgeChunk(BaseModel):
    chunk_id: str
    text: str
    citation: SourceCitation
    score: float                     # chuẩn hóa về [0, 1]
    match_kind: Literal["vector", "lexical", "hybrid", "fixture"]

class KnowledgeResult(BaseModel):
    status: Literal["ok", "no_results"]
    chunks: list[KnowledgeChunk]
    corpus_version: str
    latency_ms: int

class KnowledgeRetriever(Protocol):
    async def search(self, query: KnowledgeQuery, *, scope: RetrievalScope, timeout_s: float) -> KnowledgeResult: ...
```

| Điều kiện | Hành vi |
|---|---|
| Không có kết quả | `status="no_results"`, `chunks=[]`, **không raise**. Agent phải nói không tìm thấy nguồn, không tự sinh citation |
| Quá thời gian | Raise `KnowledgeTimeout`, không trả một phần |
| Hủy | Tôn trọng `asyncio.CancelledError`, không nuốt |
| Lỗi hạ tầng | Raise `KnowledgeUnavailable` |
| Input sai | Pydantic reject |
| Sắp xếp | `score` giảm dần, tie-break `chunk_id` để tất định |

Scope không có user ID: truy vấn tri thức dùng chung không được mang dữ liệu người dùng. Câu query có thể chứa nội dung nhạy cảm, nên Phase 2 không log nguyên văn.

`moodprint_shared.testing` cung cấp `FixtureKnowledgeRetriever` (từ các article tổng hợp) và lớp test `KnowledgeRetrieverContract`. Mọi adapter, gồm adapter pgvector của Phase 2, phải pass cùng lớp test này.

### `AgentToolContext` 🔒

```python
# contracts/agent.py
@dataclass(slots=True)
class AgentToolContext:
    auth: AuthContext
    request_id: str
    conversation_id: UUID
    run_id: UUID
    age_band: AgeBand | None
    services: AgentServices
    context: ContextBundle
    budget: ToolBudget
    locale: str = "vi"

@dataclass(frozen=True, slots=True)
class AgentServices:
    incidents: IncidentService
    evidence: EvidenceService
    plans: ActionPlanService
    memory: MemoryService
    knowledge: KnowledgeRetriever

@dataclass(frozen=True, slots=True)
class ToolPolicy:
    name: str
    version: str
    access: Literal["read", "prepare", "write"]
    needs_approval: bool
    timeout_s: float
    max_calls_per_run: int
```

Chữ ký tool không nhận `user_id`, `owner_id`, nên model không có cách nào chọn người dùng khác. `access="write"` bắt buộc `needs_approval=True`; registry từ chối đăng ký nếu sai.

Context không chứa DB session, secret key, engine hay JWT gốc.

### Streaming event schema 🔒

Định nghĩa trong `contracts/streaming.py`, xuất cả JSON Schema và TypeScript. Mỗi event có `v: 1`, `seq` tăng dần, `runId`.

| `event` | `data` | Ghi chú |
|---|---|---|
| `run.started` | `{ runId, conversationId, messageId }` | |
| `message.delta` | `{ messageId, text }` | |
| `message.completed` | `{ messageId, content, citations[], structured? }` | |
| `tool.started` | `{ callId, tool, label }` | `label` thân thiện, **không có tham số** |
| `tool.completed` | `{ callId, tool, ok }` | |
| `approval.required` | `{ approvalId, tool, label, preview, expiresAt }` | Run tạm dừng |
| `run.usage` | `{ inputTokens, outputTokens, totalTokens, requests, toolCalls, latencyMs }` | |
| `run.completed` | `{ status: "completed" \| "awaiting_approval" \| "cancelled" }` | |
| `run.failed` | `{ code, message, retryable }` | |
| `heartbeat` | `{}` | Mỗi 15 giây, giữ kết nối qua proxy |

Mã lỗi `run.failed`: `model_timeout`, `model_refusal`, `max_turns`, `tool_budget_exceeded`, `run_timeout`, `upstream_error`, `internal_error`.

## 5. Mock/real adapter

Port nằm ở `frontend/src/services/ports.ts`.

| Port | Mock (`demo`) | Real (`real`) | Trong `real`, mock vẫn dùng khi nào |
|---|---|---|---|
| `AuthPort` | Personas local | supabase-js | Không |
| `ProfilePort` | `useDemoStore` | `GET/PATCH /v1/me` | Không |
| `CasePort` | `demoService` | `/v1/cases` | Không |
| `EvidencePort` | Fixture | `/v1/evidence`, TUS | Không |
| `PlanPort` | `demoService` | `/v1/cases/{id}/plan` | Không |
| `TrustedContactPort` | Store | `/v1/trusted-contacts` | Không |
| `SupportPort` | Store | `/v1/support-drafts`, `/v1/shares` | Không |
| `KnowledgeStatePort` | Store | `/v1/knowledge/article-states` | Không |
| `KnowledgeCatalogPort` | Local | **Local** | Tới Phase 2 |
| `ChatPort` | Script | **Script, nhãn "AI mô phỏng"** | Tới Phase 3 |
| `AnalysisPort` | Fixture | **Fixture, nhãn mô phỏng** | Tới Phase 3 |
| `RoleplayPort` | Script | **Script** | Tới Phase 3 |
| `VoicePort` | Mô phỏng | **Mô phỏng** | Tới khi có STT/TTS |
| `SchoolDemoPort` | Store riêng | **Store riêng** | Phase sau |

**Quy tắc biên trong `real` workspace:**

1. State mô phỏng nằm trong key local riêng `moodprint-sim-v1:<userId>`, không gửi lên server.
2. `Evidence.origin = mock_fixture` bị API từ chối. UI ẩn nút đính kèm fixture vào hồ sơ thật.
3. CTA từ chat mô phỏng sang wizard chỉ prefill **văn bản**, người dùng xem và sửa rồi mới lưu. `linkedChatIds` bị loại bỏ vì chat mô phỏng không tồn tại trên server.
4. "Tạo hồ sơ từ nội dung đã xác nhận" của phân tích fixture bị ẩn, thay bằng ghi chú "bộ ảnh mẫu không thể lưu vào hồ sơ thật".
5. `demo_submitted`, `demo_reviewing`, `demo_closed` không tồn tại ở `real`. Nút gửi dùng `/v1/shares`; khi không có trường nào thì hiện "Chưa có trường kết nối", vẫn giữ Sao chép, Tải về.
