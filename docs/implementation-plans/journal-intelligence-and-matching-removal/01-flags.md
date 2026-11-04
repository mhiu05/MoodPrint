# 01 — Cờ tính năng mặc định `true`, không crash khi thiếu cấu hình

Phạm vi: yêu cầu 1. Task JI-01, JI-02. Đọc trước [00-overview.md](00-overview.md) mục Global Constraints.

Ruling bổ sung khi kiểm checkpoint A: `tests/chat_load_server.py` và `tests/social_load_server.py` cũng dùng `ALL_FEATURES_OFF` trước override của từng fixture. Test subprocess phải xóa env `FEATURE_FLAGS` do pytest ghim để phát hiện mặc định lọt vào; chỉ import cấu hình, không chạy lifespan hay provider. Giữ `chat_history_enabled=True` trong nền.

## Kiểm kê (đã đọc `backend/app/core/config.py` và `backend/app/ai/embedding_config.py`)

`Settings` có 31 field boolean. Kế hoạch tách chúng thành **cờ tính năng** (26 cờ hiện có + 2 cờ mới, mặc định `true`) và **công tắc an toàn/tương thích** (5 field, giữ `false`). Việc tách nhóm này lệch khỏi chữ "TẤT CẢ" trong yêu cầu, nên được ghi thành quyết định mở OD-01 ở [07](07-decisions-risks-unknowns.md).

"Khi thiếu cấu hình" mô tả hành vi **sau** JI-02. "Validator" là dòng hiện có trong `config.py`.

