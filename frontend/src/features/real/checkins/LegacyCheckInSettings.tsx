import { Link } from "react-router-dom";
import { Button } from "../../../components/UI";
import { botById } from "../../../companions/registry";
import { repeatLabel, slotLabel } from "./checkinsModel";
import type { ProactiveController, Schedule } from "./useProactiveSettings";

/** Preserved schedules stay attached to their original bot until an explicit action. */
export function LegacyCheckInSettings({ schedules, controller, onRemove }: {
  schedules: Schedule[];
  controller: ProactiveController;
  onRemove: (botId: Schedule["botId"]) => void;
}) {
  if (!schedules.length) return null;
  const botId = schedules[0].botId;
  const successor = schedules[0].migrateTo;
  const name = botById(botId)?.name ?? botId;
  const targetName = successor ? botById(successor)?.name ?? successor : null;
  const busy = Boolean(controller.saving);
  const status = controller.status?.key === botId ? controller.status : undefined;
  return (
    <div className="checkin-legacy" aria-busy={busy || undefined}>
      <h4>{name}</h4>
      <p className="checkin-help">
        Lịch cũ được giữ nguyên và không gửi lời hỏi thăm trong chế độ ba trợ lý.
        {targetName ? ` Bạn có thể chuyển từng lịch sang ${targetName}, giữ giờ và ngày đã chọn.` : " Bạn có thể xem, tắt hoặc xóa lịch này."}
      </p>
      <ul className="checkin-legacy-list">
        {schedules.map((schedule) => (
          <li key={schedule.slot}>
            <span>{slotLabel(schedule.slot)} · {schedule.localTime} · {repeatLabel(schedule.weekdays)} · {schedule.enabled ? "đang tạm dừng" : "đã tắt"}</span>
            <span className="checkin-legacy-actions">
              {successor && schedule.version > 0 ? <Button variant="secondary" disabled={busy} onClick={() => void controller.migrate(schedule)}>Chuyển sang {targetName}</Button> : null}
              {schedule.enabled ? <Button variant="text" disabled={busy} onClick={() => void controller.saveSchedule(schedule, { enabled: false })}>Tắt lịch</Button> : null}
            </span>
          </li>
        ))}
      </ul>
      {successor ? <Link to={`/assistants/${successor}?panel=info&section=check-ins`}>Mở lịch của {targetName}</Link> : null}
      {schedules.some((schedule) => schedule.version > 0) ? <Button variant="text" disabled={busy} onClick={() => onRemove(botId)}>Xóa lịch</Button> : null}
      <p className={`checkin-status ${status?.error ? "is-error" : ""}`} role="status">{status?.text ?? ""}</p>
    </div>
  );
}
