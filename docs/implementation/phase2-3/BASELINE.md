# Baseline Phase 2/3

Tag có hiệu lực cho hai feature branch là `baseline/phase-2-3-start`.

Tag này **chưa được tạo** trong commit preparation. Không dùng `baseline/phase-1-verified` để rẽ `feat/knowledge-base` hoặc `feat/agent-companion`.

## Cách kiểm sau khi integrator push tag

```powershell
git fetch origin --tags
git rev-parse "baseline/phase-2-3-start^{commit}"
git merge-base --is-ancestor 763dcdd66ba8dbbfd691ad8541db21062ac06772 "baseline/phase-2-3-start^{commit}"
git merge-base --is-ancestor "baseline/phase-2-3-start^{commit}" origin/mhiu05/feat-refactor
git rev-parse origin/main
```

`origin/main` tại thời điểm chuẩn bị vẫn là `8b329980af4038f4c2a565a6472fd01472fbdfef` cho tới khi có merge khác. Tag final chỉ được tạo trên commit đã merge vào `mhiu05/feat-refactor` và đã qua post-merge gate. Không di chuyển tag. Nếu phải sửa sau `baseline/phase-2-3-start-rc1`, tạo `rc2` hoặc `rc3`.

SHA trong file này không thay cho `git rev-parse` của tag. Nếu hai giá trị khác nhau, tin lệnh Git.
