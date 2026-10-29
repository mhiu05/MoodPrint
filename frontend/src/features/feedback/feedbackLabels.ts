import type { FeedbackInput, FeedbackStatusInput } from "../../api/contracts";

export const categories: Record<NonNullable<FeedbackInput["categories"]>[number], string> = {
  ease_of_use: "Dễ sử dụng", ai_quality: "Trò chuyện với trợ lý", interface: "Giao diện",
  performance: "Tốc độ", bug: "Lỗi gặp phải", missing_feature: "Tính năng còn thiếu",
  privacy_trust: "Quyền riêng tư / sự tin cậy", other: "Khác",
};
export const ratingLabels = ["Rất chưa hài lòng", "Chưa hài lòng", "Bình thường", "Hài lòng", "Rất hài lòng"];
export const contexts: Record<NonNullable<FeedbackInput["context"]>, string> = {
  general: "Chung", assistants: "Trợ lý", mood: "Cảm xúc", memory: "Ghi nhớ",
  privacy: "Quyền riêng tư", activities: "Hoạt động", trial_end: "Kết thúc lượt thử",
};
export const statuses: Record<FeedbackStatusInput["status"], string> = {
  new: "Mới", reviewed: "Đã xem", planned: "Đã lên kế hoạch", resolved: "Đã xử lý", spam: "Spam",
};
