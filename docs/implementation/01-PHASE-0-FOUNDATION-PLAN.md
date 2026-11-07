# Phase 0 — Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Dùng TDD: viết test thất bại, chạy thấy fail, code tối thiểu, chạy thấy pass, commit.

**Goal:** dựng nền backend, agent, database, auth, storage, memory chạy được và được kiểm chứng, chưa đụng tới UI.

**Architecture:** modular monolith một process. FastAPI import `moodprint_agent`; cả hai dùng `moodprint_shared`. Dữ liệu ở schema không expose, RLS thực thi bằng `SET LOCAL ROLE authenticated`.

**Tech Stack:** Python 3.12, uv workspace, FastAPI, Pydantic 2, SQLAlchemy 2 async + asyncpg, Supabase (Postgres 17, Auth ES256, Storage), openai-agents 0.24.x, pytest, pgTAP.

**Spec:** bản yêu cầu của owner, `00-ARCHITECTURE-DECISIONS.md`, `03`, `04`, `05`.

## Global Constraints

- Không commit secret. `.env` chỉ ở root. Không in giá trị secret ra log hoặc output.
- Không chạy test tự động lên project hosted. `APP_ENV=test` chỉ chấp nhận DB loopback.
- Agent tự áp dụng migration lên hosted theo AD-19: chỉ qua `scripts/db/push_hosted.py`, chỉ sau khi test local xanh, luôn dry-run trước và chạy advisor sau. Không DDL qua MCP. MCP `execute_sql` ghi chỉ để dọn dữ liệu smoke test tổng hợp.
- Không ghi đè giá trị owner đã điền trong `.env`. Chỉ thêm biến agent tự sinh, như `DATABASE_URL` của `moodprint_api`.
- Chỉ dùng dữ liệu tổng hợp. Không tên thật, ảnh thật của học sinh.
- `moodprint_agent` không import `app`. `moodprint_shared` không import package nội bộ.
- Không có Redis, Celery, Kafka, Kubernetes, HTTP nội bộ, Alembic, feature flag.
- Mọi bảng mới đều có RLS trong cùng migration.
- Frontend không đổi trong Phase 0.
- `openai-agents` pin chính xác `==0.24.*`, nâng version là một task riêng.
- Model OpenAI duy nhất là `gpt-6-luna`, cho runtime, test, smoke và eval (AD-14). Không có model judge. Coding agent tự chấm rubric (AD-20).

## Review Focus

| # | Điều kiện | Kỳ vọng | Test tại |
|---|---|---|---|
| 1 | Hai request đồng thời của hai user dùng chung pool | Không rò claims giữa transaction | F0-03.2 `test_concurrent_users_never_share_claims` |
| 2 | Token hợp lệ của user vừa bị xóa | Thao tác nhạy cảm bị từ chối | F0-04.1 `test_sensitive_operation_rejects_deleted_user` |
| 3 | Tiếng Việt có dấu trong SDK session và memory search; tìm không dấu | Lưu đúng UTF-8, không escape; `ban than` khớp `bạn thân` | F0-07.2, F0-08.3 |
| 4 | Client ngắt SSE giữa chừng hoặc process chết giữa lượt | Run kết thúc hoặc thành `interrupted`, lượt sau chạy được | F0-07.3, F0-07.5 |
| 5 | Thiếu `.env`, hoặc `APP_ENV=test` trỏ vào host thật | Báo lỗi tên biến, không in giá trị; từ chối khởi động | F0-02.1 |

## Spike bắt buộc

Các spike nằm trong task sở hữu. Kết quả ghi vào `docs/implementation/spikes/S-0X.md`. Fail thì dùng fallback, **không** tự thiết kế lại.

| ID | Câu hỏi | Task | Fallback |
|---|---|---|---|
| S-01 | TUS có chạy với signed upload token, kể cả resume sau 2 giờ? | F0-06.2 | JWT người dùng + policy `INSERT` hẹp trên `users/<uid>/originals/*` |
| S-02 | `schema_translate_map` có hoạt động với `SQLAlchemySession`? | F0-07.2 | Engine riêng với `server_settings={"search_path": "agent_store"}` |
| S-03 | `RunState` resume được sau khi restart process? | F0-07.4 | Mẫu `prepare` + xác nhận qua API, xem `05` §3 |
| S-04 | Hai local stack chạy song song được không? | F0-05.1 | `scripts/dev/supabase_worktree.py` sinh workdir `.local/` có port offset |
| S-05 | Custom role qua Supavisor session mode + `SET LOCAL ROLE` trên hosted? | F0-10.3 | Direct connection, hoặc pooler transaction với `statement_cache_size=0` |

---

## F0-01 — Repository and dependencies

### F0-01.1 — Workspace skeleton `[P0]`

