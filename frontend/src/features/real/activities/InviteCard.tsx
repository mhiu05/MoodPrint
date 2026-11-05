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
  // A focus invitation names the exact plan both people would commit to.
  const plan = session.kind === "focus" && session.timer?.plan?.length === 2
    ? `${session.timer.plan[0]} phút tập trung / ${session.timer.plan[1]} phút nghỉ · ${session.timer.cycles} lượt`
    : null;
  if (session.state === "invited")
    return (
      <div className="invite-card" role="group" aria-label={`Lời mời ${title}`}>
        {session.role === "inviter" ? (
          <>
            <p>
              Bạn đã mời {alias} tham gia <strong>{title}</strong>. Đang chờ {alias} đồng ý…
            </p>
            {plan ? <p className={cx.footnote}>{plan}</p> : null}
            <div className={cx.actions}>
              <Button variant="text" disabled={busy} onClick={onCancel}>
                Hủy lời mời
              </Button>
            </div>
          </>
        ) : (
          <>
            <p>
              {alias} mời bạn tham gia <strong>{title}</strong>
              {minutes ? ` (khoảng ${minutes} phút)` : ""}
            </p>
            {plan ? <p className={cx.footnote}>{plan}</p> : null}
            <div className={cx.actions}>
              <Button disabled={busy} onClick={onAccept}>
                Tham gia
              </Button>
              <Button variant="secondary" disabled={busy} onClick={onDecline}>
                Từ chối lời mời
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

/** A finished session in the chat log's inline history (H-02); not a live region. */
export function HistoryCard({ session, alias }: { session: Session; alias: string }) {
  const title = KIND_TITLES[session.kind];
  return (
    <div className="invite-card ended" role="group" aria-label={`Hoạt động đã qua: ${title}`}>
      <p>
        {title}:{" "}
        {session.state === "completed" ? "hai bạn đã hoàn thành." : endedMessage(session, alias)}
      </p>
    </div>
  );
}
