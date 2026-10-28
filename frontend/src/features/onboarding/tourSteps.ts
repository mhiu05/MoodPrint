import type { SessionView } from "../../api/contracts";

export type TourStep = {
  id: "assistants" | "mood" | "memory" | "privacy" | "matching";
  route: string;
  target: string;
  title: string;
  description: string;
  isApplicable: (session: SessionView) => boolean;
};

export function getTourSteps(
  session: SessionView,
  includeMatching = false,
): TourStep[] {
  const personal = (value: SessionView) => value.eligible;
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
      id: "privacy",
      route: "/settings",
      target: "[data-tour='privacy-controls']",
      title: "Quyền riêng tư",
      description:
        "Bạn chọn quyền xử lý dữ liệu và có thể rút lại bất cứ lúc nào." +
        (session.accountKind === "guest"
          ? " Dữ liệu của lượt thử không mở lại được sau khi hết giờ."
          : ""),
      isApplicable: personal,
    },
  ];
  if (includeMatching)
    steps.push({
      id: "matching",
      route: "/connect",
      target: "[data-tour='matching-intro']",
      title: "Kết nối khi sẵn sàng",
      description:
        "Bạn chủ động xem trước và chọn thông tin chia sẻ. Hướng dẫn không bật quyền tìm bạn.",
      isApplicable: (value) =>
        value.eligible &&
        value.accountKind !== "guest" &&
        value.ageBand === "adult",
    });
  return steps.filter((step) => step.isApplicable(session));
}
