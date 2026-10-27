import { useEffect, useRef, useState } from "react";
import { Button, cx, Dialog } from "../../../components/UI";
import { formatCountdown, remainingMs, type Clock } from "./clock";
import type { Session } from "./activityView";

const PHASES: Record<string, string> = {
  starting: "Bắt đầu sau",
  focus: "Tập trung",
  break: "Nghỉ",
  done: "Xong",
};

/** Ticks once a second; returns the server-anchored remaining time in ms. */
export function useCountdown(session: Session, clock: Clock) {
  const [, setTick] = useState(0);
  useEffect(() => {
    const timer = setInterval(() => setTick((value) => value + 1), 1000);
    return () => clearInterval(timer);
  }, []);
  const timer = session.timer;
  if (!timer) return 0;
  if (timer.pausedRemainingSec != null) return timer.pausedRemainingSec * 1000;
  return timer.phaseEndsAt ? remainingMs(timer.phaseEndsAt, clock) : 0;
}

/** Compact timer for the collapsed dock bar and the chat header. */
export function FocusTimerChip({ session, clock }: { session: Session; clock: Clock }) {
  const left = useCountdown(session, clock);
  if (!session.timer) return null;
  return (
    <span className="focus-chip" aria-label={`${PHASES[session.timer.phase]} ${formatCountdown(left)}`}>
      {PHASES[session.timer.phase]} {formatCountdown(left)}
    </span>
  );
}

export function FocusPanel({
  session,
  alias,
  clock,
  busy,
  act,
}: {
  session: Session;
  alias: string;
  clock: Clock;
  busy: boolean;
  act: (op: string, body?: Record<string, unknown>) => Promise<boolean>;
}) {
  const timer = session.timer!;
  const left = useCountdown(session, clock);
  const [ending, setEnding] = useState(false);
  const [announcement, setAnnouncement] = useState("");
  const lastPhase = useRef(timer.phase);
  const lastMark = useRef<number | null>(null);
  const paused = session.state === "paused";
  useEffect(() => {
    if (timer.phase !== lastPhase.current) {
      lastPhase.current = timer.phase;
      setAnnouncement(
        timer.phase === "break" ? "Đến giờ nghỉ" : timer.phase === "focus" ? "Bắt đầu tập trung" : "",
      );
    }
  }, [timer.phase]);
  useEffect(() => {
    const minutes = Math.ceil(left / 60_000);
    if (timer.phase === "focus" && !paused && minutes > 0 && minutes % 5 === 0 && lastMark.current !== minutes) {
      lastMark.current = minutes;
      setAnnouncement(`Còn ${minutes} phút`);
    }
  }, [left, timer.phase, paused]);
  return (
    <div className="activity-panel focus-panel">
      <p className="activity-progress">
        {PHASES[timer.phase]} · Lượt {timer.cycle}/{timer.cycles} ({timer.plan[0]}/{timer.plan[1]} phút)
      </p>
      <p className="focus-countdown" aria-live="off">
        {formatCountdown(left)}
      </p>
      <p className={cx.srOnly} aria-live="polite">
        {announcement}
      </p>
      {paused && (
        <p role="status">
          {timer.pausedBySelf ? "Bạn đã tạm dừng" : `${alias} đã tạm dừng`}
        </p>
      )}
      <ul className="presence">
        <li data-on={timer.selfPresent || undefined}>
          {timer.selfPresent ? "Bạn đang ở đây" : "Bạn tạm rời phiên"}
        </li>
        <li data-on={timer.peerPresent || undefined}>
          {timer.peerPresent ? `${alias} đang ở đây` : `${alias} tạm rời phiên`}
        </li>
      </ul>
      <div className={cx.actions}>
        {paused ? (
          <Button disabled={busy} onClick={() => void act("focus/resume")}>
            Tiếp tục
          </Button>
        ) : (
          <Button
            variant="secondary"
            disabled={busy || !["focus", "break"].includes(timer.phase)}
            onClick={() => void act("focus/pause")}
          >
            Tạm dừng
          </Button>
        )}
        {timer.selfPresent ? (
          <Button variant="secondary" disabled={busy} onClick={() => void act("focus/leave")}>
            Rời phiên
          </Button>
        ) : (
          <Button disabled={busy} onClick={() => void act("focus/join")}>
            Vào lại
          </Button>
        )}
        <Button variant="text" disabled={busy} onClick={() => setEnding(true)}>
          Kết thúc
        </Button>
      </div>
      {ending && (
        <Dialog title="Kết thúc phiên tập trung?" destructive onClose={() => setEnding(false)}>
          <p>Phiên sẽ kết thúc với cả hai. Số phút đã tập trung vẫn xuất hiện trong phần tổng kết.</p>
          <div className={cx.actions}>
            <Button variant="secondary" data-cancel onClick={() => setEnding(false)}>
              Tiếp tục tập trung
            </Button>
            <Button
              variant="danger"
              disabled={busy}
              onClick={() => {
                setEnding(false);
                void act("end");
              }}
            >
              Kết thúc phiên
            </Button>
          </div>
        </Dialog>
      )}
    </div>
  );
}
