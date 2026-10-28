# Cấu hình backend

Nguồn: [Settings](../../backend/app/core/config.py) và [EmbeddingSettings](../../backend/app/ai/embedding_config.py). Bảng lấy từ khai báo mã nguồn, không đọc `.env` hoặc giá trị runtime. Tên biến môi trường là tên field viết HOA. JSON list dùng cho trường danh sách.

Global flag chỉ mở capability; người dùng vẫn cần eligibility, consent và preference tương ứng. `backend/local-mvp.env.example` có thể bật giá trị khác mặc định. Production validation yêu cầu HTTPS origin/Auth, publishable key, database và các provider settings khi feature bật.

| Biến | Kiểu Python | Mặc định trong mã |
| --- | --- | --- |
| `APP_ENV` | `Literal['development', 'test', 'production']` | `'development'` |
| `DATABASE_URL` | `SecretStr &#124; None` | `None` |
| `DATABASE_MIGRATION_URL` | `SecretStr &#124; None` | `None` |
| `DATABASE_POOL_MODE` | `Literal['direct', 'session', 'transaction']` | `'session'` |
| `SUPABASE_URL` | `str` | `''` |
| `SUPABASE_PUBLISHABLE_KEY` | `SecretStr` | `SecretStr('')` |
| `FRONTEND_ORIGIN` | `str` | `'http://127.0.0.1:5173'` |
| `COOKIE_SECURE` | `bool` | `False` |
| `OPENAI_API_KEY` | `SecretStr` | `SecretStr('')` |
| `OPENAI_MODEL` | `str` | `''` |
| `AI_ENABLED` | `bool` | `False` |
| `AI_ACCOUNTING_ENABLED` | `bool` | `False` |
| `AI_LOCAL_TEST_USER_IDS` | `list[UUID]` | `list` |
| `STT_ENABLED` | `bool` | `False` |
| `STT_MODEL` | `str` | `''` |
| `SANDBOX_ENABLED` | `bool` | `False` |
| `CHAT_HISTORY_ENABLED` | `bool` | `True` |
| `CHAT_RETENTION_DAYS` | `int` | `30` |
| `AI_GLOBAL_CONCURRENCY` | `int` | `50` |
| `AI_USER_CONCURRENCY` | `int` | `2` |
| `AI_REQUESTS_PER_MINUTE` | `int` | `20` |
| `AI_TIMEOUT_SECONDS` | `float` | `30` |
| `DATABASE_POOL_SIZE` | `int` | `8` |
| `DATABASE_POOL_OVERFLOW` | `int` | `4` |
| `DATABASE_POOL_TIMEOUT` | `float` | `10` |
| `SESSION_IDLE_HOURS` | `int` | `12` |
| `SESSION_MAX_DAYS` | `int` | `7` |
| `STATIC_DIR` | `str` | `''` |
| `MATCHING_SCORER` | `Literal['v1', 'v2', 'shadow']` | `'v1'` |
| `ACTIVITIES_ENABLED` | `bool` | `False` |
| `ACTIVITY_KINDS` | `list[Literal['icebreaker', 'coop_quiz', 'focus']]` | `['icebreaker', 'coop_quiz', 'focus']` |
| `FOCUS_TEST_PLAN_SECONDS` | `int &#124; None` | `None` |
| `MODERATION_ADMIN_ENABLED` | `bool` | `False` |
| `AI_DAILY_TURNS_PER_USER` | `int` | `60` |
| `AI_DAILY_BUDGET_USD` | `float` | `0` |
| `GUEST_AUTH_ENABLED` | `bool` | `False` |
| `GUEST_PAID_ENABLED` | `bool` | `False` |
| `GUEST_SEMANTIC_ENABLED` | `bool` | `False` |
| `FEEDBACK_ENABLED` | `bool` | `False` |
| `FEEDBACK_ADMIN_ENABLED` | `bool` | `False` |
| `PRODUCT_TOUR_ENABLED` | `bool` | `False` |
| `RELEASE_VERSION` | `str` | `'unknown'` |
| `GUEST_DAILY_BUDGET_USD` | `Decimal &#124; None` | `None` |
| `GUEST_PRICING_JSON` | `dict[str, Any]` | `dict` |
| `GUEST_ABUSE_HMAC_KEY` | `SecretStr` | `SecretStr('')` |
| `GUEST_CAPTCHA_SITE_KEY` | `str` | `''` |
| `GUEST_AI_TURNS` | `int` | `25` |
| `GUEST_AI_PER_MINUTE` | `int` | `6` |
| `GUEST_AI_CONCURRENCY` | `int` | `1` |
| `GUEST_AI_GLOBAL_CONCURRENCY` | `int` | `10` |
| `GUEST_VOICE_CLIPS` | `int` | `6` |
| `GUEST_VOICE_SECONDS` | `int` | `180` |
| `GUEST_VOICE_PER_MINUTE` | `int` | `2` |
| `GUEST_VOICE_CONCURRENCY` | `int` | `1` |
| `GUEST_VOICE_GLOBAL_CONCURRENCY` | `int` | `3` |
| `SEMANTIC_MEMORY_ENABLED` | `bool` | `False` |
| `VOYAGE_API_KEY` | `SecretStr` | `SecretStr('')` |
| `VOYAGE_MODEL` | `str` | `'voyage-4-lite'` |
| `VOYAGE_DIMENSIONS` | `Literal[256, 512, 1024, 2048]` | `1024` |
| `VOYAGE_TIMEOUT_SECONDS` | `float` | `10` |
| `EMBEDDING_JOB_BATCH_SIZE` | `int` | `10` |
| `EMBEDDING_MAX_ATTEMPTS` | `int` | `4` |
| `EMBEDDING_LEASE_SECONDS` | `int` | `60` |
| `MEMORY_RETRIEVAL_LIMIT` | `int` | `6` |
| `MEMORY_FALLBACK_LIMIT` | `int` | `100` |
| `MEMORY_SIMILARITY_THRESHOLD` | `float` | `0.3` |
| `MEMORY_CONTEXT_CHAR_LIMIT` | `int` | `1200` |
| `PROVIDER_FORCE_IPV4` | `bool` | `False` |

