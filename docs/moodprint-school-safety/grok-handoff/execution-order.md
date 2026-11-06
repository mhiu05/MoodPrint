# Thứ tự thực thi

Nhánh nền `mhiu05/feat-refactor`. Mỗi giai đoạn: điều kiện, task, file dễ xung đột, lệnh bắt buộc, gate, tiêu chí xong, rollback. Không vào giai đoạn sau khi gate trước chưa đạt.

Lệnh CI đầy đủ trước khi push ở [README](README.md#lệnh-kiểm-tra-trước-khi-push).

## Giai đoạn 0: sửa nền

| Mục | Nội dung |
| --- | --- |
| Điều kiện | Không |
| Task | WS-01-T01 → T02 → T03 → T04 → T05 |
| Xung đột | Thấp |
| Bắt buộc | Fullstack `v3.spec.ts`, CI |
| Gate | G0 |
| Xong khi | `main` xanh, nhánh đồng bộ |
| Rollback | Revert |

PR đầu đi thẳng vào `main`, vì `main` đang đỏ.

## Giai đoạn 1: khung truy cập

| Mục | Nội dung |
| --- | --- |
| Điều kiện | G0 |
| Task | WS-02-T01 → T10; WS-09-T01 sau WS-02-T09 |
| Xung đột | `config.py`, `security.py`, `contracts.py`, `main.py`, `RealApp.tsx` (chỉ phần tách export) |
| Bắt buộc | Toàn bộ backend, frontend; `alembic check` |
| Gate | Toàn bộ test default pass |
| Xong khi | Tài khoản demo vào shell rỗng; 18+ bị từ chối ở demo |
| Rollback | Bỏ `APP_PROFILE` |

**Thứ tự PR**: T01 (settings) → T02 (migration + bot id) → T03–T06 → T07 → T08 → T09 → T10.

## Giai đoạn 2: an toàn và agent

| Mục | Nội dung |
| --- | --- |
| Điều kiện | Giai đoạn 1 |
| Task | WS-03-T01 → T13; song song WS-09-T02, T03, T04 |
| Sau đó | WS-04-T01 (PR contract) → T02 → ... → T13; WS-09-T05 |
| Xung đột | `chat_routes.py`, `schemas.py`, `runtime.py`, `provider.py`, `accounting.py` |
| Bắt buộc | Regression chat, `test_accounting*`, eval offline |
| Gate | G1 |
| Xong khi | KB-B bước 1–5 chạy với model giả; eval đạt; template duyệt |
| Rollback | Revert PR con; `troly` chỉ chạy ở demo |

## Giai đoạn 3: năng lực

| Mục | Nội dung |
| --- | --- |
| Điều kiện | WS-04-T01 merge để có contract; WS-04 xong để tích hợp |
| Task | WS-05 và WS-06 song song; WS-07 sau `WS-05-T10`, `WS-06-T09`; WS-09-T06, T08–T12 theo API |
| Xung đột | `main.py`, migration, `pyproject.toml`, `uv.lock`, `tools.py` |
| Bắt buộc | Test mỗi WS, `alembic check`, eval KB |
| Gate | G2 |
| Xong khi | Bước KB-A 1–8 và KB-B 6–8 chạy |
| Rollback | Revert PR con |

**Migration theo thứ tự**: 0033 (WS-05), 0034 (WS-06), 0035 (WS-07, WS-08). Nếu WS-06 merge trước WS-05, đổi số để chuỗi thẳng. Không tạo hai head.

## Giai đoạn 4: giọng nói

| Mục | Nội dung |
| --- | --- |
| Điều kiện | WS-04 xong; có thể song song giai đoạn 3 |
| Task | WS-08-T01 → T12 |
| Xung đột | `voice/routes.py`, `accounting.py`, `config.py` |
| Bắt buộc | `test_voice*`, `test_accounting*`, spec mic giả |
| Gate | G3 |
| Xong khi | Ba chế độ chạy; TTS theo OD-04 hoặc chữ |
| Rollback | `TTS_PROVIDER=none` |

## Giai đoạn 5: tích hợp

| Mục | Nội dung |
| --- | --- |
| Điều kiện | G2, G3 |
| Task | WS-09-T13 → T17; WS-10-T01 → T05 |
| Xung đột | `playwright.config.ts`, tài liệu |
| Bắt buộc | E2E, fullstack, axe |
| Gate | G4 |
| Xong khi | KB-A/B/C xanh; checklist thủ công xong |
| Rollback | Không áp dụng |

## Giai đoạn 6: release

| Mục | Nội dung |
| --- | --- |
| Điều kiện | G4; OD-01, OD-02, OD-05, OD-11, OD-12 đã trả lời |
| Task | WS-10-T06 → T14 theo [release-runbook](release-runbook.md) |
| Gate | G5 |
| Xong khi | Sáu điều kiện |
| Rollback | Theo runbook |

## Ai làm gì ở mỗi điểm dừng

| Điểm | Owner cần |
| --- | --- |
| Trước G1 | Chỉ định người duyệt template, chốt ngưỡng, trần chi phí |
| Trước G2 | Người duyệt thẻ, `manual_capture` |
| Trước G3 | API key TTS, bake-off |
| Trước WS-09 hoàn thiện | Chọn hướng hình ảnh |
| Trước G5 | Credential, xác nhận chuyển staging |
