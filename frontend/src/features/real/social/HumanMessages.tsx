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
  const restricted = session.notices?.some((notice) => notice.kind === "restricted");
  const enabled = session.ageBand === "adult" && session.consents.MATCH.enabled && !restricted;
  const rooms = useResource<ConnectionView[]>("/connections", enabled);
  const { refresh } = rooms;
  useEffect(() => {
    if (!enabled) return;
    const timer = setInterval(() => {
      if (document.visibilityState === "visible") refresh();
    }, 15_000);
    return () => clearInterval(timer);
  }, [enabled, refresh]);
  if (restricted)
    return (
      <StatePanel title="Kết nối đang tạm dừng">
        Các cuộc trò chuyện không khả dụng trong thời gian hạn chế. Bạn có thể
        tiếp tục dùng trợ lý và nhật ký cảm xúc.
      </StatePanel>
    );
  if (session.ageBand !== "adult")
    return (
      <StatePanel title="Bạn cần đủ 18 tuổi để kết nối">
        Nhắn tin người thật dành cho người đã đủ 18 tuổi.
      </StatePanel>
    );
  if (!session.consents.MATCH.enabled)
    return (
      <StatePanel
        title="Bạn chưa bật Tìm bạn"
        action={<Link to="/connect?tab=profile">Mở hồ sơ tìm bạn</Link>}
      >
        Để trò chuyện với người thật trở lại, xem lại hồ sơ tìm bạn rồi chọn
        Hiển thị hồ sơ. Hồ sơ chỉ hiện với người khác sau bước xem trước đó.
      </StatePanel>
    );
  return (
    <div className={cx.reading}>
      <h1 tabIndex={-1}>Tin nhắn</h1>
      <p className={cx.lede}>Bạn chỉ có thể nhắn tin sau khi cả hai đồng ý kết nối.</p>
      <ErrorNotice error={rooms.error} retry={rooms.refresh} />
      {rooms.loading && <p role="status">Đang tải kết nối…</p>}
      {rooms.data?.length === 0 && (
        <p>
          Chưa có cuộc trò chuyện.{" "}
          <Link to="/connect?tab=suggestions">Tìm người cùng điểm chung</Link>
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
        Tải lại tin nhắn
      </Button>
    </div>
  );
}
