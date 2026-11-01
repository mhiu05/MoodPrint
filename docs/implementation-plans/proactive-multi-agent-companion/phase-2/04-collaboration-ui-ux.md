# Phase 2 — 04. UI/UX cộng tác

Tham chiếu ý tưởng: cách Grok trình bày nhiều agent cùng làm việc — **tham khảo khái niệm**, không sao chép giao diện. Ràng buộc: mọi trạng thái dựa trên bản ghi thực thi thật (SSE v2 `progress` + `ai_collaborations`), không hiển thị suy luận nội bộ, không biến cuộc trò chuyện thành log kỹ thuật, giữ [DESIGN.md](../../../../DESIGN.md) (không khung bubble cho trợ lý, trạng thái không bịa giai đoạn).

## 1. Các trạng thái

| # | Trạng thái | Nguồn sự thật | Hiển thị |
| --- | --- | --- | --- |
| S0 | Lượt bình thường (không phối hợp) | Không có event `consulting` | Như Phase 1 ("Đang trả lời…") |
| S1 | Trợ lý A bắt đầu nhờ B | SSE v2 `progress {"activity":"consulting","companion":"nhip"}` — với hội thoại đã lưu, event được dựng từ row `ai_collaborations(authorized)` đã commit ([05 §3](05-backend-and-database-contracts.md)) | Dòng trạng thái: avatar Nhịp nhỏ chồng avatar Rủ Rê + "Rủ Rê đang hỏi Nhịp một chút…" |
| S2 | B xong, A đang viết | SSE v2 `progress {"activity":"composing"}` | "Đang trả lời…" (như cũ) |
| S3 | Hoàn tất có phối hợp | `final.data.collaboration` ≠ null | Dòng cộng tác phía trên nhóm bubble + nút "Vì sao?" |
| S4 | B thất bại/timeout/bị từ chối | Không có `collaboration` trong final | Như S0 — **không** hiện lỗi phối hợp |
| S5 | Người dùng tắt quyền giữa lượt | Run bị hủy (`cancelled`) | "Đã dừng phản hồi." (Phase 1 hiện có) |
| S6 | Xem lại lịch sử | `AIMessage.collaboration` từ DB | Như S3, không animation |

Không có trạng thái "Nhịp đang suy nghĩ…", không có tiến độ phần trăm, không hiện nội dung B gửi A.

## 2. Bố cục

```text
  ┌─ Rủ Rê ───────────────────────────────────────────────────────┐
  │ (Nhịp)(Rủ Rê)  Nhịp đã gợi ý một hoạt động nhẹ nhàng. Rủ Rê đã  │  ← metadata, chat-muted
  │                dựa vào đó để chuẩn bị thử thách hôm nay. Vì sao? │
  │                                                                  │
  │ Sáng nay mình có một thử thách nhỏ, ngồi một chỗ cũng được:     │  ← bubble 1
  │ nhắm mắt và đếm xem nghe được mấy âm thanh khác nhau trong 2 phút.│
  │                                                                  │
  │ Đếm được bao nhiêu thì kể mình nghe nhé 👂                       │  ← bubble 2
  │ 07:31 · Sao chép                                                 │
  └──────────────────────────────────────────────────────────────────┘
```

- Dòng cộng tác dùng kiểu `metadata` (0,8125 rem), hai avatar 16 px (artwork hiện có), không nền, không viền.
- Trên mobile: avatar giữ, câu xuống dòng; "Vì sao?" là link ≥ 44 px chiều cao vùng chạm.
- Dòng cộng tác thuộc nhóm bubble (`role="group"`), đọc trước bubble đầu: "Nhịp đã gợi ý… Tin nhắn từ Rủ Rê, 2 phần".

## 3. Template câu cộng tác (backend render)

| Cạnh | Ngữ cảnh | Câu |
| --- | --- | --- |
| `nhip_energy_for_rure` | Lời hỏi thăm sáng (R2) | "Nhịp đã gợi ý mức năng lượng phù hợp với bạn. Rủ Rê đã dựa vào đó để chuẩn bị thử thách hôm nay." |
| `nhip_energy_for_rure` | Chat (R1) | "Nhịp đã gợi ý mức năng lượng phù hợp với bạn. Rủ Rê đã dựa vào đó để chọn hoạt động này." |
| `nhip_habit_for_may` | Chat (R3) | "Nhịp đã gợi ý một thói quen nhỏ. Mây đã dựa vào đó để trả lời bạn." |
| `rure_activity_for_guong` | Chat (R4) | "Rủ Rê đã gợi ý một hoạt động. Gương đã dựa vào đó để trả lời bạn." |

Template là hằng trong `backend/app/ai/collaboration/policy.py`; LLM không viết, không sửa. Prompt primary yêu cầu **không** tự nhắc tới trợ lý kia ("Nhịp bảo rằng…") để tránh hai nguồn mô tả cộng tác.

## 4. Sheet "Vì sao?"

