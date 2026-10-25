import { Link } from "react-router-dom";

const GUIDES: Record<string, { purpose: string; to: string; action: string }> =
  {
    may: {
      purpose:
        "Kể điều đang ở trong lòng. Mây lắng nghe và giúp bạn gọi tên cảm xúc, theo nhịp của bạn.",
      to: "/self",
      action: "Ghi lại cảm xúc hôm nay",
    },
    guong: {
      purpose:
        "Khám phá sở thích, điều bạn coi trọng và những điều làm bạn là chính mình. Mọi đề xuất đều chờ bạn duyệt.",
      to: "/profile",
      action: "Xem hồ sơ riêng của mình",
    },
    nhip: {
      purpose:
        "Nhìn lại cảm xúc và chọn một thói quen nhỏ. Bạn quyết định có chia sẻ thống kê tâm trạng cho từng lượt hay không.",
      to: "/self",
      action: "Mở nhật ký cảm xúc",
    },
    rure: {
      purpose:
        "Thử câu đố hoặc học một điều mới cùng AI. Muốn chơi với người thật? Mở một cuộc trò chuyện đã kết nối để gửi lời mời.",
      to: "/messages",
      action: "Hoạt động cùng bạn kết nối",
    },
    caunoi: {
      purpose:
        "Chọn những điều bạn muốn công khai trong hồ sơ kết nối. Chuyện riêng với AI, tâm trạng và ghi nhớ không dùng để tìm bạn.",
      to: "/connect?tab=profile",
      action: "Xem hồ sơ kết nối",
    },
  };

export function AssistantGuide({ botId }: { botId: string }) {
  const guide = GUIDES[botId];
  if (!guide) return null;
  return (
    <div className="assistant-guide">
      <p>{guide.purpose}</p>
      <Link to={guide.to}>{guide.action}</Link>
    </div>
  );
}
