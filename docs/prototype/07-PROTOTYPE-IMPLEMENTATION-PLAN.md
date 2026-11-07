# MoodPrint — Prototype Implementation Plan & Acceptance Gates

> 07/11/2026 • **KẾ HOẠCH, CHƯA TRIỂN KHAI** • Phạm vi: frontend React/Vite/TS + dữ liệu mock, chưa backend/AI/API/DB/hạ tầng. Tài liệu dành cho người phụ trách sản phẩm và coding agents.

## 1. Phương thức thực hiện

**Branch mục tiêu:** `mhiu05/feat-refactor` trong GitHub repo `mhiu05/MoodPrint` (phân biệt với branch `feat-refactor` khác). Trước khi agent sửa source, phải kiểm tra `git status`, current branch, SHA, các file được giữ lại và đảm bảo `.env` không nằm trong Git. Không làm thay đổi `main`, website public, DNS, SES, Supabase hoặc EC2 trong giai đoạn prototype.

**Nguyên tắc:** bắt đầu bằng IA/data contract/design system, sau đó xây component library → các journey quan trọng → mở rộng chức năng → QA. Không tạo backends/Agents thật để “đỡ trống”. Mọi nút phải có tác dụng mock rõ ràng hoặc thông báo giới hạn chính xác.

**Phạm vi việc xóa:** xóa source cũ, tests/CI cũ đã được chủ sản phẩm quyết định. Nhưng cần giữ bản sao từ Git history; không xóa secret trên máy hay tác động tài nguyên cloud. Nếu repo đã được dọn sạch, tiếp tục từ cấu trúc trống, **không bắt buộc khôi phục**.

## 2. Outcome và Definition of Done cấp dự án

- **Product coherence:** 5 tính năng lõi đã chốt, bao gồm **Kế hoạch ứng phó trong Hồ sơ sự việc**, kết nối liền mạch; không có màn hình “trang trí” không dẫn đến hành động.
- **Experience:** 4-tab mobile shell; onboarding skip/next; demo account; tương tác đa màn, responsive.
- **Content:** 24 bài Knowledge, 30 scenarios, 12 chat scripted flows, 6 roleplays, 8 screenshot fixtures.
- **Case workflow:** tạo từ mẫu và AI, thêm/sửa timeline/evidence, phân tích nguồn, export preview, theo dõi trạng thái cá nhân.
- **Support:** nguồn hỗ trợ, chế độ bí danh, tin nhắn nháp, trạng thái demo trung thực, đường 111.
- **Admin:** school dashboard demo độc lập, KPI/list/filters từ cùng synthetic dataset.
- **QA:** tiêu chí test ở từng milestone; không cần phục hồi CI cũ nhưng phải có kiểm thử mới cho UI.
- **Deliverables:** code prototype frontend, docs đầy đủ, screenshots ở 320/390/768/1440, checklist nghiệm thu và known limitations.

## 3. Milestones theo dependency, không gán thời lượng tùy tiện

### M0 — Baseline, repo hygiene và product alignment

**Input:** tài liệu 01–07, repo branch đúng, không có yêu cầu triển khai thật.

**Tasks:**
1. Kiểm tra current branch chính xác `mhiu05/feat-refactor`, worktree sạch; không tự merge.
2. Lưu lịch sử source cũ trong Git (không phải copy secrets); dọn các file outdated đã không còn mục đích.
3. Kiểm tra `.gitignore` exclude `.env*` (ngoại trừ `.env.example` đã vệ sinh), `node_modules/`, build outputs, logs, local fixtures nhạy cảm.
4. Đặt tài liệu vào `docs/`, index/decision log. Ghi rõ Action Plan là core #3 đã duyệt, thuộc Hồ sơ sự việc, route `/cases/:caseId/plan`.
5. Xác nhận toàn bộ prototype không dùng API thật, analytics thật, map real, voice capture thật.

**Gate:** có file inventory, no secrets tracked, decision log và baseline commit riêng trước khi tạo UI.

### M1 — Design foundations và navigation shell

**Tasks:**
1. Tạo design tokens từ `04-DESIGN-SYSTEM.md` (colors, type, spacing, radii, breakpoints, motion).
2. Xây primitives (Button, Input, Card, Badge, Tabs, Dialog, EmptyState, Toast, Skeleton).
3. Dựng `StudentShell`, 4-tab bottom nav, desktop sidebar, page headers, modals.
4. Route navigation theo `03-INFORMATION-ARCHITECTURE.md`, gồm not-found và deep links.
5. Chuẩn bị responsive/language formatting, focus and keyboard navigation.

