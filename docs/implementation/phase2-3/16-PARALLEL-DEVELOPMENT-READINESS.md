# 16 — Sẵn sàng cho hai nhánh song song

Trạng thái của tài liệu này trước Gate PB đầy đủ: **chưa cho phép tạo worktree**. Owner chỉ chạy lệnh ở cuối khi báo cáo `15` và tag remote `baseline/phase-2-3-start` đã được kiểm bằng `git rev-parse`.

## Điều kiện YES

- Preparation đã merge vào `mhiu05/feat-refactor` bằng merge commit, không phải main.
- CI `offline` và `integration` SUCCESS trên SHA đã merge.
- Tag annotated `baseline/phase-2-3-start` trên origin trỏ đúng commit đã kiểm.
- `origin/main` không bị commit này đụng.
- Không còn finding Critical mở trong diff preparation.

Thiếu một điều kiện thì câu trả lời là **NO**.

## Lệnh owner, chỉ khi YES

Chạy từ worktree `mhiu05-feat-refactor` sau `git fetch origin --tags`. Kiểm thư mục đích chưa tồn tại và chưa có nhánh `feat/knowledge-base` hoặc `feat/agent-companion`.

```powershell
git fetch origin --tags
git worktree add -b feat/knowledge-base ..\MoodPrint-Knowledge baseline/phase-2-3-start
git worktree add -b feat/agent-companion ..\MoodPrint-Agent baseline/phase-2-3-start
git worktree list
```

Trong từng worktree:

```powershell
uv sync --all-packages --all-extras --locked
```

Phase 2, thư mục `MoodPrint-Knowledge`:

```powershell
$env:MOODPRINT_STACK_NAME = 'kb'
$env:MOODPRINT_PORT_OFFSET = '100'
uv run python scripts/dev/supabase_worktree.py start --name kb --offset 100 --lite
uv run python scripts/dev/bootstrap_local_db.py --name kb --offset 100
uv run python scripts/ci_ownership.py --branch feat/knowledge-base --local
```

Đọc `12-PHASE-2-GROK-EXECUTION-HANDOFF.md`. Agent là Grok 4.7. Env nằm ở `.local/stacks/kb/test.env`. Dev dự kiến frontend `5273`, backend `8100`.

Phase 3, thư mục `MoodPrint-Agent`:

```powershell
$env:MOODPRINT_STACK_NAME = 'ag'
$env:MOODPRINT_PORT_OFFSET = '200'
uv run python scripts/dev/supabase_worktree.py start --name ag --offset 200 --lite
uv run python scripts/dev/bootstrap_local_db.py --name ag --offset 200
uv run python scripts/ci_ownership.py --branch feat/agent-companion --local
```

Đọc `13-PHASE-3-OPUS-EXECUTION-HANDOFF.md`. Agent là Claude Opus 5.5. Env nằm ở `.local/stacks/ag/test.env`. Dev dự kiến frontend `5373`, backend `8200`.

Không chạy cả foundation, kb và ag cùng lúc. Tối đa hai stack. Khóa Voyage và OpenAI, cùng file budget, là việc của owner trước live. Không có trong repo.

Integration sau này đọc `14-INTEGRATION-AGENT-EXECUTION-HANDOFF.md`. Không tạo nhánh đó trong bước này.
