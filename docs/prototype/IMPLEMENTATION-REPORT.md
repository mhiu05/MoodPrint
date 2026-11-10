# MoodPrint — Báo cáo triển khai frontend prototype

Ngày: 07/11/2026. Branch: `mhiu05/feat-refactor`. Phạm vi: React + Vite + TypeScript, dữ liệu hư cấu, chạy local. Không push, merge hoặc deploy. Các đặc tả 01–08 được giữ nguyên; không sửa `.gitignore`, `.env`, `.mcp.json`, `skills-lock.json` hoặc cấu hình skills.

## 1. Màn hình và tính năng đã triển khai

| Khu vực | Hành vi hoạt động trong prototype |
|---|---|
| Welcome / Account | 4 trang Next/Back/Skip; đăng ký giả có validation; chọn An/Minh/Hà/Linh; account guard giữ deep link; không guest, không lưu email/password |
| Home | Lời chào, chat, ghi sự việc, luyện nói, kiến thức, trợ giúp, hồ sơ gần đây và checklist đọc từ canonical plan store |
| Hồ sơ | 8 mẫu, wizard 6 bước, thời gian không rõ, vai trò/ảnh hưởng/người tin cậy, lưu nháp, khôi phục sau reload, tạo/sửa/xóa, tìm/lọc/sắp xếp, trạng thái thủ công |
| Chi tiết hồ sơ | Tổng quan, timeline thêm/sửa/lọc và provenance, evidence mock sửa/xác nhận/bỏ nguồn, related cases, tóm tắt có phần chưa rõ, copy và tải văn bản thật |
| Kế hoạch ứng phó | **Nằm trong `/cases/:caseId/plan`**. 3 phương án có lý do/điều kiện/cân nhắc, tự tạo hoặc để sau; thêm/sửa/xóa/sắp thứ tự bước, ưu tiên, ghi chú, ngày xem lại, pause/continue/completed; tiến độ Home đồng bộ |
| AI Companion | Hub và lịch sử hội thoại, 30 scenario selector, 12 hội thoại đa lượt dựng sẵn, câu hỏi làm rõ, phản hồi streaming mô phỏng có thể hiện ngay, attachment fixture, rich findings và nguồn, chuyển lời đã xác nhận sang wizard |
| Phân tích ảnh | 3 bộ demo trên 8 ảnh SVG hư cấu: nhiều nguồn, mâu thuẫn giờ, gần trùng. Xem ảnh/text/time, sửa không ghi đè bản gốc, bỏ ảnh, xác nhận từng nguồn, chỉ tạo timeline từ phần xác nhận, gộp nội dung trùng, giữ phần sửa khác biệt và giới hạn |
| Roleplay | 6 scripts, giáo viên/phụ huynh/người lớn tin cậy; mục tiêu/tone, 3 lượt người dùng, nhập text/câu mẫu, pause/retry/stop, transcript và phản hồi mẫu; chọn riêng từng đoạn để chuyển Support |
| Knowledge | 24 nội dung có cấu trúc/nguồn/ngày rà soát/phạm vi, search không dấu, lọc chủ đề/tuổi/format, đã lưu/đã đọc, 10 tình huống lựa chọn, 5 quiz, related articles, deep link có nguồn sang AI |
| Support | Nguồn hỗ trợ, người tin cậy thêm/xóa, chuẩn bị lời nhắn từ case hoặc đoạn roleplay, chọn người nhận/mục đích/bí danh/tên demo, preview sửa/copy/download, draft recovery, xác nhận mô phỏng báo cáo, status timeline local |
| Khẩn cấp | `/support/urgent` công khai; tìm nơi an toàn/người lớn gần đó, `tel:111` và website chính thức do người dùng chủ động mở |
| Profile / Settings | Bí danh, tuổi, giảm motion, đăng xuất, reset xác nhận, lỗi lưu một lần, entry School Demo |
| School Admin | Layout riêng `/demo/school/*`, banner **Demo Data**, 48 báo cáo độc lập; KPI/category/month charts/list từ cùng collection; filter đồng bộ, chi tiết, ghi chú/status mock và reset riêng |

Student navigation có đúng **Home / AI / Hồ sơ / Support**, bottom nav trên mobile và sidebar trên desktop. Action Plan không có tab riêng. Các route không tồn tại/không thuộc persona có đường quay về.

## 2. Cấu trúc frontend

