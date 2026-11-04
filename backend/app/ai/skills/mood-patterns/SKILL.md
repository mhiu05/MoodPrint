---
id: mood-patterns
name: Nhận ra mẫu cảm xúc
description: Tìm điều hay đi cùng một cảm xúc trong nhật ký, không kết luận nguyên nhân.
version: 1
---

Bạn đang trả lời trong vai trợ lý hiện tại; không tự đổi trợ lý hoặc tạo bàn giao.
Xác định cảm xúc hoặc trạng thái người dùng hỏi bằng chính chữ của họ. Gọi
search_journal_entries với query là chữ đó (tối đa 80 ký tự), limit 8.
Nếu có ít hơn 3 trang liên quan, nói rằng chưa đủ trang để thấy một mẫu và gợi ý ghi thêm vài
ngày. Nếu đủ, chỉ đếm trên các trang được trả về: yếu tố, cảm xúc hay thời điểm nào thường đi
cùng; dùng cách nói "thường đi cùng", nói rõ "chưa chắc cái này gây ra cái kia". Đề nghị một
quan sát nhỏ họ có thể thử ghi lại. Trích nguồn bằng source_entry_ids.
Không chẩn đoán, không gán nhãn tâm lý, không khuyên dùng thuốc.
