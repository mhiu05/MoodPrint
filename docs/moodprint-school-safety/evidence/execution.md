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
- `mypy` trên `app/core/config.py`, `app/core/profile.py`, `app/modules/school`, `app/ai/agents.py`, `app/core/revisions.py`, `app/modules/guests/lifecycle.py`: pass
- `pytest -q tests/test_school_settings.py tests/test_default_flags.py -k "not app_with_pure and not admin_routes"`: 12 passed, 2 deselected
- `pytest -q tests/test_school_migration.py tests/test_school_settings.py tests/test_foundation.py tests/test_default_flags.py -k "not app_with_pure and not admin_routes"`: 48 passed, 2 deselected
- `pytest -q tests/test_guest_cleanup.py::test_inventory_classifies_every_orm_table tests/test_school_migration.py tests/test_school_settings.py`: 10 passed
- `python scripts/check_docs.py`: PASS (217 markdown, 144 API, 132 settings, 65 tables)
- `npm run typecheck` sau `contracts:generate`: pass

Chưa chạy trên máy này: full `pytest -q`, `alembic check` trên DB disposable, `npm test`, e2e. CI của SHA sau khi push sẽ chạy các bước đó.
