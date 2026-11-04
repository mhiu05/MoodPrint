# 08 — Sổ thực thi

Quy ước (giống `docs/implementation-plans/three-agent-orchestration-group-chat/12-execution-evidence.md`): mọi con số pass/fail/skip là **kết quả thật** của lệnh đã chạy, kèm lệnh và thời lượng. "Chưa chạy" ghi rõ. Lỗi có sẵn ở baseline tách khỏi hồi quy. Không ghi secret, URL có mật khẩu, ID tài khoản thật hay nội dung nhật ký.

| Hạng mục | Giá trị |
| --- | --- |
| Nhánh / worktree | `feat/journal-intelligence` / `E:\MoodPrint` (theo prompt bàn giao) |
| Gốc phiên này | `e2c3e5e8`, đã merge `main@d6280561`; nền kế hoạch `565f5a74` |
| PostgreSQL disposable | `scripts/disposable_postgres.py --port 36433`, container `moodprint-disposable-4e8979b64a084f1a8fe8c42aaadadf9f`, PostgreSQL 17.10 / pgvector 0.8.2 |
| Cách ly | Không mở/sửa trực tiếp `backend/.env`; sự cố subprocess có thể đọc dotenv và bản sửa được ghi tại mục JI-50 bên dưới. Không sửa `.gitignore`, stash hoặc các worktree khác. File `09-codex-prompt.md` có thay đổi sẵn của người dùng; giữ nguyên. |

## Trạng thái hiện tại (cập nhật khi chốt checkpoint)

Các commit tới checkpoint A `587e61d5` đã push thành công lên `origin/feat/journal-intelligence` (từ `e2c3e5e8`), sau khi gates 1–10/15 xanh. Chưa mở PR/merge/deploy. Các dòng lịch sử nói "đang chạy" hoặc "chưa push" được giữ để thể hiện thời điểm quan sát; trạng thái hiện tại trong bảng này và kết quả mới nhất cuối sổ có ưu tiên.

| Task | Trạng thái | Commit | Bằng chứng chính |
| --- | --- | --- | --- |
| JI-00 | xong | nền `e2c3e5e8` | baseline 1964 pass/3 skip; fixture 445 pass |
| JI-01 | xong | `59d4dd02`, bổ sung `d9cb601f` | full RED 307 fail; full GREEN 1968 pass/3 skip; 2 load fixture config pass |
| JI-02 | xong | `5f6ed77a` | 100 regression pass; check_config với empty.env exit 0 |
| JI-10 | xong | `651f1fde` | frontend unit/type/build; nav/retirement browser assertions |
| JI-11 | xong | `ddb8c18e` | copy/card retirement và frontend gates; có xung đột stash Auth/GuestEntry |
| JI-12 | xong | `edca78d0` | 57 backend regression pass; frozen prompt hashes giữ nguyên |
| JI-13 | xong | `395dbedc` | fullstack cuối 38 pass; fixture cuối 382 pass |
| JI-20 | xong | `6795c34f` | 10 migration tests pass; local head 0029/check không drift |
| JI-21 | xong | `216c3be6` | 6 settings tests + 3 browser tests pass; hợp đồng không drift |
| JI-22 | xong | `f691898d` | revision/deletion/cap/backfill/provider lock regression pass |
| JI-23 | xong | `9fefdf8d` | 105 regression pass; 17 targeted retrieval/eval pass |
| JI-24 | xong | `6adc9fa4` | CLI fake exit 0; 40 entry/15 query/55 fake calls |
| Checkpoint A | xong | `587e61d5`, đã push | backend 2065 pass/3 skip; gates 1–10/15 xanh |
| JI-40 | xong | `b3f344ac`, chưa push | 32 backend pass; hồi quy 204 pass; frontend 205 + 2 pass; browser skill 7 pass |
| Checkpoint B | xong | `7cd83b08`, đã push | backend 2082 pass/3 skip; fixture 384 pass; fullstack 38 pass |
| JI-30 + JI-31 | xong | `61469170`, chưa push | 269/228 regression pass; precommit 68 pass; browser cuối 3 pass |
| JI-25 | xong kiểm chứng task | commit task kế tiếp | 51 regression pass; ranking/timeout/settings/dimensions guards |
| JI-50 đầy đủ | một phần | SQL `9f3c238e`; docs còn cập nhật | 37 Linux tests pass; fake eval có số; live/hosted chưa chạy |
| JI-51 | ngoài phạm vi | — | không migrate/deploy/SSM/đọc hosted |

## Quyết định và preflight — 2026-11-04

- Ruling: dùng workspace hiện tại theo prompt 09 thay cho workspace cũ trong ledger; giữ nguyên thay đổi chưa commit của người dùng.
- Ruling JI-01: test mặc định phải xóa env FEATURE_FLAGS trước khi tạo Settings vì pytest_configure cố định false. Đã sửa 01-flags.md trước triển khai. Giữ nguyên bảo vệ pytest_configure; dùng ALL_FEATURES_OFF ở fixture và harness.
- OD áp dụng theo prompt: OD-01 giữ 5 công tắc an toàn false; OD-02 không đổi budget; OD-03 giữ router backend; OD-04 notice/component opt-out riêng; OD-05 90 ngày; OD-06 không xử lý guest tự động; OD-07 giữ memory đã sửa, tắt không xóa memory; OD-08 chỉ nhatky; OD-09 sửa copy trên nhánh, không đụng stash; OD-10 backfill 14 ngày; OD-13/14 không đổi; OD-15 raise mâu thuẫn tường minh, clamp mặc định.
- Yêu cầu mới của chủ dự án cho phép push, PR, merge main và kiểm thử web thật sau hoàn thiện. Không tự suy ra quyền đọc hosted DB, migrate hosted, đọc runtime SSM hoặc gọi provider thật. Phải đối chiếu tự động phát hành khi merge với yêu cầu schema 0029 trước khi thực hiện merge.
- Interfaces preflight: JI-01 → JI-02 cần env defaults thật; JI-20 → JI-21/22/30/31 dùng settings_version và FK cascade; JI-21 → JI-23/30 dùng journal_ai_allowed, autoMemoryAvailable=false tới JI-30; JI-22 → JI-23 query embed ngoài owner lock, revision fence; JI-30 + JI-31 là một khối phát hành; JI-23 → JI-40 giữ refusal/mood scope/evidence. Chưa thấy xung đột ngoài ruling env đã ghi.
- Ruling: quy tắc mới `tests/database_target.py` yêu cầu tên DB khớp run ID, owner/session owner và marker của disposable script; tên `moodprint_ji_*_test` của kế hoạch bị từ chối. Dùng DB con `moodprint_<run-id>_<12-hex>_test`, owner và marker giữ đúng phiên. Không nới guard. Hậu tố baseline `ba5e11000001`, unit `000000000001`, red `000000000002`, green JI-01 `000000000003`, fullstack/eval dành riêng `000000000004`.
- Ruling: baseline và red/green toàn suite chạy từ bản nguồn cố định trong `.tmp/journal-intelligence/`, dùng Python/lockfile hiện có. Bản baseline lấy `git archive e2c3e5e8`; red thêm đúng config mặc định mới + test mặc định, chưa ghim nền; green thêm ghim nền. Không có `backend/.env` trong archive. Cho phép chuẩn bị task kế tiếp sau targeted green, nhưng chưa đánh dấu hoàn tất/commit task trước khi full suite của chính snapshot kết thúc. Chi phí nếu sai: tests phụ thuộc checkout/git có thể cần chạy lại trong workspace thật; final gates vẫn chạy workspace thật.

## JI-00 — Baseline

Baseline mới đã hoàn tất (ledger cũ chưa có kết quả). Port 36432 đã được container khác chiếm; tạo container riêng 36433, không dừng container sẵn có. Logs phiên chỉ ở `.tmp/journal-intelligence/`; credentials chỉ ở file disposable do script tạo.

- `uv sync --locked`: exit 0 (102 packages resolved, 65 checked), không đổi lockfile.
- `uv run --locked ruff check app tests evals alembic`: PASS; `uv run --locked mypy app`: PASS, 184 source files.
- `npm.cmd ci`: exit 0, 230 packages added, 0 vulnerabilities; typecheck/build PASS. Vitest **39 files / 241 passed** (5,98 s) + Node script checks **2 passed**. Build lớn nhất: `RealApp-Brq1_h0Y.js` 406,40 kB / gzip 124,42 kB.
- DB guard diagnostic với target đúng: `pytest -q tests/test_journal.py -x`: **12 passed**, 55,71 s. Lượt đầu target sai bị guard từ chối, đã ngắt, không coi là baseline failure sản phẩm. Full suite snapshot baseline `python -m pytest -q -p no:randomly --ignore=tests/live --junitxml=<scratch>/baseline-pytest.xml`: **1964 passed, 3 skipped, 4732,76 s**, 0 fail. Ba skip có sẵn: collaboration latency opt-in, V3 live eval tốn phí opt-in, V3 latency opt-in; không thêm skip mới.

