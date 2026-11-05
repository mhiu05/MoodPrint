export function noticeText(): string {
  return "Để trợ lý Nhật ký tìm đúng những trang bạn cần, MoodPrint gửi nội dung các trang nhật ký đã lưu tới Voyage AI, một dịch vụ embedding bên ngoài, để tạo chỉ mục tìm kiếm. Chỉ mục bị xóa khi bạn sửa hoặc xóa trang, khi tắt công tắc này, hoặc khi xóa tài khoản. Bản sao ở nhà cung cấp hoặc bản sao lưu có thể chưa bị xóa ngay.";
}

export function toggleLabel(kind: "embedding" | "memory"): string {
  return kind === "embedding" ? "Tìm theo ý nghĩa trong nhật ký" : "Tự ghi nhớ điều quan trọng từ nhật ký";
}
