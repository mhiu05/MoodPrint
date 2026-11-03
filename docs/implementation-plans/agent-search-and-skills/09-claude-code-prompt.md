# Prompt cho Claude Code tiếp tục triển khai

Bạn đang tiếp quản phiên **triển khai code**, không phải phiên chỉ khảo sát hoặc viết kế hoạch.
Hãy làm việc trực tiếp trong **E:\MoodPrint**, branch hiện tại `test/03-11-26`, tiếp tục từ
working tree đang dở. Không restart implementation từ đầu hoặc revert các thay đổi đã làm.

## Đọc trước

Tuân thủ AGENTS.md và skills phù hợp. Đọc **đầy đủ**:

- `docs/implementation-plans/agent-search-and-skills/08-implementation-handoff.md` — trạng thái
  bàn giao chi tiết, files, tests, lỗi hiện tại, giới hạn và môi trường disposable.
- Toàn bộ `00-overview.md` đến `07-rollout-credentials-and-coverage.md` trong cùng thư mục.
- `implementation-evidence.md`, `collaboration-evidence.md`, `checkins-evidence.md`,
  `search-review.md`. Review là snapshot khi code còn thay đổi, có findings đã sửa;
  đọc source/test hiện tại trước khi hành động.

Source hiện tại là căn cứ. Nếu plan không khớp source/SDK pin thì xác minh, cập nhật đúng plan
và ghi ruling/evidence rồi triển khai. Đây là phiên tiếp tục hoàn thiện, không xin xác nhận
routine và không dừng ở việc đề xuất cho tôi tự làm.

## Phạm vi cần hoàn tất

1. OpenAI Web Search tự nhận ý định/manual, isolated public context, citations xuyên
   backend/SSE/persistence/reload/pagination/export, link bấm được, đầy đủ token/tool accounting.
2. Maps Apify compass/crawler-google-places: bounded adapter, async jobs vừa chat30s,
   lease/fence/restart/cancel/deadline/cleanup, place cards, authorized next-turn reuse.
3. Trusted registry hai SKILL.md hangout/learn-new-thing, auto/manual, plus menu Web/Maps/Skills,
   removable chips chỉ một lượt, frozen send snapshot và idempotent retry.
4. Collaboration effective defaults cho eligible old/new kể cả preferencefalse/missing, bỏ
   settings UI nhưng giữ runtime/consult/handoff/receipt/tools/privacy/data limits/rollback epoch.
5. Check-in settings trong info panel route owner từng agent, global timezone/quiet/badges,
   journal toggle đúng agent; bỏ Account entry, old routes an toàn; giữ inbox/history/scheduler.

## Giới hạn tuyệt đối

- Không tự ý sửa `.gitignore`.
- Không đọc/in secret hoặc sửa `backend/.env`/runtime env thật; không yêu cầu paste secret.
- Không gọi OpenAI/Apify/Google thật, AWS CLI/SSM, hosted migration/deploy.
- Không commit/push/merge/reset/revert. Giữ nguyên user changes đã có trong6frontend files
  được liệt kê ở08; RealApp chứa cả user changes và implementation mới, sửa hẹp theo vùng.
- DB tests chỉ dùng disposable PostgreSQL của harness repo, không DB đang chạy/hosted.
- Giữ dependency/SDK đang pin, không thêm/nâng vì tiện. Dùng fake/mock cho behavior changes.
- Không tự bỏ authorization/privacy/quota/budget/timeout/idempotency/cancellation/recovery gates
  để làm tests xanh. Fake tests không phải live proof/production readiness.

## Bắt đầu bằng các lỗi đang rõ

1. `git status --short`, đọc logs và current diffs, xác nhận không có suite khác dùng DB.
2. **Latest frontend build đang FAIL**: generated AIMessage.sourceBacked là required nhưng
   constructors ở RealApp.tsx và groups/GroupChat.tsx thiếu field. Sửa contract/constructors
   đúng semantics; không sửa tay generated schema. Sinh lại OpenAPI/types và chạy typecheck/build.
   File lỗi đầy đủ: `.tmp/agent-search-build.log`.
3. **Full backend suite chưa hoàn tất**: đã dừng ở~7%, có4F nhưng chưa có summary/tên lỗi.
   Không báo fullsuitepass. Review stale0024 head assertions trong test_foundation,
   test_guest_schema, test_guest_cleanup_recovery, test_discovery_migration khi head mới0028.
   Đừng lấy pytest lastfailed cache cũ làm bằng chứng của run này.
4. Ruff gần nhất còn I001 test_search_citations.py:52. Mypy184modules từng xanh nhưng cần
   fresh rerun sau fixes. Latest generated schema đã có sourceBacked.
5. Broad Playwright160tests có154pass/6fail;5fail thuộc task đã sửa và focused rerun
   **5/5pass** (`.tmp/agent-search-rerun.log`). Còn login-copy case trong ux-redesign có
   thể lệch user changes từ trước; xác minh và không revert LoginPage người dùng.
   Rerun target journeys sau buildfix, đọc mọi failure và report chính xác.

## Các điểm cần review và bổ sung bằng chứng

- Web safe_query hiện canonicalizes vào topic registry đóng để tránh leak personal prose;
  coverage bị hẹp và có thể mất subtopic/location. Hoàn thiện useful safe extraction hoặc
  thông báo unsupported rõ, không quay lại raw prompt/blacklist pass-through. Không thêm LLMrouter
  hoặc model call ngoài budget. Không gửi history/memory/journal sang search child.
- `source_backed` trên mọi bubble và context boundary là fixes mới; kiểm oldclient1/2 cả
  strict history/replay/pagination, emoji offsets và export. Không chỉ SSE1/2 test.