## JI-01 — Danh sách test giả định cờ tắt (red run)

Red run toàn suite từ snapshot bất biến đã kết thúc. Lệnh: `python -m pytest -q -p no:randomly --ignore=tests/live --junitxml=<scratch>/ji01-red-suite.xml`; kết quả **307 failed, 1661 passed, 3 skipped, 4485,46 s**. [Danh sách chính thức 307 failure](11-default-flag-red-failures.md) được sinh từ XML, không suy ra từ số dấu F: 189 AssertionError, 25 KeyError, 21 TimeoutError, 2 ValidationError, 34 RuntimeError, 21 ModelBehaviorError, 3 ValueError, 8 IndexError, 2 NoResultFound, 2 DomainError. Baseline và full green còn đang chạy; chưa dùng lượt RED làm kết quả nhánh cuối.

- RED test mới: `uv run --locked pytest -q tests/test_default_flags.py`: **1 collection error**, `ImportError: cannot import name 'FEATURE_FLAGS'`, pytest 1,29 s (runner 7,063 s).
- Sau đổi config, trước ghim nền: cùng file **4 passed**, 0,24 s.
- Ghim nền: mở rộng env trong `pytest_configure` từ `ALL_FEATURES_OFF`, đồng thời truyền baseline tường minh trong `clients`, `e2e_server.py`, `proactive_load_worker.py`. `chat_history_enabled=True`. Không xóa/sửa khối guard secret cũ.
- Targeted GREEN: `uv run --locked pytest -q tests/test_default_flags.py tests/test_guest_contracts.py tests/test_live_observability.py tests/test_three_agents.py`: **19 passed**, 98,99 s. Full green từ snapshot riêng (cùng lệnh baseline, đích DB/source khác): **1968 passed, 3 skipped, 4732,79 s**, 0 fail; tăng đúng 4 test defaults, cùng 3 skip baseline. Kết quả này chốt JI-01, không thay thế full suite sau JI-02…JI-24.
- Test đổi assertion: `test_guest_input_and_settings_defaults_fail_closed` kiểm `experience_view` unavailable/configuration_missing, feedback và guest paid false khi thiếu cấu hình, thay assertion sáu flag false vì default đổi theo yêu cầu. `test_local_live_actor_allowlist_is_closed_by_default_and_rejected_in_production` đặt `ai_enabled=False` tường minh để tiếp tục kiểm scope allowlist. Test năm companion đổi tên ghi rõ legacy baseline; không đổi assertions.
- `check_docs.py`: PASS, 179 Markdown / 1157 links / 141 operations / 115 settings / 61 tables.

## Tiếp tục triển khai — bằng chứng tạm, chưa commit

JI-01 commit cục bộ **`59d4dd02`**, chưa push. JI-02 precommit rerun đúng 8 file test đã liệt kê trong JSON `ji02-precommit`: **100 passed, 195,36 s**. Stage lấy snapshot đã kiểm chứng của task, không ghi đè thay đổi task sau trong working tree. `.gitignore` hiện có thay đổi ngoài tác vụ (người dùng đang mở file); không đọc/sửa/stage thay đổi đó.

JI-02 commit cục bộ **`5f6ed77a`**, chưa push. JI-10 chốt từ snapshot riêng đã kiểm chứng frontend unit/type/build + browser 3 ca RED→GREEN (bảng dưới); stage 44 file đúng task, giữ các sửa copy/API sau trong working tree.

JI-10 commit cục bộ **`651f1fde`**, chưa push. JI-11 chốt snapshot 16 file với RED/GREEN đã ghi, frontend suite sau tích hợp **204 pass + 2 script checks**, typecheck/build mới nhất pass. OD-09 Auth.tsx/GuestEntry.tsx có thay đổi sẽ xung đột stash người dùng; không pop/drop stash.

JI-11 commit cục bộ **`ddb8c18e`**, chưa push. JI-12 precommit `pytest -q tests/test_retired_social.py tests/test_agent_skills.py tests/test_prompt_options.py tests/test_three_agents.py tests/test_orchestration_sdk.py tests/test_groups_turn.py`: **57 passed, 118,59 s**. SHA instructions/persona được test bảo vệ; snapshot runtime chỉ chứa lọc card, chưa lấy thay đổi truy xuất JI-23.

JI-12 commit cục bộ **`edca78d0`**, chưa push. JI-20 precommit `pytest -q tests/test_journal_intelligence_migration.py tests/test_memory.py tests/test_embeddings.py tests/test_v3_migration.py tests/test_collaboration_migration.py tests/test_readiness.py`: **79 passed, 446,06 s**. JI-23 targeted `tests/test_journal_retrieval.py tests/test_journal_retrieval_eval.py`: **17 passed, 47,65 s**, gồm assertion marker usage +j2 thật và provider failure fallback. Offline `apply_supabase_review.py --upgrade 0029` review-only: **exit 0**, alembicExportMatches=true, SHA `e15bb5fefbcfec4b3e6bf76463fcf9470a32a331835c1d93977ea4c53a9bc476`, 7488 bytes không BOM/%%. Chưa apply SQL; manifest cần commit migration thật trước khi pin cuối.

JI-13 kiểm chứng tích hợp: baseline fixture **445 passed/15,0 phút**; fullstack baseline **50 tests/18 files** (chỉ collect/list, không suy ra pass), sau gỡ social + thêm journal journey **38 tests/16 files**. Fullstack run đầu **35 passed/3 failed/9,0 phút**: locator responsive `Mây` thay nhãn thật `Mây AI`; locator Trợ lý match cả legacy role; collaboration đổi cờ trước khi run trước completed. Giữ mọi assert quyền/receipt, sửa locator theo heading/nav exact và chờ phản hồi terminal. Run ba file sửa **6 passed/1 failed/1,9 phút**, lộ thêm locator nav ở tab thứ hai; sửa cùng phạm vi. Run toàn bộ tiếp **37 passed/1 failed/13,5 phút**, chỉ V3-D gửi lượt kế trước terminal: trace synthetic xác nhận 2 POST 202 + 1 POST 409, không lỗi production authorization. Thêm chờ `.group-typing` rỗng giữa các lượt, không bỏ kiểm tra typing/order/axe. Rerun `v3.spec.ts`: **8 passed/1,6 phút**. Source inventory giữ trong 10; không thêm skip/xfail.

Ruling commit JI-13: chốt code test theo bằng chứng tổng hợp **37 ca fullstack pass + 8 ca V3 mới nhất pass** (file sửa cuối chỉ thêm chờ terminal). Đây **không** được ghi là một lượt 38/38 xanh; fullstack toàn bộ vẫn phải chạy ở checkpoint A trước push. Fixture toàn bộ 382 ca đang chạy lại; lượt 379 xanh trước đó và regression có lỗi đã ghi riêng. Chi phí nếu còn race: final checkpoint chặn phát hành, không bỏ assertion để qua gate.

JI-13 commit **`395dbedc`**, chưa push. JI-20 chốt candidate 0029 + ORM + readiness + import model + inventory, với 79 precommit tests pass ở trên. Alembic env luôn tắt dotenv (test guard RED→GREEN đã ghi), target local `_test` vẫn phải đặt tường minh. Pin SQL sẽ dùng đúng hash commit này sau commit.

JI-20 commit **`6795c34f`**, chưa push. Manifest SQL ghi generatedFrom `6795c34fee6c3d7e365453e92e5ebbaf5d4b9e04`; checker **PASS: 12 pinned approvals / 12 consumed**. Checkpoint A full backend mới (`--ignore=tests/live`, JUnit riêng) và fullstack toàn bộ đang chạy, không dùng kết quả JI-01 để thay gate này.

JI-21 chốt candidate API/notice/component/hợp đồng đã export, test settings 6 pass + browser 3 pass + các hồi quy 100 pass/17 pass ghi ở trên; frontend typecheck/build/unit pass. Component hàm thuần dùng hậu tố Model theo ruling Windows. Auto memory vẫn unavailable=false. Không stage backend worker JI-22 vào commit này.

JI-21 commit **`216c3be6`**, chưa push. JI-22 chốt worker/debounce/revision fences, hooks cùng transaction, lifecycle, cap receipt bền, prefilter age và FakeEmbedder. RED/GREEN từng ca, 100 regression pass + 7 ca cap mới nhất pass đã ghi. Ruling bổ sung module `quota.py` dùng bảng có sẵn thay vì schema mới; các outcome không xác định giữ reservation bảo thủ, không có provider call giữ owner lock. Full backend checkpoint mới đang chạy trên working tree tương ứng; kết quả phải chờ, chưa tuyên bố gate xanh.

JI-22 commit **`f691898d`**, chưa push. JI-23 chốt hybrid search/runtime prompt +j2 và source evidence, theo các lượt 105 regression pass, 17 targeted pass và browser journal intelligence pass. Tool embed ngoài owner lock, recheck settings version trong lock; nhật ký/refusal/mood scope/citations không được nới. Thêm fullstack model marker chỉ test, không provider thật.

