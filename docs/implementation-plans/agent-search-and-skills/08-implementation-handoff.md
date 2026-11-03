# Bàn giao triển khai Agent Search & Skills cho Claude Code

> **Cập nhật 03/11/2026 (review cuối):** đọc [10-final-offline-review.md](10-final-offline-review.md) và `implementation-evidence.md` mục "Independent review" để biết code và kiểm chứng mới nhất. Các mục P0/P1 và trạng thái build bên dưới là snapshot lịch sử lúc bàn giao, đã có nhiều bản sửa tiếp theo; không dùng làm trạng thái hiện tại.

Ngày bàn giao: **03/11/2026**, timezone **Asia/Bangkok**. Repo **E:\MoodPrint**, branch
`test/03-11-26`. Đây là working tree đang triển khai, **chưa hoàn tất, chưa build xanh,
chưa live/staging verification, chưa production ready**. Không có commit/push/merge.

Tài liệu này cập nhật hơn các ghi chú tiến độ trước đó. Các kết quả test bên dưới thuộc
từng thời điểm; không suy rằng toàn bộ working tree cuối phiên đã vượt mọi kiểm tra.

## 1. Yêu cầu và giới hạn phải giữ

Người dùng yêu cầu thực thi toàn bộ plans00–07 theo task, không chỉ khảo sát/lập kế hoạch:
Web auto/manual có citation xuyên suốt và accounting; Apify Maps async; hai trusted skills
và composer một lượt; phối hợp mặc định hiệu lực cho oldfalse/missing/new eligible accounts;
lịch hỏi thăm vào info panel từng agent, bỏ settings khỏi Account.

- Không sửa `.gitignore`.
- Không đọc/in secret hoặc sửa `backend/.env` hay env runtime thật. `.env.example` được sửa.
- Không gọi OpenAI/Apify/Google thật, AWS CLI/SSM, hosted migration/deploy.
- Không yêu cầu dán credential vào chat. Không commit/push/merge.
- DB tests chỉ dùng disposable PostgreSQL thuộc harness repo; không dùng DB đang chạy/hosted.
- Giữ dependencies đang pin; không thêm SDK/dependency để tiện triển khai.
- Không reset/revert/ghi đè phần việc người dùng; kiểm `git status` trước khi sửa.

### Thay đổi có sẵn trước phiên, cần bảo toàn

1. `frontend/src/features/auth/AgeFields.tsx`
2. `frontend/src/features/guest/GuestEntry.tsx`
3. `frontend/src/features/public/LoginPage.tsx`
4. `frontend/src/features/public/landing.css`
5. `frontend/src/features/real/Auth.tsx`
6. `frontend/src/features/real/RealApp.tsx`

Agent không sửa5 file đầu; RealApp đã được sửa thêm cho task, phải giữ cả phần người dùng.
Bộ plans00–07 vốn là untracked lúc bắt đầu; không xóa vì tưởng là file rác.

## 2. Những phần đã viết code

### Web/citations/protocol/persistence

- `backend/app/ai/schemas.py`: `PromptOptions`, responseProtocol2/3, `Citation`, URL policy,
  code-point offsets, Maps/Places cards, SSE3 negotiation và placeholder cho old clients.
- `models.py`, `persistence.py`, `runtime.py`, `chat_routes.py`, `modules/users/export.py`:
  lưu/đọc/export citations; field `source_backed` trên từng bubble; options+protocol vào digest
  idempotency, có chuẩn hóa tools/area. GET direct history/pagination nhận responseProtocol3.
- `context.py`: ordinary history dừng ở source-backed boundary để prose Web không được
  paraphrase thành câu trả lời mất nguồn ở lượt sau. Maps reuse đi đường riêng có authorization.
- `search/{schemas,citations,policy,web,service,turn}.py`: isolated Responses child, không private
  history/memory/journal/tools; hosted cap1, output1200, timeout≤12s và chừa thời gian cho parent.
  Manual preflight có attempt hoặc trạng thái lỗi; auto intent đọc current prompt.
- `provider.py`: GroundedReply gồm segments/sourceIds, backend dựng offsets/title/URL; guard
  chung chặn model tự tạo citation/place/job cards trên nhánh thường, journal và mood.
  Runtime/group publication cũng có guard.
- `frontend/src/api/stream.ts`: parser SSE3, citations, source URL/card validation; parser1/2 giữ riêng.
- `search/CitationText.tsx`: inline source anchors và source list, noopener/noreferrer/no-referrer.
  Markdown links tùy ý vẫn không được bật thành external anchor.

