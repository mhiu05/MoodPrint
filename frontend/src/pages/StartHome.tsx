import type { Permission } from "../domain/types";
export const permissionCopy: Record<
  Permission,
  { title: string; description: string; impact: string }
> = {
  AI: {
    title: "Trò chuyện với AI",
    description:
      "Hiện phản hồi soạn sẵn khi bạn chủ động gửi tin. Không phân tích nội dung bạn nhập.",
    impact:
      "Dừng phản hồi và bản chữ mẫu đang chờ; tâm trạng và hồ sơ kết nối tự khai vẫn giữ.",
  },
  MEM: {
    title: "Ghi nhớ điều bạn đã duyệt",
    description:
      "Chỉ ghi nhớ nhận xét bạn chọn lưu riêng, trong phiên demo. Cần bật trò chuyện AI để sử dụng.",
    impact:
      "Dừng dùng các mục ghi nhớ. Bạn vẫn có thể xem, sửa hoặc xóa những mục đã duyệt.",
  },
  MATCH: {
    title: "Dùng hồ sơ để tìm bạn",
    description:
      "Chỉ dùng các mục bạn chọn, xem trước và cho phép chia sẻ. Dành cho nhân vật từ 18 tuổi.",
    impact:
      "Ngừng chia sẻ hồ sơ, hủy lời mời, đóng phòng và dừng các hoạt động; thu hồi thông tin đã cho xem.",
  },
  VOICE: {
    title: "Thử bản chữ từ ghi âm mẫu",
    description:
      "Chỉ hiện văn bản mẫu có thể sửa. Cần bật trò chuyện AI. Không sử dụng microphone.",
    impact:
      "Bỏ tiến trình và bản chữ mẫu chưa gửi. Trò chuyện bằng chữ vẫn dùng được khi AI đang bật.",
  },
};
