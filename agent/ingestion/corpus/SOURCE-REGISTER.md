# SOURCE-REGISTER

## Follow-up official-source audit (2026-11-09)

The latest evidence and preserved original hashes are in [the legal audit](../legal/LEGAL-AUDIT-2026-11-09.md). [Human review](../legal/HUMAN-REVIEW-CHECKLIST.md) remains PENDING on every row.

- The legal-text reuse basis is now verified in a **primary** official source: Intellectual Property Law Article 15(2), consolidation 160/2026, PDF p14. Earlier secondary-only limitations below describe the historical audit.
- Official Child Law consolidation 108/2025 is readable and preserved. New revision `vn-luat-tre-em-vbhn108-2025` supports two authored cards. Scope is **under 16**, not every under-18 learner.
- Official TT06/2019 is preserved. TT03/2026 Article 15(2), visually checked at PDF p7, makes **Article 6 only** expire from 30 January 2026. New source `vn-tt-03-2026-bgddt` supports the current teacher-duty summary; the old excluded candidates remain unchanged.
- ND80 identity/original effective date are confirmed. Its complete current status remains unconfirmed in the official registry (403); a 4 November 2026 Government briefing about proposed amendments is corroboration, not a status certificate. The existing transcription still has no human proofreading.

Current registry: **15 candidates**, three `open_reuse`, one `authored`, four `reference_only`, seven `unverified`. Four usable sources still miss the target of six. Three substantive cards add six chunks; **57 documents / 80 chunks** still miss the 350-chunk target. No source was split to inflate the usable-source count. Old source records and historical corpus versions were retained.

## Earlier audit, retained as historical evidence

Ngày chấm: 2026-11-09. `unverified` không có khối acquire và không vào cơ sở dữ liệu. Bảng dưới chỉ ghi điều đã kiểm chứng; chỗ chưa kiểm chứng được ghi rõ là chưa.

## Văn bản đã dùng làm nguồn `open_reuse`

**Nghị định 80/2017/NĐ-CP** (Chính phủ, ban hành 17-07-2017, hiệu lực 05-09-2017 theo Điều 16 của chính văn bản).

- Bản chính thức: `https://datafiles.chinhphu.vn/cpp/files/vbpq/2017/07/80.signed.pdf`, SHA256 `cdede8a6aa3fec59064f795483f937d179d0d6f37d9acee6914fa9bf6937a8e4`, 8 trang ảnh quét, không có lớp chữ. Bản gốc được giữ nguyên trong `agent/ingestion/legal/original/`.
- Chữ trong `agent/ingestion/legal/nd-80-2017.md` được chép thủ công từng trang từ ảnh quét (Điều 1, 2, 5, 6, 13, 16), có ghi số trang. Đã đọc đủ 8 trang để biết các điều không chép. **Chưa có người đọc soát**; không dùng OCR tự động.
- Căn cứ tái sử dụng: Luật Sở hữu trí tuệ Điều 15 khoản 2 loại văn bản quy phạm pháp luật khỏi phạm vi bảo hộ quyền tác giả. Nội dung điều luật chỉ được xác nhận qua nguồn thứ cấp, chưa mở văn bản gốc của luật. Đây là lý do hạng `open_reuse` mới ở mức **xác minh một phần**.
- Hiệu lực hiện hành: trang chính thức `vanban.chinhphu.vn` (docid 190430) không nêu văn bản sửa đổi hay thay thế, và các nguồn thứ cấp ghi "còn hiệu lực"; **cơ sở dữ liệu chính thức không đọc được** (vbpl.vn, congbao.chinhphu.vn chỉ hiển thị bằng JavaScript). Tình trạng hiện hành chưa xác nhận.

## Bảng nguồn

| Nguồn | Hạng | Quyết định |
|---|---|---|
| vn-nd-80-2017 | open_reuse | Trích nguyên văn có số trang; hiệu lực hiện hành chưa xác nhận |
| mp-authored | authored | Thẻ tự viết; chưa thẩm định bởi chuyên gia bên ngoài |
| unicef-vn-cyberbullying | reference_only | Dẫn nguồn, không sao chép; **thẻ không còn tuyên bố đã đối chiếu** |
| who-youth-violence | reference_only | Fact sheet chưa đủ điều kiện nhúng |
| vn-111-hotline | reference_only | Chỉ sự kiện 111, 24/24, miễn phí cước (đọc 2026-11-08) |
| moet-portal | reference_only | Bản quyền bộ, không nhúng cẩm nang |
| vn-luat-tre-em-2016 | unverified | Văn bản hợp nhất 108/VBHN-VPQH (27-08-2025) chỉ thấy qua nguồn thứ cấp; không mở được chữ chính thức |
| vn-tt-06-2019-bgddt | unverified | Nguồn thứ cấp nói Điều 6 bị Thông tư 03/2026/TT-BGDĐT thay thế; chưa đọc được văn bản gốc |
| vn-tt-38-2019-bldtbxh | unverified | Tên đầy đủ và hiệu lực chưa xác minh |
| stopbullying-what-is, stopbullying-report-cyber | unverified | 403, chưa xác minh public domain |
| unesco-2019-behind-the-numbers | unverified | CC BY-SA chỉ thấy qua nguồn thứ cấp |
| platform-help-general | unverified | Điều khoản nền tảng chưa cho nhúng |

## Mục tiêu chưa đạt

- **Mục tiêu 6 nguồn `open_reuse`/được hậu thuẫn: chưa đạt.** Hiện có 1 nguồn `open_reuse` và 1 nguồn `authored`. Không chia một nguồn thành nhiều nguồn để đủ số.
- Luật Trẻ em 2016, Thông tư 06/2019 và Thông tư 38/2019 là các ứng viên tiếp theo, nhưng chỉ khi đọc được văn bản chính thức (bằng trình duyệt hoặc bản có lớp chữ). Việc này bị chặn bởi trang JavaScript và HTTP 403 trong phiên này.
- Số 113 và 115 xuất hiện trong thẻ khẩn cấp từ nguồn thứ cấp; chưa đối chiếu với văn bản chính thức. Khối khẩn cấp tĩnh của Companion vẫn là nguồn có thẩm quyền.

## Khoảng trống nội dung đã biết (cố ý để truy vấn `no_results`)

Mức xử phạt, tuổi chịu trách nhiệm pháp lý, quy chế riêng của từng trường, thủ tục chuyển trường, danh bạ địa phương, tư vấn y khoa/thuốc, luật nước ngoài. Thẻ pháp lý ghi rõ những điều này **không** nằm trong phần văn bản đã đọc.
