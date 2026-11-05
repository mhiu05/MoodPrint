import { useState } from "react";
import { Link } from "react-router-dom";
import type { ApiClient } from "../../../api/client";
import type { SessionView } from "../../../api/contracts";
import { Button, cx } from "../../../components/UI";
import { botById, type BotId } from "../../../companions/registry";
import { CheckInDialog, useCheckInDialog } from "./CheckInDialog";
import { CheckInSlot } from "./CheckInSlot";
import { LegacyCheckInSettings } from "./LegacyCheckInSettings";
import { SharedCheckInSettings } from "./SharedCheckInSettings";
import { socialEligibilityText, zoneLabel } from "./checkinsModel";
import { useProactiveSettings } from "./useProactiveSettings";
import "./checkins.css";

export type AgentCheckInSettingsProps = {
  api: ApiClient;
  session: Pick<SessionView, "userId" | "features">;
  /** Route owner, independent of the active speaker or a conversation ID. */
  botId: BotId;
  botName?: string;
  onChildModalChange?: (open: boolean) => void;
};

export function AgentCheckInSettings({ api, session, botId, botName, onChildModalChange }: AgentCheckInSettingsProps) {
  const controller = useProactiveSettings(api, session.userId);
  const { view, loading, error, status, saving } = controller;
  const [sharedOpen, setSharedOpen] = useState(false);
  const [removeBot, setRemoveBot] = useState<BotId>();
  const [journalHelp, setJournalHelp] = useState(false);
  const modal = useCheckInDialog(onChildModalChange);
  const name = botName ?? botById(botId)?.name ?? botId;
  const journalBot = session.features.threeAgents ? "nhatky" : "nhip";
  const schedules = view?.schedules.filter((schedule) => schedule.botId === botId) ?? [];
  const legacy = schedules.some((schedule) => schedule.legacy);
  const kept = view?.schedules.filter((schedule) => schedule.legacy && schedule.migrateTo === botId && schedule.version > 0) ?? [];
  const legacyIds = [...new Set(kept.map((schedule) => schedule.botId))];
  const busy = Boolean(saving);
  const closeRemove = () => { setRemoveBot(undefined); modal(false); };
  const askRemove = (target: BotId) => { modal(true); setRemoveBot(target); };
  const changeShared = (open: boolean) => { modal(open); setSharedOpen(open); };
  const openShared = () => changeShared(true);
  return (
    <section className="agent-checkin-settings" aria-labelledby={`agent-check-ins-${botId}`}>
      <h3 id={`agent-check-ins-${botId}`} tabIndex={-1}>Lời hỏi thăm của {name}</h3>
      <p className="checkin-help">Lịch này dùng cho {name} qua mọi cuộc trò chuyện.</p>
      {loading ? <p role="status">Đang tải lịch hỏi thăm…</p> : null}
      {error ? <div className="checkin-note" role="alert"><p>Chưa tải được lịch hỏi thăm. Kiểm tra kết nối rồi thử lại.</p><Button variant="secondary" disabled={busy} onClick={() => void controller.load()}>Tải lại lịch</Button></div> : null}
      {!loading && view ? !view.available ? <p className="checkin-note">Lời hỏi thăm chưa mở cho tài khoản của bạn.</p> : (
        <>
          <p className="checkins-meta"><span>Đang dùng {view.limits.enabledSlots}/{view.limits.dailyCap} trên toàn tài khoản</span><span>Múi giờ: {zoneLabel(view.settings.timezone)} · {view.settings.timezone}</span></p>
          {legacy ? <LegacyCheckInSettings schedules={schedules} controller={controller} onRemove={askRemove} /> : (
            <>
              {!schedules.length ? <p>Chưa có lịch cho trợ lý này.</p> : null}
              {schedules.map((schedule) => <div key={schedule.slot}>
                {!schedule.eligibility.allowed ? <p className="checkin-note">{socialEligibilityText(schedule.eligibility.reason) ?? "Trợ lý chưa thể hỏi thăm với tài khoản hiện tại. Lịch đã lưu vẫn được giữ; bạn có thể tắt hoặc xóa."}</p> : null}
                <CheckInSlot schedule={schedule} settings={view.settings} window={view.limits.windows[schedule.slot] ?? []} step={view.limits.stepMinutes}
                  capReached={view.limits.enabledSlots >= view.limits.dailyCap && !schedule.enabled} cap={view.limits.dailyCap} disabled={busy}
                  onSave={(patch) => void controller.saveSchedule(schedule, patch)} onSharedSettings={openShared} />
              </div>)}
              {schedules.some((schedule) => schedule.version > 0) ? <div className="checkin-card-actions"><Button variant="text" disabled={busy} onClick={() => askRemove(botId)}>Xóa lịch</Button></div> : null}
            </>
          )}
          {!legacy && botId === journalBot ? <div className="checkin-journal">
            <label className="checkin-check"><input type="checkbox" checked={view.settings.journalContextEnabled} disabled={busy} onChange={(event) => void controller.saveSettings({ journalContextEnabled: event.target.checked }, botId)} /><span>Dùng khoảnh khắc đã lưu hôm qua</span></label>
            <p className="checkin-help">Dùng tối đa 3 khoảnh khắc đã lưu hôm qua để gợi ý một việc nhỏ. Khi phối hợp, các trợ lý có thể dùng tóm tắt trong phạm vi được phép; không cấp quyền xem nguyên văn cho mọi trợ lý. Không đọc bản nháp, ảnh hay âm thanh. <Button variant="text" onClick={() => { modal(true); setJournalHelp(true); }}>Tìm hiểu thêm</Button></p>
          </div> : !legacy ? <p className="checkin-help"><Link to={`/assistants/${journalBot}?panel=info&section=check-ins`}>Quản lý quyền dùng khoảnh khắc đã lưu tại {botById(journalBot)?.name ?? "Nhật ký"}</Link></p> : null}
          {legacyIds.length ? <details className="checkin-kept"><summary>Lịch cũ</summary>{legacyIds.map((id) => <LegacyCheckInSettings key={id} schedules={kept.filter((schedule) => schedule.botId === id)} controller={controller} onRemove={askRemove} />)}</details> : null}
          <SharedCheckInSettings controller={controller} open={sharedOpen} onOpenChange={changeShared} />
          {!legacy ? <p className={`checkin-status ${status?.error ? "is-error" : ""}`} role="status">{saving === botId ? "Đang lưu…" : status?.key === botId ? status.text : ""}</p> : null}
        </>
      ) : null}
      {removeBot ? <CheckInDialog destructive title={`Xóa lịch hỏi thăm của ${botById(removeBot)?.name ?? name}?`} onClose={closeRemove}>
        <p>Các lời hỏi thăm đã nhận vẫn còn trong cuộc trò chuyện.</p>
        <p className={`checkin-status ${status?.error ? "is-error" : ""}`} role="status">{status?.key === removeBot ? status.text : ""}</p>
        <div className={cx.actions}><Button variant="secondary" data-cancel onClick={closeRemove}>Giữ lại</Button><Button variant="danger" disabled={busy} onClick={async () => { if (await controller.remove(removeBot)) closeRemove(); }}>Xóa lịch</Button></div>
      </CheckInDialog> : null}
      {journalHelp ? <CheckInDialog title={`${name} dùng khoảnh khắc hôm qua như thế nào?`} onClose={() => { setJournalHelp(false); modal(false); }}>
        <p>Mỗi sáng bạn đã hẹn, {name} đọc tối đa 3 khoảnh khắc đã lưu hôm qua (chữ, cảm xúc, yếu tố bạn chọn) để gợi ý một việc nhỏ. Không đọc bản nháp, ảnh, âm thanh hoặc video.</p>
        <p>Khi phối hợp được phép, trợ lý có thể sử dụng tóm tắt trong giới hạn hiện có. Quyền này không bật lịch, không cho mọi trợ lý xem nguyên văn và không chia sẻ với người khác.</p>
        <p>Bạn có thể tắt bất cứ lúc nào. Lời hỏi thăm đã nhận vẫn nằm trong lịch sử cho đến khi cuộc trò chuyện hết hạn hoặc bạn xóa.</p>
        <div className={cx.actions}><Button onClick={() => { setJournalHelp(false); modal(false); }}>Đã hiểu</Button></div>
      </CheckInDialog> : null}
    </section>
  );
}
