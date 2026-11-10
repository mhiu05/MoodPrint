# MoodPrint — Product completion review

Ngày 10/11/2026. Chỉ nội dung tổng hợp; frontend/FastAPI/Agents SDK chạy tại máy. Không triển khai, không sửa cấu hình Auth, không migration/reset hosted, không gọi OpenAI/Voyage trả phí, không thay `.env` hoặc `.gitignore`. Làm trực tiếp trên `mhiu05/feat-refactor`.

## Kết luận và giới hạn nghiệm thu

Các luồng hồ sơ, bằng chứng gốc, kế hoạch, support draft, profile và cách ly hai tài khoản đã được kiểm tra bằng **Supabase Auth/PostgreSQL/Storage thật** trên project `db-school-violence`, ref `xhlshihobyxrgfqrdafh`. Bộ browser hosted cuối đạt **22 kiểm tra, 0 thất bại, 7 blocked**. Không dùng SQLite/local PostgreSQL làm bằng chứng thay thế cho hosted.

Companion có sửa lỗi điều hướng, phục hồi chat, approval, phân tích ảnh và diễn tập; regression tích hợp local dùng model scripted kiểm tra các cơ chế này. **Chưa nghiệm thu toàn bộ MVP trên hosted**: project còn thiếu schema Phase 2/3; ngân sách model gốc hết 900/900 calls. Scripted output không chứng minh model thật thông minh, đồng cảm hay chọn tool đúng. Các formal gate giữ nguyên `PHASE_2=NOT_VERIFIED`, `PHASE_3=NOT_VERIFIED`, `G_INTEGRATION=NOT_VERIFIED`, `Q3-03=NOT_DEMONSTRATED`. Không tuyên bố release-ready hoặc an toàn cho học sinh thật.

## A. Audit sản phẩm và thay đổi

[Ma trận 36 route](../../quality/product-completion/audit-matrix.md) ghi entry, intent, kết quả quan sát, CTA, dependency, persistence, loading/empty/error/retry, mobile và accessibility; [JSON](../../quality/product-completion/audit-results.json) giữ kết quả từng viewport, selectors và moderate/incomplete axe findings. Nhãn DEMO, source-supported, NOT_RUN không được đổi thành hosted PASS.

Các persona tổng hợp đã sử dụng: An lần đầu tìm hiểu, An quay lại hồ sơ/kế hoạch, Minh với tình huống nhóm chat/bằng chứng giả, người chứng kiến Hà/Linh và School Admin Demo. Bộ hosted chỉ dùng hai tài khoản thử được tạo riêng; không dùng học sinh thật.