- Guards chặn fabricated citations/maps cards trên generic/journal/mood/group/orchestration;
  xác minh đầy đủ tất cả branches và backend-only source authority.
- Maps cleanup fixes đã vào code: expiry trước cancel branch; DELETE404 success; late ref
  reopen cleanup; final charge persist trước xóa vendor run; statusGET404→missing. Bổ sung tests
  interleaving crash/lease takeover/cancel/cleanup partial/worker restart, không replay paid start.
- Accounting exact-once matrix: attached/detached tokens, fees, uncertainty, midnight,
  tombstone/deletion/retention, flagoff; atomic5/day,1/user,2global, subset nằm trong global.
- Kiểm manual both-tools behavior/deadline, job scope/current agent/handoff, new selection
  không bị accepted clear nhầm, unknown send/retry cùng ID/options không phát lại trả phí.
- Check-in latest dialog/focus patch đã qua5targettests nhưng cần rerun full viewport/keyboard/
  resize/axe/zoom và inspect screenshots. Giữ global timezone/version và consent-safe stalepatch.
- Review UI rollout flag semantics: route cleanup hiện unconditional; panel hiển thị khi
  proactive ORagentCheckInSettings, so với compatibility rollout trong06.K4.
- Không xóa receipt assertions trong tests. File collaboration.spec đã giữ runtime receipt/
  why/live/fallback tests, chỉ retiredsettings tests được thay thế.

## Test environment và commands

Root disposable vẫn còn, owned runID `dd013fd508944053be6bd7002906d4e4`, port55439.
Thông tin nonsecret ở `.tmp/moodprint-disposable-<runID>/metadata.json`.
Nạp `.env` **của harness disposable đó** âm thầm vào process, không in values; tuyệt đối
không đọc `backend/.env`. Hoặc provision DB riêng bằng repo harness ở port trống.
Không pytest/fullstack song song cùng DB. Full pytest phiên trước đã dừng, PIDs29348/30124
không còn lúc bàn giao; kiểm lại thay vì kill processes không thuộc mình.

Từ backend, Python sẵn có `.venv/Scripts/python.exe`; từ root dùng
`./backend/.venv/Scripts/python.exe`. Có thể dùng `uv run --locked` theo plan nếu không làm
đổi dependency. Pytest conftest đã chặn realenv/provider keys và envfile loading.

Chạy theo task và đọc kết quả thực tế:

```text
# backend, TEST_DATABASE_URL của disposable harness đã nạp riêng
python -m pytest tests/test_web_search.py tests/test_search_citations.py tests/test_search_accounting.py tests/test_search_provenance_guard.py tests/test_search_migrations.py tests/test_prompt_options.py tests/test_maps_provider.py tests/test_maps_jobs.py tests/test_maps_api.py tests/test_agent_skills.py -q
python -m pytest tests/test_collaboration_defaults.py tests/test_sharing_api.py tests/test_collaboration_migration.py tests/test_collaboration_chat.py tests/test_collaboration_proactive.py tests/test_collaboration_privacy.py tests/test_collaboration_review_fixes.py tests/test_orchestration_policy.py tests/test_orchestration_sdk.py tests/test_v3_review_fixes.py tests/test_v3_proactive.py -q
python -m pytest tests/test_proactive_api.py tests/test_proactive_schedule.py tests/test_proactive_quiet_hours.py tests/test_proactive_lifecycle.py tests/test_proactive_privacy.py tests/test_v3_proactive.py -q
python -m ruff check app tests
python -m mypy app
python ../scripts/export_openapi.py

# frontend
npm.cmd run contracts:generate
npm.cmd run typecheck
npm.cmd run build
npm.cmd test
npx.cmd playwright test tests/e2e/agent-skills.spec.ts tests/e2e/search.spec.ts tests/e2e/maps-search.spec.ts tests/e2e/agent-check-in-settings.spec.ts tests/e2e/proactive.spec.ts tests/e2e/collaboration.spec.ts tests/e2e/chat-history.spec.ts tests/e2e/multi-message.spec.ts tests/e2e/group-mentions.spec.ts tests/e2e/activities.spec.ts tests/e2e/ux-redesign.spec.ts
```

Đặt `PLAYWRIGHT_PORT` riêng và `MOODPRINT_TEST_ARTIFACT_DIR` dưới `.tmp` trước browserrun;
không sửa frontend trong khi suite chạy. Sau fixes chạy full backend fake suite khi phù hợp,
ghi đủ failures/skips, không nói toàn bộ pass từ subset. Không dùng live verification để bù
fake coverage thiếu. Không chạy lại scratch `.tmp/integrate-search-history.py` hoặc
`.tmp/restore-receipt-tests.py` — chúng không idempotent.

## Hoàn tất và báo cáo

Tiếp tục cho tới khi phần code/fake verification được hoàn thiện trong phạm vi. Nếu thiếu
credential/live proof, vẫn hoàn thiện offline và giữ search fail closed. Cập nhật checkbox
plans và evidence chỉ theo kết quả đã chạy, sửa review report stale; rà diff cuối để bảo toàn
user changes. Dọn đúng artifact do phiên tạo, không sửa.gitignore hoặc reset cả thư mục.

Báo cáo cuối bằng tiếng Việt gồm files/features thực hiện, exact tests/results/failures/skips,
migrations0025–0028 và flags/config, credentials operator tự chuẩn bị, AWS/staging steps còn lại
nhưng chưa chạy, mọi giới hạn/task chưa xong kèm lý do. Nhấn mạnh fake tests không chứng minh
live provider hoặc production ready. Không commit/push/merge/deploy.
