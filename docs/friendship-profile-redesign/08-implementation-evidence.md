# Friendship Discovery — implementation ledger

Plan: `05-implementation-plan.md`; authority: documents 03–04 and the implementation request of 2026-10-31 (Asia/Bangkok).

> Historical ledger below records the prior implementation session. Its no-commit
> boundary and unverified DB/readiness results are superseded by the new completion
> session at the end of this file, authorized to investigate, verify and commit locally.
> The original FR/NFR/PRE → T01–T37 matrix is deliberately retained as history.

## Baseline and rulings

- Branch: `test/local-2026-10-30`; pre-existing edits: `frontend/src/features/real/RealApp.tsx`, `frontend/src/features/real/journal/journal.css`; seven untracked planning documents. Preserve all; no `.gitignore` change, commit or hosted write.
- Read all seven documents in order and re-inspected real social DTO/routes/service, editor, Discovery, card, taxonomy and journal navigation guard.
- Execution: inline, task order P0 → P3 → P1 → P2 → P4 → P5 → P6. TDD + final independent source review. The supplied design/plan is approved by the user's explicit implementation request; no new design round.
- Ruling: P0 writes compatibility/navigation tests first; generated-type-dependent reducer implementation follows P3 contract generation, before any frontend writer. This avoids a temporary duplicate public DTO.
- Ruling: keep this evidence ledger instead of commit-based skill bookkeeping; user explicitly forbids commits. Work stays in the requested workspace/branch.
- Rollback floor: expanded backend must continue reading/preserving discovery v1 JSONB even if frontend is reverted. Never delete metadata for rollback.
- Environment preflight: existing backend `.venv`, frontend packages available; `TEST_DATABASE_URL` absent; Docker daemon unavailable. Real DB integration remains unverified until a guarded local disposable PostgreSQL target is available. No hosted reset fallback.

## Kết quả triển khai và giới hạn

Đã triển khai source cho P0 → P3 → P1 → P2 → P4 → P5. P6 có bằng chứng unit/browser/build và review; **chưa đạt release gate** vì integration/fullstack chưa được chạy trên DB disposable, hai test readiness ngoài phạm vi đang fail, và kiểm tra screen reader trên thiết bị thật chưa thực hiện. Skipped không được tính là pass.

- Backend: `FriendshipDiscovery` v1 tùy chọn, enum/ID/unique/max/subset validation; JSON wire camelCase, JSONB snake_case. Omitted discovery giữ metadata cũ và giao featured với full interests mới; null tường minh xóa extension. Receipt phân biệt omitted với explicit null, giữ canonical full-PUT semantics. Không thêm endpoint/migration/RLS/dependency hoặc đổi taxonomy/scorer.
- Frontend: một reducer, ba câu hỏi, sáu chip trực tiếp + hai launcher nhóm, picker tìm kiếm cục bộ/phân trang, full-set management, tối đa ba featured. Tách retained/tentative, không cắt mười interests và không ánh xạ approach sang style. Goal chỉ theo Q1 trước lần lưu đầu tiên hoặc trước override tường minh.
- Local preview không gọi mạng; server draft chỉ lưu theo yêu cầu. Review bổ sung values/languages còn thiếu, save → server preview → xem toàn bộ public snapshot → click publish riêng. Version/token hiện hành, lỗi stale/expired, uncertain-write GET reconciliation và idempotent retry được giữ.
- Guard Close/tab/link/Back/Forward/reload; pending save thất bại giữ lựa chọn và đích đến. Session expiry bỏ editor/guard, response save đến muộn không khôi phục state. Dispatcher popstate đăng ký trước HashRouter; history.go hoàn nguyên/replay giữ idx/key/usr.
- Card chung cho local/server/peer/request; full disclosure, alias/seed, reasons từ server và template starter xác định bằng public seed/version. Giữ invite/skip/block/report qua chat, không tự gửi starter hoặc bật MATCH từ draft.
- Container query, mobile từng câu hỏi + preview dialog, auto-height/sticky fallback, native input, forced colors/reduced motion; không đổi global tokens. Viền control được sửa **riêng Discovery** từ #8c9a92 (2,936:1 trên trắng) sang #87958d (3,128:1), để đạt yêu cầu tương phản của NFR01.