```text
frontend/
├── src/
│   ├── app/                  # router, layouts, canonical persisted store
│   ├── components/
│   │   ├── ui/               # buttons, fields, native dialog, feedback primitives
│   │   └── layout/           # brand, shell, navigation, toast
│   ├── features/
│   │   ├── onboarding/ auth/ home/ profile/
│   │   ├── incidents/ action-plans/
│   │   ├── ai/ knowledge/ support/
│   │   └── school-admin/     # separate seed + persisted store
│   ├── animations/           # useGSAP PageMotion, AgentStatusOrb
│   ├── mocks/
│   │   ├── data/             # student, knowledge, source seeds
│   │   ├── scenarios/        # 30 scenarios, chat and roleplay fixtures
│   │   └── services/         # typed async local adapter, latency/failure
│   ├── hooks/                # reduced motion, visual viewport
│   ├── lib/ types/ styles/
│   └── main.tsx
├── public/fixtures/          # messenger_01.svg ... messenger_08.svg
├── e2e/                     # new Playwright suite
├── scripts/check-boundaries.mjs
├── PRODUCT.md / DESIGN.md / THIRD-PARTY-NOTICES.md
└── README.md
```

Không tạo Python package, runtime agent, API hoặc migration. `backend/README.md` và `agent/README.md` chỉ mô tả trách nhiệm/cấu trúc tương lai. Asset ảnh mẫu thuộc `public/fixtures/` để dùng trực tiếp, không cần thêm thư mục assets rỗng.

## 3. Mock datasets, state và workflows

- 4 persona; 5 seed cases và 4 seed plans, luôn lọc theo owner. Danh sách người tin cậy, bookmark/read state có scope persona riêng.
- 30 tình huống `SC-01..30`, 12 chat fixtures (6 tin mỗi fixture), 6 roleplay scripts (3 lượt học sinh mỗi script).
- 8 screenshot tổng hợp, đủ thông tin bị cắt/che/gần trùng; 3 biến thể analysis. Evidence IDs có namespace theo phiên phân tích để tránh ghi đè khi mở nhiều bộ.
- 24 article blocks, 10 interactive scenarios, 5 quizzes. Metadata trỏ tới record nguồn xác định; nội dung biên tập nguyên bản cho prototype, không tuyên bố được tổ chức nguồn chứng nhận.
- 48 school reports: online 15, verbal 12, social 10, physical 6, other 5; new 9, reviewing 18, follow_up 13, closed 8. Không có student owner/case IDs trong dataset này.
- Canonical localStorage key `moodprint-demo`, school key `moodprint-school-demo`. Các biểu mẫu dùng sessionStorage có scope owner + case/nguồn/handoff. Reset xóa các draft prefix thuộc MoodPrint và khôi phục seed, giữ dữ liệu ứng dụng khác.
- Lỗi lưu mock có độ trễ và retry; không giả thành công khi thao tác thất bại. Plan draft lưu baseline; thay đổi mới trên Home phải được đối chiếu trước khi lưu bản cũ. Chat→wizard dùng draft identity riêng, không trộn câu chuyện cũ với nguồn chat mới.
- Xóa case gỡ liên kết chat/support/analysis, xóa plan/draft case; bằng chứng gốc còn dùng cho phân tích được giữ tại nguồn AI, không còn gắn case đã xóa.

Luồng chính kiểm thử: Welcome → Account → Home → Chat 3 lượt → 8 ảnh → xác nhận 6 nguồn → 6 mốc → Case → Plan chọn/lưu/hoàn thành bước → Roleplay 3 lượt → feedback → chọn đoạn → Support preview → xác nhận demo → reload timeline vẫn đủ 6 mốc.

## 4. Thiết kế và chuyển động

- Kế thừa `04-DESIGN-SYSTEM.md`: nền xanh ngà, ink xanh trầm, primary teal, lavender luyện nói, peach cho kiến thức; semantic tokens, spacing có nhịp, panel radius 12–16px, Lucide và logo/hình học tự tạo. Không dùng ảnh học sinh hoặc hotlink asset/font.
- Font hệ thống hỗ trợ tiếng Việt, fallback theo đặc tả; không cần tải font ngoài. Home dạng nhật ký cá nhân, Chat dạng transcript, hồ sơ dạng tài liệu/timeline, Knowledge dạng danh sách biên tập, admin riêng.
- GSAP + `@gsap/react/useGSAP` cho page/onboarding entrance 260ms, scope ref, cleanup/matchMedia. Native dialog đảm nhiệm focus trap và bottom sheet mobile; không tuyên bố tất cả hiệu ứng đều dùng GSAP.
- Thinking Orbs chỉ chuyển động trong trạng thái mock đang hoạt động, có nhãn mô phỏng; idle/error/reduced-motion tĩnh. Không giả web search hay tool execution.
- Safe-area bottom nav, touch controls, focus ring, skip link, semantic labels; visualViewport hook thích ứng bàn phím. Có loading/skeleton, empty, inline error/retry, success và destructive confirmation.

## 5. Kiểm chứng và bằng chứng

