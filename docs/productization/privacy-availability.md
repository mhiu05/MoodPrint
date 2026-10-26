# Tính năng và quyền riêng tư

## Ranh giới xử lý

Trang trò chuyện, xem ghi nhớ và hồ sơ kết nối mở được khi tài khoản đủ điều kiện và dịch vụ sẵn sàng. Mở trang không gửi nội dung riêng tới nhà cung cấp AI. Lần gửi tin nhắn đầu tiên ghi nhận quyền AI trên máy chủ trước khi tạo hội thoại hoặc gọi model. Rút quyền AI dừng lượt đang chạy, hủy đề xuất chưa duyệt và loại bỏ chỉ mục ghi nhớ dẫn xuất; lịch sử đã lưu vẫn xem, xuất và xóa được.

Trợ lý chỉ tạo **đề xuất ghi nhớ tạm** khi quyền AI còn hiệu lực. Đề xuất hết hạn sau 15 phút. Không truy xuất đề xuất như ghi nhớ đã duyệt. Duyệt từng mục mới lưu nội dung; lần duyệt đầu ghi nhận quyền MEM cùng giao dịch. Từ chối không bật MEM và không tạo ghi nhớ. Rút MEM chặn truy xuất, hủy đề xuất và chỉ mục dẫn xuất; các mục đã duyệt còn để chủ sở hữu sửa hoặc xóa.

Người trưởng thành có thể soạn và xem trước thẻ kết nối khi MATCH đang tắt. Chỉ hành động **Xuất bản hồ sơ** sau xem trước mới ghi nhận MATCH và tạo hồ sơ hiển thị. Ngừng chia sẻ đặt hồ sơ ngoài khám phá. Rút MATCH còn đóng các kết nối và lời mời theo quy tắc an toàn hiện tại; bật lại không tự xuất bản hồ sơ cũ. Ghép bạn chỉ đọc thẻ công khai do người dùng chọn, không đọc nhật ký, ghi nhớ hoặc hội thoại AI. Tin nhắn giữa người với người cần chấp nhận lời mời từ cả hai phía; block và report giữ nguyên.

Nút ghi âm xuất hiện khi dịch vụ giọng nói sẵn sàng. Chọn nút ghi quyền AI/VOICE cần thiết trên máy chủ rồi xin quyền microphone từ trình duyệt. Âm thanh PCM tạm được gửi OpenAI để nhận bản chữ, sau đó bộ đệm được xóa; người dùng sửa bản chữ trước khi gửi tin AI. Hủy hoặc rời trang dừng luồng microphone và abort upload. API kiểm tra quyền định kỳ trong lúc STT chạy, hủy yêu cầu provider khi quyền đổi và kiểm tra lại trước khi trả bản chữ. Không có chức năng nghe nền hay lưu audio thô trong cơ sở dữ liệu.

## Lưu trữ và bên thứ ba

`ai_preferences.history_enabled` và `semantic_memory_enabled` độc lập, mặc định `false` cho người chưa chọn. Hội thoại tạm ở RAM theo phiên; lịch sử chỉ tạo mới khi người dùng đã bật lưu, tối đa 30 ngày cho hội thoại mới. Bản cũ giữ `expires_at` đã ghi, không tự bật lưu hoặc chuyển hội thoại tạm thành bản lưu. Mọi truy vấn lịch sử lọc hạn; worker `purge_chat` xóa vật lý các bản hết hạn sau khi ứng dụng chạy, kể cả khi trình duyệt đóng. Người dùng xem, xuất và xóa bản lưu còn hạn.

Voyage chỉ nhận nội dung ghi nhớ đã duyệt và truy vấn hiện tại khi người dùng bật lựa chọn riêng và quyền AI/MEM còn hiệu lực. Tắt Voyage xóa jobs/vectors dẫn xuất và chặn yêu cầu mới theo snapshot quyền. Rút AI hoặc MEM cũng tắt lựa chọn Voyage để lần cấp quyền theo ngữ cảnh sau này không tự khởi động lại xử lý bên ngoài. Fallback tìm từ khóa trong PostgreSQL vẫn dùng được khi Voyage tắt. Bản chép hội thoại và nhật ký không đi vào Voyage.

Không cần migration schema cho thay đổi này: cột consent, lịch sử, chỉ mục và audit đã có. Mọi giá trị quyền hiện có, kể cả từ chối/rút quyền, giữ nguyên. Không chạy migration trên Supabase từ công việc này.

## Kiểm chứng và quay lại

Kiểm chứng các mốc: mới vào chat không có provider call; gửi lần đầu ghi AI; đề xuất chưa duyệt không hiện trong retrieval; từ chối không ghi MEM; duyệt ghi MEM và audit; draft/preview không ghi MATCH; xuất bản mới ghi MATCH; unpublish ẩn khỏi khám phá; voice API từ chối nếu thiếu quyền; lịch sử/Voyage vẫn mặc định tắt. Kết quả lệnh thực chạy được ghi trong báo cáo PR.

Rollback ứng dụng về commit trước chỉ sau khi xác nhận các tác động lên dữ liệu: bản ghi quyền mới và hồ sơ đã xuất bản phải được giữ, không sửa thành quyền mặc định. Nếu cần tạm ngừng provider, dùng cấu hình sẵn có để vô hiệu hóa dịch vụ AI/voice/Voyage; không xóa cơ sở dữ liệu. Sau rollback, UI cũ có thể yêu cầu thao tác bật quyền riêng dù consent đã ghi, nên cần kiểm tra luồng người dùng trước khi phát hành lại.