## Lệnh và bằng chứng đã chạy

| Kiểm tra | Kết quả thực tế |
| --- | --- |
| `npm.cmd test` | 25 files, **131 passed** sau fix review. Log `.tmp/friendship-vitest-final.log`. |
| `npm.cmd run typecheck` | Exit 0; chạy riêng và lặp lại trong build sau regenerate. |
| `npm.cmd run build` | Exit 0; log `.tmp/friendship-build-complete.log`. |
| `backend/.venv/Scripts/python.exe scripts/export_openapi.py` và `npm.cmd run contracts:generate` | Đã regenerate bằng script hiện có; diff chỉ thêm schema FriendshipDiscovery và optional discovery trong DraftInput/PublicProfile. Không đổi path/operation. |
| Playwright `discovery.spec.ts social.spec.ts states.spec.ts motion.spec.ts` | Lượt cuối **39/39 passed**, exit 0, gồm review fixes/session expiry/contrast; log `.tmp/friendship-browser-complete.log`. Hai complete touch-publication journeys ở 320/390px **2/2 passed**, exit 0, chạy riêng sau đó. Tổng 41 case pass, không skip ở lớp fixture browser. |
| pytest tập 13 file bắt buộc, gồm `test_discovery_profile.py` | **38 passed, 68 skipped**, không fail. 68 case cần DB chưa được xác minh. |
| Toàn bộ pytest local: `pytest tests --ignore=tests/live -m 'not live' -q` | **451 passed, 667 skipped, 2 failed**. Hai lỗi có sẵn: `test_foundation.py::test_ready_revisions_cover_the_reviewed_migration_window` và `test_ready_supports_expand_migration_window_and_rejects_unknown[0019_journal-200]`. HEAD đã yêu cầu 0020; test vẫn kỳ vọng 0019. Không sửa ngoài phạm vi. |
| `scripts/test_fullstack.py matching-v2.spec.ts local-mvp.spec.ts moderation.spec.ts responsive.spec.ts` | Bị chặn ở preflight vì thiếu TEST_DATABASE_URL disposable. Không khởi động/reset DB. V1/v2 real fullstack chưa chạy. |
| Supabase hiện tại | Theo yêu cầu bổ sung của người dùng: **chỉ đọc**, giữ nguyên dữ liệu. Connector list_projects lỗi transport; fallback dùng cấu hình backend sẵn có. Query catalog bằng transaction `BEGIN READ ONLY`, xác nhận `transaction_read_only=on`; không đọc payload thành viên. |
| Catalog Supabase | `matching_drafts.payload` và `published_profiles.payload` là JSONB; cả hai bật RLS. Có cột version/token/expiry/consent/taxonomy cần thiết. Hosted revision **0019_journal**, trong khi source yêu cầu **0020_private_profile_retirement**: chênh lệch ngoài phạm vi, chưa sửa. |
| Documentation/diff | `check_docs.py`: PASS, 162 Markdown files, 1003 local links, 114 API operations, 70 settings, 50 tables. `git diff --check`: exit 0. |

Không chạy live-provider, paid AI, hosted fixture reset, migration hoặc ghi dữ liệu hosted. Kiểm tra catalog không phải bằng chứng API round-trip, RLS authorization hay consent/matching lifecycle đã pass trên hosted DB.

Ruling: Windows `playwright.owned.config.ts` chạy test xong nhưng treo teardown Vite trong môi trường này. Các lượt cuối dùng `.tmp/friendship.playwright.config.ts` kế thừa nguyên owned config, tắt riêng webServer ownership, trỏ vào **Vite do task tạo riêng ở 5191** và dừng đúng PID sau QA. Không dùng lại server dev của người dùng, không sửa config được theo dõi. Một lượt owned ban đầu báo teardown timeout; không tính lượt đó là pass toàn bộ harness.

## Traceability: yêu cầu → test → bằng chứng

U = Vitest; B = Playwright synthetic fixtures; A/E = pytest DB/real fullstack; S = source/static/catalog review. “Một phần” chỉ rõ lớp còn thiếu, không suy rộng mock thành integration.

