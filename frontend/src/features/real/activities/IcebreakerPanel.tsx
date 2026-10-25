import { useEffect, useId, useRef, useState } from "react";
import { Button, cx } from "../../../components/UI";
import { answerText } from "./ActivitySummary";
import { waitingLabel, type Session } from "./activityView";

type Draft = { choice: number | null; text: string };

/** Icebreaker round: answer independently, reciprocal reveal, mutual "next". */
export function IcebreakerPanel({
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
  const key = `${session.id}:${round}`;
  // Drafts survive re-renders and 409 refreshes; never stored in the browser.
  const [drafts, setDrafts] = useState<Record<string, Draft>>({});
  const draft = drafts[key] ?? { choice: null, text: "" };
  const setDraft = (next: Draft) => setDrafts((value) => ({ ...value, [key]: next }));
  const heading = useRef<HTMLHeadingElement>(null);
  const counter = useId();
  useEffect(() => heading.current?.focus(), [round, session.progress.phase]);
  const waiting = waitingLabel(session, alias);
  const reveal = current.reveal;
  return (
    <div className="activity-panel">
      <p className="activity-progress">
        Câu {round}/{session.progress.totalRounds}
        <span className="progress-dots" aria-hidden="true">
          {Array.from({ length: session.progress.totalRounds ?? 0 }, (_, i) => (
            <i key={i} data-done={i + 1 < round || undefined} data-current={i + 1 === round || undefined} />
          ))}
        </span>
      </p>
      <h3 ref={heading} tabIndex={-1}>
        {current.item.prompt}
      </h3>
      {reveal ? (
        <>
          <div className="reveal-pair">
            <div className="reveal-bubble self">
              <span>Bạn</span>
              <p>{answerText(reveal.self, current.item.options)}</p>
            </div>
            <div className="reveal-bubble">
              <span>{alias}</span>
              <p>
                {reveal.peer === "hidden"
                  ? "Bạn đã bỏ qua câu này — câu trả lời của bạn kia được giữ kín."
                  : reveal.peer === "skipped"
                    ? `${alias} đã bỏ qua câu này.`
                    : answerText(reveal.peer, current.item.options)}
              </p>
            </div>
          </div>
          {waiting ? (
            <p role="status">{waiting}</p>
          ) : (
            <Button disabled={busy} onClick={() => void act("ready", { round })}>
              {round === session.progress.totalRounds ? "Xem tổng kết" : "Câu tiếp theo"}
            </Button>
          )}
          {session.peer.readyRound >= round && session.self.readyRound < round && (
            <p className={cx.footnote}>{alias} đã sẵn sàng</p>
          )}
        </>
      ) : current.selfResponse ? (
        <>
          <p className="own-answer">Bạn: {answerText(current.selfResponse, current.item.options)}</p>
          <p role="status">{waiting ?? "Đang mở câu trả lời…"}</p>
        </>
      ) : (
        <form
          onSubmit={(event) => {
            event.preventDefault();
            void act("responses", {
              round,
              choice: draft.choice,
              text: draft.text.trim() || null,
            });
          }}
        >
          {current.peerSubmitted && <p className="peer-badge">{alias} đã trả lời</p>}
          <fieldset className="activity-options">
            <legend className={cx.srOnly}>Chọn một câu trả lời</legend>
            {current.item.options.map((option, index) => (
              <label key={option} data-checked={draft.choice === index || undefined}>
                <input
                  type="radio"
                  name={`answer-${key}`}
                  checked={draft.choice === index}
                  onChange={() => setDraft({ ...draft, choice: index })}
                />
                {option}
              </label>
            ))}
          </fieldset>
          {current.item.allowText && (
            <label className="activity-text">
              Hoặc viết vài chữ (không bắt buộc)
              <textarea
                rows={2}
                maxLength={140}
                value={draft.text}
                aria-describedby={counter}
                onChange={(event) => setDraft({ ...draft, text: event.target.value })}
              />
              <span id={counter} className={cx.footnote}>
                {draft.text.length}/140
              </span>
            </label>
          )}
          <div className={cx.actions}>
            <Button type="submit" disabled={busy || (draft.choice === null && !draft.text.trim())}>
              Gửi câu trả lời
            </Button>
            <Button
              variant="text"
              disabled={busy}
              onClick={() => void act("responses", { round, skipped: true })}
            >
              Bỏ qua câu này
            </Button>
          </div>
        </form>
      )}
    </div>
  );
}