- **Mục tiêu:** `uv sync --all-packages` tạo một môi trường import được cả ba package.
- **Phụ thuộc:** không.
- **File:** tạo `pyproject.toml`, `.python-version` (`3.12`), `shared/pyproject.toml`, `shared/src/moodprint_shared/__init__.py`, `agent/pyproject.toml`, `agent/src/moodprint_agent/__init__.py`, `backend/pyproject.toml`, `backend/app/__init__.py`. Sửa `.gitignore`: thêm `.venv/`, `__pycache__/`, `*.py[cod]`, `.pytest_cache/`, `.ruff_cache/`, `.pyright/`, `.local/`, `supabase/.branches/`, `supabase/.temp/`. Xóa thư mục rỗng `backend/alembic`.
- **Dependency:** `shared`: `pydantic`, `pydantic-settings`. `agent`: `moodprint-shared`, `openai-agents[sqlalchemy]==0.24.*`. `backend`: `moodprint-shared`, `moodprint-agent`, `fastapi`, `uvicorn[standard]`, `sqlalchemy[asyncio]`, `asyncpg`, `pyjwt[crypto]`, `httpx`. Dev group ở root: `pytest`, `pytest-asyncio`, `ruff`, `pyright`, `import-linter`.
- **DB / API / Agent:** không.
- **Test:** `tests/test_workspace.py::test_packages_import_without_path_hacks` trong `shared/`.
- **Chấp nhận:** `uv lock` thành công; không có `sys.path` trong repo; `git status` không hiện `.venv`.
- **Verify:** `uv sync --all-packages && uv run python -c "import moodprint_shared, moodprint_agent, app"`

### F0-01.2 — Công cụ chất lượng `[P0]`

- **Mục tiêu:** một lệnh chạy lint, type, test.
- **Phụ thuộc:** F0-01.1.
- **File:** cấu hình `ruff`, `pyright` (strict cho `shared`, `agent`), `pytest` ở `pyproject.toml` root. Marker: `integration`, `live_agent`. Mặc định `addopts = -m "not integration and not live_agent"`. Tạo `scripts/check.py`.
- **Test:** tự chạy trên skeleton.
- **Chấp nhận:** `scripts/check.py` exit 0.
- **Verify:** `uv run python scripts/check.py`

### F0-01.3 — Ranh giới import `[P0]`

- **Mục tiêu:** chặn phụ thuộc ngược tự động.
- **Phụ thuộc:** F0-01.2.
- **File:** `.importlinter`: `shared` không import `moodprint_agent`, `app`; `moodprint_agent` không import `app`; router không import `app.infrastructure` trực tiếp ngoại trừ qua service.
- **Test:** thêm import sai tạm thời, thấy `lint-imports` fail, gỡ ra.
- **Chấp nhận:** tích hợp trong `scripts/check.py`.
- **Verify:** `uv run lint-imports`

---

## F0-02 — Configuration

### F0-02.1 — Settings `[P0]`

- **Mục tiêu:** một nguồn cấu hình, secret tách khỏi hằng số, lỗi rõ ràng.
- **Phụ thuộc:** F0-01.1.
- **File:** `shared/src/moodprint_shared/env.py`, `config.py`. `.env.example` đã có ở root (tạo 2026-11-07); chỉ sửa nếu field trong `EnvSettings` khác.
- **Chi tiết:**
  - `SUPABASE_DB_URL` (secret, optional) chỉ dùng cho script migration và `set_api_role_password.py`, app runtime không đọc.
  - `class EnvSettings(BaseSettings)`, `extra="ignore"`, tìm `.env` từ `Path(__file__).parents[3]`, không phụ thuộc cwd. `APP_ENV=test` **không** đọc `.env`, chỉ đọc biến process.
  - Secret dùng `SecretStr`: `OPENAI_API_KEY`, `VOYAGE_API_KEY`, `APIFY_API_TOKEN`, `SUPABASE_SECRET_KEY`, `DATABASE_URL`. `OPENAI_API_KEY` và nhóm tích hợp tương lai là optional, được kiểm tra khi dùng.
  - Không bí mật theo môi trường: `APP_ENV` (`development|test|production`), `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY`, `CORS_ALLOWED_ORIGINS`.
  - Frontend: `VITE_PUBLIC_SUPABASE_URL`, `VITE_PUBLIC_SUPABASE_PUBLISHABLE_KEY`, `VITE_PUBLIC_API_BASE_URL`.
  - `config.py`: `@dataclass(frozen=True) class AppConfig` gồm `AgentConfig`, `MemoryConfig`, `EvidenceConfig`, `KnowledgeConfig`, `ApiConfig`, `LoggingConfig`, giá trị theo `03` §7, `05` §2.
  - `get_settings()` cache, validate khi startup.
- **DB / API / Agent:** agent đọc `AppConfig`, nhận secret qua tham số do backend truyền.
- **Model:** `OPENAI_MODEL: Final = "gpt-6-luna"` trong `config.py`. `AgentConfig.companion_model`, `compaction_model`, `vision_model`, `eval_model` đều gán bằng hằng này. Không đọc model từ biến môi trường.
- **Test:** `shared/tests/test_settings.py`: `test_every_model_setting_is_gpt_6_luna`, `test_no_other_model_literal_in_source` (quét `shared/`, `agent/`, `backend/` tìm `gpt-*` hoặc `o<số>` khác `gpt-6-luna`), `test_missing_required_var_names_the_var_without_value`, `test_secret_not_in_repr`, `test_test_env_rejects_remote_database` (raise `UnsafeTestEnvironment` với host không phải `127.0.0.1`, `localhost`), `test_env_example_lists_every_field`, `test_env_example_has_no_values_for_secrets`.
- **Chấp nhận:** không có giá trị trùng lặp giữa `agent` và `backend`; `.env.example` chỉ placeholder.
- **Verify:** `uv run pytest shared/tests -q`