| Yêu cầu | T01–T37 | Bằng chứng và giới hạn |
| --- | --- | --- |
| FR01 | T01, T24, T27, T37 | B: title/exact choices/denylist; real empty state, không fallback người giả. |
| FR02 | T02 | U: new goal mapping, saved goal preservation, explicit override; B: native radio thay lựa chọn. |
| FR03 | T03, T05 | U/B: tám entries, concrete drawing/badminton, ordered featured; không synthetic category ID. |
| FR04 | T04, T08 | U/B: fourth attempt không mutate/focus loss; exact notice; full max 10. |
| FR05 | T05, T06 | B: bounded picker/search không dấu/empty/Escape/tray; S: slice 8/page, category/pagination. |
| FR06 | T07, T08, T20–T22 | U/B và backend pure payload tests giữ đủ mười IDs; A/E persistence chưa chạy. |
| FR07 | T09, T21 | U/B/A pure validation: approach không đổi style/activities; invalid enum fail. |
| FR08 | T10, T19, T31 | B: local preview tức thời, zero writes, owner placeholder; session-expiry response test; S: public-only inputs. |
| FR09 | T10, T32–T35 | B: bảy viewport, 200% text, container layout, dialog/resize; screenshot đã xem. Thiết bị vật lý chưa đo. |
| FR10 | T11, T12, T18 | B: partial save, returned version, same-key retry, uncertain save GET reconciliation, conflict confirmation. A/E chưa chạy. |
| FR11 | T14, T15, T19 | B: Close/tab/shell link/Back/Forward/repeated Back/native unload/save/discard/session expiry; history state equality. |
| FR12 | T16–T18, T31 | B: explicit final click/current token/expired recovery/uncertain publish reconciliation; A/E consent/version còn thiếu. |
| FR13 | T08, T13, T21, T36 | U/B/A pure: 3/2/1 minimums, không đoán facets; complete legacy bỏ qua supplement. A/E còn thiếu. |
| FR14 | T11, T13, T16, T17, T31 | B/S: draft/live copy và snapshot review; không đổi live từ draft; hosted lifecycle chưa test. |
| FR15 | T24–T27 | U/B: exact reasons + candidate ID, deterministic starter, pair alias/seed, public disclosure; request wrapper giữ heading/actions. |
| FR16 | T28, T29, T31 | B: invite/sent/block action/skip focus/expired no replay. Existing chat report source không đổi; real moderation/lifecycle A/E chưa chạy. |
| FR17 | T12, T16, T18, T27, T28 | B: loading/empty/error/retry/expired/sent; resource failure không unmount dirty editor. |
| FR18 | T20–T23, T36 | Backend pure schema/payload tests + generated diff; A/E round-trip và rollback exercise chưa chạy. Rollback floor ghi bên dưới. |
| FR19 | T02, T09, T30, T31 | U/A pure v1/v2/shadow invariance; scorer/retrieval/filter source không sửa. DB retrieval/races chưa chạy. |
| NFR01 | T32–T35 | Native semantics/axe builder và server review/forced colors/contrast/focus/44px. Screen reader thật chưa chạy; minor removal-focus còn lại. |
| NFR02 | T32 | B: 320/390/768/1024/1280/1440/landscape, 200% text không page overflow. Browser zoom thật và touch-device inspection chưa đủ. |
| NFR03 | T10, T26, T35 | B/U: no selection requests, stable templates, local selection timing <100ms. Không phải benchmark điện thoại thật. |
| NFR04 | T11–T23 | B/U: versions, epoch/abort/session reset, no duplicate save, explicit recovery; A/E lock/race chưa xác minh. |
| NFR05 | T10, T20–T23, T36 | S/U: một reducer, generated DTO authoritative, shared card, không editable duplicate profile. |
| NFR06 | T01, T25, T32, T34, T37 | B/screenshot/content review: tiếng Việt đúng thiết kế; IDs giữ nguyên. |
| PRE01 | T24–T26, T31 | S/B + existing AST privacy test: không import private matching models hoặc lấy journal/mood/memory/identity. A/E private-data mutation chưa chạy. |
| PRE02 | T16–T18 | B zero writes trước review/final click; existing backend consent code giữ nguyên. A/E consent-event proof chưa chạy. |
| PRE03 | T24 | B: Bạn/pair alias/seed, không Private Name trong card. |
| PRE04 | T28–T31 | Source/filter/quota/locked recheck giữ nguyên; pure invariance và teen UI pass; DB authorization tests skipped. |
| PRE05 | T11, T19 | B: không browser draft storage; session expiry xóa reducer/pending guard, late save không restore. Không thêm analytics/log lựa chọn. |
| PRE06 | T30, T36 | Không SQL/RLS/grants edit; hosted catalog xác nhận RLS bật. Chưa phải audit effective ACL/cross-user authorization. |
| PRE07 | T07, T13, T24 | B: full ten interests/facets trong disclosure; authoritative review mở mặc định. |