JI-23 commit **`9fefdf8d`**, chưa push. JI-24 CLI cuối với `--embedder fake --out <scratch>/ji24-eval`: **exit 0, 11,141 s**, 55 fake calls. Không chạy Voyage. Recall/MRR giữ số như bảng trước; latency toàn bộ baseline keyword p50 **31,9999999992433 ms**, p95 **93,99999999914144 ms**; hybrid p50 **31,9999999992433 ms**, p95 **93,0000000007567 ms** (nearest-rank percentile). JSON giữ đầy đủ từng nhóm. Các số này dưới tải synthetic/local; không suy ra latency/quality thật. `tests/test_journal_retrieval_eval.py` 2 pass và cụm retrieval/eval mới nhất 17 pass. Runner chỉ `_env_file=None`, local disposable identity guard, xóa đúng actor synthetic sau hoàn tất.

JI-24 commit **`6adc9fa4`**, chưa push. Fullstack mới nhất **38 passed, 6,2 phút** (runner 381,187 s), gồm V3-D đã chờ terminal, không còn fail. Fixture owned chạy song song fullstack: **380 passed/2 failed, 14,3 phút**; một logout trace có `net::ERR_NO_BUFFER_SPACE`, ca paused schedule còn chờ lazy component. Thử giả thuyết StrictMode bằng harness riêng: hai lượt đầu hỏng setup import Vite, sau sửa harness **1 passed/7,3 s trên code chưa sửa**; giả thuyết chưa được xác nhận nên không sửa production hook. Gỡ đúng test harness mới chưa commit và testMatch của nó; không xóa test gốc. Đóng browser public do phiên sở hữu, rerun hai ca lỗi một worker không fullstack song song: **2 passed, 8,9 s**. Ruling chạy owned suite một worker để giảm áp lực socket/memory Windows, giữ timeout/assertion; không thay worker default/CI. Full serial đang chạy.

Full backend A đã thấy một failure, collect-current có **2063 tests**, vị trí failure tương ứng `test_0020_preserves_journal_auth_matching_and_approved_memories`; rerun riêng trên sibling `_test` khác để xem lỗi, không giẫm DB full suite. Chưa coi gate A đạt.

### Hồi quy phát hiện bởi full backend A (đang chạy)

- `test_discovery_migration.py` RED riêng **1 failed, 8,65 s**: constant HEAD còn 0028 trong khi Alembic current trả 0029. Chỉ đổi HEAD→0029, giữ toàn bộ dữ liệu/RLS/rollback assert. GREEN **1 passed, 29,73 s**.
- `test_foundation.py` có hai failure trong full A: tuple READY_REVISIONS và ca 0028→200. Đổi expected head 0029, bắt 0028→503, thêm 0029→200; không mở cửa chấp nhận schema cũ. `pytest -q tests/test_foundation.py tests/test_readiness.py`: **53 passed, 53,46 s**.
- `test_guest_cleanup_recovery.py::test_guest_aware_rollback_cannot_resurrect` cũng ghim tuple 0028; đổi 0029, giữ toàn bộ denial/purge/peer assertions.
- `INVENTORY` guest thiếu ba bảng journal AI: phân loại purged (entry cascade cho job/vector, settings đã xóa tường minh). Isolated `test_inventory_classifies_every_orm_table` còn lộ phụ thuộc collection side effects đăng ký các model cũ. Bổ sung app build offline trước equality; không đổi assertion/allowlist nhóm. Lượt giữa **1 failed/6 passed/36 deselected, 24,53 s** ghi nhận setup chưa đủ; lượt cuối `tests/test_guest_cleanup.py tests/test_guest_cleanup_recovery.py tests/test_journal_indexing.py -k 'inventory_classifies or purge_removes_every_guest_owned_store or every_journal_delete_path or rollback_cannot_resurrect'`: **8 passed/49 deselected, 19,66 s**.
- Full A đang giữ các failure cũ đã collect/compile trước sửa; phải phân biệt với rerun xanh trên source mới, không ghi full suite xanh. Cần lượt full final sau sửa để chốt gate.
- Operation inventory của `test_guest_permissions.py::test_every_operation_has_guest_policy` cũng fail trong full A vì thiếu GET/PUT journal/ai-settings. Thêm vào REGISTERED_ONLY, giữ equality và mở rộng tự động hai ca live guest403/expired guest401; không sửa assertion để bỏ endpoint mới. Full file rerun đang chạy trên sibling riêng.
- Ruling lệnh eval: dùng `python -m evals.journal_retrieval.run ... --out <dir>` từ backend để import app ổn định và cấp output bắt buộc; đã cập nhật cổng 12 của 06. Không thêm dependency hoặc chạy live.

Các task dưới đây đã có triển khai và targeted tests; JI-01 đã có full green để chốt commit đầu tiên (hash bổ sung sau commit). Các task dưới bảng vẫn chờ commit riêng. Chưa chạy checkpoint A/B, chưa push/PR/merge/deploy. Những cổng thiếu bên dưới vẫn là việc phải làm.

| Task | RED quan sát | GREEN quan sát | Còn thiếu để chốt |
| --- | --- | --- | --- |
| JI-02 | Default tests: 2 fail/5 pass + 2 missing fixture; production tests cũ 3 fail; docs inventory 2 fail | `pytest -q tests/test_default_flags.py tests/test_production_settings.py tests/test_docs_inventory.py` và các test liên quan trong `ji02-final-targeted.log`: **100 passed, 141,07 s**. `check_config.py --env-file E:/MoodPrint/.tmp/empty.env`: exit 0, configuration_missing, networkAccessPerformed=false | Full regression + commit |
| JI-10 | `navigation-retired-social.spec.ts`: **3 failed** | Cùng spec **3 passed, 13,8 s**. Frontend **198 tests/33 files + 2 script checks**, typecheck/build pass. RealApp 309,16 kB/gzip 96,62 kB | Commit snapshot đã đóng băng; final browser gate |
| JI-11 | 3 files fail, **4 failed/14 passed** | Frontend **203 tests/35 files + 2 script checks**, typecheck pass | Commit snapshot; liệt kê đầy đủ test xóa/sửa |
| JI-12 | `test_retired_social.py` và hồi quy: **9 failed/13 passed, 14,71 s** | `pytest -q tests/test_retired_social.py tests/test_agent_skills.py` và hồi quy trong `ji12-green.log`: **57 passed, 86,15 s** | Commit; final SHA gate |
| JI-13 | Offline AI send: **1 failed** (nút vẫn enabled khi offline) | Sửa chặn offline bằng `useOnline`; test **1 passed, 4,6 s**. Fixture browser suite `ji13-e2e.log`: **379 passed, 12,1 phút** | Fullstack chưa qua startup; kiểm tra lại UI settings mới; inventory test |
| JI-20 | Replay trên baseline/sibling DB riêng: **1 error, 12,35 s**, thiếu migration 0029 | `pytest -q tests/test_journal_intelligence_migration.py`: **10 passed, 21,40 s**. Local `upgrade head` thành công; `alembic check`: **No new upgrade operations detected** | Các regression migration; offline SQL pin ở JI-50; commit |
| JI-21 | `test_journal_ai_settings.py`: **6 failed, 64,17 s**, HTTP 404 | **6 passed, 37,02 s**. OpenAPI export → contracts generate đã chạy. Frontend **204 tests/36 files + 2 script checks**, typecheck pass | Rerun sau enqueue hooks; browser settings; commit |
| JI-22 | `test_journal_indexing.py`: **1 collection error, 1,39 s**, thiếu module indexing | **17 passed, 64,69 s**; kiểm debounce, revisions, cascade 5 đường, retry/cap, lease, opt-out, provider ngoài lock và backfill | Regression journal/privacy/embedding; commit |

Các log/JSON ở `.tmp/journal-intelligence/` là artifact cục bộ, không commit. Thời lượng pytest và runner khác nhau do thời gian khởi động uv, chỉ dùng số pytest trong bảng. Lệnh chính xác từng lượt được giữ trong JSON tương ứng; bảng này chưa thay thế báo cáo cổng JI-50.

