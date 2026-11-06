# 09 — UX và luồng người dùng

Đủ để dựng UI mà không phải tự thiết kế. Task ở [WS-09](plans/WS-09-frontend-integration.md).

## 1. Hướng hình ảnh và quy trình impeccable

Bỏ trải nghiệm nhiều bot là đã chốt. Giao diện được đầu tư như một bản release thật. Owner yêu cầu đi theo [impeccable](https://github.com/pbakaus/impeccable). Kỹ năng đã có trong repo tại `.agents/skills/impeccable` (phiên bản 4.7.0), kèm CLI phát hiện lỗi thiết kế bằng 62 rule xác định, không cần LLM.

**Quy trình bắt buộc**

| Bước | Lệnh | Kết quả |
| --- | --- | --- |
| 1 | `init` | Viết lại `PRODUCT.md` cho sản phẩm mới, giữ dòng "không tự ý sửa .gitignore" |
| 2 | `shape <surface>` | Brief trong `.impeccable/surfaces/<surface>.md`, trước khi code |
| 3 | Build, đọc `reference/craft-floor.md` trước mỗi lần sửa UI | Code |
| 4 | `critique`, `audit` | Điểm UX, danh sách P0–P3 |
| 5 | `harden`, `onboard`, `clarify`, `adapt` | Lỗi, lần đầu, copy, cỡ màn hình |
| 6 | `polish` | Lượt cuối |
| 7 | `document` | `DESIGN.md` mô tả đúng thứ đã dựng |

Cổng tự động, chạy với `DO_NOT_TRACK=1`: `npx impeccable detect frontend/src/features/school --json` và quét URL đang chạy cho các rule cần render. Exit 2 là còn lỗi.

**Mode theo surface**

| Surface | Mode | Hệ quả |
| --- | --- | --- |
| Trang giới thiệu | Persuade | Có quan điểm rõ, một khoảnh khắc được đầu tư |
| Trò chuyện, Hồ sơ, Luyện nói, Cài đặt | Operate | Chính xác, tiết chế, không biểu diễn |
| Tìm hỗ trợ, thẻ nguồn, Giới hạn của AI | Read | Dễ đọc trước hết |

**Brief khởi đầu: "Góc yên"**. Sổ tay yên tĩnh, ấm, ít viền. Dùng `tokens.css`: nền `--color-bg` #f8f9f6, nhấn `--color-primary` #285c4b. `--color-danger` #9c352c chỉ dành cho khẩn cấp và là màu mạnh duy nhất. Lỗi thường dùng `--color-warning`. Biểu tượng Trợ lý là hình tròn trung tính, không có mặt, không nhân vật.

**Quy tắc từ craft floor áp vào đây**

- Không eyebrow phía trên tiêu đề. Không đánh số mục trang trí.
- Không lấy lưới thẻ cùng cỡ làm cấu trúc trang. Không lồng thẻ trong thẻ.
- Không viền màu dày một bên cho cảnh báo. `EmergencyCard` dùng viền đều hoặc nền.
- Không chữ gradient, không glass trang trí, không emoji thay icon. Icon `lucide-react`, cùng nét.
- Thẻ bo 12–16px. Chọn viền hoặc bóng, không cả hai.
- Cỡ đo đọc 65–75 ký tự. Tiêu đề chênh rõ về cỡ và độ đậm.
- Mã SHA-256 dùng font mono và chữ số đều cỡ, vì là dữ liệu.
- Chăm cả phần trình duyệt: focus ring, vùng chọn, caret, thanh cuộn.

**Phông chữ**: craft floor coi font hệ thống làm giọng hiển thị là thiếu quyết định, và CSP cho phép `font-src 'self'`. Đề xuất tự host **Be Vietnam Pro** dạng woff2 trong `frontend/public/fonts/`, vì được thiết kế cho tiếng Việt. Kèm file giấy phép; TO_VERIFY giấy phép OFL khi tải. Giữ `font-display: swap`, font hệ thống là dự phòng.

**Sáng tối**: chọn từ bối cảnh dùng, không theo thói quen. Học sinh thường dùng lúc kín đáo, có thể buổi tối. Sáng là mặc định; tối theo `prefers-color-scheme` là P2, được quyết định ở bước `shape`.

CSS phạm vi `.school-app` trong `frontend/src/features/school/school.css`. Dùng `tokens.css`, `Button`, `Dialog`, `StatePanel`, `ErrorNotice`, `useMotionPolicy`. Không dùng `real.css`, `agent-chat.css`.

Wireframe bên dưới mô tả bố cục và nội dung, không phải hình ảnh cuối.

## 2. Sitemap

```text
Public (không cần đăng nhập, đường dẫn thật)
  /                 Trang giới thiệu: Dùng thử ngay, Xem tình huống mẫu
  /vi-du            Tình huống mẫu để đọc và thử
  /login            Đăng nhập tài khoản mẫu
  /ho-tro           Tìm hỗ trợ
  /trung-tinh       Trang trung tính cho thoát nhanh

App (HashRouter, cần phiên)
  #/dieu-khoan      Điều khoản lần đầu
  #/tro-chuyen      Trò chuyện
  #/ho-so           Danh sách hồ sơ (cần PIN nếu đã đặt)
  #/ho-so/:caseId   Dòng thời gian
  #/ho-so/:caseId/su-viec/:eventId   Chi tiết, lịch sử phiên bản
  #/ho-so/:caseId/xuat               Xem trước và xuất PDF
  #/luyen-noi       Chọn chế độ
  #/luyen-noi/:sessionId             Phòng luyện nói
  #/ho-tro          Tìm hỗ trợ
  #/ho-tro/nen-tang/:platform        Hướng dẫn báo cáo
  #/nguoi-lon       Bảng người lớn tin cậy
  #/ke-hoach        Kế hoạch an toàn
  #/cai-dat         Cài đặt, giới hạn của AI, xóa dữ liệu
```

`classifyEntry` cần nhận thêm `/vi-du`, `/ho-tro`, `/trung-tinh`. Shell chọn theo `appProfile` từ `GET /public/experience`.

## 3. Khung ứng dụng

Mobile 360×800:

```text
┌────────────────────────────────┐
│ MoodPrint       [Thoát] [Khẩn] │  ← luôn hiện, ≥ 44px
├────────────────────────────────┤
│                                │
│        Nội dung màn hình       │
│                                │
├────────────────────────────────┤
│ Trò chuyện  Hồ sơ  Luyện  Hỗ trợ│  ← 4 tab, có nhãn chữ
└────────────────────────────────┘
```

Từ 768px trở lên: rail bên trái, khẩn cấp và thoát nhanh ở đầu rail. Kiểm tra ở 360, 390, 768, 1280.

**Nút Khẩn cấp** mở `EmergencySheet`, hoạt động không cần mạng, không cần đăng nhập:

```text
┌────────────────────────────────┐
│ Bây giờ em có an toàn không?   │
│ ┌────────────────────────────┐ │
│ │ 111  Bảo vệ trẻ em         │ │  tel:111
│ ├────────────────────────────┤ │
│ │ 113  Công an               │ │  tel:113
│ ├────────────────────────────┤ │
│ │ 115  Cấp cứu               │ │  tel:115
│ └────────────────────────────┘ │
│ Trên máy tính: hãy dùng điện   │
│ thoại gọi số này.              │
│ [Về thẻ tóm tắt của em]  [Đóng]│
└────────────────────────────────┘
```

**Nút Thoát nhanh**: một chạm, không hỏi lại. Xóa `resourceCache`, draft trong RAM, `sessionStorage`, rồi `location.replace("/trung-tinh")`. Phím Esc ba lần liên tiếp cũng kích hoạt trên desktop. Trang trung tính hiển thị nội dung ôn tập chung, có tiêu đề tab trung tính. Lần vào lại cần PIN nếu đã đặt.

**Tên trung tính**: cài đặt đổi `document.title` thành "Sổ tay" và icon tab trung tính. Không có thông báo đẩy trong MVP; nếu thêm sau, nội dung phải trung tính.

## 4. Lần dùng đầu

```text
┌────────────────────────────────┐
│ Trước khi bắt đầu              │
│ Em thuộc nhóm nào?             │
│ ( ) 11–14 tuổi  ( ) 15–17 tuổi │
│                                │
│ • Đây là AI, không phải người. │
│ • Dữ liệu lưu trên máy chủ của │
│   ứng dụng. Chỉ em xem được.   │
│ • Ứng dụng không tự báo cho ai.│
│ • Thông tin AI chỉ để tham khảo│
│ • Nếu nguy hiểm, gọi 111/113/  │
│   115.                         │
│ [ ] Em đã đọc và đồng ý        │
│          [Bắt đầu]             │
└────────────────────────────────┘
```

Màn này chỉ dành cho tài khoản mẫu. Lưu `terms_version`, thời điểm.

**Khách** không qua màn này. Bấm "Dùng thử ngay" là vào Trò chuyện, không hỏi tuổi, không thấy CAPTCHA. Nhóm tuổi mặc định `11-14`, đổi ở Cài đặt. Một thông báo gọn, không chặn, đóng được:

```text
Đây là AI, không phải người. Dữ liệu tự xóa sau 2 giờ.
Bản trải nghiệm: hãy dùng tình huống mẫu, đừng nhập thông tin thật.
Nếu đang nguy hiểm, bấm Khẩn cấp.
```

## 5. Trò chuyện

```text
┌────────────────────────────────┐
│ ○ Trợ lý · AI, không phải người│
├────────────────────────────────┤
│ Chào em, có chuyện gì em muốn  │
│ kể không?                      │
│ [Kể chuyện đang xảy ra]        │
│ [Em thấy bạn bị bắt nạt]       │
│ [Chuẩn bị nói với người lớn]   │
│                                │
│        Tụi nó lập nhóm nói xấu │
│                                │
│ Mình hiểu rồi... [1]           │
│ ⓘ Thông tin do AI tổng hợp...  │
│ ┌ Lưu vào hồ sơ? ────────────┐ │
│ │ "Lập nhóm chat nói xấu..." │ │
│ │ [Xem và sửa] [Lưu] [Bỏ]    │ │
│ └────────────────────────────┘ │
├────────────────────────────────┤
│ Nhập tin nhắn...      [Mic] [↑] │
└────────────────────────────────┘
```

| Thành phần | Hành vi |
| --- | --- |
| Citation `[1]` | Dùng lại `CitationText`; mở sheet thẻ nguồn gồm tiêu đề, nơi phát hành, ngày kiểm tra, link |
| Nhãn tham khảo | Hiện khi `sourceMarked`; câu cố định; không ẩn được |
| Tool đang chạy | Trạng thái thân thiện: "Đang tìm thông tin đã kiểm duyệt", "Đang chuẩn bị bản nháp". Không lộ tên tool |
| Proposal card | Hiện đúng nội dung sẽ lưu; Sửa, Lưu, Bỏ; lưu xong hiện biên nhận từ server |
| `EmergencyCard` | Toàn chiều rộng, viền `--color-danger`, nút 111/113/115, nút "Em đã ổn" và "Em đã gọi" |
| Nhắc nghỉ | Câu xác định sau 20 lượt hoặc 30 phút |
| Giới hạn | Bộ đếm khi còn 50 ký tự trong 500 |
| Dừng | Giữ hành vi: yêu cầu dừng, chờ kết quả cuối |

## 6. Hồ sơ

**Danh sách**: thẻ case gồm tiêu đề, số sự việc, cập nhật gần nhất. Nút "Thêm hồ sơ".

**Dòng thời gian**

```text
┌────────────────────────────────┐
│ ← Sự việc của em       [Xuất]  │
│ Lời nói · Trên mạng · Lặp lại  │
│ [+ Thêm sự việc]               │
│ ──●── Khoảng đầu tuần trước    │
│   │  Nhóm chat lớp bị đổi tên..│
│   │  Ảnh: 2 ảnh · Em kể          │
│ ──●── 12/10 (không rõ giờ)     │
│   │  ...                       │
└────────────────────────────────┘
```

**Thêm bằng chứng**: chọn ảnh hoặc video → tải lên có tiến trình → hiện kết quả. Không có bước hỏi về nội dung. Dưới nút chọn file có một dòng cố định, không chặn:

```text
Nếu nội dung liên quan tới hình ảnh tình dục của trẻ em,
đừng lưu hay gửi đi. Hãy gọi 111.
```

**Thông tin file**

```text
Đã lưu lúc 14:32, 06/11/2026 (giờ máy chủ)
Mã kiểm tra SHA-256: 9f2c…a1e0  [Xem đầy đủ]
Mã này cho thấy file không đổi kể từ lúc tải lên.
Nó không chứng minh chuyện đã xảy ra.
```

**Lịch sử phiên bản**: danh sách bản ghi, bản gốc đánh dấu "Bản đầu tiên". Sửa tạo bản mới.

**Xem trước PDF**: ba phần có nhãn rõ: "Em kể", "File em tải lên", "AI diễn giải (bản nháp đã được em xem)". Chọn phần muốn xuất. Tải về là hành động của em.

**PIN**: tùy chọn, đặt ở Cài đặt. 4–6 chữ số. 5 lần sai khóa 5 phút. Quên PIN: nhập lại mật khẩu.

## 7. Luyện nói

```text
┌────────────────────────────────┐
│ ← Nói với người lớn   Lượt 3/20│
│ Vai luyện tập do AI đóng       │
├────────────────────────────────┤
│ AI: Con muốn nói với cô chuyện │
│ gì?              [▶ Phát]      │
│ Giọng đọc do AI tạo            │
│                                │
│ Em: [bản chép lời sửa được]    │
│                                │
│        ▁▃▅▇▅▃▁                 │
│     ┌──────────────┐           │
│     │ Giữ để nói   │           │
│     └──────────────┘           │
│ [Nhập chữ]  [Dừng]  [Kết thúc] │
└────────────────────────────────┘
```

Giữ để nói bằng pointer và phím Space. Thả là dừng. Bộ đếm 30 giây. Với người dùng không giữ được: chế độ "chạm để bắt đầu, chạm để dừng" trong cài đặt. Sóng âm tắt khi `prefers-reduced-motion`.

## 8. Tìm hỗ trợ

Đọc được không cần đăng nhập, không cần API. Nội dung nằm trong bundle.

```text
┌────────────────────────────────┐
│ Tìm hỗ trợ                     │
│ [111 Bảo vệ trẻ em · 24/24] │
│ [113 Công an]               │
│ [115 Cấp cứu]               │
│ Tổ tư vấn của trường           │
│  Hỏi thầy cô chủ nhiệm...      │
│ Báo cáo trên mạng              │
│  Facebook · YouTube · TikTok   │
└────────────────────────────────┘
```

Hướng dẫn nền tảng cần đăng nhập mới đọc qua API; bản public dùng `cards.json` rút gọn do `scripts/kb/build.py` sinh ra.

## 9. Luồng ba kịch bản

```mermaid
flowchart LR
    subgraph KBA[KB-A Group anti]
      A1[Kể chuyện] --> A2[WF-01] --> A3[WF-02 lưu ảnh] --> A4[Báo cáo nền tảng] --> A5[Người lớn tin cậy] --> A6[Luyện nói] --> A7[Soạn tin]
    end
    subgraph KBB[KB-B Chặn đường]
      B1[Kể chuyện] --> B2[Câu về dao] --> B3[WF-06 template] --> B4[Em đã ổn] --> B5[WF-03 kế hoạch]
    end
    subgraph KBC[KB-C Chứng kiến]
      C1[Em thấy bạn bị đánh] --> C2[WF-05] --> C3[Không phát tán clip] --> C4[Báo thầy cô] --> C5[Luyện nói]
    end
```

Kịch bản chi tiết ở [demo/scenarios-KB-A-B-C.md](demo/scenarios-KB-A-B-C.md).

## 10. Copy mẫu

Xưng hô: 11–14 "mình – em"; 15–17 "mình – bạn". Câu ngắn. Không dùng từ chuyên môn. **Mọi template khẩn cấp là bản nháp, cần người có chuyên môn duyệt.**

| Tình huống | 11–14 | 15–17 |
| --- | --- | --- |
| Chào | Chào em. Mình là Trợ lý, một AI. Em muốn kể gì cũng được, không kể cũng không sao. | Chào bạn. Mình là Trợ lý, một AI. Bạn muốn bắt đầu từ đâu cũng được. |
| Giới hạn | Mình là AI nên có thể sai. Những chuyện quan trọng, em nên nói với một người lớn em tin. | Mình là AI nên có thể sai. Việc quan trọng nên có một người lớn bạn tin đồng hành. |
| Xác nhận lưu | Em xem lại nhé. Bấm Lưu thì nội dung này mới vào hồ sơ. | Xem lại giúp mình. Chỉ khi bạn bấm Lưu thì nội dung mới vào hồ sơ. |
| Đã lưu | Đã lưu vào hồ sơ của em. | Đã lưu vào hồ sơ của bạn. |
| Lỗi mạng | Mất kết nối rồi. Tin của em vẫn còn ở đây, em thử lại nhé. | Mất kết nối. Tin của bạn vẫn còn, thử gửi lại nhé. |
| AI bận | Mình đang chưa trả lời được. Nếu đang nguy hiểm, em bấm nút Khẩn cấp. | Mình đang chưa trả lời được. Nếu đang nguy hiểm, bấm nút Khẩn cấp. |
| Hết lượt | Hôm nay em đã dùng hết lượt trò chuyện. Nút Tìm hỗ trợ vẫn dùng được. | Hôm nay đã hết lượt trò chuyện. Tìm hỗ trợ vẫn dùng được. |
| Nhãn tham khảo | Thông tin do AI tổng hợp để tham khảo. Hãy xác minh lại với văn bản luật, thầy cô hoặc Tổng đài 111. | Giống bên trái, không đổi một chữ. |
| Chưa chắc | Mình chưa chắc, em có thể hỏi thầy cô, tổ tư vấn hoặc 111. | Mình chưa chắc, bạn có thể hỏi thầy cô, tổ tư vấn hoặc 111. |
| Nhắc nghỉ | Mình nói chuyện cũng lâu rồi. Em nghỉ một chút nhé, hoặc kể với một người em tin. | Mình nói chuyện khá lâu rồi. Nghỉ một chút, hoặc kể với một người bạn tin nhé. |

**Template khẩn cấp (nháp)**

| Nhóm | 11–14 | 15–17 |
| --- | --- | --- |
| `violence` | Điều em kể nghe nguy hiểm. Nếu em đang không an toàn, hãy đến chỗ có đông người và gọi ngay người lớn gần em. Em có thể gọi 113 (công an), 115 (cấp cứu), hoặc 111 (bảo vệ trẻ em, 24/24, miễn phí). | Điều bạn kể nghe nguy hiểm. Nếu lúc này chưa an toàn, hãy tới nơi đông người, báo người lớn ở gần. Bạn có thể gọi 113, 115 hoặc 111 (bảo vệ trẻ em, 24/24, miễn phí). |
| `sexual` | Chuyện em kể không phải lỗi của em. Em nên nói với một người lớn em tin, hoặc gọi 111. Đừng gửi hay lưu ảnh đó, vì điều này có thể gây thêm hại. Nếu đang nguy hiểm, gọi 113. | Chuyện này không phải lỗi của bạn. Hãy nói với một người lớn bạn tin hoặc gọi 111. Đừng gửi đi hay tự lưu ảnh. Nếu đang nguy hiểm, gọi 113. |
| `self_harm` | Mình rất lo cho em. Em hãy đến cạnh một người lớn ngay bây giờ và nói với họ. Em có thể gọi 111, hoặc 115 nếu em đã bị đau. Em không phải chịu một mình. | Mình lo cho bạn. Hãy ở cạnh một người lớn ngay lúc này và nói với họ. Bạn có thể gọi 111, hoặc 115 nếu đã bị thương. Bạn không phải chịu một mình. |
| `extortion` | Bị đòi tiền hay bị ép là không ổn. Em không cần tự giải quyết một mình. Hãy nói với người lớn em tin. Nếu họ dọa đánh, gọi 113. | Bị đòi tiền hay ép buộc là không ổn. Đừng tự xử lý một mình. Nói với người lớn bạn tin; nếu bị đe dọa, gọi 113. |

## 11. Trạng thái màn hình

Mọi màn hình chính phải có đủ:

| Trạng thái | Cách hiện |
| --- | --- |
| Loading | Skeleton hoặc `StatePanel`; `aria-busy` |
| Streaming | Chờ `final`; `AIActivityStatus`-style polite status |
| Empty | Một câu giải thích + một hành động |
| Error | `ErrorNotice`, nút thử lại, giữ dữ liệu đã nhập |
| Offline | `OfflineBanner`; khẩn cấp vẫn dùng được |
| Timeout | Nói rõ, cho thử lại |
| Permission denied | Micro: hướng dẫn cấp quyền, chuyển nhập chữ |
| Hết quota | Câu "Hết lượt", Tìm hỗ trợ vẫn mở |
| PIN khóa | Màn nhập PIN, không lộ tiêu đề case |

## 12. Accessibility

Mục tiêu WCAG 2.2 AA.

- Tương phản ≥ 4,5:1, thành phần UI ≥ 3:1.
- Mục tiêu chạm ≥ 44px (`--target-min`).
- Focus nhìn thấy, không bị che (2.4.11), thứ tự hợp lý, dùng `useRouteFocus`.
- Vùng cuộn có thể dùng bàn phím: `tabIndex={0}` và `aria-label` cho log hội thoại. Đây chính là lỗi đang làm CI đỏ ở `GroupChat`.
- Log hội thoại: live region lịch sự, không đọc hai lần.
- `EmergencyCard` được thông báo `role="alert"`.
- Thay thế kéo-thả và giữ-để-nói bằng thao tác đơn (2.5.1, 2.5.7).
- Cỡ chữ tới 200% không tràn ngang.
- Reduced motion qua `useMotionPolicy`.

Axe chạy trên mọi route trong Playwright. Checklist thủ công ở [10](10-evaluation-and-quality-gates.md).

## 13. Giao diện thinking

Dùng [thinking-orbs](https://github.com/Jakubantalik/thinking-orbs) 0.3.2, đã có trong `package.json`, canvas 2D, MIT. Mẫu hiện có: `AIActivityStatus.tsx` tải lười, `OrbBoundary` rơi về icon tĩnh, chữ nằm trong live region riêng.

Backend phát giai đoạn thật ([06 §13](06-ai-orchestration-and-safety.md#13-trạng-thái-thinking)). Frontend ánh xạ:

| Giai đoạn | `state` | `size` | Nhãn 15–17 |
| --- | --- | --- | --- |
| `reading` | `working` | 20 | Đang đọc tin của bạn |
| `composing` | `composing` | 20 | Đang nghĩ cách trả lời |
| `searching` | `searching` | 20 | Đang tìm thông tin đã kiểm duyệt |
| `drafting` | `shaping` | 20 | Đang chuẩn bị bản nháp |
| `checking` | `solving` | 20 | Đang kiểm tra lại nguồn |
| Đang thu âm | `listening` | 64 | Đang nghe |
| Đang tạo giọng đọc | `weaving` | 20 | Đang tạo giọng đọc |
| Chờ kết nối quá 5 giây | `connecting` | 20 | Kết nối hơi chậm |

Chỉ dùng hai preset 20 và 64, không scale CSS.

**Quy tắc**

- Không bịa giai đoạn. Không có sự kiện thì giữ nhãn hiện tại.
- Mỗi màn hình tối đa một orb.
- Canvas `aria-hidden`. Thông tin nằm ở chữ, `role="status"`, `aria-live="polite"`.
- `useMotionPolicy.animate` sai thì dùng icon tĩnh. Thư viện cũng tự hiển thị khung tĩnh khi reduced motion.
- Orb biến mất ngay khi có kết quả. Không giữ lại để cho đẹp, không làm chậm nội dung.
- **Không có orb trong luồng khẩn cấp.** Template hiện ngay.
- `theme`: `light`, hoặc `auto` nếu làm giao diện tối.
- Không dùng `breathing` như lời hứa trấn an hay bài tập thở.

Tạo `features/school/chat/ThinkingStatus.tsx` theo mẫu `AIActivityStatus`, không sửa file cũ.

## 14. Chuyển động

Dùng [GSAP](https://github.com/greensock/gsap) 3.15 và `useGSAP` từ `@gsap/react`, đã có trong dự án. GSAP hiện miễn phí kể cả plugin. Mẫu chuẩn trong repo: `useGSAP` với `scope` và `revertOnUpdate`, `gsap.matchMedia()` cho `prefers-reduced-motion: no-preference`, `useMotionPolicy` để dừng khi tab ẩn, `clearProps` sau khi xong.

Theo `reference/animate.md`, ở Operate và Read chuyển động phục vụ phản hồi, trạng thái, tính liên tục; không có vũ đạo lúc tải trang.

**Luận điểm chuyển động**

| Mục | Quyết định |
| --- | --- |
| Khoảnh khắc chính | **Niêm phong bằng chứng**: tải xong, thanh tiến trình thu lại thành dấu niêm phong, mã SHA-256 hiện ra. Khoảng 600 ms. Mỗi file một lần |
| Trang giới thiệu | Một chuỗi duy nhất: một tin nhắn đi tới một người lớn thật. Không lặp hiệu ứng theo từng mục |
| Liên tục | Proposal đã lưu thu lại thành dòng biên nhận (GSAP Flip). Sheet khẩn cấp trượt từ dưới lên |
| Phản hồi | Nút 100 ms. Giữ để nói: nút thu nhẹ, vòng theo âm lượng thật |
| Ngân sách | `transform`, `opacity`, `clip-path`. Một vòng lặp cho sóng âm. Không ScrollTrigger, không stagger khi tải |

**Thông số**, lấy từ `tokens.css`:

| Loại | Thời lượng | Ease |
| --- | --- | --- |
| Phản hồi nút | `--duration-feedback` 100 ms | `--ease-state` |
| Tin nhắn mới | `--duration-state` 160 ms, dịch tối đa 4 px | `power2.out` |
| Đổi tab | 120 ms, chỉ opacity | `power2.out` |
| Sheet, dialog | `--duration-overlay` 220 ms | `expo.out` |
| Niêm phong | 600 ms | `expo.out` |

**Quy tắc**

- Nội dung render trước, chuyển động theo sau. Không bao giờ chờ animation.
- **Khẩn cấp không chờ**: `EmergencyCard`, `EmergencySheet` có DOM và focus ngay; `role="alert"` phát ngay; chuyển động chỉ là lớp phủ, tắt được.
- Không animate chiều cao transcript, không theo từng token, không auto-scroll bằng timeline.
- Reduced motion: thay bằng đổi trạng thái tức thời hoặc 80 ms (`--duration-reduced`). Niêm phong vẫn hiện kết quả.
- Mỗi hiệu ứng dọn dẹp qua `useGSAP`, không để timeline sống sau unmount.
- Mở rộng `tests/e2e/motion.spec.ts` cho shell mới.

Viết `features/school/motion.ts` gom các hàm hiệu ứng.

## 15. Tình huống mẫu

Theo [OD-01](12-open-decisions.md#od-01--staging-là-bản-release-thật), các kịch bản là ví dụ để khách đọc và thử. Trang `/vi-du` công khai, nội dung tĩnh trong bundle, mode Read.

```text
┌────────────────────────────────┐
│ Tình huống mẫu                 │
│ Mọi nhân vật đều là hư cấu.    │
│                                │
│ Bị lập nhóm nói xấu            │
│ Minh An, lớp 7. Xem cách Trợ   │
│ lý giúp em lưu lại và nói với  │
│ cô chủ nhiệm.                  │
│ [Đọc] [Thử tình huống này]     │
│ ─────────────────────────────  │
│ Bị chặn đường đòi tiền         │
│ ...                            │
└────────────────────────────────┘
```

Mỗi tình huống gồm phần đọc (chuyện gì xảy ra, Trợ lý làm gì, vì sao) và nút thử. Bấm thử: tạo phiên khách nếu chưa có, điền sẵn câu mở đầu vào ô nhập, **chờ người dùng bấm gửi**. Với tình huống có hồ sơ, tạo sẵn hồ sơ mẫu trong tài khoản khách, tự xóa sau 2 giờ.

Tình huống có nội dung nhạy cảm chỉ ở mức không mô tả. Không lưới thẻ cùng cỡ: danh sách đọc có nhịp, theo craft floor.