## Kết quả theo từng test ID

| ID | Kết quả/lớp đã chứng minh | Chưa xác minh |
| --- | --- | --- |
| T01 | B title/3 questions/4+3 radios/8 entries | — |
| T02 | U goalMode mapping/override/first-save preservation; B radio | — |
| T03 | U/B ordered featured/count/unique | — |
| T04 | U/B fourth rejection/focus/notice | — |
| T05 | U/B concrete group children/two creative selections | — |
| T06 | B no-diacritic search/empty/Escape/focus; S eight-per-page | Exhaustive pagination/category combinations |
| T07 | U/B mười full interests và facets; pure older-writer intersection | A/E persistence |
| T08 | U retained/tentative/full max/explicit delete/minimum | Pointer/keyboard every full-max permutation |
| T09 | U/B approach độc lập style/activities | A API round-trip |
| T10 | B immediate owner card/no selection writes/viewport preservation | Physical-device timing |
| T11 | B partial save/restore/newest version/no browser draft storage | A/E durable DB |
| T12 | B 503 retry/same key/save-and-leave failure/resource error/CSRF | E real outage |
| T13 | B no guessed facets/explicit supplement/full server disclosure | A/E |
| T14 | B close/tab/link/save/discard/error-safe exit | E |
| T15 | B Back/Forward/repeated Back/native reload/history equality | Other browser engines |
| T16 | U token invalidation; B PREVIEW_CHANGED/fresh-review requirement | A expiry/concurrent version |
| T17 | B final click only/consent copy; backend code retained | A/E consent records/withdrawal |
| T18 | B stale conflict explicit overwrite; GET reconcile uncertain draft/publish | A/E multi-writer real DB |
| T19 | B session expiry + delayed save, terminal/recoverable 403, retained dirty state on refetch failure | Real two-account end-to-end switch |
| T20 | U/B legacy full facets, incompatible taxonomy read-only; backend legacy DTO valid | A/E legacy publish round-trip |
| T21 | A pure 12 schema/payload/minimum cases + three scorer invariance cases | API 422/DB round-trip |
| T22 | Pure omitted/null/intersection/order/no nested mutation | A/E older cached writer persisted |
| T23 | S compatible rollback floor | Actual frontend rollback against local DB |
| T24 | B peer alias/seed/reasons/details/request headings/actions | E actual peer population |
| T25 | U/B exact reason + ID, unsupported generic | — |
| T26 | U stable seed/version hash, both variants, candidateRef independence | — |
| T27 | B real empty/loading/failed list/resources recovery | E |
| T28 | B invite/sent/skip focus/expired no automatic replay, block UI retained | A/E block/quota/reference ownership |
| T29 | S human-chat report pathways/policy unchanged | A/E report after block/end |
| T30 | Pure v1/v2/shadow metadata invariance, B teen lock, source filters unchanged | A/E all retrieval boundaries/quotas/locks |
| T31 | Existing matching-private-model AST test pass, public-only frontend/source | A/E private-data and concurrent revocation |
| T32 | B seven viewports + 200% text/no overflow/screenshots | Physical touch, actual browser zoom |
| T33 | B radio arrows/Space/dialog focus/error links/discovery roving tabs | Minor focus after removal remains |
| T34 | B axe builder/review zero serious/critical; forced colors + measured contrast | NVDA/VoiceOver and exhaustive all-state manual audit |
| T35 | B reduced motion/local <100ms next-frame timing; shared Dialog motion regressions | Representative physical mobile benchmark |
| T36 | Regenerated OpenAPI/types, typecheck/build, pure 3/2/1 validation | A/E wire+DB integration |
| T37 | B denylist, source diff/hash review | No pixel-reference images supplied |

