# 92 — Visual QA bằng agent-browser và đặc tả E2E

## 1. Phương pháp baseline (đã thực hiện 31/10/2026)

| Hạng mục | Chi tiết |
| --- | --- |
| Công cụ | `agent-browser 0.39.4` (devDependency của frontend); đọc hướng dẫn qua `agent-browser skills get core` trước khi dùng |
| Session | Hai session đặt tên riêng: `mp-plan-baseline` (local), `mp-plan-prod-readonly` (production, chỉ landing) |
| Môi trường chat | **Vite dev riêng** cổng 5180 với `MOODPRINT_API_PROXY=http://127.0.0.1:9` (cổng chết) để không request nào tới backend thật; mọi `/api/v1/*` cần thiết được stub bằng `agent-browser network route --body` với dữ liệu **tổng hợp** (`session`, `bots`, `ai/preferences`, `ai/conversations`, một hội thoại 6 tin, `proposals`, `social/summary`). Server dev 5173/backend 8001 của người dùng không bị chạm |
| Lưu ý dữ liệu | Working tree có thay đổi chưa commit của người dùng (`RealApp.tsx`, `journal.css`) và công việc song song ở social — baseline phản ánh working tree lúc chụp |
| Production | `https://moodprint.duckdns.org/` chỉ mở landing, `--allowed-domains moodprint.duckdns.org`, không đăng nhập, không bấm "Dùng thử", không tạo dữ liệu |
| Viewport | 1440×900, 768×1024, 390×844; `set media light reduced-motion` |
| Ảnh chụp | Lưu ngoài repo (scratchpad của phiên), **không commit**, đúng quy ước "chat captures stay outside git" của dự án |
| Dọn dẹp | Đóng cả hai session, dừng Vite 5180 |

## 2. Quan sát baseline

