# Runtime LOGIN — SQL bổ sung đã được người dùng phê duyệt

24/10/2026, Asia/Bangkok. Initialization đã commit và verification PASS ở revision `0005_export_scope`; không chạy lại initialization.

Người dùng đã trả lời **“Phê duyệt SQL runtime đúng hash và phạm vi”** ngày24/10/2026. Phê duyệt template và tham số SCRAM credential như mô tả dưới đây; không cần xin lại cùng scope.

[SQL template đầy đủ](supabase-runtime-login-review.sql), SHA256:

```text
d9124bfd7747a7a04841b8e471a38ddfe6de04d87f91b20ffd63e3f79a1f0461
```

Tạo duy nhất `moodprint_backend` LOGIN/INHERIT/connection limit10, NOSUPERUSER/NOCREATEDB/NOCREATEROLE/NOREPLICATION/NOBYPASSRLS; cấp membership của `moodprint_app`. Hai role đã duyệt `moodprint_app` và `moodprint_runtime` giữ nguyên NOLOGIN. Không thêm quyền bảng/schema/Auth, không đổi ownership, policies, revision hoặc exposed schemas. Membership chỉ thừa kế domain DML, SELECT revision và EXECUTE private Auth helper đã duyệt.

Password được tạo bằng `secrets.token_urlsafe(48)` tại local. Placeholder `PASSWORD {runtime_password}` được bind bằng **SCRAM-SHA-256 verifier** do libpq tạo, không phải plaintext. Hash trên là hash **template đã review**; verifier ngẫu nhiên là tham số credential duy nhất, không ghi vào tài liệu/report/command arguments hoặc plaintext temp files. Runner không in query/exception text. Sau commit chỉ thay `DATABASE_URL` trong `backend/.env`; giữ nguyên migration owner URL và các OpenAI/security settings. `.env` hiện không được Git theo dõi.

Runner [provision_supabase_runtime.py](../../../scripts/provision_supabase_runtime.py) mặc định review-only/no network. `--apply --approved-sha256 <hash>` chỉ được dùng sau phê duyệt riêng này. Preflight whitelist đúng project/host/port5432/TLS/owner, revision0005, hai groups NOLOGIN và backend LOGIN chưa tồn tại. Nếu role đã có hoặc commit outcome chưa rõ, dừng và inspect chỉ đọc; không tự replay/reset password.

Sau commit, runner dùng credential mới kiểm SSL/current role, NOBYPASSRLS/no administrative privileges, membership, no CREATE schema, no raw Auth access và helper trả false cho session không tồn tại. Có tối đa3 reconnect attempts cho cache/network; không lặp reset. Health/Auth/E2E là các gate tiếp theo, không suy từ role creation.

Local regression:4 tests PASS kiểm env preservation/encoding, approved-hash rejection trước connection, foreign-target rejection và chạy đúng role SQL với SCRAM trên PostgreSQL local/rollback. Local role đã rollback. Remote template đã được user duyệt và commit; runtime SSL/least-privilege/transaction/ready200 và hosted E2E PASS. Probe đầu42501 do tên Auth relation trong diagnostic; sửa catalog OID và verify-only PASS, không mở rộng quyền hoặc replay DDL.

Performance advisors sau initialization có2 INFO foreign keys thiếu covering indexes (`blocks.blocked_id`, `candidate_references.peer_id`) và31 INFO unused indexes trên schema mới. Không xóa indexes hoặc tự thêm DDL ngoài phạm vi đã duyệt; initial schema snapshot không có security lint; latest Auth advisor WARN leaked-password protection disabled được ghi riêng ở post-E2E inspection.
