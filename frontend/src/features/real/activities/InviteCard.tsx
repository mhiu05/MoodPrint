import { Button, cx } from "../../../components/UI";
import { endedMessage, KIND_TITLES, type Definition, type Session } from "./activityView";

/** Inline card in the chat log for invitations and how they ended (both roles). */
export function InviteCard({
  session,
  alias,
  catalog,
  busy,
  onAccept,
  onDecline,
  onCancel,
}: {
  session: Session;
  alias: string;
  catalog: Definition[];
  busy: boolean;
  onAccept: () => void;
  onDecline: () => void;
  onCancel: () => void;
}) {
  const title = KIND_TITLES[session.kind];
  const minutes = catalog.find((item) => item.kind === session.kind)?.estimatedMinutes;
  if (session.state === "invited")
    return (
      <div className="invite-card" role="group" aria-label={`Lời mời ${title}`}>
        {session.role === "inviter" ? (
          <>
            <p>
              Bạn đã mời {alias} chơi <strong>{title}</strong>. Đang chờ {alias} đồng ý…
            </p>
            <div className={cx.actions}>
              <Button variant="text" disabled={busy} onClick={onCancel}>
                Hủy lời mời
              </Button>
            </div>
          </>
        ) : (
          <>
            <p>
              {alias} mời bạn chơi <strong>{title}</strong>
              {minutes ? ` (khoảng ${minutes} phút)` : ""}
            </p>
            <div className={cx.actions}>
              <Button disabled={busy} onClick={onAccept}>
                Đồng ý
              </Button>
              <Button variant="secondary" disabled={busy} onClick={onDecline}>
                Để sau
              </Button>
            </div>
          </>
        )}
      </div>
    );
  if (["declined", "cancelled", "expired", "aborted"].includes(session.state))
    return (
      <div className="invite-card ended" role="status">
        <p>
          {title}: {endedMessage(session, alias)}
        </p>
      </div>
    );
  return null;
}
