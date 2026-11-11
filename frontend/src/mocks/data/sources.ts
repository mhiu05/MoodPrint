import type { KnowledgeSource } from "../../types";

export const knowledgeSources: KnowledgeSource[] = [
  {
    id: "UNICEF-VN",
    publisher: "UNICEF Việt Nam",
    title: "Bắt nạt trực tuyến là gì — Làm thế nào để ngăn chặn điều này?",
    url: "https://www.unicef.org/vietnam/vi/bat-nat-truc-tuyen-la-gi-lam-the-nao-de-ngan-chan-dieu-nay",
    applicability:
      "Việt Nam · tài liệu giáo dục về an toàn trực tuyến; không phải tư vấn pháp lý hay chẩn đoán.",
    checkedAt: "2026-11-07",
  },
  {
    id: "STOP-DEFINITION",
    publisher: "StopBullying.gov",
    title: "What Is Bullying",
    url: "https://www.stopbullying.gov/bullying/what-is-bullying",
    applicability:
      "Hoa Kỳ · tham khảo khái niệm, dạng hành vi và dấu hiệu lặp lại/chênh lệch quyền lực. Không áp dụng pháp luật Hoa Kỳ tại Việt Nam.",
    checkedAt: "2026-11-07",
  },
  {
    id: "STOP-REPORT",
    publisher: "StopBullying.gov",
    title: "Report Cyberbullying",
    url: "https://www.stopbullying.gov/cyberbullying/how-to-report",
    applicability:
      "Hoa Kỳ · chỉ tham khảo phần ghi nhận, chặn và báo cáo nội dung. Phần pháp luật và nghĩa vụ nhà trường của Hoa Kỳ không áp dụng tại Việt Nam.",
    checkedAt: "2026-11-07",
  },
  {
    id: "VN-111",
    publisher: "Tổng đài Quốc gia bảo vệ trẻ em",
    title: "Số điện thoại bảo vệ trẻ em",
    url: "https://tongdai111.vn/tin/so-dien-thoai-bao-ve-tre-em",
    applicability:
      "Việt Nam · thông tin chính thức về Tổng đài 111, miễn phí, hoạt động 24/24.",
    checkedAt: "2026-11-07",
  },
];

export const supportSources = [
  {
    id: "teacher",
    title: "Giáo viên bạn tin tưởng",
    tag: "Ở trường",
    description:
      "Có thể cùng bạn xem lại việc xảy ra ở lớp và bàn một bước tiếp theo. Bạn được chọn người mình thấy an toàn.",
    preparation: "Chuẩn bị 2–3 sự việc cụ thể và điều bạn muốn cô/thầy giúp.",
    recipient: "Giáo viên",
    icon: "school",
  },
  {
    id: "parent",
    title: "Người chăm sóc hoặc phụ huynh",
    tag: "Gần gũi",
    description:
      "Nếu đây là người bạn thấy an toàn, hãy chọn một lúc có thể nói riêng và không bị vội.",
    preparation:
      "Có thể mở đầu: “Con muốn được nghe trước khi mình bàn cách xử lý.”",
    recipient: "Người chăm sóc",
    icon: "heart",
  },
  {
    id: "other",
    title: "Một người lớn khác",
    tag: "Bạn có lựa chọn",
    description:
      "Người thân, nhân viên hỗ trợ ở trường hoặc người lớn khác mà bạn tin cậy có thể là điểm bắt đầu.",
    preparation:
      "Không cần ép mình chọn gia đình nếu điều đó khiến bạn không an toàn.",
    recipient: "Người lớn tin cậy khác",
    icon: "people",
  },
  {
    id: "111",
    title: "Tổng đài bảo vệ trẻ em 111",
    tag: "Việt Nam · 24/24 · miễn phí",
    description:
      "Kênh chính thức tiếp nhận thông tin và hỗ trợ bảo vệ trẻ em. Bạn chủ động chọn mở cuộc gọi trên thiết bị.",
    preparation:
      "Nếu có thể, chuẩn bị điều đang xảy ra và nơi bạn đang ở. Không cần hoàn thành hồ sơ SafeVoice trước.",
    recipient: "Tổng đài 111",
    icon: "phone",
  },
  {
    id: "platform",
    title: "Báo nội dung trên nền tảng",
    tag: "Tự thực hiện ngoài ứng dụng",
    description:
      "Dùng chức năng báo cáo, chặn và cài đặt riêng tư của nền tảng. SafeVoice không đăng nhập hay thao tác thay bạn.",
    preparation:
      "Xem hướng dẫn lưu ngữ cảnh và kiểm tra trung tâm trợ giúp chính thức của nền tảng.",
    recipient: "Nền tảng",
    icon: "shield",
  },
] as const;