### F0-02.2 — Logging `[P0]`

- **Mục tiêu:** log có cấu trúc, không rò dữ liệu nhạy cảm.
- **Phụ thuộc:** F0-02.1.
- **File:** `shared/src/moodprint_shared/logging.py`.
- **Chi tiết:** JSON ở production, text ở dev. Filter che key `authorization`, `apikey`, `token`, `password`, `content`, `message_data`, `original_text`, chuỗi khớp pattern JWT, `sk-`, `sb_secret_`. `contextvars` cho `request_id`.
- **Test:** `test_redacts_authorization_header`, `test_redacts_jwt_inside_message`, `test_request_id_propagates`.
- **Chấp nhận:** test pass.
- **Verify:** `uv run pytest shared/tests/test_logging.py -q`

---

## F0-09.1 — Contract nháp `[P0]`

Làm **trước** backend để hai phía cùng code theo. Đóng băng ở F0-09.2.

- **Mục tiêu:** toàn bộ DTO và Protocol trong `04` §4 tồn tại và type-check.
- **Phụ thuộc:** F0-01.2.
- **File:** `shared/src/moodprint_shared/contracts/{auth,errors,paging,incidents,evidence,plans,memory,conversations,context,knowledge,agent,streaming}.py`.
- **Chi tiết:** `open_session` trả `AgentSession`, một Protocol cục bộ có `get_items`, `add_items`, `pop_item`, `clear_session`, để `shared` không phụ thuộc `openai-agents`. Error type: `NotFound`, `Forbidden`, `VersionConflict`, `RunInProgress`, `KnowledgeTimeout`, `KnowledgeUnavailable`, `QuotaExceeded`.
- **Agent:** đây là bề mặt duy nhất agent dùng.
- **Test:** `shared/tests/test_contracts.py`: DTO frozen, `AuthContext.__repr__` không chứa claims, event round-trip JSON.
- **Chấp nhận:** `pyright` strict pass.
- **Verify:** `uv run pyright shared`

---

## F0-05 — Database

### F0-05.1 — Local Supabase `[P0]`

- **Mục tiêu:** dựng được stack local có Auth, Storage, Postgres.
- **Phụ thuộc:** F0-01.1.
- **File:** `supabase/config.toml`, `scripts/dev/bootstrap_local_db.py`, `docs/implementation/spikes/S-04.md`.
- **Chi tiết:** `npx supabase@<pin> init`. Pin version trong `package.json` root hoặc biến trong script. JWT local cần khóa bất đối xứng để giống hosted: cấu hình `auth.signing_keys_path`, sinh khóa ES256 không commit vào `.local/`. Nếu CLI đang pin không hỗ trợ, ghi vào S-04 và cho phép HS256 chỉ trong `APP_ENV=test` qua `AUTH_TEST_JWT_SECRET`. Script đặt password `moodprint_api` local, xuất biến test.
- **Spike:** S-04.
- **Test:** thủ công: `npx supabase start`, `npx supabase status`.
- **Chấp nhận:** migration áp dụng từ trống; S-04 có kết luận.
- **Verify:** `npx supabase db reset`

### F0-05.2 — Extensions, schema, role `[P0]`

- **Mục tiêu:** nền bảo mật cho mọi migration sau.
- **Phụ thuộc:** F0-05.1.
- **File:** `supabase/migrations/*_f0_extensions_roles.sql`, `*_f0_private_helpers.sql`.
- **DB:** extension `vector`, `pg_trgm`, `unaccent` trong `extensions`; schema `app`, `app_private`, `agent_store`; role `moodprint_api`; `REVOKE EXECUTE ON public.rls_auto_enable` có guard; hàm trong `03` §5.
- **Test:** `supabase/tests/05_grants.sql`.
- **Chấp nhận:** `anon` không có `USAGE` trên schema mới.
- **Verify:** `npx supabase test db`

### F0-05.3 — Bảng Phase 0 `[P0]`

- **Mục tiêu:** tất cả bảng `f0_*` của `03` §4.
- **Phụ thuộc:** F0-05.2.
- **File:** `*_f0_profiles.sql`, `*_f0_conversations.sql`, `*_f0_agent_store.sql`, `*_f0_memory.sql`.
- **Test:** `00_rls_coverage.sql`, `01_owner_isolation.sql`, `06_audit_append_only.sql`, `07_memory_rules.sql`.
- **Agent:** `agent_store` khớp SDK.
- **Chấp nhận:** mọi bảng có RLS và policy; `agent_runs_one_active` chặn run thứ hai.
- **Verify:** `npx supabase db reset && npx supabase test db`

### F0-05.4 — SQLAlchemy model và drift `[P0]`

- **Mục tiêu:** model khớp DB.
- **Phụ thuộc:** F0-05.3, F0-03.2.
- **File:** `backend/app/modules/*/models.py`, `backend/tests/integration/test_schema_drift.py`.
- **Chi tiết:** model viết tay, `schema="app"`. `Base.metadata.create_all` bị cấm.
- **Test:** `test_models_match_database` so tên cột, kiểu, nullable bằng `inspect`.
- **Chấp nhận:** thêm cột giả vào migration làm test fail.
- **Verify:** `uv run pytest -m integration backend/tests/integration/test_schema_drift.py`

