import type { SessionView } from "../../api/contracts";

export type TourStep = {
  id: "assistants" | "mood" | "memory" | "profile";
  route: string;
  target: string;
  title: string;
  description: string;
  isApplicable: (session: SessionView) => boolean;
};

export function getTourSteps(
  session: SessionView,
): TourStep[] {
  const personal = (value: SessionView) => value.eligible && value.ageBand === "adult";
  const steps: TourStep[] = [
    {
      id: "assistants",
      route: "/assistants",
      target: "[data-tour='assistants-list']",
      title: "Chọn trợ lý",
      description:
        "Chọn trợ lý hợp với điều bạn muốn làm hôm nay. Bạn có thể đổi bất cứ lúc nào.",
      isApplicable: personal,
    },
    {
      id: "mood",
      route: "/self",
      target: "[data-tour='mood-entry']",
      title: "Ghi lại cảm xúc",
      description:
        "Ghi lại cảm xúc của bạn. Ghi chú là tùy chọn và vẫn là thông tin riêng.",
      isApplicable: personal,
    },
    {
      id: "memory",
      route: "/memory",
      target: "[data-tour='memory-intro']",
      title: "Bạn duyệt điều được ghi nhớ",
      description:
        "Trợ lý chỉ ghi nhớ khi bạn duyệt. Bạn có thể sửa hoặc xóa sau.",
      isApplicable: personal,
    },
    {
      id: "profile",
      route: "/profile",
      target: "[data-tour='personal-account']",
      title: "Tài khoản",
      description:
        "Quản lý tài khoản, gửi góp ý và xem hướng dẫn tại đây." +
        (session.accountKind === "guest"
          ? " Dữ liệu của lượt thử không mở lại được sau khi hết giờ."
          : ""),
      isApplicable: personal,
    },
  ];
  return steps.filter((step) => step.isApplicable(session));
}
