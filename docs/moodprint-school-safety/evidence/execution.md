# Ledger thực thi

Nhánh `mhiu05/feat-refactor`. Mỗi mục ghi việc đã chạy, không suy ra từ test chưa chạy.

## G0 — WS-01

| Mục | Kết quả |
| --- | --- |
| WS-01-T01 | Đã có trên `main` qua PR #45, merge commit `8b329980`, sửa `6d2662d6`. Không làm lại |
| WS-01-T02 | Merge `origin/main` vào `mhiu05/feat-refactor`. `git rev-list --left-right --count origin/main...HEAD` = `0	11` (trái = 0) |
| SHA | `1a3f488aaa7c03c8174518daa549a082255d9cda` |
| CI | [Verify local application](https://github.com/mhiu05/MoodPrint/actions/runs/42263062916) — `conclusion=success` trên đúng SHA đó. Mọi bước của job `verify` xanh, kể cả backend, migration `alembic check`, frontend, fullstack, docs, Docker |
| WS-01-T03 | Đạt |
| Gate | G0 đạt trên SHA merge. Commit sau SHA này cần CI riêng trước khi coi tip của nhánh là xanh |

### WS-01-T05 — `backend/app/ai/routes.py`

Lệnh `rg "ai.routes|from app.ai import routes"` trong `backend` không có kết quả Python. File chỉ re-export `router` từ `app.ai.chat_routes`. `main.py` mount `app.ai.chat_routes.router` trực tiếp, không import `app.ai.routes`.

Kết luận: đây là compatibility shim không được gắn vào app. Không xóa, vì task cấm xóa và hệ thống cũ đang đóng băng.

## WS-02 đang làm

T01 và T02 đi cùng commit với ledger này. Chưa push, nên chưa có CI cho SHA mới.

Đã chạy local, đều exit 0:

- `ruff check` trên các file đã sửa: pass
- `mypy` trên các module profile, eligibility, security, auth routes, database connection: pass
- `pytest` profile/migration/foundation/default flags (bỏ 2 test cần Postgres của `test_default_flags`): 48 passed, 2 deselected
- `pytest` inventory + school settings + migration: 10 passed
- `pytest tests/test_school_route_guard.py tests/test_school_settings.py`: 7 passed
- `python scripts/check_docs.py`: PASS (217 markdown, 144 API, 132 settings, 65 tables)
- `npm run typecheck` sau `contracts:generate`: pass

Chưa chạy vì Docker daemon chưa sẵn trên máy này: `tests/test_school_eligibility.py`, `tests/test_eligibility.py`, `alembic check`. CI sau khi push sẽ chạy chúng.
