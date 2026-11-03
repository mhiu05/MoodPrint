# Review và hoàn thiện Agent Search & Skills — 03/11/2026

Repo `E:\MoodPrint`, branch `test/03-11-26`. Báo cáo này cập nhật hơn snapshot bàn giao08 và
báo cáo Claude. Working tree chưa commit; các thay đổi có sẵn của người dùng được giữ nguyên.

## Đánh giá báo cáo Claude

Báo cáo Claude ghi đúng các giới hạn kiểm chứng và là checkpoint hữu ích. Chưa thể coi đó
là kết quả hoàn tất: còn lỗi Maps khi abort/cleanup thất bại, thứ tự khóa worker/cancel,
deadline HTTP streaming, hai lỗi lịch hỏi thăm và các journey thất bại chưa được kiểm.
Review độc lập đã sửa các lỗi dưới đây và chạy lại các kiểm tra local tương ứng.

Đây là kết quả **offline/fake/disposable PostgreSQL**. Không phải bằng chứng live hoặc
production ready. Không gọi provider trả phí, AWS CLI/SSM hoặc hosted migration/deploy.

## Phần đã hoàn thiện thêm

### Maps backend

Các files chính: `backend/app/ai/search/maps_jobs.py`, `apify.py`, các regression trong
`test_maps_jobs.py`, `test_maps_provider.py`, `test_maps_worker_health.py`.

- Abort chưa xác nhận vẫn giữ suất concurrency, kể cả UI đã timed out/cancelled; claim kế
  tiếp bị chặn ở cap1. Liability không được hoàn tiền vì lỗi mạng.
- Qua TTL vẫn thử abort actor pending; chỉ cleanup storage khi provider xác nhận terminal.
- Claim lease commit trước khi chờ owner gate; không còn khóa job → owner ngược với
  cancel/delete. Barrier test trên PostgreSQL kiểm yêu cầu hủy không bị chặn bởi khóa ngược.
- Deadline tổng cho HTTP headers/body là3 giây, ngoài HTTPX idle timeout; tick I/O tối đa
  20 giây dưới lease25 giây. Stream nhỏ giọt giả lập được hủy và đóng đúng hạn.
- Ref trả về muộn sau lease takeover mở lại cleanup và giữ lại suất chạy cho đến khi
  biết actor đã dừng. Không replay paid start hoặc gọi model từ worker.
- Lỗi cleanup không chiếm lại suất của actor đã xác nhận dừng ở tick trước, kể cả chưa
  biết phí cuối. Settlement đã lưu không mất khi cleanup crash/metadata đã bị xóa.
- Heartbeat xóa marker của tiến trình cũ, chỉ cập nhật sau tick DB thành công; kiểm stale,
  schema chưa ready, lỗi DB, admission off và đóng client/engine bằng fakes.

Heartbeat chứng minh process/DB liveness; lỗi provider được retry bên trong tick có thể vẫn
cập nhật marker. Không dùng heartbeat để kết luận credential hợp lệ hoặc cleanup thành công.

### UI và hành vi phục hồi

Các files chính: `CheckInSlot.tsx`, `conversation-info.css`, `MapsSearchCard.tsx` và các
spec `agent-check-in-settings`, `search`, `maps-search`, `activities`, `ux-redesign`.

- Select tạm dừng hiển thị đúng ngày đã lưu, cho chọn tiếp tục; không còn luôn ghi
  “Không tạm dừng”. Cài đặt giờ yên lặng mở shared editor và trả focus về đúng nút.
- Header info đứng ngoài vùng cuộn; tiêu đề lịch được focus qua deep link không bị che,
  kể cả khi tăng cỡ chữ200%. Không đổi owner lịch theo specialist đang trả lời.
- Maps404 có thông báo kết quả không còn khả dụng và hướng dẫn tìm ở lượt mới; không
  lặp vô ích “Thử tải lại”, không phân biệt lý do hết hạn hay bị thu hồi quyền.