| Cờ (env) | Mặc định hiện tại → mới | Phụ thuộc / bí mật / hạ tầng | Khi thiếu cấu hình | Rủi ro khi true | Validator hiện có |
| --- | --- | --- | --- | --- | --- |
| `AI_ENABLED` | false → **true** | `OPENAI_API_KEY`, `OPENAI_MODEL` | `AiRuntime.status_for` trả `configuration_missing` (`runtime.py:155-170`); UI dùng `aiServiceMessage` | Gọi model trả tiền; trần toàn cục chỉ có khi `AI_DAILY_BUDGET_USD>0` | prod: raise nếu thiếu key/model (`config.py:209-212`) → **bỏ raise**, ghi `degraded` |
| `AI_ACCOUNTING_ENABLED` | false → **true** | bảng `ai_usage` (0006) | Chạy được; `recover_expired` lúc khởi động | Nếu `AI_DAILY_BUDGET_USD>0` mà model ngoài `CAPPED_RATES` thì `reserve_accounting` trả 503 `budget_unavailable` cho mọi lượt (`accounting.py:94-101`) | điều kiện của collaboration/V3 ở prod |
| `STT_ENABLED` | false → **true** | key + `STT_MODEL` | `main.py:267-270` chỉ tạo `OpenAITranscriber` khi đủ; voice báo không khả dụng | Chi phí STT | prod: raise (`config.py:213-216`) → **bỏ raise**, ghi `degraded` |
| `SANDBOX_ENABLED` | false → **true** | không có | Không có nơi đọc ngoài `scripts/check_config.py:66` và `scripts/export_openapi.py:23` | Không có tác dụng | — (xóa sau demo) |
| `CHAT_HISTORY_ENABLED` | true → true | — | — | — | — |
| `AI_MULTI_MESSAGE_ENABLED` | false → **true** | — | — | SSE v2 khi client yêu cầu `?protocol=2`; v1 không đổi | là tiền đề của collaboration/V3 |
| `AI_WEB_SEARCH_ENABLED` | false → **true** | accounting, budget>0, `AI_SEARCH_DAILY_BUDGET_USD`, model `gpt-6-luna`, `AI_WEB_SEARCH_PRICING_VERSION`, attestation | `search_ready` trả false (`search/policy.py:141-151`); capability báo "Tìm kiếm chưa sẵn sàng" | Phí tool | — |
| `AI_MAPS_SEARCH_ENABLED` | false → **true** | như trên + `APIFY_API_TOKEN`, build, pricing, attestation, worker | `search_ready(…,"apify")` false | Phí Apify (trần USD 0,50/run) | — |
| `MAPS_SEARCH_WORKER_ENABLED` | false → **true** | service `maps` trong compose | Cờ chỉ là lời khẳng định "có worker" trong `search_ready`; `app/jobs/maps_search.py` không đọc nó | Có token mà không chạy service `maps` thì job pending tới TTL | — |
| `AI_AGENT_SKILLS_ENABLED` | false → **true** | — | — | Skill nạp vào instructions | — |
| `PROACTIVE_ENABLED` | false → **true** | bảng 0022 | — | Người dùng tự đặt lịch | — |
| `PROACTIVE_WORKER_ENABLED` | false → **true** | proactive + AI + accounting + budget>0 | Sau JI-02: nếu thiếu tiền đề và cờ **không** đặt tường minh thì clamp về false, worker idle (`jobs/proactive.py:307`) | Chi phí check-in nền | prod: raise (`config.py:219-228`); **giữ raise khi đặt tường minh** |
| `AI_COLLABORATION_ENABLED` | false → **true** | multi_message; prod: accounting | Clamp về false nếu thiếu tiền đề và cờ đến từ mặc định | Run con tốn tiền; cap 10/ngày | raise (`config.py:173-178`, `229-231`) → raise chỉ khi đặt tường minh |
| `AI_COLLABORATION_DEFAULTS_ENABLED` | false → **true** | — | — | Cấp mặc định mọi cạnh chia sẻ cho người đủ điều kiện (`collaboration/grants.py:47-56`); hosted đã dùng | — |
| `AI_THREE_AGENT_EXPERIENCE_ENABLED` | false → **true** | bảng 0024 | — | Cohort rỗng nghĩa là **mọi** tài khoản: 5 trợ lý cũ thành chỉ đọc | là tiền đề của B/C |
| `AI_SMART_ORCHESTRATION_ENABLED` | false → **true** | A + multi_message; prod: accounting | Clamp như collaboration | Planner + specialist tốn tiền; cap 20/ngày | `config.py:180-191`, `232-234` |
| `AI_GROUP_CHAT_ENABLED` | false → **true** | như trên | Clamp | Tối đa 3 người nói/lượt | như trên |
| `ACTIVITIES_ENABLED` | false → **true** | bảng 0013 | — | API activity sống nhưng không còn UI (02); sweeper `advance_due` vẫn chạy bất kể cờ (`main.py:113-116`) | — |
| `MODERATION_ADMIN_ENABLED` | false → **true** | `StaffRole` | Route tồn tại; người không phải staff nhận 403 thay vì 404 | Lộ sự tồn tại của route admin | — (authz đã xác minh: `moderation/staff.py`, đọc lại role mỗi request, đòi re-auth 12 h) |
| `FEEDBACK_ADMIN_ENABLED` | false → **true** | `StaffRole=admin` | Như trên (`assert_feedback_admin`) | Như trên | — |
| `GUEST_AUTH_ENABLED` | false → **true** | Supabase URL/key, `GUEST_CAPTCHA_SITE_KEY`, `GUEST_ABUSE_HMAC_KEY`, DB | `experience_view` báo `configuration_missing` (`guests/availability.py:11-38`) | Đủ cấu hình thì khách vào thử được | — |
| `GUEST_PAID_ENABLED` | false → **true** | `GUEST_DAILY_BUDGET_USD>0` + `GUEST_PRICING_JSON` | `guest_paid_available` false → `GUEST_PAID_UNAVAILABLE` | Chi tiêu khách trong trần đã duyệt | — |
| `GUEST_SEMANTIC_ENABLED` | false → **true** | guest paid + Voyage | Không enqueue (`embeddings.py:111-114`) | Phí embedding của khách | — |
| `FEEDBACK_ENABLED` | false → **true** | `GUEST_ABUSE_HMAC_KEY` | `feedback_open` false (`feedback/policy.py:6-12`) | — | — |
| `PRODUCT_TOUR_ENABLED` | false → **true** | — | — | — | — |
| `SEMANTIC_MEMORY_ENABLED` | false → **true** | `VOYAGE_API_KEY` | `semantic_memory_available` false; preference người dùng vẫn mặc định false | Phí Voyage khi người dùng opt-in | prod: raise (`config.py:217-218`) → **bỏ raise** |
| `JOURNAL_SEMANTIC_ENABLED` (mới, `EmbeddingSettings`) | — → **true** | `VOYAGE_API_KEY` | Truy xuất từ khóa + gần nhất; công tắc người dùng hiển thị "chưa sẵn sàng" | Gửi văn bản nhật ký ra Voyage (03) | không raise |
| `JOURNAL_AUTO_MEMORY_ENABLED` (mới) | — → **true** | AI sẵn sàng | Không tạo job memory | Gọi model nền (04) | không raise |
| `AUTH_CAPTCHA_ENABLED` | false → **false** | phải khớp cài đặt CAPTCHA của Supabase Auth + site key | — | Bật khi Supabase không bật thì form đăng nhập đòi Turnstile không có site key: chặn đăng nhập ở dev; prod raise (`config.py:198-199`) | giữ |
| `COOKIE_SECURE` | false → **false** | HTTPS | — | Bật trên `http://127.0.0.1` thì cookie không được gửi | — |
| `PROVIDER_FORCE_IPV4` | false → **false** | mạng | — | Tùy chọn mạng, không phải tính năng | — |
| `AI_WEB_SEARCH_TOKEN_BOUND_VERIFIED` | false → **false** | xác nhận của người vận hành | — | `true` mặc định là khẳng định đã kiểm chứng trong khi chưa kiểm, tức mở khóa chặn chi phí | — |
| `APIFY_MAPS_CHARGE_BOUND_VERIFIED` | false → **false** | như trên | — | như trên | — |

