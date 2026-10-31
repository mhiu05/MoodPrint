# 10 — Kiểm thử và tiêu chí chấp nhận

## Tầng test

| Tầng | Công cụ | Ghi chú |
| --- | --- | --- |
| Đơn vị thuần | pytest | triage, plan schema, policy, mention parser, selector policy, validator chuyên gia |
| Tích hợp SDK thật | pytest + `ScriptedModel` (lớp `agents.Model`) | `Runner`, `Agent.as_tool`, `handoff`, `input_filter`, hooks đều là mã SDK thật; chỉ model là giả. Không mock `as_tool`/`handoff` |
| Tích hợp DB | PostgreSQL disposable `*_test` | migration, CHECK, RLS, xóa tài khoản, cô lập người dùng |
| SSE | pytest + httpx stream | thứ tự, replay `afterSeq`, không trùng |
| Frontend | vitest, typecheck, build | validator stream, parser mention, model nhóm |
| E2E fixture | Playwright (`tests/*.spec.ts`) | UI với API stub |
| Full-stack | `scripts/test_fullstack.py` | backend thật + PostgreSQL + Chromium, model giả qua `/__test` |
| Trình duyệt thật | agent-browser | 1440/768/390/360, bàn phím, reduced motion, console |
| Live eval | `evals/v3_orchestration.py` | gpt-6-luna sinh, Claude chấm; ngân sách < 3 USD |

## Tiêu chí G3

Xem đề bài §19; trạng thái thật ghi ở [12](12-execution-evidence.md). Lỗi có sẵn (baseline) được liệt kê riêng, không tính là hồi quy.