## Red/green và review

- Backend mới ban đầu fail bốn valid-metadata/preservation assertions vì `extra_forbidden`; sau DTO/service fix, 12 pure schema/payload/minimum cases pass. Ba metadata-invariance cases pass trên v1/v2/shadow; không đổi scorer để đạt test.
- Module pure/frontend mới ban đầu chưa collect được do chưa tồn tại; không coi đó là behavioral pass. Các regression hành vi sau đó đã quan sát fail trước fix: zero-feature save tự feature lại; PREVIEW_INVALIDATED chuyển builder sang review; input bị glyph chặn click; Back mất editor; supplement mất focus khi đủ minimum; picker Escape bị search input nuốt; axe selected group-name mismatch; card sent bị refresh xóa; contrast 2,936 < 3; uncertain write chưa có reconcile; refresh failure mất dirty state; CSRF/terminal-403 trap exit.
- Review độc lập read-only phát hiện hai Important (resource-error unmount; generic 403 trap). Đã thêm failing Playwright và sửa một lượt; test lại green. Self-review phát hiện builder-stage bypass, có failing Vitest và fix.
- **Minor deferred:** khi xóa một tray/full-set item bằng keyboard, nút đang focus bị unmount và chưa chọn focus kế tiếp. Tab/Escape vẫn hoạt động; đây là thiếu sót focus polish, không phải chứng nhận accessibility đầy đủ.
- Considered/declined: fallback first-three khi metadata absent/empty và goalMode preserve sau save đúng 04; omission/intersection/receipt-presence đúng compatibility; starters exact-evidence conservative. Không mở rộng scope sửa readiness/migration hoặc private chat/journal.

## Readiness và rollback

Backend reader/writer mở rộng phải sẵn sàng trước frontend writer mới. Khi rollback frontend, **giữ backend đọc và bảo toàn discovery v1**; không quay về DTO từ chối JSONB đã lưu và không xóa metadata để rollback.

Không commit/push/PR/merge/deploy. Giữ `.gitignore` và hai file dirty ban đầu nguyên byte. Workspace còn thư mục `docs/implementation-plans/proactive-multi-agent-companion/` xuất hiện ngoài task trong khi làm việc; không đụng vào. Các log/screenshot synthetic của task nằm dưới `.tmp/friendship-*`; scratch config không phải thay đổi hạ tầng được đề xuất.

Hash cuối trùng baseline đã ghi trước khi sửa các file liên quan: RealApp `73cd98b44baf287b7c73b2cea2757759d259c001fcc2a136aad62771797d00bb`; journal.css `696171260316f83f00fa97cf532a46b36d4eec7677cd66f56e26e282cbb68c81`; `.gitignore` `21c9ed300b8608c64991df618b22279e4763a4f65f85b4d4c3b8893577102cc6`. Regeneration lặp lại giữ OpenAPI `1f08f3fb53b124f137c32a6764e029d3128e38d6b903d7f32d7e6f4c9ff5e1ae` và generated types `8c8d75a84210fed5d7e04a0b13ec93869b6dec82fca6ed23d5320c9e90226169`.

Release còn chặn bởi DB integration/fullstack chưa chạy; hosted migration mismatch đã nêu; manual screen-reader/physical-device coverage chưa đủ. Không chuyển skipped hoặc source review thành claim acceptance đã pass ở lớp DB.

## Phiên khôi phục và hoàn thiện — 2026-10-31

Đọc lại 01–08, kiểm tra Git/source thay vì tin báo cáo trước. Root/branch đúng:
`E:/MoodPrint`, `test/local-2026-10-30`; HEAD đầu phiên
`d6eaf71908a13d31b3d9192e59ebf2f52129811e`; main
`5d2b384516b9318e6ee132c1a8b08dcbc374b79b`. Không đổi branch, không reset/stash.
Người dùng phiên này cho phép local commit; các lệnh cấm commit trong lịch sử không
còn áp dụng. Không push/PR/merge/deploy hoặc ghi hosted.

### Thay đổi và quyết định mới

- Sửa focus khi xóa featured/full interest: mục kế tiếp → mục trước → heading/search/
  hành động ổn định; cuối danh sách manage trả focus về heading khi launcher biến mất.
  Announce nhãn và số lượng sau full deletion. Ba browser regression đã fail trước fix.