Ngân sách: `AI_DAILY_BUDGET_USD` mặc định 0 = **không có trần toàn cục** (`config.py:113-116`). Khi đó collaboration/orchestration chỉ còn cap theo người/ngày (`budget_ratio=None`, `collaboration/coordinator.py:314-316`, `orchestration/workflow.py:347-349`). Search và worker proactive vẫn đóng khi budget 0. Kế hoạch không đổi mặc định này (không phải cờ), nhưng JI-51 đòi đặt budget dương trên môi trường demo (OD-02).

## JI-01 — Mặc định true + nền test cố định

**Mục tiêu:** Mọi cờ tính năng mặc định `true` và vẫn ghi đè được bằng env; suite hiện có giữ hành vi cũ nhờ nền tường minh.

**Ruling thực thi 2026-11-04:** `pytest_configure` cố định một số env feature bằng `false`; env thắng field default. Mọi test kiểm mặc định và fixture `clients_defaults` phải xóa env của toàn bộ `FEATURE_FLAGS` (cùng URL/key tùy chọn liên quan) bằng `monkeypatch.delenv(..., raising=False)` trước khi tạo `Settings(_env_file=None)`. Giữ nguyên khối bảo vệ `.env` trong `conftest.py`. Nền legacy dùng `ALL_FEATURES_OFF` ở fixture/harness; `chat_history_enabled=True`. Hai field journal mới được thêm ngay trong JI-01. Red run toàn suite sau đổi default, trước ghim nền vẫn bắt buộc.

**Files:**
- Modify: `backend/app/core/config.py` (field 25–124; thêm `FEATURE_FLAGS`, `SAFETY_SWITCHES`; **thêm luôn field** `journal_auto_memory_enabled: bool = True`, JI-30 mới dùng)
- Modify: `backend/app/ai/embedding_config.py` (`semantic_memory_enabled`; **thêm field** `journal_semantic_enabled: bool = True` và property `journal_semantic_available = journal_semantic_enabled and bool(voyage_api_key)`, JI-22/23 mới dùng). Nhờ vậy `len(FEATURE_FLAGS) == 28` đúng ngay từ JI-01 và `check_docs.py` thấy 2 setting mới trong `configuration.md` cùng commit
- Create: `backend/tests/settings_baseline.py`
- Modify: `backend/tests/conftest.py:118`, `backend/tests/e2e_server.py:70-99`, `backend/tests/proactive_load_worker.py:89` và mọi file tạo `Settings(` phụ thuộc mặc định (tìm bằng bước 2)
- Create: `backend/tests/test_default_flags.py`
- Modify: `backend/tests/test_guest_contracts.py:148-157`, `backend/tests/test_live_observability.py:58`, `backend/tests/test_three_agents.py:20-30`
- Modify: `backend/.env.example`, `backend/local-mvp.env.example`, `deploy/runtime.env.example`, `docs/backend/configuration.md` (cột mặc định), comment `deploy/compose.staging.yml:46` ("Settings defaults to false")