---

## F0-03 — FastAPI

### F0-03.1 — App factory `[P0]`

- **Mục tiêu:** app chạy, có error format chuẩn.
- **Phụ thuộc:** F0-02.2, F0-09.1.
- **File:** `backend/app/main.py`, `core/errors.py`, `core/request_id.py`, `core/deps.py`, `api/health.py`.
- **API:** `GET /health`, `GET /ready`. CORS lấy từ `CORS_ALLOWED_ORIGINS`, `allow_credentials=False` vì dùng Bearer, không wildcard.
- **Chi tiết:** `create_app(settings)`; lifespan khởi tạo engine, JWKS client, HTTP client, reconciler, và đóng tuần tự khi tắt. Request ID: nhận `X-Request-ID` nếu đúng pattern, nếu không thì sinh mới. Handler chuyển error `contracts/errors` và `RequestValidationError` sang envelope. Thông báo bằng tiếng Việt.
- **Test:** `backend/tests/test_app.py`: `test_health_needs_no_dependencies`, `test_ready_503_names_component_only`, `test_error_envelope_shape`, `test_unhandled_error_hides_details`, `test_request_id_echoed`, `test_invalid_request_id_replaced`, `test_cors_rejects_unknown_origin`, `test_startup_shutdown_closes_engine`.
- **Chấp nhận:** toàn bộ pass.
- **Verify:** `uv run pytest backend/tests/test_app.py -q`

### F0-03.2 — Engine và UnitOfWork có RLS `[P0]`

- **Mục tiêu:** cách duy nhất để chạm dữ liệu người dùng.
- **Phụ thuộc:** F0-03.1, F0-05.3.
- **File:** `backend/app/core/db.py`, `core/uow.py`, `backend/tests/integration/test_rls_context.py`.
- **Interface:**

  ```python
  def create_engine(settings: EnvSettings, cfg: AppConfig) -> AsyncEngine: ...
  class UnitOfWork:
      session: AsyncSession
  @asynccontextmanager
  async def user_uow(engine: AsyncEngine, auth: AuthContext) -> AsyncIterator[UnitOfWork]: ...
  ```

- **Chi tiết:** `user_uow` mở transaction, chạy `SET LOCAL ROLE authenticated`, `set_config('request.jwt.claims', :c, true)`. Commit khi thoát êm, rollback khi lỗi. `pool_pre_ping=True`, `pool_size` trong config. Không có helper "uow không auth" ngoài reconciler.
- **Test:** `test_auth_uid_matches_context`, `test_owner_only_sees_own_rows`, `test_claims_cleared_after_commit`, `test_rollback_clears_role`, `test_concurrent_users_never_share_claims` (50 lượt gather xen kẽ, `pool_size=2`), `test_no_transaction_held_outside_block`.
- **Chấp nhận:** sau khi commit, `current_user == 'moodprint_api'`, `auth.uid() is null` trên cùng connection.
- **Verify:** `uv run pytest -m integration backend/tests/integration/test_rls_context.py`

---

## F0-04 — Authentication

### F0-04.1 — JWT verifier `[P0]`

- **Mục tiêu:** dependency `get_auth` theo AD-07.
- **Phụ thuộc:** F0-03.1.
- **File:** `backend/app/core/auth.py`, `backend/app/infrastructure/auth_admin.py`, `backend/tests/test_auth.py`.
- **Interface:**

  ```python
  class JwtVerifier:
      def __init__(self, settings: EnvSettings, cfg: AppConfig, http: httpx.AsyncClient): ...
      async def verify(self, token: str) -> VerifiedClaims: ...
  async def get_auth(request: Request, verifier: JwtVerifier = Depends(...)) -> AuthContext: ...
  async def require_live_user(auth: AuthContext, token: str, ...) -> None: ...
  ```

- **Chi tiết:** dùng khóa test ES256 sinh trong test, JWKS giả. Allow-list thuật toán đọc từ config. Fetch JWKS không chặn event loop (`httpx`, rồi `PyJWK.from_dict`). Refetch khi lạ `kid`, tối đa một lần mỗi 60 giây. Không log token.
- **API:** chưa có route; test bằng route tạm trong test app.
- **Test:** `test_valid_token`, `test_expired`, `test_wrong_audience`, `test_wrong_issuer`, `test_alg_none_rejected`, `test_hs256_rejected`, `test_unknown_kid_refetches_once`, `test_jwks_outage_returns_503_not_401`, `test_anonymous_user_rejected`, `test_missing_sub_rejected`, `test_sensitive_operation_rejects_deleted_user`, `test_user_metadata_never_grants_role`.
- **Chấp nhận:** toàn bộ pass.
- **Verify:** `uv run pytest backend/tests/test_auth.py -q`

### F0-04.2 — Profile và `/v1/me` `[P0]`