### Search accounting

- `search/models.py`: `AiSearchUsage`, content-free fee ledger, provider/parent/child IDs,
  reservation/actual, state, active slot, token fallback và tokens_uncertain.
- `search/accounting.py`: atomic claim theo shared budget lock,5/user/day,1 active/user,
  2 active global, subset budget trong global, fee Web/Maps riêng token child.
- `ai/accounting.py`: mọi budget reader qua aggregator cộng external liability; subset tính
  child tokens một lần, global dùng AiUsage cho attached child và fallback khi detached.
- Web service tạo child AiRun không conversation_id để không đụng unique active conversation.
  Unknown dispatch/token usage giữ liability, không refund về0; recovery không replay.
- Account all-private/account purge detaches identity/job refs, bảo toàn nghĩa vụ tài chính.
  Retention/startup có recovery search. Cần kiểm thêm toàn bộ lifecycle matrix.

### Maps adapter/jobs/API/UI

- `search/apify.py`: httpx fixed api.apify.com, auth header, không paid-start retry; actor
  compass/crawler-google-places; build phải pin; start async waitForFinish0,60s actor, cap0.05;
  body allowlist một category/khu vực,5 places, enrichment/reviews/images off; body≤64KiB.
  Chỉ normalized name/category/address/rating/count/hours; tự dựng Google Maps URL.
- `maps_jobs.py`: content-free jobs, start/ref, lease/fence, worker poll/abort/cleanup,
  wall90s, result TTL10min trong RAM/vendor, owner/scope/session/data-version authorization.
  Không có model call sau chat completed. GET status không start actor.
- `maps_routes.py`: private GET no-store, versioned cancel. Runtime `mapsSearchId` reuse cùng
  conversation, không actor thứ hai; dùng kết quả trong follow-up thì backend gắn PlacesCard,
  saved/export giữ normalized places. Temporary không persist result prose vào DB.
- `jobs/maps_search.py`: worker riêng chỉ poll/reconcile/abort/cleanup, heartbeat không gọi provider.
- `MapsSearchCard.tsx`: visible polling, stop hidden/unmount, lỗi/retry read, cancel; action reuse
  chỉ điền draft/options, không auto-send; `PlacesCard` cho kết quả đã dùng trong saved reply.

### Trusted skills/composer

- `skills/registry.py`: hai path hằng, metadata scalar khớp registry, size16KiB, UTF8,
  containment/symlink checks; load một lần. Không executable/script/plugin discovery.
- Hai files `skills/hangout/SKILL.md`, `skills/learn-new-thing/SKILL.md` đã có workflows.
- `skills/resolver.py`: current-prompt deterministic manual>auto, phủ định/ambiguous handling;
  giữ current agent, không tự handoff; skills đi direct thay smart planner.
- `skills/routes.py`: authenticated `/ai/prompt-capabilities?botId=...`, chỉ public metadata/reasons.
- `composer/{promptOptions,ComposerOptions}.tsx/ts`, CSS, RealApp: plus menu, skill submenu,
  removable chips, Maps area, RAM-only selection, accepted-clear theo selection revision,
  retry giữ clientMessageId/options, scope/New/logout reset theo view lifecycle.
- Tất cả direct new-UI sends/streams/history dùng protocol3; groups giữ protocol cũ.

### Phối hợp mặc định

- Shared `collaboration/grants.py` dùng `GrantToken(policy, version)` cho legacy và V3.
- Defaults overlay bỏ ảnh hưởng oldfalse/missing, không sửa historical preferences.
  Legacy rollback vẫn dùng old rows. Giữ eligibility, AI/history/cohort/runtime/journal gates.
- Receipt tables/in-memory consultation/steps có permission_policy và permission_version/epoch.
  Revalidate dispatch/publish/continuation; continuation gắn với đúng conversation và used receipt.
- GET sharing phản ánh effective policyMode/policyEpoch; PUT trả410 khi defaults mode active.
- `collaboration/preflight.py`: read-only aggregate counts, không export danh tính/content.
- UI bỏ Account summary và SharingPage/dead CSS; route `/companion-sharing` redirect assistants.
  Giữ CollaborationLine/AgentStepsLine/HandoffBanner/runtime và explanation theo boundary thật.
- Chi tiết fake evidence: `collaboration-evidence.md`.