`Dialog` hiện có (modal trên < 1100 px, popover modeless trên desktop theo mẫu `ConversationInfo`).

> **Vì sao Rủ Rê chọn thử thách này?**
> Bạn đã cho phép Nhịp chia sẻ **mức năng lượng** (thấp / vừa / cao) với Rủ Rê. Lần này Nhịp đọc khoảnh khắc đã lưu của bạn hôm qua và chỉ gửi cho Rủ Rê **mức năng lượng và thời lượng gợi ý**.
> Rủ Rê **không** thấy nhật ký, cảm xúc, yếu tố hay câu chữ của bạn.
> [Đổi cài đặt phối hợp]

Sheet chỉ nêu **loại** dữ liệu đã chia sẻ, không nêu giá trị cụ thể ("thấp, 5 phút"), vì receipt không lưu nội dung (tối thiểu hóa). Đây là mặc định đã chọn; hiển thị giá trị cụ thể đòi hỏi lưu thêm enum vào receipt — quyết định mở OD-10 ([94](../94-dependencies-risks-and-open-decisions.md)).

## 5. Trang cài đặt "Trợ lý phối hợp"

Route `/companion-sharing`, điểm vào từ Tài khoản và từ sheet "Vì sao?".

```text
Trợ lý phối hợp với nhau
Khi bạn cho phép, một trợ lý có thể nhờ trợ lý khác một việc nhỏ.
Chỉ những gì ghi dưới đây được chia sẻ. Mặc định đều tắt.

[□] Nhịp gợi ý mức năng lượng cho Rủ Rê
    Chia sẻ: mức năng lượng (thấp/vừa/cao), thời lượng gợi ý.
    Không chia sẻ: nhật ký, cảm xúc, yếu tố, tin nhắn của bạn.
    Cần bật "Dùng khoảnh khắc đã lưu hôm qua" ở Lịch hỏi thăm.   [Mở]

[□] Nhịp gợi ý thói quen nhỏ cho Mây
    Chia sẻ: loại nhu cầu bạn vừa kể (giấc ngủ, căng thẳng, tập trung, năng lượng).
    Không chia sẻ: câu chữ của bạn, nhật ký, ghi nhớ.

[□] Rủ Rê gợi ý hoạt động cho Gương
    Chia sẻ: một chủ đề sở thích (ví dụ: vẽ, âm nhạc) và thời lượng.
    Không chia sẻ: câu chữ của bạn, ghi nhớ.

Cầu Nối không nhận thông tin từ trợ lý khác.
```

Hành vi như trang lịch: lưu từng công tắc, `role="status"` xác nhận, lỗi trong thẻ. Cạnh 1 hiển thị `aria-disabled` + lý do nếu chưa bật journal context.

## 6. Thất bại và fallback

| Tình huống | UI |
| --- | --- |
| Specialist timeout | Không có dòng cộng tác; câu trả lời đơn |
| Specialist output sai | Như trên |
| Quyền bị tắt từ tab khác giữa lượt | Lượt kết thúc `cancelled` ("Đã dừng phản hồi."); không có nội dung phối hợp |
| Tải lại trang giữa S1 | `GET conversation` có `activeRunId` → nối lại SSE v2; danh sách event dựng từ DB ([05 §3](05-backend-and-database-contracts.md)) nên `consulting` được phát lại nếu bước nhờ còn đang chạy, hoặc `composing` nếu đã xong — trạng thái luôn khớp DB |
| Collaboration bị `discarded` (primary lỗi) | Lỗi chuẩn của lượt; không dòng cộng tác |

## 7. Accessibility và motion

- `progress` consulting cập nhật **dòng trạng thái hiện có** (`role="status"`, `aria-atomic`) — không tạo live region mới, không đọc hai lần.
- Hai avatar `aria-hidden`; tên trợ lý có trong câu.
- Motion: avatar specialist trượt vào 4 px/160 ms như entrance trạng thái hiện có; reduced motion → tĩnh. Không animation nối dây, không hiệu ứng "đang trao đổi".

## 8. Không làm

- Không hiển thị "agent", "tool", "handoff", "delegation", "run", tên model.
- Không hiển thị chuỗi suy luận, input/output của specialist, digest.
- Không tạo cảm giác các trợ lý "nói chuyện riêng" về người dùng (không dùng "Nhịp và Rủ Rê đã bàn về bạn").

## 9. Ghi chú triển khai

- Template R2 đổi thành "Nhịp đã gợi ý mức năng lượng phù hợp với bạn. Rủ Rê đã dựa vào đó để chuẩn bị thử thách hôm nay." (review độc lập: câu cũ sai khi mức năng lượng cao).
- Dòng trạng thái "A đang hỏi B một chút…" chỉ có chữ, không có avatar chồng (D-08); avatar có ở dòng cộng tác.
- Nút "Vì sao?": hộp ôm chữ để viền focus không đè dòng trên; vùng chạm 44 px bằng `::before` (lỗi tìm thấy bằng agent-browser ở 360 px).
