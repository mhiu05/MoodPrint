# 08 — Sổ thực thi

Quy ước (giống `docs/implementation-plans/three-agent-orchestration-group-chat/12-execution-evidence.md`): mọi con số pass/fail/skip là **kết quả thật** của lệnh đã chạy, kèm lệnh và thời lượng. "Chưa chạy" ghi rõ. Lỗi có sẵn ở baseline tách khỏi hồi quy. Không ghi secret, URL có mật khẩu, ID tài khoản thật hay nội dung nhật ký.

| Hạng mục | Giá trị |
| --- | --- |
| Nhánh / worktree | `feat/journal-intelligence` / `E:\MoodPrint-journal-intelligence-exec` |
| Gốc | `origin/main@565f5a74`; kế hoạch gốc lưu ở `E:\MoodPrint`, nhánh `test/04-11-26` |
| PostgreSQL disposable | `scripts/disposable_postgres.py --port 36432` (điền tên container khi tạo) |
| Cách ly | Không sửa `E:\MoodPrint` (stash + `.gitignore` của chủ dự án), `E:\MoodPrint-agent-platform-v3`, `E:\MoodPrint-proactive-phase1`, `E:\MoodPrint-proactive-phase2` |

## JI-00 — Baseline

Chưa chạy.

## JI-01 — Danh sách test giả định cờ tắt (red run)

Chưa chạy. Ghi đầy đủ tên test fail khi đổi mặc định mà chưa ghim nền, và cách sửa từng test.

## JI-02 … JI-51

Chưa chạy.