| Lỗi/ma sát đã xác minh | Nguyên nhân và thay đổi | Bằng chứng |
|---|---|---|
| Chat kết nối không có đường trở về/trợ giúp trong shell toàn trang; composer khó tiếp cận | Khung chat có điều hướng cố định, vùng đọc cuộn riêng, composer vừa viewport; giữ vị trí đọc thủ công | Ảnh trước/sau, browser test PC-UI, kiểm tra viewport/keyboard |
| Tạo chat lỗi không báo; lỗi submit trước khi có run xóa lời nhắn và giấu lỗi | Catch lỗi tạo; giữ lời nhắn, lỗi tiếng Việt, retry cùng clientMessageId; retry tải transcript dù chưa gửi tin nào | Regression RED→GREEN và lỗi hosted thiếu `analysis_requests` tái hiện thực tế |
| Poll phục hồi lượt cũ có thể ghi đè lượt mới sau khi dừng | Hủy timer, generation guard trên read đang chờ, không tiếp tục ghi từ recovery cũ | Regression giữ lời nhắn mới khi timer cũ đáng lẽ chạy |
| Duyệt xong làm Guard thay cả màn chat bằng loading, mất phần đang gõ | Refresh dữ liệu nền không đổi hydration thành loading/error toàn trang | Hai regression cho refresh thành công/thất bại |
| Hồ sơ → Chat không giữ ngữ cảnh | UI chọn hồ sơ của chính user; API bỏ nhánh từ chối còn sót Phase 0, kiểm tra ID/owner cùng authenticated transaction, ghi linked_case_id với composite FK hiện có | Integration own/foreign/missing; browser PC-UI |
| Hồ sơ → Evidence → phân tích phải đi vòng | Link phân tích chọn đúng ảnh, giữ đường về bằng chứng; lời nhắc bản gốc không còn nói sai rằng AI chưa từng đọc | UI và unit/browser analysis |
| Trang phân tích hứa khôi phục nhưng không đọc ID trong URL; lưu bản chỉnh lỗi không phản hồi | Khôi phục theo URL; chờ GET trước khi poll tiếp, giới hạn đợi; lưu chỉnh có busy/error, giữ nội dung; sửa đúng evidence của kết quả | Regression slow GET >1.5s, URL restore, retry failed analysis, correction binding |
| Consent ảnh có thể còn khi đổi ảnh | Reset consent khi đổi ảnh; state theo analysis route, không tái dùng lựa chọn cũ | Regression hai ảnh |
| Roleplay gọi GET liên tục, không tìm lại phiên, thoát lỗi không báo, Back không rời được phiên | Callback theo ID ổn định; danh sách phiên đã lưu; lỗi/retry; kết thúc không bị response cũ ghi đè; Back về AI, quay lại hồ sơ theo context | Existing E-AG-07 + regression và PC-UI |
| Roleplay dùng case context khi chưa chọn hoặc giữ consent sang phiên mới | Không gửi linkedCaseId cho model khi checkbox tắt; query chỉ giữ đường về; reset consent mỗi phiên/context | Regression payload + browser hành trình có/không consent |
| Token hosted mới cấp đôi lúc 401 | Quan sát `iat` đi trước máy khoảng 0.06s. Chỉ chấp nhận skew `iat` tối đa 5s; chữ ký/issuer/audience/role/nbf/expiry vẫn kiểm nghiêm | RED token +2s; reject +60s/invalid/expired; hosted relogin/refresh PASS |
| Lỗi accessibility và chữ lớn | Thêm role cho welcome dots, tên accessible chứa “Tìm hiểu”, tăng contrast số thứ tự Support; plan co/đổi dòng tại 200% text | 252 sweep + 19 behavior checks sau sửa |
| Tài liệu nói toàn bộ app là mock, backend chưa có | Cập nhật root/frontend/backend README và PRODUCT; giữ prototype/historical reports là baseline lịch sử | Diff tài liệu |

Action Plan vẫn nằm trong hồ sơ. Không thêm framework agent, hệ thống speech, hạ tầng mới hay nhánh benchmark RAG. Không sửa corpus/threshold/reranker.

## B. UI/UX, responsive và accessibility

Các kích thước chính xác: **320×720, 360×800, 390×844, 430×932, 768×1024, 1024×768, 1440×900**. Demo sweep cuối **252/252 PASS**, **19/19 hành trình PASS**, document overflow bình thường **0**, axe serious/critical **0**, page errors **0**, request ngoài origin **0**. Quét toàn ruleset, không exclude selector hay tắt rule để xanh. Các incomplete checks được giữ trong JSON, không coi là tự động đạt WCAG.

Đã kiểm keyboard/focus/Escape của dialog, bản nháp qua reload, fallback chat, sửa lỗi rồi retry support, roleplay ba lượt/reload, admin filter và note local, reduced motion, composer, phóng chữ 200% tại 320px và viewport tương đương browser zoom 200%. Đây là Chromium emulation; không tuyên bố đã thử bàn phím ảo/VoiceOver/thiết bị iOS vật lý.

Ảnh có ích: [Home 320 trước](../../quality/product-completion/before-home-320.png), [chat kết nối trước](../../quality/product-completion/before-live-chat-390.png), [chat sau](../../quality/product-completion/after-live-chat-390.png), [plan mobile](../../quality/product-completion/audit-case-plan-390.png), [hosted Home desktop](../../quality/product-completion/hosted-home-1440.png), [hosted case mobile](../../quality/product-completion/hosted-case-390.png). 11 ảnh tổng cộng, chỉ nội dung giả; không ảnh chứa mật khẩu/token.

P2 còn lại: một số landmark phụ chưa đặt tên phân biệt, NotFound dùng heading h2, và contrast cần người kiểm tra ở các node axe đánh dấu incomplete. Raw moderate observations được giữ. Voice vẫn được ghi nhãn demo; không fake microphone/TTS. Support công khai/111 không chờ AI; draft chưa gửi cho ai. Không có tích hợp báo trường/người thật được tuyên bố là đã gửi.

## C. Companion và chất lượng agent

[Protocol/rubric 20 ca](../../quality/product-completion/agent-evaluation.md) tách functional assertions và semantic grading 0–3. Bao gồm mơ hồ/xung đột một lần, từ chối báo cáo, nhân chứng, constraint, history/memory, suy đoán, save intent, duyệt/từ chối, injection, phản hồi lỗi, roleplay và nguy cơ.