| Kiểm tra | Kết quả | Bằng chứng |
|---|---|---|
| TypeScript | PASS, exit 0 | `verification/typecheck.log` |
| ESLint | PASS, 0 errors / 0 warnings | `verification/lint.log` |
| Unit/state/component | **50/50**, 12 files | `verification/tests.log` |
| Production build | PASS, exit 0, không cảnh báo chunk lớn | `verification/build.log` |
| E2E Chromium | **PASS 6/6**: entry/nav, guard/urgent, admin isolation, full journey 390px, full journey 1440px, responsive; lượt cuối 1,8 phút | `verification/e2e.log` |
| Responsive | 14 route × 8 viewport = 112 lượt: 320/360/375/390/430/768/1024/1440; không overflow; chat input ở viewport thấp 390×480 vẫn trong màn | `e2e/responsive.spec.ts`, screenshots |
| Console / network | Không page error/console error trong responsive run; không request ngoài origin trong journeys | assertions trong E2E |
| Bundle boundaries | 58 source files / 15 build files; không phát hiện credential pattern, application HTTP/socket/telemetry/microphone call hoặc SDK production | `verification/boundaries.json` |
| Accessibility bổ sung | axe-core 4.12.1, WCAG2A/AA trên 9 route; lỗi contrast/accessible name tìm được đã sửa | `a11y-evidence.json` |
| Format | Prettier check sạch | lệnh ở README / execution ledger |

Hai mục axe cần review thủ công: background textarea preview bị nav che trong viewport khi quét; SVG chart labels không tự xác định background. Màu khai báo textarea #183B37/trắng đạt 12,21:1; labels chart #355C4E/trắng đạt 7,52:1. Đây là kiểm tra bổ sung, không phải chứng nhận accessibility toàn diện. Không báo đã test VoiceOver/NVDA hoặc phần cứng điện thoại thật.

18 ảnh mobile/desktop của Home, Chat, Plan, Roleplay, Knowledge, Support, School Demo và analysis/support message ở `screenshots/`. Các ảnh được tạo bằng trình duyệt thật; full-page capture có thể hiển thị fixed nav tại vị trí viewport khi chụp.

Build chia React vendor (~316kB), motion (~71kB), app (~202kB), AI lazy (~95kB); kích thước chưa gzip. Không lấy kết quả suite/CI cũ làm bằng chứng. Warning `NO_COLOR/FORCE_COLOR` trong CLI test runner là môi trường terminal, không phải console error trong app.

## 6. Review, giới hạn và phần chưa triển khai

Independent code review ban đầu tìm 10 Important và 2 Minor; các lỗi scope/reset, context, draft conflict/loss, duplicate correction, processing recovery và ARIA đã được sửa, có kiểm thử hồi quy. Xem `REVIEW-NOTES.md` và phần đóng review ở cuối file đó. Sau visual review còn sửa contrast số mục bài đọc, cỡ chữ metadata, focus cleanup và liên kết khi xóa case.

Giới hạn có chủ đích:

- Chat phản hồi theo fixture; câu ngoài nhánh nhận fallback trung thực. Rich interpretation là nội dung mẫu, không tự diễn giải ý nghĩa phần người dùng sửa. Timeline phản ánh đúng phần được xác nhận.
- Voice demo là nhịp/transcript, không âm thanh, không STT/TTS, không microphone. Không đọc ảnh upload tùy ý hoặc chạy OCR thật.
- Copy phụ thuộc quyền clipboard của trình duyệt, có hướng tải text/chọn văn bản. Export là `.txt`, không có PDF thật hay chứng nhận pháp lý.
- Account/persistence chỉ local demo, không phải auth/access control hoặc lưu trữ dữ liệu nhạy cảm production.
- Chưa test Safari/Firefox, trình đọc màn hình thật, thiết bị iOS/Android thật hoặc nghiên cứu với học sinh. Kiểm tra bàn phím được mô phỏng bằng viewport/visualViewport; vẫn cần test phần cứng trước sản phẩm thật.
- Chưa có live reminders, email/SMS, nhận báo cáo, xác minh trường, bản đồ, retrieval, model hoặc cloud. Website nguồn/tel chỉ mở khi người dùng tự chọn.

## 7. Chạy local và bước tiếp theo

```powershell
cd frontend
npm install
npm run dev
```

Chọn một mock account sau onboarding. Không cần `.env`/API key. Reset ở Settings; reset admin có nút riêng. Các lệnh test đầy đủ nằm trong `frontend/README.md`.

Production preview từ `dist/` cũng đã mở được Welcome → account → Home → AI lazy chunk qua browser, không ghi nhận lỗi browser. Build chỉ ở local; không deploy.

Để tích hợp thật sau này: chốt chính sách tài khoản/quyền dữ liệu và tiếp nhận hỗ trợ → định nghĩa OpenAPI/FastAPI adapter và schema → xây auth/database/evidence access → đánh giá nguồn kiến thức và RAG → đưa 30 scenarios/8 screenshots thành eval fixtures cho module `agent/` → thêm OCR/voice có transcript review/timeout/cancel → tích hợp trường sau khi xác minh đối tác/quy trình tiếp nhận → staging/monitoring/release theo yêu cầu riêng. Chưa thực thi các bước đó trong phiên này.