## Nhóm vận hành

- **Database:** runtime URL dùng role tối thiểu; migration URL dùng owner riêng. `DATABASE_POOL_MODE` ghi nhận lựa chọn topology; connection implementation vẫn cần đối chiếu endpoint/pooling thực tế. Prepared statements bị tắt ở connection layer.
- **AI:** `AI_ENABLED`, model/key, concurrency/rate/timeout; daily USD budget cần accounting. `AI_LOCAL_TEST_USER_IDS` chỉ được phép ở development, không phải production bypass.
- **History:** `CHAT_HISTORY_ENABLED` và retention là capability global; preference mặc định của user vẫn tắt.
- **Embedding:** Voyage credentials + semantic capability + user opt-in/MEM. `PROVIDER_FORCE_IPV4` chỉ dùng xử lý network khi cần, không thay authorization.
- **Social:** scorer mặc định v1; activities và moderation admin mặc định tắt. `ACTIVITY_KINDS` là rollout subset.
- **Sandbox:** hiện không có model tool thực thi code/file; không cần bật để chạy các bot hiện tại.

## Cách thay đổi an toàn

1. Sửa `.env` cục bộ có chủ đích, không ghi đè file hiện có hoặc đưa giá trị vào commit/log.
2. Validate bằng `uv run --locked python ../scripts/check_config.py` từ backend; đọc phạm vi script trước khi dùng cấu hình hosted.
3. Restart process để Settings mới có hiệu lực; kiểm tra live/ready và capability qua session.
4. Test cả flag on/off và thiếu dependency; không thay unavailable bằng fake response.

Frontend không nhận secrets từ bảng này. `MOODPRINT_API_PROXY` là biến Vite dev-server, không phải Settings field. `TEST_DATABASE_URL` là cấu hình harness riêng và không fallback sang DATABASE_URL.

Giá trị cấu hình và hiệu lực có thể khác nhau: saved-chat retention bị clamp tối đa 30 ngày trong persistence/routes; `SESSION_MAX_DAYS` đặt cookie max-age, còn server kiểm tra sliding idle expiry. Xem [lifecycle](data-lifecycle.md), [Auth](../supabase/auth.md).
