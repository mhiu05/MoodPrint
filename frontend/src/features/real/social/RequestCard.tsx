import { Link } from "react-router-dom";
import { Button, cx } from "../../../components/UI";
import type { components } from "../../../api/generated/schema";
import { PeerCard } from "./CandidateCard";

type RequestView = components["schemas"]["RequestView"];
export type Decision = "accept" | "decline" | "cancel";

const STATUS: Record<string, string> = {
  pending: "Đang chờ phản hồi",
  accepted: "Đã kết nối",
  declined: "Lời mời đã được từ chối",
  cancelled: "Lời mời đã được hủy",
  expired: "Lời mời đã hết hạn",
  invalidated:
    "Lời mời không còn hiệu lực vì quyền tìm bạn hoặc trạng thái kết nối đã thay đổi",
};

function daysLeft(expiresAt: string, now = Date.now()) {
  const days = Math.ceil((new Date(expiresAt).getTime() - now) / 86_400_000);
  return days <= 1 ? "còn dưới 1 ngày" : `còn ${days} ngày`;
}

/** A pending request shows the counterpart's public card (DR-07); terminal ones collapse. */
export function RequestCard({
  item,
  label,
  busy,
  onDecide,
}: {
  item: RequestView;
  label: (key: string) => string;
  busy: boolean;
  onDecide: (item: RequestView, decision: Decision) => void;
}) {
  const incoming = item.direction === "incoming";
  const actions =
    item.status === "pending" ? (
      <div className={cx.actions}>
        {(incoming
          ? ([
              ["accept", "Đồng ý kết nối"],
              ["decline", "Từ chối"],
            ] as const)
          : ([["cancel", "Hủy lời mời"]] as const)
        ).map(([decision, title]) => (
          <Button
            key={decision}
            variant={decision === "accept" ? "primary" : "secondary"}
            disabled={busy}
            onClick={() => onDecide(item, decision)}
          >
            {title}
          </Button>
        ))}
      </div>
    ) : null;
  const status = (
    <p className="request-status">
      {STATUS[item.status] || "Lời mời đã kết thúc"}
      {item.status === "pending" && !incoming && ` · ${daysLeft(item.expiresAt)}`}
    </p>
  );
  const open = item.connectionId && item.status === "accepted" && (
    <Link to={`/chat/${item.connectionId}`}>Mở cuộc trò chuyện</Link>
  );
  if (item.peer)
    return (
      <PeerCard
        {...item.peer}
        heading={
          incoming
            ? `${item.peer.alias} muốn kết nối với bạn`
            : `Lời chào gửi ${item.peer.alias}`
        }
        label={label}
      >
        {status}
        {actions}
      </PeerCard>
    );
  return (
    <article className="real-item">
      <h3>{incoming ? "Một lời chào dành cho bạn" : "Lời chào bạn đã gửi"}</h3>
      {status}
      {actions}
      {open}
    </article>
  );
}