- Maps terminal/cancel ngừng poll; GET đang bay không ghi đè cancellation đã được xác nhận.
- Thêm browser fixtures cho Web empty/timeout/rate-limit/budget/cancel, không gắn nguồn giả,
  reload vẫn giữ fallback và lượt tiếp theo không mang chip cũ.
- Thêm Maps empty/failure/timeout/gone, lỗi mạng và retry cùng job, keyboard reuse trên mobile,
  back/reload, cancel không tạo lượt chat/actor mới. Reuse chỉ sửa draft, không tự gửi.

### Test từng lỗi thay vì chỉ chạy lại đến khi xanh

- Guest embedding fake giữ phản hồi muộn dù local timeout đã gửi cancellation, rồi trả sau
  deadline DB. Đây là đúng race cần kiểm; không nới deadline hoặc sửa quy tắc production.
- Dock test giữ API interception liên tục và thay đổi fixture state. Trace cũ chứng minh
  việc `unroute` tạo khoảng trống để GET lịch sử local lọt qua dev proxy, nhận401 rồi
  chuyển `/login`. Không phải lỗi animation ngẫu nhiên. Không có paid request/remote mutation.
- Login regression kiểm accessible form hiện tại. Không sửa các files Auth/LoginPage của
  người dùng để khôi phục marketing copy đã bỏ.

## Kết quả kiểm chứng mới

Mọi DB test dùng harness `dd013fd508944053be6bd7002906d4e4` tại loopback55439; Docker label và
DB ownership marker được kiểm. Env test được nạp riêng, không in giá trị. Không chạy hai
pytest/fullstack suites song song trên DB này.

| Kiểm tra | Kết quả | Evidence ở repo root |
| --- | --- | --- |
| Backend skills/options/Web/accounting/citations/migrations/provenance/defaults/SSE/guest/readiness | 245 passed, 673.96s | `.tmp/final-search-backend.log` |
| Backend Maps jobs/provider/API/worker health và guest embeddings | 26 passed, 48.50s | `.tmp/final-maps-all-complete.log` |
| Ruff `app tests` | Pass | `.tmp/final-ruff.log` |
| Mypy `app` | 184 source files clean | `.tmp/final-mypy.log` |
| Frontend Vitest | 39 files, 241 passed | `.tmp/final-frontend-unit.log` |
| Node regression (Redocly và mock API guard) | 2/2 pass | cùng unit log |
| Frontend typecheck/build | Exit0 cả hai | `.tmp/final-frontend-{typecheck,build}.log` |
| Playwright5 spec Search/Skills/Maps/check-ins/activities sau fixes | 53 passed, 2.1min | `.tmp/final-search-ui-verified.log` |
| Playwright11 spec tích hợp cuối | 174 passed, 5.8min | `.tmp/final-agent-search-acceptance.log` |

Hai nhóm backend trên không trùng file: tổng271 test mục tiêu pass. Không cộng các lượt red,
rerun và historical runs thành số lượng test mới. Full backend khoảng1900 test chưa chạy lại;
run Claude1925pass/1fail là lịch sử, lỗi đó được sửa và module4test hiện pass trong nhóm26.

Lượt browser rộng trước bản sửa fixture:167pass/1fail ở dock; không coi lượt đó là xanh.
Sau lượt174pass, harness được harden thêm: mock-only Vite không proxy request chưa được
intercept tới backend. Regression dùng hai HTTP servers cục bộ giả lập đã fail trước fix
(sentinel nhận request) và pass sau fix (404, sentinel nhận0request). Config fullstack/live
riêng không thay đổi; không thêm dependency. Node regressions cuối: **2/2 pass**.
Sau guard: **45/45** browser cases activities/collaboration/proactive pass (1.8min), log
`.tmp/final-e2e-guard.log`. Không cộng lượt này vào174 để báo tổng test độc lập. Mock suite
buộc chạy server riêng, không reuse dev server có thể bật proxy thật. Smoke Web sau thay đổi
này **1/1 pass** (11.0s), typecheck exit0, ghi ở `.tmp/final-owned-server-smoke.log`.
Screenshot đã nhìn thực tế ở320/1280 và desktop200% cỡ chữ. Axe, focus/keyboard, resize và
overflow được kiểm tự động ở320/390/768/1099/1100/1280. Không tuyên bố đã manual screen-reader,
native device QA hoặc browser zoom thật chỉ từ screenshot/DOM tests này.

