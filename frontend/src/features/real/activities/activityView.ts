import type { components } from "../../../api/generated/schema";

export type Session = components["schemas"]["ActivitySessionView"];
export type Definition = components["schemas"]["ActivityDefinitionDTO"];
export type Kind = Session["kind"];

export const OPEN_STATES = ["invited", "active", "paused"];
export const KIND_TITLES: Record<Kind, string> = {
  icebreaker: "Câu hỏi làm quen",
  coop_quiz: "Đố vui đồng đội",
  focus: "Cùng tập trung",
};

export function isOpen(session?: Session | null) {
  return Boolean(session && OPEN_STATES.includes(session.state));
}

/** Turn-based kinds: is the viewer expected to do something right now? */
export function isMyTurn(session?: Session | null) {
  if (!session || session.state !== "active" || session.kind === "focus") return false;
  if (session.progress.phase === "answering") return !session.current?.selfResponse;
  if (session.progress.phase === "revealed")
    return session.self.readyRound < session.progress.round;
  return false;
}

/** The waiting line shown while the peer still has to act, or null. */
export function waitingLabel(session: Session | null | undefined, alias: string) {
  if (!session) return null;
  if (session.state === "invited")
    return session.role === "inviter" ? `Đang chờ ${alias} đồng ý…` : null;
  if (session.state !== "active" || session.kind === "focus") return null;
  const round = session.progress.round;
  if (session.progress.phase === "answering" && session.current?.selfResponse)
    return session.current.peerSubmitted ? null : `Đang chờ ${alias} trả lời…`;
  if (session.progress.phase === "revealed" && session.self.readyRound >= round)
    return session.peer.readyRound >= round ? null : `Đang chờ ${alias}…`;
  return null;
}

/** Compact status for the collapsed dock bar and the message list. */
export function shortStatus(session: Session) {
  if (session.state === "invited")
    return session.role === "inviter" ? "Đã gửi lời mời" : "Lời mời mới";
  if (session.kind === "focus")
    return session.state === "paused" ? "Đang tạm dừng" : "Đang tập trung";
  const total = session.progress.totalRounds ?? 0;
  const label = session.kind === "coop_quiz" ? "Vòng" : "Câu";
  return `${label} ${session.progress.round}/${total}${isMyTurn(session) ? " · Đến lượt bạn" : ""}`;
}

/** Whether a new invite of `kind` may be sent (no open session, no local cooldown). */
export function canInvite(
  current: Session | null | undefined,
  kind: Kind,
  cooldownUntil: Partial<Record<Kind, number>>,
  now = Date.now(),
) {
  if (isOpen(current)) return false;
  return !(cooldownUntil[kind] && cooldownUntil[kind]! > now);
}

export function endedMessage(session: Session, alias: string) {
  switch (session.endReason) {
    case "invite_declined":
      return session.role === "inviter"
        ? `${alias} chưa muốn chơi lúc này`
        : "Bạn đã để lời mời lại sau";
    case "invite_cancelled":
      return session.role === "inviter" ? "Bạn đã hủy lời mời" : "Lời mời đã được hủy";
    case "invite_expired":
      return "Lời mời đã hết hạn";
    case "ended_by_self":
      return "Bạn đã kết thúc hoạt động";
    case "ended_by_peer":
      return `${alias} đã kết thúc hoạt động`;
    case "idle_expired":
    case "pause_expired":
      return "Hoạt động đã dừng vì không có ai tiếp tục";
    case "completed":
      return "Đã hoàn thành";
    default:
      return "Hoạt động đã dừng vì kết nối không còn khả dụng";
  }
}
