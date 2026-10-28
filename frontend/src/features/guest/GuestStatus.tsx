import "./guest.css";
import { useEffect, useState } from "react";
import { cx } from "../../components/UI";
import { WARNING_MS, remainingLabel } from "./guestClock";

/**
 * Minute-granularity trial status. Only the one-time five-minute notice and the end are announced
 * to assistive technology; the visible label updates quietly and is not a live region.
 */
export function GuestStatus({
  remainingMs,
  onEnd,
}: {
  remainingMs: number;
  onEnd: () => void;
}) {
  const [warned, setWarned] = useState(false);
  const warning = remainingMs > 0 && remainingMs <= WARNING_MS;
  useEffect(() => {
    if (warning) setWarned(true);
  }, [warning]);
  return (
    <div className="guest-status" data-testid="guest-status">
      <p className={cx.footnote}>Đang dùng thử · còn {remainingLabel(remainingMs)}</p>
      <button type="button" className="guest-end-link" onClick={onEnd}>
        Kết thúc và xóa lượt dùng thử
      </button>
      <p className="visually-hidden" role="status" aria-live="polite">
        {warned ? "Lượt dùng thử sắp kết thúc trong vài phút." : ""}
      </p>
    </div>
  );
}