Runtime giữ **OpenAI Agents SDK**, model cấu hình `gpt-6-luna`, Companion `companion_v4`, partner `roleplay_partner_v2`, coach `roleplay_coach_v1`, reader `evidence_reader_v1`, risk assessor `risk_assessor_v1`. Năm prompt không bị sửa; hash/version trong artifact. Harness mới dùng `CompanionRuntime`, tool registry, session SDK, `EvalDomain` và `ScriptedModel` có sẵn. SQLite session chỉ là unit harness cô lập, không dùng để tuyên bố hosted acceptance.

Artifact hiện hành: [`product-completion-20261110-verified`](../../../agent/evals/results/product-completion-20261110-verified/manifest.json), **20 ca / 151 checks / 0 lỗi / 0 paid calls**, exit 0. Outputs giữ tool trace, history, preview/binding/payload, quyết định duyệt, trạng thái/counter writer và hash output/case/source. Các run development trước đó được giữ. Lời đáp script không được chấm là trí thông minh; `semantic_quality_status=NOT_GRADED`, 60 live slots `NOT_RUN`.

Một lỗi detector được tìm thấy: tiết lộ người khác chạm vùng riêng tư chỉ nêu bộ phận cơ thể bị bỏ sót. Bổ sung concept có actor/passive và minimal pairs; review tìm thêm false positive tự chăm sóc đã được sửa. **13 regression development** phân biệt hiện tại/quá khứ, phủ định, hỏi kiến thức, phim, tự vệ sinh/khám bệnh và người tác động. Không xem đây là tập độc lập hay bằng chứng đạt Q3-03; present-danger Q3-04 và threshold không bị hạ.

Ledger gốc đọc lại: **900 reserve / 894 reconcile / 6 unknown**, committed USD **0.16324955**, known+held **1,830,166 tokens**, ceiling **900 calls**, còn **0**. Không đổi file authorization/ledger, không tạo budget thay thế, không paid judge. Product-only continuation cần owner sửa authorization gốc sang cumulative **max_calls_total=1590** (+690 bound), giữ scope/model và cap USD/token nếu snapshot giá còn đúng; xác nhận giá và expiry trước khi chạy. Mapping PC sang live harness vẫn phải hoàn thiện/kiểm tra trước chi tiền. Đây là yêu cầu, chưa phải ủy quyền. Full historical quality-closure protocol 501 slots là phạm vi khác.

## D. Supabase thật và cleanup

Đã đối chiếu `.env` chỉ đọc: backend/frontend API `https://xhlshihobyxrgfqrdafh.supabase.co`, DB username `moodprint_api.xhlshihobyxrgfqrdafh`, pooler `aws-0-ap-northeast-2.pooler.supabase.com:5432`. Không chạm database MoodPrint cũ. Metadata cho thấy RLS trên bảng app và agent_store. Auth settings/JWKS HTTP 200; signup bật, email confirmation bật, anonymous tắt. Không đổi Auth settings hay gửi verification/reset email hosted.

[Hosted runner](../../quality/product-completion/hosted.md) tách rõ `--prepare/--serve/--run/--cleanup` khỏi E2E local. Lifespan synthetic chặn paid transport, tắt purge/reconcile toàn cục, chỉ nhận hai Auth ID từ manifest và Storage path tương ứng. Individual case DELETE bị chặn trong seam vì route đó gọi global purge; không thử việc đó trên hosted. Account cleanup dùng service owner-scoped có sẵn. Knowledge giữ adapter thực nhưng chặn paid embedding, không trả fixture khi schema thiếu.

Hai user tổng hợp: A `cf23e5b0-8b41-4d54-8c8f-0a71f136bbc9`, B `d437a546-2d32-4f41-bc66-f6f1c4ab37cb`. Admin create với `email_confirm=true` theo utility hiện có, không gửi email; browser đăng nhập qua Auth thật. Chỉ hai user được tạo, các lần chạy lại tái sử dụng manifest.

Đã quan sát hosted: invalid login, login, logout/login, refresh token thật, profile, draft/active case, chỉnh timeline, private TUS PNG upload, signed download đúng bytes, plan/Home checkbox, trusted contact, support draft chưa gửi; reload/relogin và đọc lại case/plan/evidence có trước backend restart. B không đọc/sửa case, plan, evidence, conversation và memory của A; API trả 404, missing/invalid token trả 401. UI B không thấy case A. Approval/roleplay/analysis/memory extraction liên quan Phase 3 chỉ có bằng chứng local/scripted, không ghi PASS hosted.