### Lịch trong agent info

- `checkins/useProactiveSettings.ts`: shared store per API/user/epoch, serialized writes,
  versions, optimistic rollback, global cap từ server, foreground/cross-tab refresh không content.
  STALE_VERSION chỉ áp patch người dùng vừa sửa vào snapshot mới, không bật lại journal consent.
- `AgentCheckInSettings`, `CheckInSlot`, `SharedCheckInSettings`, `LegacyCheckInSettings`,
  `CheckInDialog`: slots theo route owner, journal toggle chỉ Nhật ký/Nhịp; timezone/quiet/badges
  dùng chung, impact/conflict links; legacy migrate/remove explicit, Cầu Nối không enable mới.
- `ConversationInfo`: stable native dialog host, desktop show modeless, compact showModal;
  focus/select/textarea loop; child portal giữ draft qua resize. Latest fix hides suspended panel
  ở cả desktop để không giành focus; lưu lastFocused và RAF restore sau child cleanup.
- RealApp gắn info trước tin đầu, owner không đổi theo speaker; old `/check-ins?bot=` redirect
  đúng panel, no/invalidbot về roster manageCheckIns; proactive links giữ conversation query;
  roster, specialist banner và group member có đường mở info. Account bỏ schedule entry.
- Không thay proactive scheduler/API DTO hoặc migrate schedule data.

## 3. Migrations/config/deploy assets đã viết, CHƯA apply hosted

Chain mới:

1. `0025_search_citations` →0024: citations JSONB + source_backed bool.
2. `0026_search_usage` →0025: external liability ledger, private RLS/ACL.
3. `0027_maps_jobs` →0026: private content-free async jobs.
4. `0028_collaboration_defaults` →0027: permission_policy trên hai receipt tables.

READY_REVISIONS đã đổi thành0028. Các migration search từ chối destructive downgrade;
0028 downgrade chỉ khi không còn non-legacy policy receipts. Schema cần compatibility review.

`backend/.env.example`, `deploy/runtime.env.example` thêm flags/pricing/build/token placeholders.
`deploy/compose.staging.yml` thêm maps worker(pool1/overflow0), API pool4+1; tổng overlap dự kiến16
để còn4 headroom. `deploy/aws/deploy.sh` thêm maps health gate. **Không chạy deploy/AWS.**

Flags mới hiện fail closed: AI_WEB_SEARCH_ENABLED, AI_MAPS_SEARCH_ENABLED,
AI_AGENT_SKILLS_ENABLED, AI_AGENT_CHECK_IN_SETTINGS_ENABLED, AI_SEARCH_ROLLOUT_USER_IDS,
search quotas/subbudget; APIFY_API_TOKEN, APIFY_MAPS_ACTOR_BUILD, APIFY_MAPS_PRICING_VERSION,
APIFY_MAPS_CHARGE_BOUND_VERIFIED, MAPS_SEARCH_WORKER_ENABLED;
AI_WEB_SEARCH_PRICING_VERSION/AI_WEB_SEARCH_TOKEN_BOUND_VERIFIED;
AI_COLLABORATION_DEFAULTS_ENABLED(false)/AI_COLLABORATION_POLICY_EPOCH(2).

## 4. Kết quả kiểm thử thực tế

Không cộng các runs chồng lặp thành số test độc lập.

| Kiểm tra | Kết quả / giới hạn |
|---|---|
| Citation/contract/persistence ban đầu |40/40 pass sau sửa route param|
| Adapter/registry pure fake |18 pass tại thời điểm đó|
| Maps jobs + accounting/usage/budget + multi-message |30 pass|
| Web/manual skill SDK integration |2 pass|
| Search migrations/source/runtime group |15 pass|
| Source persistence + Maps API integration gần cuối |13 pass; fake Web/Maps, owner/reuse/saved places|
| Collaboration prescribed regression(subagent DB riêng) |157 pass; sau đó defaults mở rộng56; final supplemental142 pass|
| Check-in focused unit |23 pass|
| `npm.cmd test` |39 files/239 Vitest pass +1 Node Redocly test; trước latest focus/label patch|
| Broad browser fixture regression |**154 pass,6 fail** trong6.7m; log ở `.tmp/agent-search-e2e.log`|
| Focused browser rerun sau sửa5 lỗi liên quan |**5/5 pass** trong20.9s, log `.tmp/agent-search-rerun.log`|
| Mypy lần gần nhất có kết quả |184 modules pass; trước vài thay đổi cuối|
| Ruff lần gần nhất |1 I001 import-order ở test_search_citations.py:52, chưa fix/rerun|
| Compose config với synthetic/example values |exit0; không run services|
| `bash -n deploy/aws/deploy.sh` |exit0|
| Latest frontend build |**FAIL** do sourceBacked required trong generated AIMessage|
| Full backend `pytest -m 'not live'` |**CHƯA XONG**:dừng lúc~7%,4 dấuF; không có tên lỗi/final summary|