## Migration, config và credential khi operator tiếp tục

- Migrations0025 citations,0026 search usage,0027 async Maps jobs,0028 collaboration defaults.
  Các migration đã được fake/disposable migration tests kiểm, chưa áp dụng hosted.
- Config mẫu: `backend/.env.example`, `deploy/runtime.env.example`; deployment assets:
  `deploy/compose.staging.yml`, `deploy/aws/deploy.sh`. Không sửa `.env` thật hoặc `.gitignore`.
- Cờ vẫn tắt: `AI_WEB_SEARCH_ENABLED`, `AI_MAPS_SEARCH_ENABLED`, `AI_AGENT_SKILLS_ENABLED`,
  `AI_COLLABORATION_DEFAULTS_ENABLED`, `MAPS_SEARCH_WORKER_ENABLED`. Chỉ mở cohort sau các gate07.
- Web dùng key OpenAI hiện có; operator cần tự xác minh model/account hỗ trợ tool, usage/token
  bound và pricing version trước khi bật `AI_WEB_SEARCH_TOKEN_BOUND_VERIFIED`.
- Maps cần `APIFY_API_TOKEN`, actor build được pin, pricing version và xác minh cap/minimum
  thực tế trước khi bật `APIFY_MAPS_CHARGE_BOUND_VERIFIED`. Không cần Google API key cho adapter
  Apify hiện tại. Không dán credential vào chat.
- UI lịch dùng `features.proactive`; không còn `AI_AGENT_CHECK_IN_SETTINGS_ENABLED`. Rollback
  vị trí UI bằng image pair tương thích; không tắt proactive worker để rollback việc đổi UI.

## Các bước còn lại, chưa thực hiện

1. Operator áp dụng migration trên staging sau backup/review, cập nhật SecureString runtime
   hiện có theo07 mà không in secret; chưa có lý do thêm IAM/ARN chỉ vì thêm biến.
2. Recreate/redeploy backend và worker Maps; xác nhận health/restart/cancel/drain/cleanup trên
   container thật. Pool compose hiện API4+1, proactive2+0, Maps1+0; kiểm connection headroom
   khi overlap và shutdown thực tế.
3. Xác minh billing/pricing/build/token bounds với provider; live smoke có budget giới hạn
   chỉ sau khi operator chủ động cho phép, tối đa một actor/5places/cap được xác nhận.
4. Mở Skills cohort rồi Web/Maps và collaboration defaults theo07; đo calls/liability/denials,
   xác minh eligible oldfalse/new accounts, timezone và kill-switch/rollback trên staging.
   Các gate M4/S4/C4 liên quan rollout vẫn chưa được đánh dấu hoàn tất.
5. Trước release rộng, hoàn thành manual keyboard/screen-reader/browser zoom/device QA và
   load/concurrency gates tùy chọn. Full backend suite mới cũng có thể chạy như release gate;
   báo cáo hiện tại chỉ cam kết271 test mục tiêu và các frontend checks nêu trên.

Giới hạn phase đầu giữ nguyên: Web dùng projection/query registry công khai đóng, từ chối
private/unsupported topic; Maps không tự lấy GPS, enrich contact hoặc lưu prose vào temporary
chat. Credential chưa sẵn sàng thì search fail closed. Không có commit/push/merge/deploy.