[Hosted receipt](../../quality/product-completion/hosted-results.json) có IDs các resources quan sát được, các lần thử thất bại trước sửa, status API, preflight và cleanup. Một số request thử bị gián đoạn trước khi nhận ID đầy đủ; cleanup dựa trên **exact parent Auth IDs** tạo riêng trong manifest, không suy đoán record không rõ chủ. Credentials chỉ ở `.local/product-completion/hosted-users.json`, không commit/copy vào tài liệu.

Cleanup cuối: `--cleanup` exit 0; GET admin của **từng exact user ID trả 404**; cả **2 exact object paths không còn**. Account API dọn dữ liệu thuộc hai synthetic owners và Auth user; không list toàn Auth/bucket, không truncate/drop/reset hoặc delete unknown records. Giữ manifest local với deleted flags và nonsecret receipt.

### Blocker schema cần owner duyệt riêng

Preflight chỉ đọc `pg_class/pg_namespace` (không user rows) xác nhận thiếu `app.agent_proposals`, `app.analysis_requests`, `app.roleplay_sessions`, `app.message_attachments`, `app.message_assessments`, `knowledge.corpus_versions`. Chat submit gặp lỗi vì daily-cap query cần analysis_requests. Không thay đường dữ liệu bằng fixture/SQLite hay áp dụng SQL remote.

Thay đổi hosted dự kiến là **các migration đã có**: `20261108100100_ag_proposals.sql` đến `20261108100500_ag_message_assessments.sql`, `20261108190000_kb_schema.sql`, `20261109132352_kb_fix_private_ingestion_privileges.sql`, sau khi owner xác nhận migration history/forward plan chính xác. Schema/grants/RLS được kiểm trên local bằng migrations hiện tại, 479 pgTAP assertions. Không có migration mới hoặc sửa migration cũ. Việc đưa corpus hợp lệ lên hosted và bật provider có ngân sách là bước owner duyệt riêng; không làm RAG benchmark mới.

## E. Full-stack QA và lỗi giữ lại

| Lệnh / môi trường | Exit / kết quả |
|---|---|
| `uv sync --all-packages --all-extras --locked` | 0; 77 resolved / 74 checked |
| `uv run python scripts/check.py` | 0; ruff/format/pyright/import contracts; **1640 passed / 156 deselected**, 280.18s trên bản có delta linked-case |
| `uv run python scripts/export_contract_schemas.py --check`, `export_openapi.py --check` | 0; không drift |
| `npm ci` | 0; 7 moderate dependency advisories, không auto-upgrade |
| frontend `typecheck`, `lint`, `build`, `check:boundaries`, `format:check -- --end-of-line auto` | 0; source/bundle boundary clean. Windows checkout dùng CRLF theo `core.autocrlf=true`; kiểm tra format mặc định báo khác dòng kết thúc, kiểm tra auto đạt; CI checkout LF kiểm lệnh mặc định |
| frontend `npm test -- --maxWorkers=2` | 0; **27 files / 159 tests**, 81.40s sau sửa late roleplay response |
| pgTAP `supabase_worktree.py test --name int --offset 300 --lite` | 0; 21 files / 479 assertions; không reset DB |
| `uv run pytest -m integration -q --tb=short` với env riêng `.local/stacks/int/test.env` | 0; **150 passed**, bao gồm own/foreign/missing linked-case |
| demo `e2e_stack.py --run --project demo --name int --offset 300` | 0; 13 passed |
| scripted local `e2e_stack.py --run --project real --name int --offset 300 --agent scripted` | 0; **37 passed** trong 7.2 phút và **1 urgent test passed**. Chạy lại `--grep PC-UI` trên delta consent cuối: **1 passed** trong 10.0s, kiểm cả mặc định không consent, thoát phiên, opt-in và bảy viewport |
| `node scripts/audit-product.mjs`, final `--recheck --recheck-route=case-detail:320` | 0; 252 sweep + 19 behavior checks; axe/browser/network như mục B |
| hosted `hosted_product.py --prepare`, `--run`, `node frontend/scripts/hosted-product.mjs`, `--cleanup` | 0 ở final; 22 PASS / 0 FAIL / 7 BLOCKED; refresh/restart/cleanup exact paths có receipt |
| offline `agent/evals/product.py --out ...product-completion-20261110-verified` | 0; 20 ca / 151 checks; 60 live NOT_RUN |