**Interfaces:**
- Produces: `app.core.config.FEATURE_FLAGS: tuple[str, ...]` (28 tên, mỗi tên là một field bool mặc định `True`); `SAFETY_SWITCHES: dict[str, str]` (tên → lý do, mặc định `False`); `tests.settings_baseline.ALL_FEATURES_OFF: dict[str, bool]` (= `{name: False for name in FEATURE_FLAGS} | {"chat_history_enabled": True}`).

- [ ] **Bước 1: Viết test đỏ** `backend/tests/test_default_flags.py`:

```python
from app.core.config import FEATURE_FLAGS, SAFETY_SWITCHES, Settings

def test_every_feature_flag_defaults_true():
    s = Settings(_env_file=None)
    assert len(FEATURE_FLAGS) == 28
    assert [f for f in FEATURE_FLAGS if getattr(s, f) is not True] == []

def test_safety_switches_stay_false_and_are_not_features():
    s = Settings(_env_file=None)
    assert set(SAFETY_SWITCHES) == {"auth_captcha_enabled", "cookie_secure", "provider_force_ipv4",
        "ai_web_search_token_bound_verified", "apify_maps_charge_bound_verified"}
    assert not set(SAFETY_SWITCHES) & set(FEATURE_FLAGS)
    assert all(getattr(s, f) is False for f in SAFETY_SWITCHES)

def test_every_bool_field_is_classified():
    bools = {n for n, f in Settings.model_fields.items() if f.annotation is bool}
    assert bools == set(FEATURE_FLAGS) | set(SAFETY_SWITCHES)

def test_env_can_still_disable_each_flag(monkeypatch):
    for name in FEATURE_FLAGS:
        monkeypatch.setenv(name.upper(), "false")
    s = Settings(_env_file=None)
    assert [f for f in FEATURE_FLAGS if getattr(s, f) is not False] == []
```

- [ ] **Bước 2: Chạy để thấy đỏ, rồi lập danh sách test phụ thuộc mặc định cũ**

```powershell
# backend/, DB disposable của JI-00
uv run --locked pytest -q tests/test_default_flags.py           # FAIL: FEATURE_FLAGS chưa tồn tại
```

Sau khi đổi mặc định (bước 3), **trước** khi ghim nền, chạy toàn bộ suite một lần: `uv run --locked pytest -q -p no:randomly 2>&1 | Tee-Object $env:TEMP\ji01-red.txt`. Ghi tên mọi test fail vào ledger mục JI-01 (danh sách chính thức các test giả định cờ tắt). Đã biết chắc từ đọc code:

| Test | Vì sao fail | Sửa |
| --- | --- | --- |
| `test_guest_contracts.py::test_guest_input_and_settings_defaults_fail_closed` (148-157) | Assert 6 cờ guest/feedback/tour là `False` | Đổi sang assert **fail-closed theo khả dụng**: `experience_view` → `guest_available is False`, `guest_unavailable_reason == "configuration_missing"`, `feedback_open(s) is False`, `guest_paid_available(s) is False` với `Settings(_env_file=None)` |
| `test_live_observability.py::test_local_live_actor_allowlist_is_closed_by_default…` (58) | `Settings()` đọc `.env` và `ai_enabled` giờ true | `Settings(_env_file=None, ai_enabled=False)`; test vẫn kiểm allowlist |
| `test_three_agents.py::test_bots_are_the_five_companions_by_default…` (20) | Dùng fixture `clients`, giờ V3 bật | Sau khi ghim nền (bước 4) thì pass; đổi tên thành `…_on_the_legacy_baseline…`; thêm test mới ở JI-02 cho mặc định |
| ~43 file test chat với `may`/`nhip`/`guong`/`rure`/`caunoi` qua `clients` | V3 bật + cohort rỗng làm trợ lý cũ chỉ đọc (`409 LEGACY_COMPANION`) | Ghim nền |
| `e2e_server.py` | Không đặt `ai_agent_skills_enabled`, `ai_collaboration_defaults_enabled`, `semantic_memory_enabled`, `stt_enabled`… nên đổi hành vi fullstack | `Settings(**{**ALL_FEATURES_OFF, …giá trị tường minh hiện có})` |

- [ ] **Bước 3: Đổi mặc định** trong hai file config, khai báo `FEATURE_FLAGS`/`SAFETY_SWITCHES` ngay dưới class `Settings`. Giữ nguyên comment lý do; đổi các comment "default off" thành "default on; env may disable".