Broad browser6 failures:

-3 check-in modal/selector/focus cases;
-Maps area accessible name;
-rename return-focus;
-`ux-redesign.spec.ts` case `first-time sign in explains what MoodPrint is in one sentence`.

5 lỗi đầu đã sửa và focused rerun pass. Login case vẫn đỏ: test tìm heading
`Bắt đầu với MoodPrint` nhưng LoginPage là file người dùng đã sửa từ trước. Không revert copy
của người dùng hoặc nới assertion tùy tiện; xác minh diff rồi báo hoặc cập nhật test nếu có căn cứ.
Chưa chạy lại toàn bộ broad suite sau5 fixes. Chưa có visual inspection của screenshots.

## 5. Các việc đang dở / ưu tiên cho Claude

### P0 — Làm build/typecheck xanh

Latest `.tmp/agent-search-build.log` báo generated `AIMessage.sourceBacked:boolean` required
nhưng frontend message constructors chưa có field:

-`frontend/src/features/real/RealApp.tsx` live bot mapping khoảng1275, optimistic self khoảng1547–1548.
-`frontend/src/features/real/groups/GroupChat.tsx` bot append khoảng99, self append khoảng238.

Chọn contract thích hợp rồi sửa mọi constructor, **không sửa tay generated schema**. Thường self/group
non-search làfalse; source-backed direct bot phải suy từ validated backend metadata/citations/cards
hoặc mở rộng validated protocol field hợp lệ. Review kỹ việc marker internal SSE đang bị strip.
Sinh lại OpenAPI/types khi đổi contract. Typecheck trước đây pass không đại diện trạng thái cuối.

### P1 — Hoàn thiện regression/review

-Chạy test mới `test_maps_api.py` và toàn bộ search/skills/source/budget suite trên DB disposable.
-Bổ sung RED→GREEN cho late start-ref sau lease takeover; cleanup crash sau delete run + GET404;
  unknown Web tokens/fee qua cancel/restart/account tombstone/midnight/retention/flags off;
  exact global và subset once-counting; concurrent limits/dailycap.
-Các fix review R1–R8 phần lớn đã vào code; `search-review.md` có đoạn **stale** nói R1–R4 còn mở.
  Re-read source/test để xác nhận, cập nhật trạng thái report, không làm lại mù quáng.
-Kiểm client1/2 history/replay byte-shape: history hiện có thể vẫn thêm `citations:[]`/`sourceBacked`
  vào DTO cũ; strict older-client compatibility cần thêm regression, không chỉ SSE placeholder.
-Source-backed từng bubble/pagination/export và ordinary follow-up boundary cần tích hợp đầy đủ.
-Full backend suite bị dừng; có4F chưa có tên. Pytest cache có entries cũ không phải evidence run này.
  Rerun có log streaming/`-x`/`-ra` thích hợp để lấy đúng failure names.
-Literal migration head0024 còn trong `tests/test_foundation.py`, `test_guest_schema.py`,
  `test_guest_cleanup_recovery.py`, `test_discovery_migration.py`. Review/update đúng0028 và giữ
  kiểm thử reject older heads, không đổi expected chỉ để test pass. `test_readiness.py` đã đổi.
-Ruff/mypy/typecheck/build/contracts generation cần fresh run sau fixes.
-Rerun browser target suite, unit tests sau latest patches; giữ receipt runtime assertions đã có.
  Không chỉnh frontend trong lúc browser suite đang chạy.
-Visual QA screenshots ở desktop/mobile, keyboard/zoom/reduced-motion; browser DOM/axe pass
  không được nói là đã nhìn giao diện.
-Checkbox của plans/ledger chưa được cập nhật đầy đủ. Chỉ tick task đủ evidence thật.

### Giới hạn thiết kế cần quyết định minh bạch