**Gate:** 4 tab hoạt động; layout không vỡ ở 320/375/390/430/768/1440; keyboard traversal và focus rõ.

### M2 — Onboarding, mock account, home

**Tasks:**
1. Welcome 4 trang Next/Back/Skip, welcome copy và hình minh họa tự tạo.
2. Mock account entry; persona selector, age band, nickname; không thu/lưu password thật.
3. Home hero, quick actions, recent cases, step progress, Knowledge picks, help now.
4. Reset demo data và session giả; case owner scope theo persona.

**Gate:** J01 end-to-end; skip không bypass account; Home nhận thông tin đúng từ store; không có network/auth thật.

### M3 — Canonical mock store, incident forms và timeline

**Tasks:**
1. Tạo typed entity schemas và seed `DemoUser/Case/Event/Evidence/...` theo `05-MOCK-SCENARIOS.md`.
2. Cài mock repositories/store adapters; state không clone riêng từng màn.
3. Case list search/filter/sort, case detail, status transition, case templates.
4. Wizard 6 bước, save draft, edit, confirm exit, add event/evidence (mock only), timeline.
5. Report preview và source provenance labels.

**Gate:** J04/J05; home cases và case list nhất quán; sửa một event phản ánh ở timeline/summary; không bịa timestamp.

### M4 — AI Companion chat/analysis mock

**Tasks:**
1. AI hub với Chat và Roleplay làm hai entry chính.
2. Scripted chat engine deterministic, 12 flows, quick replies, fallback trung thực cho text ngoài nhánh.
3. Fixture gallery 8 screenshot hư cấu; UI review, corrections, uncertainty labels, possible duplicates.
4. Analysis detail với 4 vùng quan sát/điểm cần xem xét/chưa rõ/bước tiếp theo; source refs.
5. Convert verified findings to case draft (explicit user confirm).

**Gate:** J02/J03; analysis không tự assert thủ phạm/chứng cứ đã xác thực; screenshot source trace hợp lệ; không gọi OpenAI/Vision/OCR thật.

### M5 — Roleplay text và voice demo

**Tasks:**
1. Roleplay selector giáo viên/phụ huynh; mục tiêu, tone, script fixture.
2. Text conversation 3–5 lượt, selectable responses + nhập text mô phỏng.
3. Voice demo: transcript/waveform/play-pause state, không yêu cầu microphone.
4. Feedback 3 mục: điều đã trình bày rõ, có thể bổ sung, câu gợi ý.
5. Save mock transcript sample to support composer, retry, session exit confirm.

**Gate:** J07/J08; không có phản hồi gây tổn thương; text và voice mode cho cùng nội dung, không hứa STT/TTS thật.

### M6 — Knowledge Hub và interactive learning

**Tasks:**
1. Curate 24 article summaries từ nguồn đã liệt kê, có URL/source/time/review note.
2. Tạo content list/search/filter/read/bookmark; scenario cards/quiz; deep link từ AI.
3. Mỗi bài có callouts hữu ích, tình huống ví dụ, các lựa chọn và “khi cần tìm người hỗ trợ”.
4. Phân biệt nguồn áp dụng ở Việt Nam và nguồn tham khảo quốc tế; không bịa luật/số liệu.

**Gate:** J12; search/filter có no results state; link nguồn hợp lệ; nội dung dễ đọc ở 320px.

### M7 — Support Center, alias và help now

**Tasks:**
1. Support landing: Knowledge/Find help/Urgent/Profile.
2. Source list + Contact info cho 111, mẫu nói với giáo viên/phụ huynh/người tin cậy.
3. Message composer + draft/preview/copy + alias/disclose.
4. Report demo flow: confirm `chưa gửi thật`, status timeline demo; không có real send.
5. Help-now route mở trực tiếp; link/tel không cần đi qua chat.

**Gate:** J09/J10; không chứa dòng “Trường đã nhận” không có qualifier; có thể tìm 111 trong ≤2 thao tác từ mọi tab.

### M8 — Hoàn thiện Kế hoạch ứng phó (core #3) và School Admin Demo

**Tasks Kế hoạch ứng phó (bắt buộc trong prototype):**
1. Trong Case Detail có tab/section **Kế hoạch ứng phó**, dùng route `/cases/:caseId/plan`; cho người dùng chọn 2–3 phương án, tạo checklist và ghi chú tiến độ.
2. Cho phép thêm/sửa/đánh dấu/tạm dừng các bước; thể hiện draft, active, paused và completed theo một `caseId`.
3. Home progress đọc từ **cùng canonical mock plan store**, và AI/Support deep-link được về kế hoạch của hồ sơ đúng.
4. Demo không khẳng định đã gửi báo cáo, đã liên hệ người lớn hoặc đã đảm bảo an toàn; mọi tương tác là mock.
5. Các mô hình dữ liệu và route được định nghĩa sớm từ M0/M1, M8 tập trung hoàn thiện UI và cross-flow, không để core #3 trở thành phần tùy chọn.