- **Mục tiêu:** luồng end-to-end đầu tiên: token thật → RLS → DB.
- **Phụ thuộc:** F0-04.1, F0-03.2.
- **File:** `backend/app/modules/profiles/*`, `backend/app/api/v1/me.py`, `backend/tests/integration/conftest.py`, `test_me.py`.
- **API:** `GET`, `PATCH /v1/me`.
- **Chi tiết:** fixture `user_a`, `user_b` tạo qua Auth admin của local stack, đăng nhập lấy token thật. `user_metadata` chỉ seed nickname, age_band hợp lệ; sai thì để null, không fail.
- **Test:** `test_first_get_creates_profile`, `test_second_get_is_idempotent`, `test_concurrent_first_get_creates_one_row`, `test_patch_validates_nickname`, `test_user_a_cannot_read_user_b`, `test_no_token_401`, `test_metadata_invalid_age_band_ignored`.
- **Chấp nhận:** dùng JWT thật từ local Auth.
- **Verify:** `uv run pytest -m integration backend/tests/integration/test_me.py`

### F0-04.3 — Phân biệt client Supabase `[P0]`

- **Mục tiêu:** ghi rõ và ép bằng test ai dùng khóa nào.
- **Phụ thuộc:** F0-04.2.

| Client | Khóa | Ở đâu | Dùng cho |
|---|---|---|---|
| Browser `supabase-js` | Publishable | `frontend/` (F1-01) | Chỉ Auth |
| Backend Postgres | `DATABASE_URL` của `moodprint_api` | `core/db.py` | Dữ liệu |
| `StorageGateway` | Secret | `infrastructure/storage_gateway.py` | Signed URL, xóa, info |
| `AuthAdmin` | Secret | `infrastructure/auth_admin.py` | Xóa user, `get_user` |

- **Test:** `backend/tests/test_secret_scope.py::test_secret_key_read_only_in_infrastructure` quét source: `supabase_secret_key` chỉ xuất hiện trong `app/infrastructure/`, `shared/env.py`, và wiring `main.py`.
- **Chấp nhận:** test pass.
- **Verify:** `uv run pytest backend/tests/test_secret_scope.py -q`

---

## F0-06 — Storage

### F0-06.1 — Bucket và gateway `[P0]`

- **Mục tiêu:** bucket private, gateway duy nhất.
- **Phụ thuộc:** F0-05.2, F0-04.3.
- **File:** `*_f0_storage_bucket.sql`, `backend/app/infrastructure/storage_gateway.py`, `backend/app/modules/evidence/keys.py`, `storage_keys` test.
- **DB:** bucket đã có trên hosted. Migration vẫn `insert ... on conflict (id) do nothing` để local stack có bucket, rồi assert `public=false`, `file_size_limit is null`, `allowed_mime_types is null`, raise nếu sai.
- **Interface:**

  ```python
  class StorageGateway:
      async def create_upload_token(self, key: str) -> SignedUpload: ...
      async def object_info(self, key: str) -> ObjectInfo | None: ...
      async def create_download_url(self, key: str, ttl_s: int, *, attachment_name: str | None) -> str: ...
      async def delete(self, keys: list[str]) -> None: ...

  def original_key(owner_id: UUID, evidence_id: UUID, mime: str | None) -> str: ...
  def derived_key(owner_id: UUID, evidence_id: UUID, kind: str, derivative_id: UUID, ext: str) -> str: ...
  ```

- **Test:** `test_keys_never_contain_filename`, `test_unknown_mime_has_no_extension`, `test_original_and_derived_prefixes_disjoint`, `test_bucket_is_private` (integration), `test_bucket_has_no_limits` (integration).
- **Chấp nhận:** gateway không có method nào chấp nhận `upsert`.
- **Verify:** `uv run pytest -m integration backend/tests/integration/test_storage_gateway.py`

### F0-06.2 — Spike upload và phân quyền `[P0]`

- **Mục tiêu:** chứng minh AD-08 trên local stack.
- **Phụ thuộc:** F0-06.1.
- **File:** `backend/tests/integration/test_storage_access.py`, `docs/implementation/spikes/S-01.md`. Evidence API đầy đủ thuộc F1-03.
- **Spike:** S-01. Dùng `tuspy` hoặc `tus-js-client`: upload file 20 MB, chunk 6 MB; dừng giữa chừng, resume; thử token gần hết hạn; xác nhận `x-signature` cần cho request nào.
- **Test:** `test_signed_token_uploads_small_file`, `test_tus_resume_after_interruption`, `test_cannot_overwrite_existing_object`, `test_user_jwt_cannot_read_object`, `test_user_jwt_cannot_list_bucket`, `test_anon_cannot_read`, `test_download_url_expires`, `test_user_a_token_not_usable_on_other_key`.
- **Chấp nhận:** có kết luận S-01; nếu dùng fallback thì cập nhật `03` §7 và AD-08 cùng commit.
- **Verify:** `uv run pytest -m integration backend/tests/integration/test_storage_access.py`

---

## F0-08 — Memory (bắt buộc ở Phase 0)

### F0-08.1 — Memory CRUD `[P0]`