- [ ] **Bước 4: Ghim nền test.** `tests/settings_baseline.py` export `ALL_FEATURES_OFF`; `conftest.py:118` thành `Settings(_env_file=None, database_url=…, **ALL_FEATURES_OFF)`; `e2e_server.py` như bảng. Test nào cố ý kiểm mặc định thì dùng `Settings(_env_file=None)` không có baseline.

- [ ] **Bước 5: Chạy lại**

```powershell
uv run --locked pytest -q tests/test_default_flags.py tests/test_guest_contracts.py tests/test_live_observability.py tests/test_three_agents.py
uv run --locked pytest -q        # kỳ vọng: số pass = baseline JI-00; mọi fail khác phải có trong danh sách "có sẵn" của JI-00
```

- [ ] **Bước 6: Đồng bộ ví dụ env và tài liệu.** Các file `*.env.example` hiện ghi `=false` tường minh, sẽ ghi đè mặc định mới và làm người đọc hiểu sai. Xóa dòng `=false` cho cờ tính năng, thay bằng comment "mặc định true; đặt false để tắt". Giữ `false` cho 5 công tắc an toàn. `docs/backend/configuration.md`: cập nhật cột mặc định và thêm 2 setting mới.

- [ ] **Bước 7: Commit**: `git add backend/app/core/config.py backend/app/ai/embedding_config.py backend/tests backend/*.example deploy/runtime.env.example deploy/compose.staging.yml docs/backend/configuration.md; git commit -m "feat(config): default every feature flag on; pin the legacy test baseline"`

**Tiêu chí chấp nhận:** 4 test mới pass; suite đầy đủ không có fail mới so với baseline JI-00; `check_docs.py` PASS.
**Rủi ro:** test bị "ghim nền" sẽ không còn kiểm hành vi mặc định. Bù lại bằng bộ test mặc định ở JI-02 và job CI "defaults" ở JI-50.
**Rollback:** revert commit; env vẫn ghi đè được từng cờ nên rollback cấu hình không cần đổi code.

## JI-02 — Validator degrade thay vì crash; khởi động với mặc định thuần

**Mục tiêu:** App khởi động và ready với mặc định thuần dù thiếu bí mật/budget; cấu hình mâu thuẫn đặt tường minh vẫn bị chặn.

**Files:**
- Modify: `backend/app/core/config.py:173-235` (validator), thêm `degraded_features()`
- Modify: `backend/app/main.py:58-62` (`create_app`: log `feature_degraded`), `scripts/check_config.py` (in danh sách degrade, không in giá trị bí mật)
- Test: `backend/tests/test_default_flags.py` (thêm), sửa test raise hiện có nếu chúng dựa trên mặc định

**Interfaces:**
- Produces: `Settings.degraded_features() -> tuple[tuple[str, str], ...]`, mỗi phần tử là cặp (tên cờ, mã lý do). Mã lý do ∈ `{"openai_configuration_missing", "stt_configuration_missing", "voyage_key_missing", "proactive_prerequisites_missing", "multi_message_disabled", "three_agents_disabled", "accounting_disabled", "apify_configuration_missing"}`. Không bao giờ chứa giá trị cấu hình.
- Quy tắc clamp (theo tiền lệ `guest_capacity_within_global`, `config.py:163-171`): cờ phụ thuộc mà thiếu tiền đề thì (a) **raise** nếu tên cờ nằm trong `model_fields_set`, tức người vận hành đặt tường minh một cấu hình mâu thuẫn; (b) **clamp về `False` và ghi lý do** nếu giá trị đến từ mặc định. Thiếu bí mật (OpenAI/STT/Voyage/Apify) **không bao giờ raise**: tính năng tự báo không khả dụng ở runtime.

- [ ] **Bước 1: Test đỏ**