**Tasks School Admin:**
1. Separate `/demo/school` layout và store.
2. 48 school demo reports hư cấu; KPI/charts/list cùng tính toán từ dataset; filter updates all.
3. Drill-down giả, status simulation, demo banner mỗi màn hình.
4. Không chuyển các case cá nhân sang school demo.

**Gate:** J06/J13; seed aggregation khớp; brand/copy demo minh bạch; student/admin data isolation.

### M9 — Product polish, QA, packaging

**Tasks:**
1. UX audit theo flows J01–J14; kiểm tra từng CTA không bị chết.
2. Form validation, skeleton/empty/error/retry/confirm states, transition polish, reduced motion.
3. Responsive visual QA, keyboard and screen reader smoke, tap target, screenshot consistency.
4. Data consistency audit: ids, timestamps, labels, seeded counts; restore seed.
5. Source accuracy audit: URL, age scope, không sử dụng claim sai, không fake report delivery.
6. Prototype walkthrough demo 2 tuyến: (a) 8 screenshot → case → support; (b) không chắc bị bắt nạt → Knowledge → roleplay.
7. Viết limitations và README vận hành **frontend local only**; không deploy.

**Gate:** toàn bộ P0/P1 passed và mọi blocker đóng; nếu còn lỗi nghiêm trọng về hỗ trợ khẩn cấp, danh tính hoặc khẳng định AI sai thì không gọi prototype hoàn thiện.

## 4. Công việc có thể chạy song song giữa nhiều coding agents

| Workstream | Scope | Phụ thuộc | Chống conflict |
|---|---|---|---|
| A — UI Foundations | tokens, components, Shell, nav | M0 | sở hữu `components/`, styles, AppShell |
| B — Case & Mock Data | entities, fixture, case wizard/timeline | schema lock từ M1 | sở hữu `features/incidents`, `mocks/core` |
| C — AI & Roleplay UI | AI hub/chat/analysis/roleplay | schemas đã thống nhất | sở hữu `features/ai`, `mocks/ai` |
| D — Knowledge & Support | content, search, support composer | design system + ports | sở hữu `features/knowledge`, `features/support` |
| E — School Admin Demo | synthetic dataset, dashboard | mock model conventions | sở hữu `features/school-demo`, `mocks/admin` |
| F — UX QA/Docs | acceptance/test scripts, visual audit | các màn tối thiểu | sở hữu `docs/`, QA fixtures |

**Tích hợp:** một người giữ `routing`, `types/contracts`, `package.json`; chỉ merge sau khi shared interfaces được review. Với git worktrees, mỗi workstream dùng một branch/worktree riêng; tránh hai agents cùng viết `App.tsx`/global CSS. Không mở CI/CD production trong giai đoạn này.

## 5. Rủi ro thứ tự xây dựng

- **Sai lầm:** code landing page quá đẹp trước khi có data model → mọi màn hình rời rạc. **Giải pháp:** mock schema trước cả case/AI.
- **Sai lầm:** roleplay voice UI giả nhưng hiển thị thật → mất lòng tin. **Giải pháp:** nhãn mô phỏng/không xin quyền mic.
- **Sai lầm:** AI script tự gắn mọi trường hợp là bắt nạt → bias. **Giải pháp:** SC-02/18/19/22/23 là negative cases bắt buộc.
- **Sai lầm:** School Admin lấy từ student store → lộ thông tin. **Giải pháp:** separate demo repository và seed.
- **Sai lầm:** màn form kéo dài → người dùng bỏ cuộc. **Giải pháp:** lưu nháp và nhập từng bước, không ép timestamp.
- **Sai lầm:** không có đường trợ giúp khẩn cấp → sản phẩm dễ gây hại. **Giải pháp:** Help-now entry từ mọi tab.

## 6. Nghiệm thu theo scenario & màn

