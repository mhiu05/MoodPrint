import type { SessionView } from "../../api/contracts";

export function aiServiceMessage(features: SessionView["features"]): string {
  switch (features.aiStatus) {
    case "configuration_missing":
      return "Trợ lý chưa được kết nối với dịch vụ AI. Bạn có thể quay lại sau.";
    case "configuration_invalid":
      return "Kết nối dịch vụ AI cần được kiểm tra. Bạn có thể quay lại sau.";
    case "disabled":
      return "Dịch vụ trò chuyện AI đang tạm tắt. Lịch sử đã lưu vẫn xem, xuất và xóa được.";
    default:
      return "Dịch vụ trò chuyện AI chưa sẵn sàng. Bạn có thể thử lại sau.";
  }
}