- Giữ tám entry ban đầu: sáu canonical ID, hai expansion rõ ràng và đồng cấp cho
  Sáng tạo/Thể thao; child picker giữ semantics thật. Không tạo ID giả, không cắt
  interests cũ hoặc ánh xạ communication approach sang style.
- Ruling: readiness chỉ chấp nhận **0020**, từ chối **0019** và unknown. Migration
  0020 xóa private_items/source/purpose; không phải expand-only. Production guard
  hiện có là đúng; sửa các assertion lỗi thời sau khi tái hiện, không nới readiness.
- Migration rehearsal mới đi qua full Alembic chain, seed legacy journal/auth/profile/
  memory và discovery JSONB, kiểm tra data preservation/intended retirement, chạy
  lại upgrade head, từ chối downgrade destructive. Base RLS được bootstrap riêng;
  không quy công bật RLS cho Alembic 0001 hoặc migration 0020.
- Docker ban đầu dừng; đã khởi động và tạo container riêng PostgreSQL **17.10**,
  pgvector **0.8.2**, loopback **55439**, tmpfs không dùng user volume.
  Container UUID `e6057f89fb764591a91d08eaa58cc35b`; metadata không chứa password
  tại `.tmp/moodprint-disposable-e6057f89fb764591a91d08eaa58cc35b/metadata.json`.
- Guard reset kiểm tra TEST_DATABASE_URL độc lập, driver/host/query overrides,
  địa chỉ peer loopback thật, current/session user, DB owner, run marker và APP_ENV=test.
  Scratch DB tạo tên unique, không pre-delete; cleanup recheck ownership. Sửa hai
  fixture migration từng pre-delete tên cố định, và fixture guest migration review.
- Cập nhật README/CI theo guard mới: provision DB có ownership, mask URL, truyền
  run marker và APP_ENV, cleanup đúng container. Không thay hạ tầng hosted.
- Full pytest có DB phát hiện test guest memory vẫn gọi signature trước retirement
  (`purpose` dư). Tái hiện TypeError riêng, xác nhận có trong HEAD; sửa hai lời gọi,
  giữ nguyên expiry/authorization assertions. Module retest **4 passed**, exit 0.
  Hai unused imports có sẵn trong HEAD cũng được bỏ để repository Ruff gate pass.
- Hai lượt review fresh-context read-only (backend, final cross-layer) và review
  bổ sung CI không tìm thấy confirmed Important/Critical defect. Không coi review
  source là thay thế kiểm thử DB hoặc screen reader.

### Lệnh và bằng chứng mới

| Gate / lệnh | Kết quả phiên này / artifact |
| --- | --- |
| Baseline `pytest tests/test_foundation.py tests/test_readiness.py -q` | 18 passed, 12 skipped, 2 failed, exit 1; tái hiện đúng hai stale readiness expectations. |
| `npm.cmd test` | **131 passed**, 25 files, exit 0; chạy lại tại root task sau thay đổi, cùng kết quả agent log `.tmp/friendship-ui-vitest.log`. |
| `npm.cmd run typecheck`; `npm.cmd run build` | Cả hai exit 0; build chạy lại sau contract regeneration và fullstack test update. |
| Fixture Playwright discovery/social/states/motion | **44 passed, 0 failed, 0 skipped**, exit 0; `.tmp/friendship-ui-playwright.log`. Gồm ba regression focus mới. |
| `pytest tests/test_disposable_database_safety.py tests/test_foundation.py -q` | **35 passed**, exit 0; 13 fail-closed safety cases + 22 foundation cases. APP_ENV production case đã fail trước guard. |
| Baseline real DB discovery/migration/social | 28 passed, 2 failed, exit 1; một assertion legacy thiếu optional discovery:null, một thiếu bootstrap RLS trong setup rehearsal. Cả hai được sửa đúng nguyên nhân. `.tmp/friendship-db-baseline.log`. |
| Fullstack v1 — bốn suite yêu cầu | **7 passed, 0 failed, 0 skipped**, exit 0; `.tmp/friendship-fullstack-v1-final.log`. |
| Fullstack v2 — matching-v2 | **4 passed, 0 failed, 0 skipped**, exit 0; `.tmp/friendship-fullstack-v2-final.log`. |
| `scripts/export_openapi.py`; `npm.cmd run contracts:generate` | Exit 0; hashes giữ `1f08f3fb...ff5e1ae` và `8c8d75a8...226169`; không endpoint drift. |
| Repository Ruff / `mypy app` | Ruff pass; mypy **126 source files**, exit 0. |
| Pinned Docker actionlint | Exit 0; workflow được mount read-only, không chạy CI hoặc deploy. |
| `check_reviewed_artifacts.py` | Exit 0; **11 pinned approvals / 11 consumed**; không sửa reviewed SQL. |