| Priority | Journey | Điều kiện nghiệm thu | Blocker nếu không đạt |
|---|---|---|---|
| P0 | J01 | onboarding/account demo/4-tab | yes |
| P0 | J02 | Chat hỏi làm rõ và không gán nhãn quá mức | yes |
| P0 | J04 | Case wizard và lưu nháp | yes |
| P0 | J09 | Support nháp + alias không tuyệt đối | yes |
| P0 | J10 | Urgent và 111 tiếp cận ngay | yes |
| P1 | J03 | 8 ảnh fixture, xác nhận, timeline | yes |
| P1 | J05 | case edit/timeline consistency | yes |
| P1 | J07/J08 | 2 roleplay có feedback | yes |
| P1 | J12 | KB browse/search/source | yes |
| P1 | J13 | Admin demo data isolation | yes |
| P1 | J06 | Kế hoạch ứng phó hoàn chỉnh bên trong Hồ sơ sự việc | yes |
| P2 | J14 | edge states, reset, deep links | yes |

## 7. Data acceptance checks

- Mọi `Case.ownerId` tham chiếu đúng user; không có cross-user case trên Student UI.
- Mọi timeline event `evidenceIds` tham chiếu evidence tồn tại trong cùng case.
- Claim có `kind=inferred/unknown` không được render trong phần fact đã xác nhận.
- 8 fixture gốc có đủ 8 `evidenceId`, flag truncated và duplicate.
- 48 school demo reports → KPI/Charts/list recompute cùng dataset; không hardcode số tổng riêng.
- Roleplay `turns` có thứ tự nhất quán, feedback gắn với user choice đúng.
- KB có `sourceIds`, canonical URL, `countryScope`, `lastReviewed` hoặc label chưa rà soát.
- Reset demo khôi phục state; không xóa file ngoài browser hay service thật.

## 8. Test specification mới (không phục hồi CI cũ)

### UI unit/component

- Button states, form validation, bottom nav active/deeplink, focus traps, modal exit confirmation.
- Helpers format date precision, source badges, status transitions, alias preview.

### Integration mock state

- Chat → case draft → save → Home recent card.
- Analysis MEDIA-01..08 → review text → timeline references.
- Roleplay → support draft → copy status.
- Plan checklist → Home progress.
- Admin filter → KPI/list consistency, no student data.

### End-to-end scripted

- E2E-A: onboarding demo → chat SC-01 → case → support draft.
- E2E-B: AI SC-08 8 screenshots → approve 6 facts → case timeline → summary preview.
- E2E-C: roleplay teacher → feedback → copy message.
- E2E-D: bystander KB → trusted person resource.
- E2E-E: urgent help direct URL accessible.
- E2E-F: school admin filter/inspect synthetic report.
- E2E-G: reset demo, ensure seed restored.

### Visual/accessibility

- Screenshot matrix 320/375/390/430/768/1024/1440; keyboard only; screen-reader smoke; contrast and reduced-motion.
- Test nội dung dài tiếng Việt và text wrap, browser back, mobile keyboard overlays.

**Không dùng kết quả pass của CI cũ làm bằng chứng cho prototype mới.** Khi có code mới, tạo test suite mới từ contract này. Lựa chọn công cụ kiểm thử cụ thể có thể quyết định trong implementation.

## 9. Release của prototype vs sản phẩm thật

| Mốc | Cho phép | Không cho phép |
|---|---|---|
| Docs baseline | Markdown PRD/IA/Design/Mock/Architecture | gọi API thật, sửa hạ tầng |
| Prototype local | UI và fixture mock | Supabase Auth, email thật, AI calls |
| Internal demo | demo data cho người xem, có banner | nhận báo cáo thật, claim đã được trường xử lý |
| Production product | chỉ sau quyết định/kiểm chứng riêng | không được tự động coi prototype là sản phẩm sẵn sàng |

**Website hiện public:** việc commit lên nhánh feature không tự deploy theo luồng `main` đã được xem ở lần kiểm tra trước. Tuy nhiên khi merge/push `main`, release automation có thể thay đổi runtime; phải kiểm tra cơ chế release hold/Actions/poller **trước** merge và không tự ý xóa branch, DNS, email, AWS.

## 10. Checklist bàn giao cho coding agent

- [ ] Đã đọc đủ 7 tài liệu và lập traceability matrix `feature → route → fixture → test`.
- [ ] Đang ở đúng branch `mhiu05/feat-refactor`, không push/merge ngoài phạm vi được giao.
- [ ] Không tái dùng source/Agents/CI cũ, không tự tạo backend/hạ tầng.
- [ ] Design tokens và mock schema có owner rõ trước khi chia workstreams.
- [ ] Mỗi PR có screenshot mobile, thông tin routes và journeys đã cover.
- [ ] Các từ “AI”, “phân tích”, “đã gửi”, “ẩn danh” được mô tả đúng mức khả năng mock.
- [ ] Không có API key hoặc credential trong build/commit.
- [ ] Product owner review các trạng thái nhạy cảm; kiểm tra Action Plan là core #3 trong Hồ sơ sự việc, không tách tab riêng.
