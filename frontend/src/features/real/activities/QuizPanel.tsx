import { useEffect, useRef } from "react";
import { Check } from "lucide-react";
import { Button, cx } from "../../../components/UI";
import { waitingLabel, type Session } from "./activityView";

/** Cooperative quiz round: shared question, independent answers, team score. */
export function QuizPanel({
  session,
  alias,
  busy,
  act,
}: {
  session: Session;
  alias: string;
  busy: boolean;
  act: (op: string, body?: Record<string, unknown>) => Promise<boolean>;
}) {
  const round = session.progress.round;
  const current = session.current!;
  const reveal = current.reveal;
  const heading = useRef<HTMLHeadingElement>(null);
  useEffect(() => heading.current?.focus(), [round, session.progress.phase]);
  const waiting = waitingLabel(session, alias);
  const mine = current.selfResponse;
  const theirs = reveal && typeof reveal.peer === "object" ? reveal.peer : null;
  return (
    <div className="activity-panel">
      <p className="activity-progress">
        Vòng {round}/{session.progress.totalRounds} · Đội: {session.score?.team ?? 0} điểm
      </p>
      <h3 ref={heading} tabIndex={-1}>
        {current.item.prompt}
      </h3>
      {reveal ? (
        <>
          <ul className="quiz-reveal">
            {current.item.options.map((option, index) => {
              const correct = reveal.correctIndex === index;
              const chosen = reveal.self?.choice === index && !reveal.self?.skipped;
              const peerChose = theirs?.choice === index && !theirs?.skipped;
              return (
                <li key={option} data-correct={correct || undefined}>
                  {correct && <Check size={16} aria-hidden="true" />}
                  <span>{option}</span>
                  {correct && <span className="quiz-tag">Đáp án đúng</span>}
                  {chosen && <span className="quiz-tag">Bạn chọn</span>}
                  {peerChose && <span className="quiz-tag">{alias} chọn</span>}
                </li>
              );
            })}
          </ul>
          {reveal.explanation && <p>{reveal.explanation}</p>}
          {reveal.peer === "skipped" && <p className={cx.footnote}>{alias} đã bỏ qua.</p>}
          {reveal.points != null && (
            <p className="quiz-points">
              +{reveal.points}
              {reveal.points === 3 ? " (cả hai đúng!)" : ""}
            </p>
          )}
          {waiting ? (
            <p role="status">{waiting}</p>
          ) : (
            <Button disabled={busy} onClick={() => void act("ready", { round })}>
              {round === session.progress.totalRounds ? "Xem tổng kết" : "Vòng tiếp theo"}
            </Button>
          )}
        </>
      ) : mine ? (
        <>
          <p className="own-answer">
            Bạn: {mine.skipped ? "Đã bỏ qua" : current.item.options[mine.choice ?? 0]}
          </p>
          <p role="status">{waiting ?? "Đang mở đáp án…"}</p>
        </>
      ) : (
        <>
          {current.peerSubmitted && <p className="peer-badge">{alias} đã trả lời</p>}
          <div className="quiz-options" role="group" aria-label="Các lựa chọn">
            {current.item.options.map((option, index) => (
              <button
                type="button"
                key={option}
                disabled={busy}
                onClick={() => void act("responses", { round, choice: index })}
              >
                {option}
              </button>
            ))}
          </div>
          <Button
            variant="text"
            disabled={busy}
            onClick={() => void act("responses", { round, skipped: true })}
          >
            Bỏ qua
          </Button>
        </>
      )}
    </div>
  );
}