Lệnh full pytest/fullstack/paths chi tiết, phân biệt rollback/frontend binary và
manual procedure nằm trong [09 final QA report](09-final-qa-report.md). Mọi lỗi
baseline ở trên là lịch sử có evidence, không phải pass được tạo bằng skip/assertion yếu.
Kết quả full pytest cuối và commit được bổ sung sau khi các tiến trình kết thúc.

**Kết quả chốt (đã chạy xong):** full non-live **1141 passed / 0 failed / 0 skipped**,
exit 0, 929.36s; log `.tmp/friendship-pytest-final.log`, XML cùng tên. Lệnh từ backend:
`python -m pytest tests --ignore=tests/live -m "not live" -q --tb=short -ra --durations=20 -o faulthandler_timeout=60 --junitxml=../.tmp/friendship-pytest-final.xml`.

Lượt full có DB đầu tiên là **1138 passed / 2 failed / 0 skipped**, exit 1:
guest proposal signature cũ (đã sửa/retest) và accounting chờ model-start quá 3s.
Accounting module chạy riêng **5 passed**, rồi toàn bộ lượt cuối tuần tự cũng pass
với nguyên timeout/assertions; không sửa production AI hoặc nới giới hạn để làm xanh.
Giữ log/XML lỗi ban đầu tại `.tmp/friendship-pytest-database.*`.

Bộ release 18 module được chạy lại sau assertion T31 mới: **163 passed**, exit 0,
177.97s, gồm **90 case PostgreSQL thật** và **73 case không cần PostgreSQL**;
không fail/skip. Trong luồng v1/v2/shadow hiện có, đã đổi private identity, journal,
mood, AI memory của hai user và draft peer khác published snapshot; public cards
giữ nguyên toàn bộ fields ngoài candidateRef xoay vòng, không lộ canary; invite/accept
vẫn hoạt động. Mở rộng AST denylist cho journal. Review độc lập hai test diff không
phát hiện assertion yếu đi hoặc fixture leakage. Canary một peer kiểm tra card;
ordering dùng riêng các multi-peer ranking tests hiện có.

Đã xác minh **độc lập với hai dirty files ngoài scope**: Vite load overlay từ HEAD
cho RealApp/journal.css, không ghi hai file của người dùng. Fixture browser **44/44**,
fullstack v1 **7/7**, v2 **4/4**, mọi harness exit 0. T19 trước đây ràng buộc URL/login
vào dirty redirect; đã quan sát fail với HEAD dù auth form/private clearing đúng.
Test mới kiểm tra Email/sign-in và clear editor/late responses, pass trên cả HEAD
và dirty RealApp. Logs `.tmp/friendship-head-auth-red.log`, `friendship-head-auth-green.log`,
`friendship-current-auth-green.log`, `friendship-fixture-head-final.log`,
`friendship-head-fullstack-v1.log`, `friendship-head-fullstack-v2.log`.

Không có relevant release-gate test bị skip. Các test live-provider ngoài scope
được exclude tường minh, không được tính là pass. Manual limitations vẫn giữ nguyên.

### Bổ sung traceability (không thay matrix lịch sử)