-`safe_query` hiện dùng closed canonical topics(language/science/technology/learning/places),
  tránh gửi raw personal prose. Unknown topic needs_query; ví dụ weather Hà Nội có thể mất vùng,
  subtopic có thể bị rút quá mức. Đây là privacy-safe nhưng **coverage bị thu hẹp**, chưa đạt
  broad Web Search. Không quay lại blacklist pass-through; mở rộng bằng safe extraction có test,
  không thêm LLM router/call hoặc gửi private prompt sang search để làm router.
-Web ordinary follow-up cố ý không nhận lại source prose; chỉ explicit Maps reuse có context.
  Cần copy/fallback rõ cho giới hạn này, hoặc source-aware continuation đúng provenance.
-Pricing bounds/build/account/worker runtime readiness chưa live verified. Flags phải off.
-Settings overlay giữ consent policy hiện hữu: personal `consent_enabled('AI',false)` đangtrue;
  không tự thay semantics consent. Chi tiết trong collaboration-evidence.md.
-UI compatibility flag mới đã có nhưng route cleanup hiện unconditional và panel hiện khi
  proactive ORagentCheckInSettings. Review rollout semantics với06.K4, ghi ruling hoặc sửa.
-Worker chỉ dựa settings/cấu hình và deployment health gate; readiness thật/stale heartbeat
  giữa containers chưa có live proof. Không tuyên bố production ready.

### Hygiene và operator sau này

-`.gitignore`, dependencies/lock, `.env` thật không sửa. Không commit.
-`frontend/evidence/test-results/.last-run.json` và một folder failedtest bị sinh vào tracked area
  từ lần đầu chạy. Chỉ dọn artifact phiên này nếu xác định baseline; không reset cả thư mục.
  Các lần sau dùng MOODPRINT_TEST_ARTIFACT_DIR dưới `.tmp`.
-`.tmp/integrate-search-history.py`, `.tmp/restore-receipt-tests.py` là scratch từng dùng;
  **không chạy lại**, không idempotent và có thể xóa/nhân đôi tests. Không coi là scripts triển khai.
-Operator tự chuẩn bị key OpenAI hiện có, Apify scopedtoken+pinnedbuild+verified pricing.
  Google key chưa cần vì không có Google fallback. AWS còn compatibility migration, SecureString
  hiện có, installed Compose/worker, redeploy/recreate, staging/cohort/cost/rollback checks theo07.
  Không thực hiện những bước live/hosted đó trong phiên Claude này.

## 6. Môi trường và tiến trình khi bàn giao

-Đã dừng đúng full pytest phiên này (session69534; PIDs29348/30124 không còn ở kiểm tra sau).
  Browser focused rerun đã completed5pass. Không dừng những Node/Playwright processes khác
  vì không có bằng chứng thuộc phiên này.
-Disposable DB của root **vẫn giữ** cho phiên tiếp theo:
  container `moodprint-disposable-dd013fd508944053be6bd7002906d4e4`, loopbackport55439.
  Metadata: `.tmp/moodprint-disposable-dd013fd508944053be6bd7002906d4e4/metadata.json`.
  Env test harness cùng folder `.env`: chỉ nạp âm thầm vào process, không print credential.
  Đây là env disposable do harness tạo, khác `backend/.env` thật bị cấm đọc.
-Có thể dùng lại chỉ khi kiểm ownership/marker theo harness, không suite khác đang dùng;
  hoặc tự provision container mới port khác bằng scripts/disposable_postgres.py.
-Docker Desktop đã được khởi chạy hidden để harness hoạt động; không stop daemon tùy tiện.
-Không pytest/fullstack song song trên cùng DB. Khi xong, harness `--remove <run_id>` chỉ xóa
  đúng owned container. Collaboration worker đã xóa container riêng55440 của nó.

## 7. Tài liệu nên đọc theo thứ tự

1. Prompt tiếp tục: `09-claude-code-prompt.md`.
2. File bàn giao này; `implementation-evidence.md`.
3. Đầy đủ00–07 như yêu cầu gốc; source là authority.
4. `collaboration-evidence.md`, `checkins-evidence.md`, `search-review.md` (review snapshot stale
   ở vài findings; xác minh code hiện tại).
5. `.tmp/agent-search-{build,rerun,e2e,vitest,full-backend,backend,ruff,mypy}.log` theo nhu cầu.

Các thành phần đã viết là nền triển khai thực tế đáng tiếp tục. **Không bắt đầu lại từ đầu,
không kết luận hoàn tất trước khi xử lý build/tests/review còn dở.**