```python
PROD = dict(_env_file=None, app_env="production", frontend_origin="https://moodprint.example",
            supabase_url="https://project.supabase.co", supabase_publishable_key="sb_publishable_x",
            database_url="postgresql://u:p@db.example:5432/postgres")

def test_production_defaults_boot_without_optional_secrets():
    s = Settings(**PROD)
    reasons = dict(s.degraded_features())
    assert reasons["ai_enabled"] == "openai_configuration_missing"
    assert reasons["semantic_memory_enabled"] == "voyage_key_missing"
    assert reasons["journal_semantic_enabled"] == "voyage_key_missing"
    assert s.proactive_worker_enabled is False            # clamped: budget 0
    assert ("proactive_worker_enabled", "proactive_prerequisites_missing") in s.degraded_features()

def test_explicit_contradiction_still_fails_fast():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, ai_collaboration_enabled=True, ai_multi_message_enabled=False)

def test_default_dependents_clamp_when_prerequisite_is_disabled():
    s = Settings(_env_file=None, ai_multi_message_enabled=False)
    assert not (s.ai_collaboration_enabled or s.ai_smart_orchestration_enabled or s.ai_group_chat_enabled)

async def test_app_with_pure_defaults_serves_health_and_reports_unavailable(database):
    # create_app(Settings(_env_file=None, database_url=…)) trên DB test; lifespan chạy hết
    # /api/v1/health/live == 200; /api/v1/health/ready == 200 (DB ở head)
    # session của actor seed: features.ai is False, features.aiStatus == "configuration_missing",
    # features.webSearch is False, features.mapsSearch is False

async def test_admin_routes_need_a_staff_role_not_a_flag(clients_defaults):
    # flags mặc định: GET /api/v1/admin/reports với actor thường → 403 STAFF_REQUIRED (không phải 404, không phải 200)
    # GET /api/v1/admin/feedback → 403
```

`clients_defaults` là fixture mới trong `conftest.py`: giống `clients` nhưng **không** có `ALL_FEATURES_OFF`.

- [ ] **Bước 2: Chạy để thấy đỏ:** `uv run --locked pytest -q tests/test_default_flags.py` → FAIL (`degraded_features` chưa có; `Settings(**PROD)` raise vì thiếu OpenAI key).

- [ ] **Bước 3: Cài đặt.** Thay các `raise` của `collaboration_requires_v2`, `v3_requires_three_agents` và các nhánh prod (`config.py:209-234`) theo quy tắc clamp. Lý do clamp lưu vào `PrivateAttr _clamped: list[tuple[str, str]]`; `degraded_features()` = `_clamped` + điều kiện thiếu bí mật tính tại chỗ. Giữ nguyên raise của `AUTH_CAPTCHA_ENABLED` (cờ mặc định false; bật tường minh mà thiếu site key thì chặn đăng nhập). `create_app` log mỗi cặp một dòng `feature_degraded flag=%s reason=%s` ở mức WARNING.

- [ ] **Bước 4: Rà test raise hiện có.** `rg -n "pytest.raises\(ValidationError" backend/tests/test_proactive_api.py backend/tests/test_v3_review_fixes.py backend/tests/test_multi_message_contract.py backend/tests/test_auth_captcha.py backend/tests/test_auth_flows.py`. Các test này đặt cờ tường minh (ví dụ `test_proactive_api.py:350-364`) nên vẫn phải raise và **không được sửa**. Test nào raise chỉ vì thiếu key OpenAI/STT/Voyage thì đổi thành assert `degraded_features`, ghi tên vào ledger.

- [ ] **Bước 5: Chạy:** `uv run --locked pytest -q tests/test_default_flags.py tests/test_proactive_api.py tests/test_v3_review_fixes.py tests/test_multi_message_contract.py tests/test_auth_captcha.py tests/test_ops_config.py`; `uv run --locked python ../scripts/check_config.py` (không có `.env`) in danh sách degrade, exit 0.

- [ ] **Bước 6: Deploy test Linux** (JI-50): `deploy/aws/tests/test_proactive_deployment.py` vẫn pass. Nó đặt `PROACTIVE_WORKER_ENABLED` tường minh qua runtime file.

- [ ] **Bước 7: Commit** `feat(config): degrade missing secrets instead of refusing to start`

**Tiêu chí chấp nhận:** `Settings(**PROD)` không raise; app với mặc định thuần trả `/health/ready` 200 trên DB head; admin vẫn 403 với người thường; search/guest paid vẫn đóng khi thiếu cấu hình.
**Rủi ro:** mất "fail fast" khi người vận hành quên key OpenAI trên prod. Bù lại bằng log WARNING + `check_config.py` trong preflight JI-51 (bắt buộc đọc danh sách degrade trước khi bỏ cổng bảo trì).
**Rollback:** revert commit. Env tường minh vẫn tái tạo được hành vi cũ.
