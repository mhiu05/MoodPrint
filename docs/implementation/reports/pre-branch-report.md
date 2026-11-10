# Pre-branch report

Nhánh: `integration/pre-branch-readiness`. Base dự kiến của PR: `mhiu05/feat-refactor`. Không merge vào `main`.

## Trạng thái

Source đã commit tại `a620718069c86accf9dfcb40d2dc2a37a65dcfc6`. Full foundation gate, hai stack, canary GitHub, PR, merge và tag **chưa được ghi là VERIFIED trong bản này**. Số unit dưới đây đo trước commit source. Receipt `.local/prebranch-gate.json` chỉ có giá trị khi `commit` trong file trùng `git rev-parse HEAD` sau commit tài liệu, và nó không chứng minh CI hay tag.

## Đã đo trên cây làm việc trước commit báo cáo

Lệnh:

```powershell
uv run pytest scripts/tests scripts/db/tests -q --tb=line
```

Kết quả: **648 passed**, exit 0. Suite này gồm ownership, CI ownership, migration scope/order, e2e stack và hosted push orchestration bằng fixture. Không có lời gọi hosted và không có lời gọi model trả phí.

Ba regression đã đỏ trước khi sửa, rồi xanh trong cùng suite:

- `CREATE TABLE ... INHERITS` và `PARTITION OF` bị từ chối.
- History hosted đổi trong preflight apply bị từ chối trước CLI.
- `--base` không phải ancestor bị ownership exit 2.

## Chưa đo ở bản này

- `scripts/verify_prebranch.py` và `scripts/verify_phase1.py` trên SHA sạch.
- Hai stack `kb`/`ag` đồng thời, pgTAP, Auth/Storage, demo E2E exit 0.
- `migration_order_check.py` trên stack local thật. Khi chưa có migration `kb_`/`ag_`, kết quả harness chỉ chứng minh baseline.
- Canary GitHub với ref `canary/ownership/...`.
- CI trên SHA PR và merge commit.

Cập nhật file này sau khi các lệnh đó có exit code. Không điền sẵn pass.
