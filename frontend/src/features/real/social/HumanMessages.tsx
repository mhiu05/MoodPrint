import { useEffect } from "react";
import { Link } from "react-router-dom";
import { Button, cx, StatePanel } from "../../../components/UI";
import type { components } from "../../../api/generated/schema";
import { ErrorNotice, useResource, useSession } from "../RealApp";
import { previewLine, relativeTime } from "./format";
import { badgeText } from "./useSocialSummary";

type ConnectionView = components["schemas"]["ConnectionView"];

export function HumanMessages() {
  const { session } = useSession();
  const enabled = session.ageBand === "adult" && session.consents.MATCH.enabled;
  const rooms = useResource<ConnectionView[]>("/connections", enabled);
  const { refresh } = rooms;
  useEffect(() => {
    if (!enabled) return;
    const timer = setInterval(() => {
      if (document.visibilityState === "visible") refresh();
    }, 15_000);
    return () => clearInterval(timer);
  }, [enabled, refresh]);
  if (session.ageBand !== "adult")
    return (
      <StatePanel title="Tính năng kết nối chưa khả dụng">
        Nhắn tin người thật dành cho người đã đủ 18 tuổi.
      </StatePanel>
    );
  if (!session.consents.MATCH.enabled)
    return (
      <StatePanel title="Bạn đang tắt quyền tìm bạn">
        <Link to="/settings">Xem quyền tìm bạn</Link>
      </StatePanel>
    );
  return (
    <div className={cx.reading}>
      <h1 tabIndex={-1}>Tin nhắn</h1>
      <p className={cx.lede}>Trò chuyện bắt đầu khi cả hai cùng đồng ý.</p>
      <ErrorNotice error={rooms.error} retry={rooms.refresh} />
      {rooms.loading && <p role="status">Đang tải kết nối…</p>}
      {rooms.data?.length === 0 && (
        <p>
          Chưa có cuộc trò chuyện.{" "}
          <Link to="/connect">Tìm người cùng điểm chung</Link>
        </p>
      )}
      {rooms.data?.map((room) => (
        <Link
          className={`${cx.messagePreview} ${room.unreadCount ? cx.messageUnread : ""}`}
          key={room.id}
          to={`/chat/${room.id}`}
        >
          <div>
            <h2>
              {room.alias}
              {room.unreadCount > 0 && (
                <span className={cx.srOnly}>
                  {`, ${room.unreadCount} tin nhắn chưa đọc`}
                </span>
              )}
            </h2>
            <p>{previewLine(room.lastMessagePreview, room.lastMessageSender)}</p>
          </div>
          <div className={cx.messageMeta}>
            {room.lastMessageAt && (
              <time dateTime={room.lastMessageAt}>
                {relativeTime(room.lastMessageAt)}
              </time>
            )}
            {room.unreadCount > 0 && (
              <span className={cx.unreadCount} aria-hidden="true">
                {badgeText(room.unreadCount)}
              </span>
            )}
          </div>
        </Link>
      ))}
      <Button variant="text" onClick={rooms.refresh}>
        Tải lại kết nối
      </Button>
    </div>
  );
}
