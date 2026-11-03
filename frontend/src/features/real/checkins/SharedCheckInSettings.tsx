import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Button, cx } from "../../../components/UI";
import { botById } from "../../../companions/registry";
import { CheckInDialog } from "./CheckInDialog";
import { deviceZone, inQuiet, quietOptions, slotLabel, zoneLabel } from "./checkinsModel";
import type { ProactiveController, SettingsPatch } from "./useProactiveSettings";

function zones() {
  try { return Intl.supportedValuesOf("timeZone"); }
  catch { return ["Asia/Ho_Chi_Minh", "Asia/Bangkok", "Asia/Tokyo", "UTC"]; }
}

export function SharedCheckInSettings({ controller, open, onOpenChange }: {
  controller: ProactiveController;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  return (
    <div className="checkin-shared">
      <h4>Dùng chung cho mọi trợ lý</h4>
      <p className="checkin-help">Múi giờ, giờ yên lặng và chấm báo dùng chung trên toàn tài khoản.</p>
      <Button variant="secondary" onClick={() => onOpenChange(true)}>Đổi múi giờ dùng cho tất cả trợ lý</Button>
      {open ? <SharedEditor controller={controller} onClose={() => onOpenChange(false)} /> : null}
    </div>
  );
}

function SharedEditor({ controller, onClose }: { controller: ProactiveController; onClose: () => void }) {
  const { view, saving, status } = controller;
  const settings = view!.settings;
  const [draft, setDraft] = useState<SettingsPatch>({});
  const timezone = draft.timezone ?? settings.timezone;
  const quietStart = draft.quietStart ?? settings.quietStart;
  const quietEnd = draft.quietEnd ?? settings.quietEnd;
  const badgesEnabled = draft.badgesEnabled ?? settings.badgesEnabled;
  const [query, setQuery] = useState("");
  const allZones = useMemo(zones, []);
  const options = quietOptions();
  const matches = allZones.filter((zone) => zone.toLowerCase().includes(query.trim().toLowerCase().replace(/\s+/g, "_"))).slice(0, 200);
  const affected = view!.schedules.filter((schedule) => schedule.version > 0 && !schedule.legacy);
  const conflicts = affected.filter((schedule) => schedule.enabled && inQuiet(schedule.localTime, quietStart, quietEnd));
  const busy = Boolean(saving);
  return (
    <CheckInDialog title="Dùng chung cho mọi trợ lý" onClose={onClose}>
      <p>Giờ địa phương của mọi lịch được giữ nguyên khi đổi múi giờ. Thời điểm gửi tiếp theo được tính lại theo múi giờ mới. Ngày của nhật ký vẫn theo múi giờ tài khoản.</p>
      {controller.error ? <div role="alert"><p>Chưa tải lại được lịch. Kiểm tra kết nối rồi thử lại.</p><Button variant="secondary" disabled={busy} onClick={() => void controller.load()}>Tải lại lịch</Button></div> : null}
      <label className="checkin-zone-search"><span>Tìm múi giờ</span><input disabled={busy} value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Ví dụ: Tokyo" /></label>
      <label className="checkin-zone-search"><span>Múi giờ</span><select disabled={busy} value={timezone} onChange={(event) => setDraft((value) => ({ ...value, timezone: event.target.value }))}>
        {[...new Set([timezone, ...matches])].map((zone) => <option key={zone} value={zone}>{zoneLabel(zone)} — {zone}</option>)}
      </select></label>
      {deviceZone() !== timezone ? <Button variant="text" disabled={busy} onClick={() => setDraft((value) => ({ ...value, timezone: deviceZone() }))}>Dùng múi giờ của thiết bị ({zoneLabel(deviceZone())})</Button> : null}
      <fieldset className="checkin-quiet" disabled={busy}>
        <legend>Giờ yên lặng</legend>
        <p className="checkin-help">Trợ lý không nhắn trong khoảng này. Cần dài từ 4 đến 12 tiếng.</p>
        <div className="checkin-controls">
          <label><span>Bắt đầu</span><select value={quietStart} onChange={(event) => setDraft((value) => ({ ...value, quietStart: event.target.value }))}>{options.map((value) => <option key={value}>{value}</option>)}</select></label>
          <label><span>Kết thúc</span><select value={quietEnd} onChange={(event) => setDraft((value) => ({ ...value, quietEnd: event.target.value }))}>{options.map((value) => <option key={value}>{value}</option>)}</select></label>
        </div>
      </fieldset>
      <label className="checkin-check"><input type="checkbox" disabled={busy} checked={badgesEnabled} onChange={(event) => setDraft((value) => ({ ...value, badgesEnabled: event.target.checked }))} /><span>Hiện chấm báo khi có lời nhắn mới</span></label>
      <div className="checkin-impact">
        <h3>Các lịch chịu ảnh hưởng</h3>
        {affected.length ? <ul>{affected.map((schedule) => <li key={`${schedule.botId}/${schedule.slot}`}><Link to={`/assistants/${schedule.botId}?panel=info&section=check-ins`} onClick={onClose}>{botById(schedule.botId)?.name ?? schedule.botId} · {slotLabel(schedule.slot)} · {schedule.localTime}{schedule.enabled ? "" : " · đã tắt"}</Link></li>)}</ul> : <p>Chưa có lịch đã lưu. Cài đặt này sẽ dùng cho mọi lịch bạn tạo sau này.</p>}
      </div>
      {conflicts.length ? <div className="checkin-note" role="alert"><p>Giờ yên lặng này trùng với lịch đang bật. Mở lịch để đổi giờ hoặc tắt trước khi lưu:</p><ul>{conflicts.map((schedule) => <li key={`${schedule.botId}/${schedule.slot}`}><Link to={`/assistants/${schedule.botId}?panel=info&section=check-ins`} onClick={onClose}>{botById(schedule.botId)?.name ?? schedule.botId} · {slotLabel(schedule.slot)} · {schedule.localTime}</Link></li>)}</ul></div> : null}
      <p className={`checkin-status ${status?.error ? "is-error" : ""}`} role="status">{status?.key === "general" ? status.text : busy ? "Đang lưu…" : ""}</p>
      <div className={cx.actions}>
        <Button variant="secondary" onClick={onClose}>Đóng</Button>
        <Button disabled={busy || conflicts.length > 0} onClick={async () => {
          // Submit changed fields only so a stale panel cannot replay unrelated consent/settings.
          const patch = {
            ...(draft.timezone !== undefined && timezone !== settings.timezone ? { timezone } : {}),
            ...(draft.quietStart !== undefined && quietStart !== settings.quietStart ? { quietStart } : {}),
            ...(draft.quietEnd !== undefined && quietEnd !== settings.quietEnd ? { quietEnd } : {}),
            ...(draft.badgesEnabled !== undefined && badgesEnabled !== settings.badgesEnabled ? { badgesEnabled } : {}),
          };
          if (Object.keys(patch).length && await controller.saveSettings(patch)) setDraft({});
        }}>{busy ? "Đang lưu…" : "Lưu cài đặt chung"}</Button>
      </div>
    </CheckInDialog>
  );
}