- **Mục tiêu:** tạo, đọc, sửa, xóa memory đã duyệt.
- **Phụ thuộc:** F0-04.2.
- **File:** `backend/app/modules/memory/{models,repository,service,schemas}.py`, `backend/app/api/v1/memories.py`.
- **API:** `/v1/memories`.
- **Agent:** implement `MemoryService`.
- **Test:** `test_create_read`, `test_duplicate_active_returns_existing`, `test_normalized_duplicate_detected`, `test_update_supersedes_old`, `test_delete_removes_whole_chain`, `test_user_b_gets_404`, `test_length_limit`, `test_list_excludes_superseded`.
- **Chấp nhận:** sau `delete`, nội dung không còn ở bất kỳ row nào.
- **Verify:** `uv run pytest -m integration backend/tests/integration/test_memory_crud.py`

### F0-08.2 — Candidate lifecycle `[P0]`

- **Mục tiêu:** model chỉ đề xuất, người dùng duyệt.
- **Phụ thuộc:** F0-08.1.
- **File:** `modules/memory/service.py`, `api/v1/memories.py`.
- **API:** `/v1/memory-candidates`.
- **Test:** `test_propose_does_not_create_memory`, `test_approve_creates_with_provenance`, `test_approve_with_edit_uses_edited_text`, `test_reject_creates_nothing`, `test_expired_cannot_be_approved`, `test_decide_twice_conflict`, `test_supersede_via_candidate`, `test_user_b_cannot_decide`.
- **Chấp nhận:** không có code path nào ghi `user_memories` mà không qua `create` do người dùng gọi hoặc `decide`.
- **Verify:** `uv run pytest -m integration backend/tests/integration/test_memory_candidates.py`

### F0-08.3 — Retrieval cơ bản `[P0]`

- **Mục tiêu:** lấy memory liên quan xuyên conversation.
- **Phụ thuộc:** F0-08.1.
- **File:** `agent/src/moodprint_agent/memory/retrieval.py` (công thức điểm thuần), `backend/app/modules/memory/repository.py` (SQL).
- **Test:** `test_search_returns_relevant`, `test_search_without_diacritics` (`ban than` khớp `bạn thân`), `test_no_match_returns_empty_not_all`, `test_excludes_expired_and_superseded`, `test_scoped_to_owner`, `test_limit_respected`, `test_updates_last_retrieved_at`, `test_ordering_deterministic`.
- **Chấp nhận:** memory tạo ở conversation 1 tìm được ở conversation 2.
- **Verify:** `uv run pytest -m integration backend/tests/integration/test_memory_search.py`

### F0-08.4 — Context Builder `[P0]`

- **Mục tiêu:** pipeline trong `05` §5.
- **Phụ thuộc:** F0-08.3, F0-09.1.
- **File:** `agent/src/moodprint_agent/memory/context_builder.py`, `agent/tests/test_context_builder.py`.
- **Test (dùng fake service):** `test_memory_included_when_relevant`, `test_not_every_memory_included`, `test_budget_drops_lowest_priority_and_records_it`, `test_dedupes_by_hash`, `test_stale_memory_labeled`, `test_provenance_on_every_item`, `test_memory_service_failure_degrades_with_dropped_reason`, `test_identity_has_no_email`, `test_stable_order`.
- **Chấp nhận:** không có import DB trong module.
- **Verify:** `uv run pytest agent/tests/test_context_builder.py -q`

---

## F0-07 — Agent runtime

### F0-07.1 — Companion, registry, budget `[P0]`

- **Mục tiêu:** agent tối thiểu với `ScriptedModel`.
- **Phụ thuộc:** F0-09.1.
- **File:** `agent/src/moodprint_agent/{companion,context,budget,errors}.py`, `tools/{registry,diagnostics}.py`, `prompts/companion_v1.md`.
- **Test:** `test_registry_rejects_write_without_approval`, `test_tool_signature_has_no_user_id`, `test_get_server_time_runs`, `test_per_tool_limit`, `test_run_budget_exceeded`, `test_tools_version_changes_with_policy`, `test_prompt_version_exposed`.
- **Chấp nhận:** `get_server_time` chạy qua `Runner.run` với `ScriptedModel`, không cần API key.
- **Verify:** `uv run pytest agent/tests -q`

### F0-07.2 — Conversation và SDK session `[P0]`

- **Mục tiêu:** Layer A bền vững.
- **Phụ thuộc:** F0-07.1, F0-03.2.
- **File:** `agent/src/moodprint_agent/memory/session.py`, `backend/app/modules/conversations/*`, `backend/app/api/v1/conversations.py` (CRUD, messages GET), `spikes/S-02.md`.
- **Spike:** S-02.
- **Test:** `test_sdk_tables_match_sdk_metadata`, `test_session_survives_engine_restart` (dispose engine, tạo mới, đọc lại), `test_vietnamese_stored_as_utf8_not_escaped`, `test_open_session_rejects_other_owner`, `test_begin_turn_idempotent_on_client_message_id`, `test_second_concurrent_turn_409`, `test_delete_conversation_clears_sdk_rows`, `test_app_messages_independent_of_sdk_items`.
- **Chấp nhận:** session đọc lại đúng sau khi tạo engine mới.
- **Verify:** `uv run pytest -m integration backend/tests/integration/test_conversations.py`

### F0-07.3 — Runtime và SSE `[P0]`

