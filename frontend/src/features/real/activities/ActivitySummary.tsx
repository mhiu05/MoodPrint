import { Button } from "../../../components/UI";
import { endedMessage, type Session } from "./activityView";

const RATINGS = [
  ["liked", "Thích"],
  ["neutral", "Bình thường"],
  ["not_for_me", "Không hợp với mình"],
] as const;

/** Private feedback chips; the peer never sees the rating. */
export function FeedbackChips({
  session,
  busy,
  onRate,
}: {
  session: Session;
  busy: boolean;
  onRate: (rating: string) => void;
}) {
  if (session.state !== "completed") return null;
  if (session.self.feedbackGiven)
    return <p role="status">Cảm ơn bạn. Đánh giá này chỉ mình bạn biết.</p>;
  return (
    <div className="feedback-chips" role="group" aria-label="Bạn thấy hoạt động này thế nào? (chỉ mình bạn biết)">
      <p>Bạn thấy hoạt động này thế nào? (chỉ mình bạn biết)</p>
      {RATINGS.map(([value, label]) => (
        <button type="button" key={value} disabled={busy} onClick={() => onRate(value)}>
          {label}
        </button>
      ))}
    </div>
  );
}

function answerText(
  answer: { choice?: number | null; text?: string | null; skipped?: boolean } | null | undefined,
  options: string[],
) {
  if (!answer) return "—";
  if (answer.skipped) return "Đã bỏ qua";
  return [answer.choice != null ? options[answer.choice] : null, answer.text]
    .filter(Boolean)
    .join(" · ");
}

/** Factual completion summary: no badges, streaks or invented achievements. */
export function ActivitySummary({
  session,
  alias,
  busy,
  onRate,
  onContinue,
}: {
  session: Session;
  alias: string;
  busy: boolean;
  onRate: (rating: string) => void;
  onContinue: () => void;
}) {
  const summary = session.summary;
  return (
    <div className="activity-summary">
      <h3>{session.state === "completed" ? "Hoàn thành!" : endedMessage(session, alias)}</h3>
      {session.kind === "icebreaker" && summary?.answeredTogether != null && (
        <p>Hai bạn cùng trả lời {summary.answeredTogether}/3 câu.</p>
      )}
      {session.kind === "coop_quiz" && summary?.teamScore != null && (
        <p>
          Đội của hai bạn: <strong>{summary.teamScore}/{summary.maxScore}</strong>
        </p>
      )}
      {session.kind === "focus" && summary?.focusMinutesTogether != null && (
        <p>
          Bạn đã tập trung {summary.focusMinutesSelf} phút · {alias} {summary.focusMinutesPeer}{" "}
          phút · Cùng nhau {summary.focusMinutesTogether} phút
        </p>
      )}
      {(session.history ?? []).length > 0 && (
        <ol className="summary-rounds">
          {(session.history ?? []).map((row) => (
            <li key={row.round}>
              <p className="summary-prompt">{row.item.prompt}</p>
              {session.kind === "coop_quiz" && row.reveal.correctIndex != null && (
                <p>Đáp án đúng: {row.item.options[row.reveal.correctIndex]}</p>
              )}
              <p>Bạn: {answerText(row.reveal.self, row.item.options)}</p>
              <p>
                {alias}:{" "}
                {row.reveal.peer === "hidden"
                  ? "được giữ kín vì bạn đã bỏ qua"
                  : row.reveal.peer === "skipped"
                    ? "Đã bỏ qua"
                    : answerText(row.reveal.peer, row.item.options)}
              </p>
            </li>
          ))}
        </ol>
      )}
      <FeedbackChips session={session} busy={busy} onRate={onRate} />
      <Button onClick={onContinue}>Tiếp tục trò chuyện</Button>
    </div>
  );
}

export { answerText };