| # | Quan sát | Bằng chứng | Hệ quả cho Phase 1/2 |
| --- | --- | --- | --- |
| B-01 | Tin của trợ lý là văn bản trần (không khung); tin người dùng là pill xám bên phải | Ảnh desktop 1440 | Nhóm bubble không dùng khung (DESIGN.md) |
| B-02 | Hai tin bot liền nhau (khác run) cách nhau như hai lượt riêng: hàng 1 cao 78 px, khoảng trống trên dưới lớn | Đo `getBoundingClientRect`: top 283/373, height 78/155 | Cần khoảng cách hẹp trong nhóm để đọc như một lượt |
| B-03 | Nhãn ngày **"Today"** tiếng Anh giữa UI tiếng Việt | `.message-date-separator` = `29/10/2026 \| Today`; nguồn [messageDates.ts:23](../../../frontend/src/features/real/messageDates.ts#L23) | Sửa thành "Hôm nay"/"Hôm qua" (P1-07) |
| B-04 | Focus bàn phím vào tin bot hiện giờ "20:05" + nút sao chép | `activeElement` = "Tin nhắn từ Nhịp", `.message-details-open` = 1 | Giữ cho từng bubble |
| B-05 | `role="log"` có `aria-live="off"`; `.conversation-messages` có `aria-live="polite" aria-relevant="additions text"` | `eval` thuộc tính | Chèn cả nhóm một lần để đọc một lần |
| B-06 | Mobile 390: chat full-screen, **ẩn** thanh điều hướng; nút ← về danh sách | Ảnh 390 chat | Chỉ báo chưa đọc phải có trên nút ← |
| B-07 | Mobile 390 roster: tab bar 5 mục dưới cùng, mỗi dòng trợ lý có chỗ bên phải | Ảnh 390 roster | Badge tab "Trợ lý" + chấm từng dòng |
| B-08 | Sheet "Thông tin cuộc trò chuyện" trên mobile là `dialog` modal, các section h3 + mô tả + nút | `dialog[open].conversation-info` = true; ảnh | Thêm section "Lời hỏi thăm" theo cùng mẫu |
| B-09 | Desktop: tiêu đề "Lịch sử trò chuyện" / "Làm mới" bị xuống dòng trong cột roster hẹp | Ảnh 1440 | Mục "Lời nhắn mới" trên roster cần nhãn ngắn |
| B-10 | Trạng thái lượt bị gián đoạn hiện dưới tin người dùng: "Phản hồi bị gián đoạn; lượt này không tự chạy lại." | Ảnh | Giữ nguyên |
| B-11 | Không có tràn ngang ở 390 (`scrollWidth = 390`), composer cao 44 px | `eval` | Điều khiển mới ≥ 44 px |
| B-12 | Reduced motion được emulate đúng (`matchMedia` = true), log `scroll-behavior: auto` | `eval` | Test reduced motion dùng cùng cơ chế |
| B-13 | Production landing: "Bắt đầu với MoodPrint", "Dùng thử 2 giờ" **disabled** kèm "Chưa thể bắt đầu lượt dùng thử. Thử lại sau."; `/api/v1/health/ready` = 200; `/session` = 401 (chưa đăng nhập) | Snapshot + network | Production đang chạy image chấp nhận hosted 0019 |

Giới hạn: không kiểm chat đã đăng nhập trên production (cần tài khoản thử nghiệm tổng hợp do owner cấp); không có backend thật nên không kiểm SSE thật, history pagination thật hay lỗi mạng thật ở baseline.

## 3. Quy trình E2E đề xuất cho triển khai

| Lớp | Cách | Khi nào |
| --- | --- | --- |
| Fixture (CI) | Playwright `page.route("**/api/v1/**")` như [ux-fixtures.ts](../../../frontend/tests/e2e/ux-fixtures.ts); SSE fixture trả body `text/event-stream` | Trạng thái UI, a11y, responsive |
| Fullstack (CI) | `frontend/tests/fullstack/*` + backend thật + `ScriptedModel`; thêm router **chỉ khi `APP_ENV=test`**: `POST /api/v1/test/proactive/tick` (chạy một tick với đồng hồ giả) và `POST /api/v1/test/clock` | Scheduler, giao trùng, consent |
| agent-browser (thủ công, trước G1/G2) | Như §1: Vite riêng + stub, hoặc trỏ vào fullstack server local; `snapshot -i`, `screenshot`, `set viewport`, `set media … reduced-motion`, `network route` để mô phỏng lỗi | Duyệt trực quan, ảnh bằng chứng |

Fixture dữ liệu chung: user `11111111-…` (adult), teen `44444444-…`, guest; 5 bot; hội thoại Nhịp có 6 tin; lời hỏi thăm sáng 2 bubble có `origin="proactive"`, `proactiveSlot="morning"`; nhật ký tổng hợp với canary `CANARY-JOURNAL-*`.

## 4. Đặc tả ca E2E

Ký hiệu: **F** = fixture, **FS** = fullstack, **AB** = agent-browser. Mọi ca chạy ở 1440 và 390 trừ khi ghi khác.

### E2E-01 — Nhiều bubble (P1)
| | |
| --- | --- |
| Tiền đề | `AI_MULTI_MESSAGE_ENABLED`; hội thoại Mây mới |
| Dữ liệu | SSE v2: progress, final 3 bubble (bubble 3 có card `navigate_bot: rure`), completed |
| Thao tác | Gõ "Mình hơi mệt", Enter |
| Kỳ vọng UI | Trạng thái "Đang trả lời…" rồi 3 khối văn bản xuất hiện **cùng lúc** sau `completed`; một `group` "Tin nhắn từ Mây, 3 phần"; giờ + sao chép ở khối cuối; card ở khối cuối |
| Kỳ vọng API | Request events có `protocol=2`; sau đó `GET conversation` trả 3 row cùng `runId`, `partIndex` 0..2 |
| Khẳng định | `toHaveCount(3)`; không khối nào hiện trước event `completed` (chặn stream tại `final` → 0 khối) |
| Chẩn đoán | Lưu HAR fixture, snapshot a11y, console errors |
| Workflow | F (Playwright); AB: route events body, `snapshot -i`, `screenshot` |

### E2E-02 — Một bubble và tương thích v1 (P1)
| | |
| --- | --- |
| Tiền đề | Flag tắt **hoặc** server trả v1 |
| Dữ liệu | SSE v1 `final {text, cards}` |
| Thao tác | Gửi tin |
| Kỳ vọng UI | Một khối như hiện tại |
| Kỳ vọng API | Client chấp nhận v1 khi đã yêu cầu `protocol=2` |
| Khẳng định | Không lỗi "Chưa nhận được phản hồi hợp lệ" |
| Chẩn đoán | Nội dung SSE thô |
| Workflow | F |

### E2E-03 — Lời hỏi thăm mới xuất hiện (P1)
| | |
| --- | --- |
| Tiền đề | Lịch Nhịp sáng 07:30 bật; người dùng đang mở danh sách trợ lý |
| Dữ liệu | FS: entry tổng hợp hôm qua; đồng hồ test 07:30:05 |
| Thao tác | Gọi tick test; chờ ≤ 30 s (poll inbox) hoặc focus tab |
| Kỳ vọng UI | Badge "Trợ lý, 1 lời nhắn mới"; dòng Nhịp có chấm; mục "Lời nhắn mới: Nhịp · Lời hỏi thăm buổi sáng · 07:30"; mở → nhãn "☀ Lời hỏi thăm buổi sáng · 07:30", 1–3 khối, dòng "Bài viết đã tham khảo" |
| Kỳ vọng API | `GET /ai/inbox` unreadTotal=1; job `delivered` |
| Khẳng định | Không có tin `actor=self` mới; nội dung không xuất hiện trong roster |
| Chẩn đoán | `ai_proactive_jobs` status/skip_reason; log `proactive_job_state` |
| Workflow | FS; AB để chụp |

### E2E-04 — Cấu hình lịch sáng/tối (P1)
| | |
| --- | --- |
| Tiền đề | Không có lịch |
| Dữ liệu | Adult và teen |
| Thao tác | Mở `/check-ins`; bật Nhịp sáng, chọn 07:30, Ngày thường; bật Rủ Rê tối 22:30 (adult) / thử 21:30 (teen); bật 5 khung; tạm dừng 3 ngày; xóa lịch |
| Kỳ vọng UI | "Đã lưu" sau mỗi thao tác; "Lần tới: 07:30 thứ Hai"; teen không có lựa chọn sau 21:00; khung thứ 5 bị chặn với câu cap; tạm dừng hiển thị ngày; dialog xóa |
| Kỳ vọng API | PUT với `expectedVersion` tăng dần; DELETE; lỗi đúng code |
| Khẳng định | Reload giữ trạng thái |
| Chẩn đoán | Response body lỗi |
| Workflow | F + FS |

### E2E-05 — Chỉ báo chưa đọc và đánh dấu đã đọc (P1)
| | |
| --- | --- |
| Tiền đề | 2 lượt giao chưa đọc (Nhịp 2 bubble, Rủ Rê 1 bubble) |
| Thao tác | Mở Nhịp; cuộn tới tin; quay lại |
| Kỳ vọng UI | Trước: badge 2; sau khi xem Nhịp: badge 1, chấm Nhịp mất; "Đánh dấu đã đọc tất cả" → 0 |
| Kỳ vọng API | `PUT /read` với `lastReadSequence` = sequence lớn nhất hiển thị; unread theo **run** (2 bubble = 1) |
| Khẳng định | Badge không bao giờ > số lượt giao |
| Chẩn đoán | Thứ tự request read/inbox |
| Workflow | F |

### E2E-06 — Reload và tiếp tục phiên (P1)
| | |
| --- | --- |
| Tiền đề | Run đang chạy có 3 bubble; lời hỏi thăm chưa đọc |
| Thao tác | Reload giữa stream; reload sau completed |
| Kỳ vọng UI | Giữa stream: nối lại events (`afterSeq`), cuối cùng 3 khối, không trùng; sau completed: 3 khối giữ thứ tự; badge vẫn đúng |
| Khẳng định | Không id tạm `-final` còn sót |
| Workflow | F + FS |

### E2E-07 — Đồng bộ nhiều tab (P1)
| | |
| --- | --- |
| Tiền đề | Hai tab cùng phiên, cả hai có badge 1 |
| Thao tác | Tab A mở tin |
| Kỳ vọng UI | Tab B badge về 0 trong ≤ 2 s (BroadcastChannel) hoặc ≤ 30 s (poll) |
| Khẳng định | BroadcastChannel message chỉ chứa `type/conversationId/sequence` |
| Workflow | F (Playwright 2 page cùng context) |

### E2E-08 — Bố cục mobile (P1)
| | |
| --- | --- |
| Tiền đề | 390×844 và 768×1024 |
| Thao tác | Roster → chat Nhịp → nút ← ; mở `/check-ins` |
| Kỳ vọng UI | Badge tab bar; chấm trên nút ← khi trợ lý khác có tin; trang lịch một cột; điều khiển ≥ 44 px; không tràn ngang |
| Khẳng định | `scrollWidth == innerWidth`; vùng chạm ≥ 44 px |
| Workflow | F + AB ảnh |

### E2E-09 — Back/forward (P1)
| | |
| --- | --- |
| Thao tác | Mục "Lời nhắn mới" → hội thoại → Back → Forward → `/check-ins#nhip` → Back |
| Kỳ vọng UI | URL và nội dung khớp; focus heading đúng; không mở lại stream cũ; read không bị gửi lại sai |
| Workflow | F |

### E2E-10 — Bàn phím và screen reader (P1)
| | |
| --- | --- |
| Thao tác | Chỉ dùng Tab/Shift+Tab/Enter/Space/Escape trên `/check-ins` và chat có nhóm bubble |
| Kỳ vọng | Công tắc đọc "Buổi sáng, bật/tắt"; `fieldset` "Lặp lại"; nhóm "Tin nhắn từ Nhịp, 2 phần"; nhãn "Lời hỏi thăm buổi sáng từ Nhịp lúc 07:30"; trạng thái lưu qua `role=status`; axe 0 vi phạm nghiêm trọng |
| Workflow | F + `@axe-core/playwright` |

### E2E-11 — Reduced motion (P1)
| | |
| --- | --- |
| Tiền đề | `emulateMedia({ reducedMotion: "reduce" })` / `set media light reduced-motion` |
| Kỳ vọng | Nhóm bubble và badge xuất hiện không transform/opacity animation (computed style ngay lập tức ở trạng thái cuối) |
| Workflow | F + AB |

### E2E-12 — Thu hồi consent nhật ký (P1)
| | |
| --- | --- |
| Tiền đề | Lời hỏi thăm Nhịp dẫn xuất nhật ký đã giao |
| Thao tác | Tắt "Dùng khoảnh khắc đã lưu hôm qua"; trả lời Nhịp "ok mình thử" |
| Kỳ vọng UI | Tin cũ vẫn hiển thị; câu trả lời mới không nhắc nội dung nhật ký |
| Kỳ vọng API | Input model của lượt mới **không** chứa tin proactive-journal (fake model ghi input); job Nhịp chưa chạy → `cancelled` |
| Workflow | FS |

### E2E-13 — Backend/provider timeout (P1)
| | |
| --- | --- |
| Dữ liệu | Fake model treo > timeout; lời hỏi thăm với provider lỗi |
| Kỳ vọng UI | Chat: thông báo `AI_TIMEOUT` hiện có, draft khôi phục theo quy tắc hiện tại; proactive: không có tin, không lỗi hiển thị cho người dùng |
| Kỳ vọng API | Job `retry` rồi `skipped(expired)` |
| Workflow | FS |

### E2E-14 — Job bị chạy trùng (P1)
| | |
| --- | --- |
| Thao tác | Gọi tick test hai lần song song (hai process FS nếu harness hai worker sẵn có) |
| Kỳ vọng | Đúng một lượt giao; badge 1 |
| Chẩn đoán | Đếm `ai_runs origin=proactive` |
| Workflow | FS |

### E2E-15 — Mất mạng (P1)
| | |
| --- | --- |
| Thao tác | `context.setOffline(true)` giữa stream; sau 5 s bật lại; offline khi lưu lịch |
| Kỳ vọng UI | Banner mất kết nối hiện có; sau khi online: reconcile, không gửi lại tự động; lưu lịch hiện lỗi trong thẻ và cho thử lại với cùng Idempotency-Key |
| Workflow | F |

### E2E-16 — Tài khoản/hội thoại hết hạn (P1)
| | |
| --- | --- |
| Dữ liệu | Hội thoại `expiresAt` quá khứ; tài khoản `deletion_pending`; phiên hết hạn |
| Kỳ vọng | Hội thoại hết hạn không có trong inbox; lời hỏi thăm mới tạo hội thoại mới; `deletion_pending` → không giao; phiên hết hạn → màn đăng nhập như hiện có |
| Workflow | FS |

### E2E-17 — Chỉ báo cộng tác trung thực (P2)
| | |
| --- | --- |
| Dữ liệu | Run Rủ Rê có receipt `completed` + một run có receipt `timeout` |
| Kỳ vọng UI | Run 1: dòng "Nhịp đã gợi ý… Rủ Rê đã dựa vào đó…" + "Vì sao?" mở sheet, Escape đóng, focus trả về; run 2: **không** dòng cộng tác |
| Khẳng định | DTO run 2 `collaboration = null` |
| Workflow | F + FS |

### E2E-18 — Trạng thái "đang hỏi" trực tiếp (P2)
| | |
| --- | --- |
| Dữ liệu | SSE v2: progress `{}`, progress `consulting nhip`, progress `composing`, final có `collaboration`, completed |
| Kỳ vọng UI | "Rủ Rê đang hỏi Nhịp một chút…" chỉ giữa `consulting` và `composing`; reduced motion tĩnh; mobile xuống dòng đúng |
| Workflow | F + AB |

### E2E-19 — Tắt quyền chia sẻ giữa lượt (P2)
| | |
| --- | --- |
| Thao tác | Tab A gửi tin cho Rủ Rê (specialist bị giữ); tab B tắt cạnh |
| Kỳ vọng | Tab A "Đã dừng phản hồi."; không dòng cộng tác; receipt `cancelled` |
| Workflow | FS |

### E2E-20 — Không có dữ liệu nhật ký (P1)
| | |
| --- | --- |
| Dữ liệu | Consent bật nhưng hôm qua không có entry saved (chỉ có draft) |
| Kỳ vọng UI | Lời hỏi thăm không nhắc "hôm qua", không có dòng "Bài viết đã tham khảo" |
| Kỳ vọng API | Payload `journal.status = "no_entries"`; không `ai_message_sources` |
| Workflow | FS |

## 5. Không được tuyên bố

Không ca nào ở §4 đã chạy. Baseline §2 chỉ chứng minh trạng thái UI **hiện tại** với dữ liệu stub; không chứng minh hành vi backend.