- Ruling JI-20: PostgreSQL CHECK cho `source_entry_version >= 1` chấp nhận NULL. Thêm `source_entry_version IS NOT NULL` trong nhánh journal_auto để thực thi ý nghĩa đặc tả. Không thêm cột/schema ngoài 0029; thêm ca NULL vào test sai nguồn gốc. Chi phí nếu sai: dữ liệu auto thiếu provenance bị từ chối chủ động.
- Ruling JI-13: kiểm thử trạng thái offline chuyển từ human chat đã gỡ sang AI phát hiện nút gửi AI không khóa khi offline. Thêm guard/disabled vào AI composer và kiểm chứng RED→GREEN; giữ cancellation/recovery hiện hành.
- Ruling JI-13: giữ coverage quản trị moderation bằng endpoint seed **chỉ test**, yêu cầu cả test env và app_env=test, thay việc tạo báo cáo qua giao diện social đã gỡ. Chưa coi fullstack moderation đạt cho tới lượt fullstack xanh.
- Ruling docs: tài liệu hiện hành trỏ sang navigation còn tồn tại; audit lịch sử ghi rõ đường dẫn/commit baseline của hook social đã gỡ, không giữ link hỏng. Tài liệu matching ghi spec browser đã retired, backend tests còn nguyên.
- Docker Desktop dừng trong thời gian phiên gián đoạn; các lượt full suite trước đó bị ngắt/lỗi kết nối, **không tính pass**. Chỉ khởi động lại container do phiên tạo, tái tạo DB tmpfs với owner/marker đúng; không khởi động/dừng container khác. Ba full suite baseline/red/green đã chạy lại, chưa có kết quả cuối.
- Một lượt pytest ban đầu thu thập `tests/live` và dừng tại target guard; không gọi mạng/provider. Sau phát hiện, mọi full suite dùng `--ignore=tests/live`. RED chính thức không lấy từ lượt lỗi môi trường này.
- Fullstack `ji13-fullstack` dừng trước khi test: server chưa sẵn sàng trong startup budget. Backend log rỗng, frontend ready; sẽ chạy lại khi các suite nặng xong, không nới timeout harness.
- Reviewer/implementer phụ JI-13 bị giới hạn usage trước khi gửi báo cáo. Parent kiểm tra log/diff và tiếp tục phần thiếu; không suy ra hoàn tất từ trạng thái agent.
- Một lệnh Ruff từ root với config backend gây reorder import ngoài phạm vi. Đã chạy lại đúng cwd backend và xác minh các file ngoài phạm vi không còn diff. Không giữ thay đổi đó.
- Đã xem landing/login web hiện hành bằng browser, không đăng nhập, không đọc dữ liệu riêng, không gọi provider; screenshot cục bộ. Đây là bản đang chạy trước thay đổi, **không phải xác minh tính năng mới trên hosted**.

## Bằng chứng tiếp tục JI-21…JI-24 (chưa commit)

- JI-21 browser RED: **3 failed** do Vite/esbuild Windows phân giải `JournalAiSettings.tsx` sang `journalAiSettings.ts` (thiếu export). Ruling: đổi hàm thuần thành `journalAiSettingsModel.ts`, ghi rõ vào 03; API/component giữ tên. Sau đó **2 failed/1 passed**: controlled checkbox khôi phục trạng thái cũ trong thời gian chờ response. Cập nhật optimistic state, rollback state khi request lỗi. GREEN `PLAYWRIGHT_PORT=5190 node node_modules/@playwright/test/cli.js test journal-ai-settings.spec.ts --reporter=list`: **3 passed, 26,0 s**, gồm 1440/390px, reload, unavailable save, axe trên section và guest không request.
- Regression `pytest -q tests/test_journal_ai_settings.py tests/test_journal_indexing.py tests/test_journal.py tests/test_journal_contract.py tests/test_privacy_lifecycle.py tests/test_embeddings.py tests/test_memory.py tests/test_v3_migration.py tests/test_collaboration_migration.py tests/test_reviewed_artifacts.py`: **2 failed/109 passed, 346,08 s**. Hai fail là fixture JI-21 seed job trùng job đã được hook JI-22 tạo. Chỉ xóa job của entry synthetic trước seed fixture riêng, không thay constraint/assertion. Rerun `tests/test_journal_ai_settings.py`: **6 passed, 16,79 s**.
- JI-23 RED `pytest -q tests/test_journal_retrieval.py`: **1 collection error, 1,86 s**, thiếu module retrieval. GREEN đầu **8 passed, 49,62 s**. Sau bổ sung SDK timeout và quyền: hồi quy có **2 failed/91 passed, 135,20 s**, đúng hai assertion cũ về limit/shape; đổi limit không hợp lệ 6→9 (giới hạn mới 8), cho phép field `match`, và kiểm `100_` không thành wildcard qua hai kết quả `recent` thay vì [] vì fallback gần nhất là hành vi mới. Không bỏ assertion owner/draft/date/size.
- JI-23 test bổ sung mood-scope dùng sai output schema SDK: **1 failed/104 passed, 127,03 s**. Sửa test chỉ kiểm tool không được cấp trong mood scope; đường mood SDK đầy đủ vẫn nằm trong `test_mood_evidence_runtime.py`. GREEN `pytest -q tests/test_journal_retrieval.py tests/test_journal_ai.py tests/test_mood_evidence_runtime.py tests/test_scoped_mood_tool.py tests/test_context_selection.py tests/test_sdk_adapter.py tests/test_three_agents.py tests/test_orchestration_sdk.py`: **105 passed, 143,76 s**.
- JI-23 bổ sung test runtime đổi settings version khi query embed đang chờ, xác minh provider không giữ owner lock và vector cũ bị bỏ: `pytest -q tests/test_journal_retrieval.py`: **13 passed, 36,18 s**. Query timeout thực sự đi qua SDK và lượt completed; citations vẫn bắt buộc thuộc nguồn đã trả với lỗi 409 JOURNAL_CITATION_INVALID. Usage runtime marker `+j2`, không đổi persona/prompt đóng băng.
- JI-24 RED `pytest -q tests/test_journal_retrieval_eval.py`: **1 collection error, 0,59 s**, thiếu eval module. GREEN: **2 passed, 7,37 s**, dataset 40 entry/15 query đúng 5 keyword + 6 paraphrase + 4 pattern. Skill DeepEval được đối chiếu nhưng workflow thêm dependency/provider trái giới hạn của chủ dự án; giữ harness pytest/SQL và fake embedder đã đặc tả, không cài DeepEval.
- CLI `python -m evals.journal_retrieval.run --embedder fake --out <scratch>/ji24-eval`: lần đầu lộ guard nhận AsyncSession sai loại; sửa sang AsyncConnection. Lần sau metric xong nhưng cleanup lộ FK consent; sửa thứ tự xóa entry → consent → age declaration → đúng user synthetic. Lượt cuối **exit 0, runner 13,734 s**, 55 fake calls, không provider thật. Recall@6/MRR@6 keyword baseline **1/1**, paraphrase **0/0**, pattern **0/0**; hybrid keyword **1/1**, paraphrase **1/1**, pattern **0,625/0,75**, tổng **0,9/0,9333333333333333**. Các latency đầy đủ ở report JSON cục bộ; sẽ lấy số sau lượt CLI cuối ở gate JI-50. Chỉ chứng minh pipeline, chưa chứng minh chất lượng Voyage.
- Ruling JI-22: cap/ngày phải tính ngày thành công, không phải ngày enqueue; job backfill có thể qua đêm. `available_at` được đóng dấu thời điểm succeeded để đếm ngày local; owner lock đếm thêm lease running còn hạn (trừ chính job) để giữ phần cap đang xử lý trên worker khác. Không thêm schema ngoài 0029. RED hai ca completion-day/concurrent: **2 failed/17 deselected, 16,20 s**. GREEN `pytest -q tests/test_journal_indexing.py tests/test_journal_ai_settings.py tests/test_journal_retrieval_eval.py`: **27 passed, 49,96 s**.
- Backend Ruff đúng cwd: **All checks passed**; mypy **188 source files pass** tại thời điểm có retrieval. Docs checker **179 Markdown / 1154 links / 143 operations / 122 settings / 64 tables, PASS**. Cần chạy lại final gates sau các task còn lại.

## JI-50 / phát hành

### JI-25 — Truy xuất consult có xếp hạng

Sau commit nguyên khối memory **`61469170`**, RED `pytest -q tests/test_orchestration_sdk.py -k consult_ranks_relevant`: **1 failed/7 deselected, 4,82 s**, helper chưa nhận `query_vector`. Thêm helper settings keyword-only để lọc đúng config, fallback None giữ recent cũ; vector tính trong decide sau decision cho phép và trước open_step, không owner lock; recheck preference version/model/dimensions khi lấy nguồn. GREEN test end-to-end qua SDK thực/fake model **1 passed/7 deselected, 4,88 s**. Giữ 14 ngày/5 trang/600 ký tự, nguồn foreign/outside window bị loại.

Mở rộng cùng test cho preference đổi trong embed, dimensions đổi và timeout ⇒ fallback recent hoàn tất. Rerun hồi quy có hai lệnh sai danh sách/path Windows (`test_orchestration_state.py` không tồn tại, sau đó prefix backend lặp): **exit 4/no tests ran**, không ghi PASS. Đã dùng Path.relative_to(...).as_posix() lấy đúng ba file orchestration + retrieval để chạy; kết quả còn chờ. Ruff có một import-order test, đã sửa; mypy 190 files PASS.