| IDs | Bằng chứng bổ sung |
| --- | --- |
| T01–T10, T24–T27, T32–T37 | 131 unit + 44 fixture browser; tám viewport gồm 430px, forced colors/200% text/reduced motion, screenshots đã xem; exact copy/evidence-grounded starter giữ nguyên. |
| T07/T11–T13/T17/T20–T23 | Real API/JSONB tests: partial draft, full ten interests, omission/intersection/null, no consent before publish, published fallback và older-writer rollback simulation. |
| T16/T18/T19 | Real concurrent same-version save; expired token rejection; publish retry không duplicate consent/publication; fullstack thu hồi session thật khi editor dirty → clear/login. |
| T24/T27–T31 | Real v1/v2 candidates, publication availability/withdrawal, matching/moderation/report lifecycle; baseline server filters không đổi. Full applicable backend run bổ sung consent/quota/lock/privacy tests. |
| **T38 (new)** | Ba red→green keyboard removal tests: main/picker trays, full-set consecutive/final removal, Escape/dialog restore và stable fallback. |
| **T39 (new)** | Readiness 0019 denied/0020 accepted/unknown denied + real 0019→0020 migration rehearsal, legacy data/ACL và downgrade refusal. |
| **T40 (new)** | Real UI selection zero writes → private save → reload/reopen → supplement → server review → explicit publish → candidate → withdraw → session revocation, v1/v2. |
| **T41 (new)** | Thirteen DB guard cases; real async/sync ownership verification, scratch create/write/remove smoke; provisioning và CI compatibility. |

### UX và giới hạn còn lại

Đã xem screenshots 320/390/**430**/768/1024/1280/1440px và 844×390 landscape.
Hai cột desktop, mobile question flow, đủ tám entries và full public disclosure;
không overflow/che bottom action trong matrix. Agent-browser axe builder và sports
picker **0 violations**; fixture axe review và real responsive axe pass riêng.
Artifacts ở `.tmp/friendship-ui-final/`, `.tmp/friendship-ui-430-viewport.png`,
`.tmp/friendship-ui-sports-picker.png`, `.tmp/friendship-fullstack-v1-final/`.

**Chưa thực hiện** NVDA/VoiceOver, physical iPhone/Android, physical-device latency
hoặc native zoom mọi browser. Không claim WCAG conformance hay physical pass.
09 có manual procedure cụ thể. Hosted revision 0019 chỉ là observation lịch sử;
phiên này không đọc lại hay sửa hosted. Future release cần migration0020 được
ủy quyền riêng, theo sequence trong 09; backend rollback phải giữ discovery reader.

### Bảo toàn công việc khác

RealApp và journal.css vẫn đúng hash baseline `73cd98b4...d00bb` và
`69617126...68c81`. Trong lúc task chạy, `.gitignore` được thay đổi ngoài các thao tác
của task, thêm `.tmp/` (hash mới `a7da6f523f3ac4aaa38653766adc24b77a960643a9e172e070cbf60804586d01`).
Giữ nguyên thay đổi đó và loại khỏi staging/commit; không revert công việc đang chạy
song song. Thư mục companion planning vẫn không đụng tới. Các artifact synthetic
task-owned phát sinh ở frontend/evidence được chuyển vào `.tmp` sau khi kiểm tra
đường dẫn, không đưa vào commit. Không secret/environment file nào được stage.

### Chốt giao nhận và Git

**READY_FOR_PR_REVIEW** — đủ các gate tự động cục bộ để review PR trong task riêng;
không claim production `RELEASE_READY`. NVDA/VoiceOver, physical-device/native zoom
và xác nhận migration/ACL hosted trước triển khai vẫn là bước ngoài phạm vi đã nêu.

Commit triển khai đã kiểm chứng: **`b2f04a5440da23cfab1e77c2a41781ca37de85ef`**,
`feat(friendship): finalize discovery experience and integration verification`.
46 file source/test/contracts/test infrastructure/README/CI; danh sách đầy đủ trong 09.
Tài liệu 01–09 được commit evidence riêng sau commit source này. SHA commit chứa báo
cáo lấy bằng `git log -1 --format=%H -- docs/friendship-profile-redesign/09-final-qa-report.md`
và được ghi trong final response + `.tmp/friendship-final-git.json` sau Git verification.

Cleanup `scripts/disposable_postgres.py --remove e6057f89fb764591a91d08eaa58cc35b`
exit 0: đã xóa đúng container có label/tmpfs và credentials cục bộ của run; không
xóa shared daemon hay dữ liệu khác. Test server/listener do task tạo đã dừng.
Artifacts synthetic còn ở `.tmp`; không đưa vào commit. Supabase hosted không thay đổi
bởi task; không push, PR, merge hoặc deploy.