Các lần đỏ không bị xóa: chat/analysis/roleplay regression trước sửa; clock-skew hosted 401; initial hosted wait/selector assumptions; preflight dùng to_regclass thiếu schema usage trước khi chuyển metadata read; native PowerShell stderr hiển thị NativeCommandError cho intentional fake-provider failure dù harness hoàn tất; một lần runner từ chối ghi đè artifact có sẵn; pgTAP 4 failures do assertion toàn bảng; PC-UI phát hiện case link 422; roleplay response cũ có thể ghi đè trạng thái đã thoát. Các lỗi sản phẩm được sửa với regression; fixture/harness assumptions được ghi khác với product defect. Không suppress browser5xx để xanh.

Quan sát hiệu năng: không load benchmark mới; hosted I/O chậm hơn local, nên waits kiểm signal thay sleep và timeout UI giữ dữ liệu. Poll không tạo request mới trước read cũ hoàn tất. Build còn cảnh báo chunk chính khoảng 545kB minified; jsdom không có canvas cho Orb tạo warning không fail. Không tuyên bố đã load test production.

Khi bàn giao, frontend tại `http://localhost:5173` và backend tại `http://127.0.0.1:8000` trả HTTP 200 (health/ready). Backend kiểm tra chạy qua `.local/product-completion/inspection_api.py`, dùng cấu hình Supabase thật đã đối chiếu, tắt paid client và worker purge/reconcile toàn cục. Đây là phiên kiểm tra local có giới hạn đã nêu, không phải chế độ giả lập thành công của Companion. Hosted audit servers riêng đã dừng sau cleanup.

## F. Git và CI

Starting SHA và upstream sau fetch: **`e02abdfab5221ffc7b620104194387ab15e6feb1`**, cây sạch, đúng repository/worktree. Không branch/worktree mới, không sửa main, không force-push/reset history. Thay đổi thuộc UI/case handoff/auth verification, agent scripted product protocol/safety regression, hosted guard utilities, scoped SQL tests và tài liệu/bằng chứng. Danh sách chính xác: `git diff --name-only e02abdf..HEAD`.

Commit source và commit evidence/report được ghi trong ledger bàn giao. SHA cuối của chính report không thể nhúng vào byte của commit chứa nó: xác định bằng `git log -1 --format=%H -- docs/implementation/reports/product-completion-review.md`, kiểm `git ls-remote origin refs/heads/mhiu05/feat-refactor`. CI workflow [Foundation](https://github.com/mhiu05/MoodPrint/actions/workflows/ci.yml) chạy trên SHA được push; kết quả và URL run chính xác được kiểm lại, lưu `.local/product-completion/delivery-receipt.json` và nêu trong handoff cuối. Không dùng CI SHA cũ để tuyên bố SHA cuối xanh.

## G. Remaining issues

| Mức | Vấn đề / hành động còn cần |
|---|---|
| P0 / External blocker | Hosted thiếu schema Phase 2/3: chặn Companion/approval/analysis/roleplay/Knowledge thật. Owner cần duyệt forward migration plan riêng; chưa thực thi |
| P0 / External blocker về an toàn | Q3-03 chưa được chứng minh; independent Vietnamese safety review còn thiếu. Không dùng với dữ liệu học sinh thật |
| External blocker | Paid live budget hết 900/900; chưa kiểm chất lượng model thật trên protocol sản phẩm. Amendment và live mapping như mục C |
| External blocker | Không thử public hosted signup/email verification/reset delivery; giữ settings thật và không gửi email thử hàng loạt. Genuine expired hosted JWT chưa có fixture |
| P2 | Moderate landmark/NotFound heading và contrast incomplete manual review; Chromium emulation chưa thay kiểm thiết bị/AT vật lý |
| P2 | Bundle-size warning và 7 npm moderate advisories cần đánh giá dependency riêng, không nâng major tự động |
| Deferred / ngoài phạm vi | Voice thật, liên hệ trường/cơ quan, deployment/AWS, release, nghiên cứu RAG, paid judge |

Không còn P0/P1 do phần sửa đã biết được cố tình bỏ qua. Các blocker trên vẫn ngăn tuyên bố hoàn tất nghiệm thu toàn bộ hosted MVP; unit/code tồn tại không thay bằng chứng UI.