- **Mục tiêu:** endpoint stream hoạt động.
- **Phụ thuộc:** F0-07.2, F0-08.4.
- **File:** `agent/src/moodprint_agent/{runtime,events}.py`, `backend/app/agent_gateway/{wiring,sse}.py`, route trong `api/v1/conversations.py`.
- **API:** `POST /v1/conversations/{id}/messages`, `GET /v1/runs/{id}`, `POST /v1/runs/{id}/cancel`.
- **Test:** `test_event_order` (`run.started` trước, `run.usage`, `run.completed` cuối), `test_seq_monotonic`, `test_tool_events_have_no_arguments`, `test_usage_persisted_to_agent_runs`, `test_model_error_maps_to_run_failed_without_raw_text`, `test_run_timeout_cancels`, `test_max_turns_failed`, `test_client_disconnect_run_completes_and_persists`, `test_heartbeat_emitted`, `test_tracing_disabled_and_store_false`, `test_events_validate_against_schema`.
- **Chấp nhận:** với `ScriptedModel`, gửi tin → nhận stream → reload `GET messages` thấy cả hai tin.
- **Verify:** `uv run pytest -m integration backend/tests/integration/test_agent_stream.py`

### F0-07.4 — Approval contract `[P1]`

- **Mục tiêu:** ổn định luồng tạm dừng, để Phase 3 chỉ thêm tool.
- **Phụ thuộc:** F0-07.3.
- **File:** `runtime.py`, `backend/app/modules/conversations/approvals.py`, `spikes/S-03.md`. Tool test-only trong `agent/tests/`.
- **API:** `POST /v1/runs/{id}/approvals/{approvalId}`.
- **Spike:** S-03.
- **Test:** `test_write_tool_pauses_run`, `test_approve_resumes`, `test_reject_returns_message_to_model`, `test_serialized_state_has_no_auth_claims`, `test_other_user_cannot_approve`, `test_expired_approval_rejected`, `test_double_decide_conflict`, `test_resume_after_runtime_recreated`.
- **Chấp nhận:** S-03 có kết luận; hợp đồng `approval.required` giữ nguyên dù chọn fallback.
- **Verify:** `uv run pytest -m integration backend/tests/integration/test_agent_approval.py`

### F0-07.5 — Reconciler `[P1]`

- **Mục tiêu:** dọn trạng thái kẹt.
- **Phụ thuộc:** F0-07.3, F0-06.1.
- **File:** `backend/app/jobs/reconcile.py`, migration thêm hàm trong `app_private`.
- **Test:** `test_stale_run_marked_interrupted`, `test_next_turn_repairs_session_after_crash`, `test_second_reconciler_skips_locked_rows`, `test_reconciler_cannot_read_content`, `test_pending_upload_expires`.
- **Chấp nhận:** giả lập crash bằng cách để run ở `running` với heartbeat cũ; lượt sau chạy được.
- **Verify:** `uv run pytest -m integration backend/tests/integration/test_reconcile.py`

---

## F0-09.2 — Đóng băng contract `[P0]`

- **Mục tiêu:** chuẩn bị điều kiện cho Phase 2/3.
- **Phụ thuộc:** F0-07.3, F0-08.4.
- **File:** `shared/src/moodprint_shared/testing/{knowledge_fixture,knowledge_contract,auth}.py`, `shared/contract-schemas/*.json`, `scripts/export_contract_schemas.py`, `shared/tests/test_contract_snapshot.py`.
- **Chi tiết:** `FixtureKnowledgeRetriever` đọc dữ liệu tổng hợp từ `shared/src/moodprint_shared/testing/data/knowledge_fixture.json`. `moodprint_agent/knowledge/__init__.py` có `create_retriever(cfg)`, chỉ trả fixture.
- **Test:** `KnowledgeRetrieverContract`: `test_ok_shape`, `test_no_results_is_not_error`, `test_top_k_respected`, `test_sorted_by_score`, `test_filters_apply`, `test_timeout_raises`, `test_cancellation_propagates`, `test_deterministic`. Snapshot JSON Schema: đổi contract làm test fail.
- **Chấp nhận:** Phase 3 có thể chạy tool test với fixture; Phase 2 chỉ cần viết adapter mới.
- **Verify:** `uv run pytest shared/tests -q`

---

## F0-10 — Verification

### F0-10.1 — Cổng kiểm tra `[P0]`

- **Mục tiêu:** một lệnh chạy toàn bộ.
- **Phụ thuộc:** tất cả task P0.
- **File:** `scripts/verify_phase0.py`.
- **Chi tiết:** chạy tuần tự `scripts/check.py`, `npx supabase db reset`, `npx supabase test db`, `pytest -m integration`, `get_advisors` thủ công trên local. Bảo đảm frontend không đổi: `git diff --stat <base> -- frontend` rỗng.
- **Test:** tự thân.
- **Chấp nhận:** mọi mục `07` §3 pass.
- **Verify:** `uv run python scripts/verify_phase0.py`

### F0-10.2 — CI `[P1]`

- **Mục tiêu:** có CI trước khi làm song song.
- **Phụ thuộc:** F0-10.1.
- **File:** `.github/workflows/ci.yml`: Python check, frontend check, integration với `supabase start`. Không dùng secret thật.
- **Chấp nhận:** CI xanh trên branch.
- **Verify:** Xem run trên GitHub sau khi owner cho phép push.

