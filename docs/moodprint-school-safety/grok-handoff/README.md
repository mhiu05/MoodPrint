# Bàn giao cho Grok

Mục tiêu: tự làm từ task đầu tiên tới khi release staging thành công. Chỉ dừng hỏi owner ở các điểm ghi dưới đây và trong [12-open-decisions](../12-open-decisions.md).

Prompt khởi động: [GROK-PROMPT](GROK-PROMPT.md).

## Đọc theo thứ tự

1. [00-executive-summary](../00-executive-summary.md)
2. [01-codebase-audit](../01-codebase-audit.md)
3. [execution-order](execution-order.md)
4. [release-runbook](release-runbook.md)
5. Plan của WS đang làm trong [plans/](../plans/WS-01-codebase-migration.md)

## Việc đầu tiên

`main` đang đỏ. Làm ngay [WS-01-T01](../plans/WS-01-codebase-migration.md).

## Quy tắc nhánh

- Nhánh nền: `mhiu05/feat-refactor`.
- Nhánh con: `mhiu05/feat-refactor-wsNN-<tên>`.
- Sau mỗi WS: merge `main` vào nhánh nền, chạy lại test.
- PR dùng [pr-template](pr-template.md).

## Quyền

Theo §8.2 của prompt: sửa code, test, migration, config, CI, Dockerfile, docs mà plan yêu cầu; tạo nhánh, commit, push, PR; merge khi CI xanh và gate đạt; đồng bộ với `main`; tạo migration và SQL review; áp hosted khi có credential; kích hoạt release.

`.gitignore` chỉ sửa khi task nêu rõ. Hiện không task nào cần.

## Công cụ

| Việc | Công cụ | Ghi chú |
| --- | --- | --- |
| Database hosted | Supabase MCP | Role `postgres`. SQL hosted chỉ theo runbook, nguyên văn, đúng hash. Không dùng `apply_migration` |
| SSM, EC2, log | AWS MCP | Kiểm tra phiên ở preflight. Không in giá trị bí mật |
| Thiết kế | `.agents/skills/impeccable` | Quy trình ở [09 §1](../09-ux-and-user-flows.md#1-hướng-hình-ảnh-và-quy-trình-impeccable) |
| Agent | `openai-agents==0.24.0` | Xem [06 §11](../06-ai-orchestration-and-safety.md#11-dùng-openai-agents-python-thế-nào). Không nâng phiên bản nếu không cần |
| Chuyển động | `gsap`, `@gsap/react` | Đã cài. Xem [09 §14](../09-ux-and-user-flows.md#14-chuyển-động) |
| Thinking | `thinking-orbs` | Đã cài. Xem [09 §13](../09-ux-and-user-flows.md#13-giao-diện-thinking) |
| Eval live | `evals/budget.py` | Tổng dưới 3 USD |

## Giới hạn

Không push thẳng hay force-push `main`. Không tắt, skip, nới CI. Không xóa test. Không đưa secret vào code, log, commit, PR. Không phá dữ liệu hosted. Không quảng bá tới học sinh khi OD-15 chưa trả lời. Không điền `reviewed_by` cho mục mhiu05 chưa đánh dấu. Eval live không vượt 2,80 USD tổng. Chỉ dùng `gpt-6-luna` cho model ngôn ngữ.

## Hỏi owner khi

- Cần credential hoặc quyền chưa có.
- CI đỏ sau 3 lần thử theo 3 hướng khác nhau.
- Một gate không đạt.
- Tới mục chưa trả lời trong [12-open-decisions](../12-open-decisions.md).
- Hành vi production ở profile `default` có nguy cơ đổi.

## Lệnh kiểm tra trước khi push

Khớp `.github/workflows/verify.yml`. Từ root:

```bash
cd backend
uv sync --locked
uv run python ../scripts/disposable_postgres.py        # in environment_file
# nạp environment_file, đặt APP_ENV=test
uv run --locked ruff check app tests evals alembic
uv run --locked mypy app
uv run --locked pytest -q
uv run --locked python ../scripts/export_openapi.py
cd ../frontend
npm ci
npm run contracts:generate
git diff --exit-code -- src/api/generated/schema.d.ts ../backend/openapi.json
npm run typecheck
npm test
npm run build
npm run test:e2e
cd ../backend
uv run --locked python ../scripts/test_fullstack.py
cd ..
python scripts/check_reviewed_artifacts.py
python scripts/check_docs.py
python3 -m unittest discover -s deploy/aws/tests -v    # cần Linux
```

Backend chạy lâu: trên Windows có thể tới một giờ. Có thể chạy test liên quan khi phát triển, nhưng trước PR phải chạy đủ.

Dọn DB: `python scripts/disposable_postgres.py --remove <run_id>`.

## Bẫy đã biết

| Bẫy | Hậu quả | Cách tránh |
| --- | --- | --- |
| Thiếu cập nhật `api-reference.md`, `configuration.md`, `schema.md` | `check_docs.py` đỏ | Cập nhật cùng PR |
| Link Markdown tới file chưa có trong `docs/` | `check_docs.py` đỏ | Dùng backtick cho đường dẫn chưa có |
| Spec Playwright không có trong `testMatch` | Không chạy mà không báo | Thêm vào config |
| `model` lạ trong `ai_usage` | **Mọi lượt chat bị từ chối** | Chỉ dùng `settings.openai_model` |
| `reserve_accounting` giữ 2 USD mỗi run | Trần 20 USD đạt nhanh | Dùng hạn mức nhỏ cho call giới hạn |
| Role PostgreSQL là cluster-wide | Tạo role làm hỏng `test_runtime_provision` | Xóa role sau diễn tập |
| Sửa `frontend/` khi fullstack chạy | Vite tải lại trang | Không sửa trong lúc chạy |
| `backend/.env` trỏ hosted | Nguy hiểm | Không đọc; test dùng `_env_file=None` |
| `%%` trong SQL offline | PL/pgSQL lỗi | Dùng `'...' \|\| quote_ident(r)` |
| Tool lỗi `reasoning` chiếm `max_output_tokens` | Stream incomplete | `reasoning` thấp, `max_tokens` đủ |
| Merge `main` liên tiếp | Publish bị bỏ qua | Chờ CI của lần trước |
| `gpt-4o-mini-tts` | Tắt 06/01/2027 | Không dùng |
| Thêm route mới bằng `require_registered_actor` | Khách bị chặn | Khách dùng được mọi tính năng |
| Thêm bảng mà quên `guests/lifecycle.py` | Dữ liệu khách không tự xóa, test inventory đỏ | Cập nhật cùng PR |
| Commit ảnh chụp app | Repo công khai | Giữ trong `.tmp/` |
| Phát audio Realtime chưa kiểm tra | Nói khác văn bản đã duyệt | Luôn qua `verbatim_ok` trước |
| Chế độ song song của `input_guardrail` | Agent chạy trước khi có kết quả an toàn | `run_in_parallel=False` |

## Báo cáo

**Sau mỗi PR merge**: link PR, link CI, test đã chạy và kết quả, gate đạt hay chưa, việc tiếp theo.

**Sau release**: SHA, link workflow, output health check, smoke ba kịch bản, migration đã áp, flag đã bật, vấn đề tồn tại.

Không nói test pass nếu chưa chạy.
