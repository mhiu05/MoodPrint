# 12 — Sổ thực thi V3

Quy ước: mọi con số pass/fail/skip là **kết quả thật** của lệnh đã chạy; "chưa chạy" được ghi rõ. Lỗi có sẵn được tách khỏi hồi quy.

| Hạng mục | Giá trị |
| --- | --- |
| Nhánh / worktree | `feat/three-agent-smart-orchestration-group-chat` / `E:\MoodPrint-agent-platform-v3` |
| Gốc | `feat/proactive-companion-phase2@c8c55f8` (HEAD kiểm ngày 2026-11-01, cây theo dõi sạch) |
| PostgreSQL disposable | container riêng `moodprint-agent-v3-db` (`pgvector/pgvector:0.8.2-pg17`, tmpfs, `127.0.0.1:56432`), mật khẩu chỉ trong scratchpad phiên; DB `moodprint_v3_{unit,baseline,migration,fullstack,gate}_test`. Không dùng container Phase 1/2, không dùng hosted |
| SDK | `openai-agents==0.24.0` (không nâng cấp) |
| Cách ly | Không sửa `E:\MoodPrint` (Codex), `E:\MoodPrint-proactive-phase1`, `E:\MoodPrint-proactive-phase2`; chỉ đọc bằng git |

## V3-00 — Baseline

`pytest -q` trên bản tách rời `c8c55f8` (`git archive` vào scratchpad, DB `moodprint_v3_baseline_test`): **1520 passed, 4 failed, 2 skipped** (1259 s).

| Test lỗi | Phân loại |
| --- | --- |
| `test_guest_embeddings::test_guest_proposal_and_history_expiry_capped` | Có sẵn từ `d6eaf71` (sổ Phase 1, Phase 2) |
| `test_guest_migration_review::test_pending_review_never_executes_remote_or_overwrites_approval`, `test_reviewed_artifacts` ×2 | Môi trường: bản baseline nằm dưới `%TEMP%` (guard "SQL phải ở thư mục tạm" chấp nhận đường dẫn lẽ ra bị từ chối, để lại `pending.sql`) — cùng phân loại đã xác minh ở Gate G2 Phase 2; kiểm lại trong worktree thật ở cổng cuối |

## Gate A — Ba trợ lý mặc định (V3-01…V3-05)

- **V3-01 migration 0024** (`alembic/versions/0024_three_agent_groups.py`): `alembic upgrade head` trên DB trắng → `0024_three_agent_groups (head)`; `alembic check` → "No new upgrade operations detected". `tests/test_v3_migration.py` **2 passed**: tua schema về đúng 0023, gieo dữ liệu Phase 2 của cả 5 trợ lý (hội thoại, tin, lịch Nhịp, cạnh Phase 2) → nâng cấp → không hàng nào bị ghi lại/di chuyển, mọi hội thoại `direct`, `mentions='[]'`, không cạnh V3 nào được bật mặc định; CHECK từ chối 6 dạng hội thoại sai, run con thiếu cha, tin bot có mentions, 9 dạng receipt sai (kể cả `deny_reason='distress'`), 4 dạng thành viên sai; RLS bật, không quyền PUBLIC; xóa theo chủ sở hữu không chạm tài khoản khác.
- **V3-02/03 registry, prompt, API** (`app/ai/agents.py`, `registry.py`, `prompts.py`, `chat_routes.py`): năng lực theo bảng (`journal`, `mood_scope`, `memory`, `challenges`) thay cho rẽ nhánh theo tên bot; 3 persona mới hợp nhất. Prompt cũ giữ nguyên byte: sha256 `instructions('may')`/`('nhip')` = `697a0b191c2a…`/`2c102b424cba…` ở cả Phase 2 và V3. `tests/test_three_agents.py` **8 passed** (5 trợ lý mặc định / đúng 3 khi bật cờ, cohort, hội thoại cũ đọc được + 409 `LEGACY_CONVERSATION`/`LEGACY_COMPANION`, không mang transcript cũ sang Điều phối, tắt cờ trả về Phase 2, tool/persona riêng từng trợ lý, mood scope chỉ cho Nhật ký, ID nhóm không lọt vào API 1:1).
- **V3-04 proactive** (`proactive/policy.py`, `routes.py`): lịch cũ giữ nguyên + tạm dừng (`legacy_companion`), không chiếm hạn mức ngày; `POST …/migrate` chuyển rõ ràng (cùng giờ/ngày/trạng thái, tắt hàng cũ, bắt đầu từ mai nếu lịch cũ đã có job hôm nay); Cầu Nối `NO_SUCCESSOR`. `tests/test_v3_proactive.py` **6 passed** (gồm worker bỏ qua lịch cũ không gọi model; Nhật ký sáng đọc nhật ký hôm qua chỉ dưới `journal_context_enabled`).
- **V3-05 frontend**: registry + 3 avatar SVG mới, roster đúng 3 trợ lý (server quyết), hội thoại cũ mở chỉ đọc có nhãn + lối sang trợ lý kế nhiệm, trang hỏi thăm có thẻ "Lịch cũ" + "Chuyển sang …". `npx tsc --noEmit` 0 lỗi; `vitest` **168 passed (28 files)**.
- OpenAPI xuất lại + `schema.d.ts` sinh lại; `check_docs.py` PASS (sau khi thêm 10 cài đặt, 2 endpoint, 2 bảng vào inventory).
- Ruff sạch; mypy `Success: no issues found in 151 source files`.
- Hồi quy bộ AI/chat/proactive/collaboration/guest-schema (75 file test, DB `moodprint_v3_gate_test`): **864 passed, 1 failed, 1 skipped** — fail duy nhất `test_guest_embeddings::test_guest_proposal_and_history_expiry_capped` (có sẵn ở baseline).
- **Ghi nhận TDD**: ở Gate A, code migration/registry viết trước test (test viết ngay sau, xác nhận bằng các ca từ chối CHECK và so sánh byte prompt). Từ Gate B áp dụng test đỏ trước (`test_orchestration_policy.py` đỏ do thiếu module trước khi viết `triage/plan/policy`).