### F0-10.3 — Áp dụng lên hosted `[P0]`

- **Mục tiêu:** hosted có baseline, xác nhận S-05. Agent tự làm.
- **Phụ thuộc:** F0-10.1, F0-11.1, O-01 (`SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY`, `SUPABASE_SECRET_KEY`, `SUPABASE_DB_URL` đã điền trong `.env`).
- **File:** `scripts/db/push_hosted.py`, `scripts/db/set_api_role_password.py`, `scripts/smoke_hosted.py`.
- **Chi tiết:**
  1. `push_hosted.py --dry-run`: in danh sách file sẽ áp dụng. Script dừng nếu có file không nằm trong `supabase/migrations/` của commit hiện tại, hoặc nếu hosted có migration không tồn tại trong repo.
  2. Agent tự đọc danh sách, rồi `push_hosted.py --apply`.
  3. `set_api_role_password.py`: sinh password 32 byte, `alter role moodprint_api login password ...` qua `SUPABASE_DB_URL`, ghi hoặc thay dòng `DATABASE_URL` trong `.env`, không in.
  4. MCP `list_migrations`, `list_tables(["app","app_private","agent_store"])`, `get_advisors` security và performance.
  5. `smoke_hosted.py`: `/ready`; tạo user tổng hợp `smoke+<uuid>@example.test` bằng Auth admin, đã confirm; `GET /v1/me`; tạo và xóa một memory; tải 1 KB lên bucket qua signed token rồi xóa; xóa user. Luôn dọn dẹp trong `finally`.
- **Spike:** S-05.
- **Chấp nhận:** lịch sử migration hosted khớp tên file; advisor không còn WARN `rls_auto_enable`, không có `rls_disabled_in_public` hay `policy_exists_rls_disabled`; smoke pass; không còn user, object smoke.
- **Verify:** output script và advisor ghi vào `docs/implementation/reports/phase-0-report.md`.

---

## F0-11 — Cấu hình hosted qua dashboard

### F0-11.1 — Kiểm tra và cấu hình project bằng Chrome `[P0]`

- **Mục tiêu:** đặt các cấu hình mà MCP không làm được, ghi lại trạng thái thật.
- **Phụ thuộc:** không (làm song song từ đầu Phase 0). Cần trình duyệt đã đăng nhập Supabase.
- **Công cụ:** Claude in Chrome. Gọi `tabs_context_mcp` trước, mở tab mới tới `https://supabase.com/dashboard/project/xhlshihobyxrgfqrdafh`. Không bấm hành động xóa project, reset password database, rotate key, hay nâng gói tính phí.
- **Việc làm:**

| Mục | Nơi trên dashboard | Giá trị |
|---|---|---|
| Gói, region, compute | Settings → General / Billing | Chỉ đọc, ghi vào báo cáo |
| Global file size limit | Storage → Settings | Mức tối đa gói cho phép (Free 50 MB, Pro tới 500 GB). Nếu Free, ghi rõ và báo owner, không nâng gói |
| Bucket | Storage → `incident-evidence` | Xác nhận private, không giới hạn |
| Site URL | Authentication → URL Configuration | `http://127.0.0.1:5173` cho dev |
| Redirect URLs | Như trên | `http://127.0.0.1:5173/**`, `http://127.0.0.1:5178/**`, `http://localhost:5173/**` |
| Email confirmation | Authentication → Providers → Email | Bật |
| Anonymous sign-ins | Authentication → Settings | Tắt |
| Mật khẩu | Authentication → Providers → Email | Tối thiểu 8 ký tự; bật leaked password protection nếu gói có |
| JWT expiry | Authentication → Settings / JWT | 3600 giây |
| Signing key | Authentication → JWT signing keys | Xác nhận ES256 đang dùng |
| SMTP | Authentication → Emails → SMTP | **Không đổi** ở Phase 0/1. Smoke test tạo user đã confirm qua admin API; email thật chỉ cần khi có người dùng ngoài |
| Data API exposed schemas | Settings → Data API | Chỉ `public`, `graphql_public`. Không thêm `app` |
| Pooler host | Connect → Session pooler | Ghi host và region vào báo cáo để kiểm `.env` |

- **File:** `scripts/check_hosted_auth_settings.py`, phần cấu hình trong `docs/implementation/reports/phase-0-report.md`.
- **DB / API / Agent:** không đổi code ứng dụng.
- **Test:** script gọi `GET {SUPABASE_URL}/auth/v1/settings` với publishable key, kiểm signup bật, autoconfirm email tắt, anonymous sign-in tắt. Đối chiếu tên trường thật trong response trước khi viết assert. Không in key.
- **Chấp nhận:** bảng trên có giá trị thật trong `phase-0-report.md`, kèm ảnh chụp không chứa secret.
- **Verify:** `uv run python scripts/check_hosted_auth_settings.py`

---

## Thứ tự và tiêu chí xong

Xem đồ thị trong `08`. Phase 0 xong khi:

- [ ] Mọi task P0 pass, `scripts/verify_phase0.py` exit 0.
- [ ] S-01..S-05 có kết luận.
- [ ] `07` §3 đạt.
- [ ] `docs/implementation/reports/phase-0-report.md` có bằng chứng, nêu rõ mục nào fallback.
