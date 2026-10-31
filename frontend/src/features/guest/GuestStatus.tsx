import "./guest.css";
import { useEffect, useState } from "react";
import { cx } from "../../components/UI";
import { WARNING_MS, remainingLabel } from "./guestClock";

/**
 * Minute-granularity trial status. Only the one-time fifteen-minute notice and the end are announced
 * to assistive technology; the visible label updates quietly and is not a live region.
 */
export function GuestStatus({
  remainingMs,
  aiAvailable,
  aiTurnsRemaining,
  aiTurnsLimit,
  onEnd,
}: {
  remainingMs: number;
  aiAvailable: boolean;
  aiTurnsRemaining?: number;
  aiTurnsLimit?: number;
  onEnd?: () => void;
}) {
  const [warned, setWarned] = useState(false);
  const warning = remainingMs > 0 && remainingMs <= WARNING_MS;
  useEffect(() => {
    if (warning) setWarned(true);
  }, [warning]);
  return (
    <div className="guest-status" data-testid="guest-status">
      <p className={cx.footnote}>Đang dùng thử · còn {remainingLabel(remainingMs)}</p>
      {aiAvailable && aiTurnsRemaining != null && aiTurnsLimit != null && aiTurnsRemaining <= 10 ? (
        <p className={cx.footnote} role="status">
          {aiTurnsRemaining === 0
            ? "Bạn đã dùng hết lượt trò chuyện của lượt dùng thử."
            : `Bạn đã sử dụng ${aiTurnsLimit - aiTurnsRemaining}/${aiTurnsLimit} lượt trò chuyện trong phiên dùng thử.`}
        </p>
      ) : null}
      {onEnd ? (
        <button type="button" className="guest-end-link" onClick={onEnd}>
          Kết thúc và xóa lượt dùng thử
        </button>
      ) : null}
      <p className="visually-hidden" role="status" aria-live="polite">
        {warned ? "Phiên dùng thử còn 15 phút hoặc ít hơn." : ""}
      </p>
    </div>
  );
}
