import { useId, useState } from "react";
import { Moon, Sun } from "lucide-react";
import { Button } from "../../../components/UI";
import type { Schedule, SchedulePatch, Settings } from "./useProactiveSettings";
import { inQuiet, nextDeliveryText, pauseUntil, repeatKind, shortDate, slotLabel, timeOptions, WEEKDAY_SHORT, weekdaysFor, type RepeatKind } from "./checkinsModel";

export function CheckInSlot({
  schedule,
  settings,
  window,
  step,
  capReached,
  cap,
  disabled,
  onSave,
  onSharedSettings,
}: {
  schedule: Schedule;
  settings: Settings;
  window: string[];
  step: number;
  capReached: boolean;
  cap: number;
  disabled: boolean;
  onSave: (patch: SchedulePatch) => void;
  onSharedSettings?: () => void;
}) {
  const id = useId();
  const [custom, setCustom] = useState(repeatKind(schedule.weekdays) === "custom");
  const label = slotLabel(schedule.slot);
  const options = timeOptions(window, step, settings.quietStart, settings.quietEnd, schedule.localTime);
  const quietCuts = timeOptions(window, step, "00:00", "00:00").some((value) => inQuiet(value, settings.quietStart, settings.quietEnd));
  const repeat: RepeatKind = custom ? "custom" : repeatKind(schedule.weekdays);
  const Icon = schedule.slot === "morning" ? Sun : Moon;
  const paused = schedule.pausedUntil;
  return (
    <div className="checkin-slot">
      <div className="checkin-slot-head">
        <label className="checkin-switch">
          <input
            type="checkbox"
            role="switch"
            checked={schedule.enabled}
            aria-disabled={capReached || disabled || (!schedule.eligibility.allowed && !schedule.enabled) || undefined}
            aria-describedby={capReached ? `${id}-cap` : undefined}
            onChange={(event) => {
              if (disabled || (capReached && event.target.checked) || (!schedule.eligibility.allowed && event.target.checked)) return;
              onSave({ enabled: event.target.checked });
            }}
          />
          <Icon size={18} aria-hidden="true" />
          <span className="checkin-slot-label">{label}</span>
          <span className="checkin-switch-state" aria-hidden="true">{schedule.enabled ? "Bật" : "Tắt"}</span>
        </label>
      </div>
      {capReached ? (
        <p id={`${id}-cap`} className="checkin-help">Bạn đã dùng {cap} lời hỏi thăm mỗi ngày. Tắt một lời khác để bật lời này.</p>
      ) : null}
      {schedule.enabled ? (
        <>
          {schedule.autoPaused ? (
            <div className="checkin-banner" role="note">
              <p>Mình tạm dừng lời hỏi thăm này vì 3 lời gần đây bạn chưa mở. Bật lại khi bạn muốn nhé.</p>
              <Button variant="secondary" disabled={disabled} onClick={() => onSave({ enabled: true })}>Bật lại</Button>
            </div>
          ) : null}
          <div className="checkin-controls">
            <label>
              <span>Giờ nhắn</span>
              <select value={schedule.localTime} aria-disabled={disabled || undefined} onChange={(event) => !disabled && onSave({ localTime: event.target.value })}>
                {options.map((value) => (
                  <option key={value} value={value} disabled={inQuiet(value, settings.quietStart, settings.quietEnd)}>{value}</option>
                ))}
              </select>
            </label>
            <label>
              <span>Lặp lại</span>
              <select
                value={repeat}
                aria-disabled={disabled || undefined}
                onChange={(event) => {
                  if (disabled) return;
                  const kind = event.target.value as RepeatKind;
                  setCustom(kind === "custom");
                  if (kind !== "custom") onSave({ weekdays: weekdaysFor(kind) });
                }}
              >
                <option value="daily">Mỗi ngày</option>
                <option value="weekdays">Ngày thường (T2–T6)</option>
                <option value="weekend">Cuối tuần</option>
                <option value="custom">Tự chọn…</option>
              </select>
            </label>
            <label>
              <span>Tạm dừng</span>
              <select
                value={paused ? "paused" : ""}
                aria-disabled={disabled || undefined}
                onChange={(event) => {
                  if (disabled) return;
                  const choice = event.target.value;
                  if (choice === "off") onSave({ enabled: false });
                  else if (choice === "") onSave({ pausedUntil: null });
                  else if (choice) onSave({ pausedUntil: pauseUntil(Number(choice), settings.timezone) });
                }}
              >
                <option value="">Không tạm dừng</option>
                {paused ? <option value="paused" disabled>Đang tạm dừng đến hết {shortDate(paused)}</option> : null}
                <option value="1">1 ngày</option>
                <option value="3">3 ngày</option>
                <option value="7">7 ngày</option>
                <option value="off">Đến khi mình bật lại</option>
              </select>
            </label>
          </div>
          {repeat === "custom" ? (
            <fieldset className="checkin-days">
              <legend>Những ngày nhắn</legend>
              {WEEKDAY_SHORT.map((name, index) => {
                const day = index + 1;
                const checked = schedule.weekdays.includes(day);
                return (
                  <label key={name}>
                    <input
                      type="checkbox"
                      checked={checked}
                      disabled={disabled || (checked && schedule.weekdays.length === 1)}
                      aria-disabled={disabled || undefined}
                      onChange={() => onSave({ weekdays: checked ? schedule.weekdays.filter((d) => d !== day) : [...schedule.weekdays, day].sort() })}
                    />
                    <span>{name}</span>
                  </label>
                );
              })}
            </fieldset>
          ) : null}
          {paused ? (
            <p className="checkin-next">
              Đang tạm dừng đến hết {shortDate(paused)}.{" "}
              <Button variant="text" disabled={disabled} onClick={() => onSave({ pausedUntil: null })}>Tiếp tục</Button>
            </p>
          ) : !schedule.autoPaused ? (
            <p className="checkin-next">{nextDeliveryText(schedule.nextDeliveryAt, settings.timezone)}</p>
          ) : null}
          {schedule.slot === "evening" && quietCuts && onSharedSettings ? (
            <p className="checkin-help"><Button variant="text" disabled={disabled} onClick={onSharedSettings}>Muốn chọn muộn hơn? Đổi giờ yên lặng</Button></p>
          ) : null}
        </>
      ) : null}
    </div>
  );
}