JI-25 GREEN hồi quy cuối `pytest -q tests/test_orchestration_policy.py tests/test_orchestration_sdk.py tests/test_orchestration_sse.py tests/test_journal_retrieval.py`: **51 passed, 51,68 s**, runner 54,484 s; bốn ca ranking/fallback đều hoàn tất qua SDK. Khởi động full backend final trên DB7 và fixture final/server owned sau khi code đã ổn định; chưa chỉnh frontend trong khi suite chạy. Reviewer độc lập fresh-context `journal_final_review` đã được giao toàn diff/schema/worker/context/retrieval, chỉ đọc source, không DB/provider/network. CI checkpoint B `7cd83b08` **success**: [Verify](https://github.com/mhiu05/MoodPrint/actions/runs/41811789160).

### Bắt đầu khối JI-30 + JI-31 sau checkpoint B

`git push origin feat/journal-intelligence`: **exit 0**, `587e61d5..7cd83b08`; JI-40 `b3f344ac` và checkpoint B đã lên origin. Chưa mở PR/merge/deploy. Khối memory dùng một commit nguyên khối theo ruling 04 để không có commit phát hành worker thiếu labels/API/UI.

JI-30 RED `pytest -q tests/test_journal_auto_memory.py`: **1 collection error, 1,27 s** (runner 2,875 s), `ModuleNotFoundError: app.ai.journal_memory`. Tests đã bao gồm debit/accounting thật qua fake SDK có usage synthetic, không tạo provider client thật, debounce, grounded/clinical/PII/claim/dedup, retry, edit/delete fence, opt-out, budget/daily cap và data_version không đổi. Ruling tên trợ lý vs danh từ thường được ghi 04; không đổi clinical fold guard.

JI-30 GREEN đầu cùng lệnh: **21 passed, 17,73 s** (runner 19,828 s). Model là fake SDK có usage synthetic 100 input/10 output, `_openai` bị test thay thành hàm raise để cấm tạo client thật. Thêm tám settings đã vào inventory. Worker memory không phụ thuộc Voyage; enqueue/reconcile lọc registered/adult/AI policy trước LIMIT và live recheck; provider ngoài transaction, owner→job; publish không tăng data_version. Dùng cap receipt riêng bền/72h, budget share tính cả reservation dưới cùng global lock, pricing/quota/SDK timeout/retry guards giữ nguyên. Không commit worker riêng khi JI-31 chưa hoàn tất.

Lint/type JI-30 lần đầu: 3 import-order + 1 unused import; mypy 3 lỗi annotation/None/Literal trong module mới. Đã sửa (result None xử lý failed/retry content-free), Ruff fix 4 diagnostics; mypy **190 source files PASS**. Các hồi quy và cổng đầy đủ sau khối còn phải chạy, chưa dùng 21 test này để tuyên bố toàn nhánh xanh.

JI-30 hồi quy trước đổi interface memory: `pytest -q tests/test_journal_auto_memory.py tests/test_memory.py tests/test_embeddings.py tests/test_ai_quota.py tests/test_budget_reservations.py tests/test_proactive_*.py` (script mở glob thành danh sách cố định): **269 passed, 190,53 s**, runner 194,860 s. Không sửa `tests/test_memory.py`.

JI-31 RED `pytest -q tests/test_journal_auto_memory_api.py`: **6 failed, 10,37 s**, runner 14,797 s: thiếu origin/source date, bulk route, MemoryText/nhãn context, planner lọt automatic label vào recentTurns. Frontend RED `npm.cmd test`: **1 suite failed/36 passed, 205 tests passed, 3,36 s**, thiếu module memoryView. GREEN API + context selection: **9 passed, 9,02 s**. Browser lần đầu “No tests found” vì config testMatch đóng; thêm đúng spec memory-auto vào allowlist. Chạy trên Memory UI cũ từ checkpoint B (candidate lưu byte): **1 failed**, badge expected 2/got 0. Phục hồi candidate: **1 passed, 5,3 s** (test 3,1 s): badge/link nguồn, edit expectedVersion, delete hai bước, bulk dialog focus “Giữ lại”, idempotency key và không gọi xóa journal.

JI-31 regression đầu: **6 failed / 166 passed, 203,21 s** (runner 207,578 s); chỉ sáu test embedding còn expected `str` trong khi interface đặc tả chuyển `MemoryText`. Đổi đúng bảy assertion giá trị sang `MemoryText(..., 'approved')`, giữ mọi filtering/provider/bounds assertion, ghi inventory. Frontend Vitest GREEN **206 tests/37 files, 3,64 s** + 2 script checks; typecheck lúc đầu một lỗi test truyền undefined cho origin, mở helper nhận undefined để giữ tương thích DTO cũ; typecheck rerun PASS. Lint sau JI-31 có hai import/unused rồi một import order lifecycle, đã sửa; full Ruff PASS và mypy **190 source files PASS**.

Review biên xóa memory: thêm `test_memory_deletion_fences_pending_extraction_without_resurrecting_old_entries` bulk/scope. RED **2 failed/21 deselected, 8,32 s**; model đã dispatch nhưng kết quả trễ tái tạo memory sau user xóa. Thêm fence terminal skipped + clear lease + cancelled run dưới owner→job; giữ financial usage. GREEN **2 passed/21 deselected, 7,68 s**. Ruling 04 ghi semantics reconcile/tombstone, không schema mới.

Review biên cap/backfill/timeout: **1 failed/4 passed/23 deselected, 14,11 s**; chỉ whitespace legacy (tab/newline/NBSP) lọt SQL LIMIT làm starvation. Đồng bộ SQL btrim với Python str.strip whitespace; không nới eligibility. GREEN toàn file auto-memory mới nhất **28 passed, 39,32 s** (runner 41,625 s), gồm cap bền qua cascade, active cap trước/sau provider, owner-lock tự do khi provider chờ, cửa sổ backfill 14 ngày và SDK timeout cancel/uncertain liability $2. Full regression sau sửa đang chạy; chưa commit khối.

Frontend sau khối JI-31: `npm.cmd run typecheck` PASS; `npm.cmd test` **206 tests/37 files pass, 3,44 s** cộng **2 script checks/1792,274 ms**; build PASS/Vite 5,46 s, RealApp **313,06 kB/gzip 97,60 kB**. Tài liệu architecture/context/schema và API đã phân hai origin đúng code; docschecker **181 Markdown/1162 links/144 operations/130 settings/64 tables PASS**.

Rà caller của interface mới: RED riêng `test_guest_review_regressions.py -k 'query_embedding_needs or funded_query_embedding'`: **4 failed/9 deselected, 9,77 s**, expected string cũ ở ba ca closed gate và một replay case. Chỉ đổi expected value sang MemoryText approved, giữ toàn bộ funded-admission/provider/charge assertions; inventory ghi rõ. Rerun cả file đang chạy trên DB chẩn đoán riêng.

Caller guest GREEN cả file: **13 passed, 27,50 s**, runner 30,140 s. Hồi quy 11 file (memory/context/privacy/embeddings/auto API+worker/guest permissions/orchestration/indexing/settings/budget): **228 passed, 260,19 s**, runner 264,797 s, 0 fail.

Review recovery bổ sung sau lượt 228: RED `test_recovered_usage_lease_cannot_publish_a_late_model_result` **1 failed/28 deselected, 4,88 s**. Job lease còn hạn nhưng accounting đã recover run thành interrupted; publisher chưa kiểm `persist_snapshot=False`. Thêm xác nhận settlement và lock run sau usage (giữ thứ tự recovery usage→run), không publish kết quả worker đã mất lease. GREEN nhóm recovery + bulk/scope fence: **3 passed/26 deselected, 7,10 s**. Precommit rerun cả worker/API/budget/privacy/guest-return đang chạy; sẽ có full suite final sau JI-25.

Precommit mới nhất `pytest -q tests/test_journal_auto_memory.py tests/test_journal_auto_memory_api.py tests/test_budget_reservations.py tests/test_privacy_lifecycle.py tests/test_guest_review_regressions.py`: **68 passed, 79,91 s**, runner 82,906 s. Không sửa test_memory. Browser rà heading cũ: RED `ux-redesign.spec.ts --grep proposal` **1 failed/2 passed, 14,4 s**, chỉ region “Đã duyệt” đã đổi vì nay có automatic origin. Sửa một locator, giữ assertions về pending/rejected/saved. GREEN `memory-auto.spec.ts` + hai ca memory cũ: **3 passed, 8,6 s**. Ruff full PASS/mypy 190 files PASS. Chốt JI-30/31 cùng một commit; full final và review độc lập còn ở phía sau JI-25, chưa push nhóm memory.

### Checkpoint B — kết quả cuối trước push

Source task `b3f344ac`, full `pytest -q --ignore=tests/live --junitxml=<scratch>/ji50-backend-b.xml` trên DB disposable riêng: **2082 passed / 3 skipped / 0 failed, 2715,39 s** (runner **2744,203 s**), **2085 test** thu thập. Ba skip opt-in giống checkpoint A/baseline, không skip/xfail mới. Không sửa code khi suite chạy; các cập nhật giữa lúc chạy chỉ là tài liệu/preflight nhóm B.

| Gate | Kết quả B / bằng chứng |
| --- | --- |
| 1 | Ruff toàn bộ PASS; mypy 189 source files PASS, source giữ nguyên sau task commit |
| 2 | Full backend 2082 pass/3 skip, 0 fail; 2715,39 s |
| 3 | Default flags 9 pass, tổng testcase 3,985 s trong JUnit B |
| 4 | DB migration local sau tmpfs reset upgrade head/current 0029/check không drift; 10 migration tests pass/7,837 s |
| 5 | Checker 12 pinned/12 consumed PASS; 28 reviewed-artifact tests pass/22,890 s; 15 database-operation tests pass/28,914 s |
| 6 | OpenAPI export → contracts:generate ở JI-40; sau commit `git diff --exit-code -- backend/openapi.json frontend/src/api/generated/schema.d.ts` exit 0 |
| 7 | Docs checker PASS: 181 Markdown/1162 links/143 operations/122 settings/64 tables |
| 8 | Typecheck PASS; 205 tests/36 files + 2 script checks PASS; build PASS, RealApp 311,40 kB/gzip 97,22 kB |
| 9 | Owned fixture serial 384 pass/15,4 phút |
| 10 | Fullstack retry giữ nguyên timeout 38 pass/7,2 phút, runner 451,000 s; startup failure trước đó và seed diagnostic đã ghi riêng |
| 15 | `git diff --check` PASS; scanner source thêm mới 0 candidate chưa phân loại; artifacts không stage |

Gate 11 đã có 37 Linux tests PASS ở A, không có deploy-code thay đổi tại B. Gate 12 vẫn chỉ fake, chưa chạy Voyage/chờ duyệt chi phí. Gate 13 live chưa chạy/chờ duyệt chi phí. Gate 14 final whole-branch review còn chờ sau nhóm memory và JI-25; review trước A đã xử lý ba Important. Không suy ra hosted readiness hoặc quyền JI-51 từ các gate local này.

### JI-40 — RED/GREEN và hồi quy

Chốt task: hồi quy 10 file chạy lại **204 passed, 214,63 s** (runner 219,188 s), 0 fail. Checkpoint B đang chạy full backend/fixture trên source này, chưa push JI-40. CI origin cho checkpoint A `587e61d5` đã **success**: [Verify local application](https://github.com/mhiu05/MoodPrint/actions/runs/41801661898). Plugin workflow chỉ liệt kê run PR, nên theo dõi run push bằng `gh run list` read-only.

JI-40 commit local **`b3f344ac`**. Sau restart Docker, DB migration riêng trống được upgrade head rồi Alembic check lại bằng driver tắt dotenv/đặt URL `_test`: exit 0, không drift. Các suite checkpoint B tiếp tục chạy, chưa phát hành nhóm memory.

Checkpoint B fixture `node node_modules/@playwright/test/cli.js test --config playwright.owned.config.ts --workers=1 --reporter=list`: **384 passed, 15,4 phút**, 0 fail. Tăng đúng hai ca skill so với checkpoint A. Fullstack B bắt đầu sau khi fixture kết thúc, dùng DB hậu tố `000000000004_test`; không sửa frontend khi suite chạy. Backend B ở DB `000000000007_test` vẫn đang chạy, chưa chốt checkpoint/push.

Fullstack B lần đầu **exit 1, runner 31,312 s**, `Test server unavailable`, chưa có test nào chạy. Log synthetic backend chỉ tới feature-degraded, frontend đã ready; không có assertion hoặc provider failure. Không nới timeout startup 30 s hay timeout ứng dụng. Sau harness đã dừng process sở hữu, chạy riêng `tests.e2e_server.seed()` bằng runner DB4 (Settings `_env_file=None`, synthetic only): **exit 0, 12,437 s** để kiểm tra/import và khởi tạo DB sau tmpfs reset; không khởi chạy web/server ngoài harness. Retry nguyên harness và timeout cũ đang chạy; chưa coi fullstack B PASS.

Retry fullstack B nguyên lệnh/timeout: **38 passed, 7,2 phút**, 0 fail; kết quả sau này thay trạng thái chờ phía trên. Cả tuổi 18+, privacy/revocation, receipts, journal evidence, V3 direct/consult/handoff và groups đều nằm trong suite. Backend B vẫn đang chạy, chưa coi checkpoint B xanh.

Ruling tài liệu an toàn: 06 còn ghi worktree không có `.env`, trái workspace E: đã được chủ dự án cảnh báo. Sửa thành giữ nguyên file production, chỉ snapshot test không có file, và thêm prefix migration URL local `_test` cùng lệnh cho các ví dụ Alembic. Không đọc hoặc đụng file production để kiểm tra; đây là đồng bộ kế hoạch theo bàn giao, không thay guard/test.

- Bắt đầu sau checkpoint A đã push `587e61d5`. RED `pytest -q tests/test_agent_skills.py tests/test_prompt_options.py`: **14 failed / 18 passed, 19,69 s**; registry thiếu bốn ID/AGENTS, resolver chưa nhận diện/chặn distress, API enum chưa có skill mới. Ca refusal timeout vì request bị schema 422 trước model. Frontend RED `npm.cmd test -- promptOptions`: **1 failed / 204 passed, 5,31 s**, thiếu `skillChipLabel`; lệnh này thực tế chạy toàn bộ Vitest, không chỉ file lọc.
- Bốn file skill được tạo đúng thứ tự weekly-review → mood-patterns → guided-journal → reframe-thought, body lấy nguyên văn từ 05, version 1. Runtime thêm allowlist, manual validation trước tạo run, distress guard; không cấp tool mới hoặc thay persona/frozen instructions.
- Lượt GREEN đầu bị Docker Engine dừng: log mới có 25 dấu pass và một error kết nối, chưa có kết quả suite cuối; đã dừng đúng process test sở hữu, không coi là code failure hoặc PASS. Khởi động Docker Desktop ẩn, xác minh label run-id rồi chỉ start lại container disposable của phiên. Do tmpfs reset, tạo lại năm DB local đúng run-id/owner/marker; không đụng container khác, không đọc backend/.env.
- Sau khôi phục, **31 passed / 1 failed, 14,38 s**: test weekly sai khi đọc `run.journal_evidence` sau terminal. Code hiện có scrub evidence; sửa test quan sát output JSON thật của tool và citation đã publish, đồng thời assert evidence được scrub. Ruling đã sửa 05; không sửa privacy cleanup. GREEN cuối cùng cùng lệnh: **32 passed, 13,85 s** (runner 16,984 s), gồm refusal tool **403 JOURNAL_READ_DENIED**, lượt completed/no citation và mood scope 422.
- Browser: lần dựng regression proof đầu sai cwd của Python nên chưa phục hồi UI cũ, test chạy trên candidate và **1 passed/11,9 s**; không coi là RED. Lần đúng phục hồi chỉ ba file UI của tác vụ từ checkpoint A (candidate được lưu byte trước đó): **1 failed**, test 9,4 s, không tìm thấy chip “Nhìn lại tuần” vì UI cũ ghi “Học điều mới”. Phục hồi candidate, chạy cả file: hai ca mới pass nhưng hai viewport fail locator copy menu cũ; đã dừng đúng cây process test, sửa hai locator theo copy mới, giữ assertions. Lượt cuối `playwright ... agent-skills.spec.ts --workers=1`: **7 passed, 19,5 s**.
- Frontend GREEN `npm.cmd run typecheck`; `npm.cmd test -- promptOptions`: **205 tests / 36 files pass, 5,29 s**, cộng **2 script checks pass/647,285 ms**. Build pass, Vite 4,54 s; RealApp **311,40 kB/gzip 97,22 kB**. OpenAPI xuất qua script không dotenv rồi `contracts:generate`; không sửa tay schema.
- Ruff lần đầu có 3 I001 ở import test mới, đã `ruff --fix`; full lint PASS. Mypy **189 source files PASS**. Docs sau cập nhật registry/runtime PASS, **181 Markdown/1162 links/143 operations/122 settings/64 tables**.
- Hồi quy mở rộng 10 file: **203 passed / 1 failed, 146,08 s**; chỉ guest capability inventory còn ghim hai skill. RED riêng `test_guest_prompt_capabilities_are_a_zero_projection`: **1 failed, 4,40 s**, đúng bốn ID thừa. Equality đổi thành sáu ID, giữ assertion mọi `available=False`; GREEN **1 passed, 12,00 s**. Toàn bộ 204 ca đang chạy lại trước commit task; checkpoint B backend/fixture cũng đã bắt đầu trên DB/server riêng, không sửa frontend trong lúc browser đang chạy.

### Checkpoint A — kết quả cuối trước push

Full backend sau sửa: `pytest -q --ignore=tests/live --junitxml=<scratch>/ji50-backend-a-green.xml`, DB disposable hậu tố `000000000007_test`: **2065 passed / 3 skipped / 0 failed, 2233,27 s** (runner 2261,281 s). Source của hai commit bổ sung `d9cb601f` và `9f3c238e` đã có đầy đủ trong lượt này. Không thêm skip/xfail. Cả 2068 test đã được thu thập và thực thi/skip theo đúng opt-in hiện hữu.

| Gate | Lệnh / phạm vi | Kết quả tại checkpoint A |
| --- | --- | --- |
| 1 | `python -m ruff check app tests evals alembic ../scripts/apply_supabase_review.py ../scripts/check_reviewed_artifacts.py`; `python -m mypy app` | PASS; 189 source files mypy |
| 2 | Full pytest như trên | 2065 pass, 3 skip, 0 fail; 2233,27 s |
| 3 | `tests/test_default_flags.py` trong full pytest | 9 pass |
| 4 | Local Alembic driver đặt URL `_test` và `_env_file=None`: `upgrade head`, `current`, `check`; `tests/test_journal_intelligence_migration.py` | head 0029; không drift; 10 pass |
| 5 | `scripts/check_reviewed_artifacts.py`; `tests/test_reviewed_artifacts.py`; `test_database_operations.py` | 12 pinned/12 consumed; 28 pass và 15 pass; SQL nguyên văn chạy local với roles rollback |
| 6 | `scripts/export_openapi.py` → `npm.cmd --prefix frontend run contracts:generate` → `git diff --exit-code` hai file sinh | PASS, không drift |
| 7 | `python scripts/check_docs.py` | PASS; 181 Markdown, 1162 links, 143 operations, 122 settings, 64 tables |
| 8 | `npm.cmd run typecheck`; `npm.cmd test`; `npm.cmd run build` | PASS; 204 unit tests/36 files + 2 script checks; build RealApp 311,30 kB/gzip 97,17 kB |
| 9 | `node node_modules/@playwright/test/cli.js test --config playwright.owned.config.ts --workers=1 --reporter=list` | 382 pass/14,3 phút; không đổi default workers của CI |
| 10 | `python ../scripts/test_fullstack.py` qua runner DB riêng | 38 pass/6,2 phút; runner 381,187 s; FakeEmbedder và synthetic SDK |
| 11 | Container Linux test có sẵn, network none, repo read-only, command đầy đủ bên dưới | 37 tests OK/11,708 s |
| 12 | `python -m evals.journal_retrieval.run --embedder fake --out <scratch>/ji24-eval` | exit 0/runner 11,141 s; chỉ pipeline synthetic. Voyage: **chưa chạy, chờ chủ dự án duyệt chi phí** |
| 13 | Eval live skill/memory | **Chưa chạy, chờ chủ dự án duyệt chi phí**; các nhóm tùy chọn còn triển khai |
| 14 | Review độc lập trước checkpoint | 3 Important đã sửa và RED→GREEN; chưa phải review cuối toàn nhánh |
| 15 | `git diff --check`; scanner added-source giữ kín giá trị nghi ngờ | PASS; 0 candidate chưa phân loại, không đưa artifact browser vào commit |

Ruling tài liệu: cập nhật thêm `docs/frontend/README.md` và `docs/frontend/testing.md` ngoài danh sách tối thiểu JI-50 vì vẫn mô tả route/spec social đã gỡ. Giữ nguyên kết quả lịch sử trong các mục baseline; không đổi test để làm đẹp số liệu. Push feature branch chỉ kích hoạt Verify, không publish. Workflow publish tự động chỉ nhận Verify trên `main`; merge vẫn phải tuân thủ thứ tự image tương thích/migration 0029/image tính năng đã ghi, không suy ra quyền JI-51.

### Bổ sung hồi quy checkpoint A sau lượt full backend đầu

Commit local `d9cb601f` chứa lifecycle inventory, pin load fixtures và đồng bộ regression assertions/schema rehearsal; chưa push. `.gitignore` và prompt 09 đang có thay đổi của chủ dự án, không stage hoặc sửa.

Lượt full backend A đầu: `pytest -q --ignore=tests/live --junitxml=<scratch>/ji50-backend-a.xml` trên DB disposable riêng: **8 failed / 2052 passed / 3 skipped, 2700,05 s**. Tám failure là discovery migration head; foundation head; foundation ca 0028; guest inventory; guest rollback head; guest operation policy inventory; guest 0015→head assertion; journal 0019 rollback với FK 0029. Tất cả đã có sửa và targeted GREEN như ghi bên dưới; lượt full mới sau sửa đang chạy, chưa coi gate 2 xanh. Không thêm skip: ba skip opt-in giống baseline.

Trong chính lượt full A đầu (trích JUnit, không suy từ collection): default flags **9/9 pass, tổng testcase 2,720 s**; migration 0029 **10/10 pass, 9,771 s**; reviewed artifacts **28/28 pass, 27,096 s**; database operations **15/15 pass, 20,123 s**, gồm thực thi nguyên văn chuỗi SQL đã pin với Supabase roles trong DB local và rollback roles. Đây không thay cho rehearsal từ snapshot hosted: chưa có snapshot, không đọc hosted.

Gate 6: `scripts/export_openapi.py` (qua runner xóa key và không dotenv) exit 0; `npm.cmd --prefix frontend run contracts:generate` exit 0; `git diff --exit-code -- backend/openapi.json frontend/src/api/generated/schema.d.ts` exit 0, không drift.

SQL 0029 đã sinh bằng offline Alembic không dotenv, **7488 byte**, không BOM/`%%`; SHA256 `e15bb5fefbcfec4b3e6bf76463fcf9470a32a331835c1d93977ea4c53a9bc476`, generatedFrom migration commit `6795c34fee6c3d7e365453e92e5ebbaf5d4b9e04`. `apply_supabase_review.py --upgrade 0029` ở chế độ review-only exit 0, `alembicExportMatches=true`; không `--apply`, không kết nối hosted. Chốt riêng SQL/offline exporter từ bằng chứng 28 reviewed-artifact tests pass trước khi chốt checkpoint; đây chưa phải checkpoint A xanh hoặc quyền rollout hosted. Image Linux test đã dùng có digest local `sha256:7f862ffe38dd78e5416feb8610bea8f131b70c05a5e4287039d09645d83c4100`.

- Standalone load fixtures: RED `pytest -q tests/test_load_settings_baseline.py`: **2 failed, 18,42 s**; subprocess xóa env cờ do pytest ghim rồi so với `ALL_FEATURES_OFF` cộng đúng các tính năng từng fixture chủ động bật. Chat/social load server chưa được chạy; chỉ import cấu hình, không lifespan/network. GREEN **2 passed, 13,95 s**. Ruling JI-01: hai entrypoint tải cũng phải ghim nền tắt; nếu không mặc định mới có thể bật worker ngoài phạm vi fake provider của fixture. Giữ chat history bật.
- Schema regression RED `pytest -q tests/test_guest_schema.py::test_upgrade_from_0015_preserves_registered_rows_and_matches_models tests/test_journal_migration.py::test_journal_upgrade_downgrade_preserves_legacy_mood_and_private_acl`: **2 failed, 15,68 s** (head assertion cũ 0028; rollback 0019 bị FK của 0029 chặn). Ruling: assertion head chuyển 0029; diễn tập migration lịch sử tháo 0029 trước rồi phục hồi sau 0019, trong cùng transaction rollback cả temporary roles. Không sửa DDL hay bỏ assertion bảo toàn/RLS. GREEN `pytest -q tests/test_guest_schema.py tests/test_journal_migration.py tests/test_load_settings_baseline.py`: **6 passed, 34,86 s**.
- Gate 1 sau các sửa trên: Ruff **All checks passed**; mypy **189 source files**, không lỗi. Gate 7: **181 Markdown / 1161 local links / 143 operations / 122 settings / 64 tables, PASS**. Reviewed artifacts **12 pinned / 12 consumed, PASS**.
- Gate 11 Linux: lệnh tài liệu cũ dùng `python:3.12-slim` chạy **37 tests, 5 failures/4 errors**, do image không có Docker CLI/Compose cho các test Storage mới; không phải lỗi `fcntl`, không sửa hoặc skip test. Chạy lại bằng image test có sẵn `moodprint-release-deploy-tests:latest`: `docker run --rm --pull=never --network none --mount 'type=bind,source=E:\MoodPrint,target=/repo,readonly' --workdir /repo --env PYTHONDONTWRITEBYTECODE=1 --mount type=bind,source=/var/run/docker.sock,target=/var/run/docker.sock moodprint-release-deploy-tests:latest python -m unittest discover -s deploy/aws/tests -v`: **37 tests, OK, 11,708 s**. Chỉ synthetic config và container Caddy; không AWS/hosted/provider. Không thêm dependency dự án hay thay assertions.

### Sự cố guard subprocess và khắc phục

Trong lần rà cổng SQL, phát hiện `scripts/apply_supabase_review.py:alembic_export` gọi `python -m alembic` trong cwd backend; `alembic/env.py` tạo `Settings()` với mặc định `env_file='.env'`. Guard pytest chỉ tồn tại trong interpreter cha. Lượt regression JI-22 có chạy `test_reviewed_artifacts.py` nên đã đi qua đường có thể đọc `backend/.env` trái giới hạn của chủ dự án. Không mở/in/sửa file trực tiếp, không có secret hay nội dung file trong output; các lệnh đó là `--sql` offline với database URL local và không kết nối hosted. Đây vẫn là vi phạm giới hạn đọc file; không ghi là an toàn chỉ vì không có network. Đã thông báo chủ dự án ngay khi phát hiện, không đọc lại file để kiểm chứng.

Ruling: sửa offline exporter trước mọi lần gọi tiếp theo: env đặt `APP_ENV=test`, URL migration local `_test` ngay trong subprocess; xóa provider key khỏi env con; dùng `python -c` đặt `Settings.model_config["env_file"] = None` **trước** import Alembic. Không thay khối guard pytest. RED `pytest -q tests/test_reviewed_artifacts.py -k offline_export_disables`: **1 failed/20 deselected, 2,38 s** (migration URL rỗng). GREEN `-k 'offline_export_disables or every_upgrade_approval_matches or initialization_approvals_match'`: **3 passed/18 deselected, 137,15 s**; SQL equivalence giữ nguyên.

Ruling bổ sung: mọi Alembic invocation phải an toàn kể cả các migration tests khác có subprocess riêng. `alembic/env.py` luôn tạo `Settings(_env_file=None)`, target chỉ đến từ env tường minh; không thay Settings ứng dụng. Test mới monkeypatch `DotEnv.dict` thành hàm raise **trước** import Alembic, nên RED không thể đọc file thật: **1 failed/21 deselected, 10,71 s**, đúng lỗi `Alembic attempted dotenv access`. Sau sửa, `-k 'alembic_subprocess_never or offline_export_disables'`: **2 passed/20 deselected, 10,56 s**. Tài liệu migrations cập nhật. Baseline/red/green full suite vẫn chạy trong archive không chứa `.env`, không phải workspace backend thực.

### Fullstack mới

`python ../scripts/test_fullstack.py journal-intelligence.spec.ts`: RED **1 failed** vì embeddingAvailable=false; thêm FakeEmbedder cho document/query trong entrypoint test và model chỉ xử lý marker synthetic riêng. Lượt kế tiếp **1 failed** do locator marker trùng text user khi lượt sau đang chạy; sửa locator giới hạn log + đầu câu bot. GREEN **1 passed, 43,0 s** (test 41,0 s): ba entry → đợi chỉ mục → query diễn đạt khác → citation đúng, giữ sau reload → xóa entry → indexedEntries giảm → lượt mới không còn nguồn đã xóa. Không gọi Voyage/OpenAI thật.

Fullstack toàn bộ có lần startup timeout trước tests dưới tải ba suite backend; chưa nới timeout, sẽ chạy lại khi tải giảm. Fixture owned toàn bộ hiện chạy **382 tests**; chưa có kết quả cuối, đã có một ca chờ lịch vượt timeout cần kiểm tra sau khi kết thúc.

### Review trước checkpoint và bổ sung test biên

Reviewer độc lập `journal_precheckpoint_review` (read-only, không secret/network/test mutation) nêu 3 Important: nullable relaxation của 0029 bị SQL reviewer từ chối; batch legacy thiếu bằng chứng tuổi làm kẹt backfill; cascade job làm cap/ngày bị reset. Đã tiếp nhận; chưa coi review cuối toàn nhánh hoàn tất vì JI-30/31/40/25 chưa có.

- Document provider budget: RED `test_document_metadata_and_text_together_fit_provider_limit` **2 failed/19 deselected, 54,49 s** ở limit 7000/7900. Giữ metadata có biên, cắt text theo tổng 8000. GREEN `pytest -q tests/test_journal_indexing.py tests/test_journal_retrieval_eval.py`: **23 passed, 96,97 s**. Ruling cập nhật 03.
- Backfill: RED `-k ineligible_legacy`: **4 failed/21 deselected, 14,58 s** (missing/future/too_young/wrong_policy declaration). Thêm SQL predicate chung khớp `adult_eligible` trước LIMIT, vẫn live recheck dưới owner lock. GREEN **4 passed/21 deselected, 41,45 s**.
- SQL review constraint swaps: RED **4 failed/22 deselected, 6,30 s** (chưa có interface); GREEN **4 passed/22 deselected, 2,35 s**, chỉ cho cặp constraint tên chính xác có ADD NOT VALID + VALIDATE; unrelated constraint và DROP COLUMN vẫn bị từ chối. Reviewer còn chỉ ra `memories.proposal_id DROP NOT NULL` là relaxation expand-only; thêm allowlist tên table/column cụ thể, không bỏ blanket DROP guard. GREEN cả hai nhóm **6 passed/22 deselected, 2,61 s**. Map/pin 0029 còn chờ commit migration.
- Cap bền: dùng receipt nội bộ trong bảng Idempotency sẵn có, chỉ ngày/count, không journal/entry/job ID. Reserve mọi ngày trong [now, lease_until] dưới owner lock để cả completion qua nửa đêm không vượt cap; settle ngoài lifetime job, success vẫn bị charge sau cascade; failure rõ ràng refund; unknown crash giữ reservation. Reviewer đã đối chiếu thiết kế, đồng ý schema-free với các invariants này. Ruling giữ 72h để bao trùm một ngày calendar qua thay đổi timezone (tối đa ~50h), API receipts vẫn 24h. Account deletion xóa quota receipt, late settlement không tạo lại. Không sửa schema ngoài 0029.
- Cap durable RED đầu có 2 lỗi cú pháp test `AsyncClient.delete(json=...)`; sửa test dùng `request('DELETE', ...)` rồi RED chính thức **2 failed/1 passed/25 deselected, 24,91 s** (reset sau cascade và thiếu quota module). GREEN nhóm cap/deletion/midnight/concurrency/completion: **6 passed/22 deselected, 21,27 s**. Retention/account RED **2 failed/1 passed/28 deselected, 22,19 s**; hồi quy cuối đang chạy.
- Owned fixture toàn bộ: `node .../cli.js test --config playwright.owned.config.ts --reporter=list`: **381 passed/1 failed, 18,5 phút**, một ca `paused schedules show their actual state and can resume from the selector` chưa thấy combobox sau 7s khi UI vẫn loading. Không sửa timeout/assertion. Rerun đúng test, cùng code/config: **1 passed, 10,1 s** (test 5,4 s). Ghi là intermittent dưới tải, chưa ghi toàn suite xanh. Artifact không commit.
- Mypy sau quota: **189 source files PASS**. Quét added-source content-free: **3852 dòng, 0 candidate chưa phân loại** tại thời điểm scan; phải scan lại trước checkpoint/push. Inventory test xóa/đổi tên được ghi ở [10-test-change-inventory.md](10-test-change-inventory.md): 89 tên browser cũ, 18 body browser đổi, 7 file unit retired; đây là source inventory, không phải số runtime (template/width được mở rộng).

- Retention/account fix và hồi quy `pytest -q tests/test_journal_indexing.py tests/test_journal_ai_settings.py tests/test_journal_retrieval.py tests/test_journal_retrieval_eval.py tests/test_journal.py tests/test_journal_contract.py tests/test_privacy_lifecycle.py tests/test_embeddings.py`: **100 passed, 426,88 s**. Sau lượt này bổ sung bảo vệ outcome provider không rõ, nên không coi đây là full suite cuối của code mới nhất.
- Ruling cap ambiguous: timeout/transport loss/response lỗi có thể đã bị provider tính phí; giữ reservation bảo thủ. Chỉ refund khi adapter chứng minh chưa dispatch (`embedding_unconfigured`/`embedding_input_invalid`), hoặc refund phần ngày không dùng khi có vector thành công. Test RED ambiguous **1 failed/31 deselected, 23,06 s**; GREEN nhóm ambiguous/delete/midnight/retention/account **7 passed/25 deselected, 80,87 s**. Không nới cap để pass test.
- Frontend validation mới: typecheck RED có 4 import helper social đã gỡ còn sót ở `mvp.spec.ts`; bỏ đúng 4 import không còn callsite, không đổi assertion. Unit **204 passed/36 files, 13,47 s** + **2 script checks**. Build **PASS, 15,24 s**, RealApp 311,30 kB/gzip 97,17 kB. OpenAPI export đã chạy với `_env_file=None`; contracts generate chạy lại sau export, typecheck rerun **exit 0**. Không sửa schema.d.ts bằng tay.

Chưa hoàn tất. Fullstack spec journal intelligence riêng đã pass như trên; fullstack toàn bộ chưa pass. Ba full backend baseline/red/green vẫn chưa kết thúc. Chưa checkpoint A/B, chưa commit/push/PR/merge. JI-40, JI-30/31, JI-25 và phần final JI-50 còn phải làm.

JI-51 vẫn ngoài phạm vi: không migrate hosted, deploy, SSM hay đọc DB hosted. Cổng Voyage/live eval chưa chạy, chờ chủ dự án duyệt chi phí. Linux deploy chưa chạy. Copy Auth.tsx/GuestEntry.tsx sẽ xung đột với `stash@{0}` của chủ dự án; stash giữ nguyên.
