# Backend

Backend Python 3.12/FastAPI là modular monolith, dùng async SQLAlchemy + psycopg, Pydantic DTO và Alembic. [pyproject.toml](../../backend/pyproject.toml) cùng [uv.lock](../../backend/uv.lock) quyết định dependencies. Chạy từ `backend/` bằng `uv run --locked python -m app`; CLI cấu hình selector event loop cho psycopg trên Windows.

## Composition root

[create_app](../../backend/app/main.py) tạo Settings, Database, AiRuntime, transcriber tùy flag; cài error handling, body limit, security headers, health routes và các router. Không migration ở startup. Lifespan recover run metadata, khởi chạy sweeper/indexer và đóng tasks/clients/engine khi shutdown.

| Module | Trách nhiệm | Dữ liệu chính |
| --- | --- | --- |
| `auth` | Password/provider flow, app session, eligibility | User, AuthSession, AgeDeclaration |
| `consent` | Quyền theo purpose, version và invalidation | Consent, ConsentEvent |
| `profiles` | Taxonomy cho hồ sơ kết nối | taxonomy JSON |
| `mood` | Nhật ký ngày local, summary có nguồn | Mood |
| `ai` | Conversation, runs, tools, history, memory, embeddings | AI tables, Memory |
| `social` | Public profile, discovery, requests, room/message, notifications | PublishedProfile, Pair, Connection |
| `matching` | Scoring, ranking, explanations, stats | Hàm thuần + aggregate counters |
| `activities` | State machine và shared activity projections | ActivitySession, Participant, Response |
| `moderation` | Identity reveal, reports, staff decision/enforcement | IdentityField, RevealAccess, Report |
| `users` | Export, deletion jobs và account lifecycle | DataJob |
| `voice` | Validate audio, transcribe, preview text | Không lưu audio trong application DB |

`core` giữ cross-cutting policies; `infrastructure/database` giữ connection và shared ORM. Module có thể gọi service/hook của module khác trong cùng transaction; không giả định có message broker hoặc background queue phân tán. `Outbox` là model tương thích cũ, không phải delivery path active của AI/social.

Đọc [API](api.md), [API inventory](api-reference.md), [cấu hình](configuration.md), [lifecycle](data-lifecycle.md), [vận hành](operations.md).
