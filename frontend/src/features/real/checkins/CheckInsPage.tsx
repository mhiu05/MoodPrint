import { useCallback, useEffect, useId, useMemo, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Moon, Sun } from "lucide-react";
import type { components } from "../../../api/generated/schema";
import type { BotPublicDTO } from "../../../api/contracts";
import { ApiError } from "../../../api/client";
import { Button, cx, Dialog, StatePanel } from "../../../components/UI";
import { BotAvatar } from "../../../companions/Avatar";
import { botById } from "../../../companions/registry";
import { ErrorNotice, useResource, useSession } from "../RealApp";
import {
  BOT_ORDER,
  checkInError,
  deviceZone,
  inQuiet,
  nextDeliveryText,
  pauseUntil,
  quietOptions,
  repeatKind,
  shortDate,
  slotLabel,
  timeOptions,
  WEEKDAY_SHORT,
  weekdaysFor,
  zoneLabel,
  type RepeatKind,
  type Slot,
} from "./checkinsModel";
import "./checkins.css";

type View = components["schemas"]["ProactiveView"];
type Schedule = components["schemas"]["ScheduleView"];
type Settings = components["schemas"]["ProactiveSettingsView"];
type SchedulePatch = Partial<Pick<Schedule, "enabled" | "localTime" | "weekdays" | "pausedUntil">>;
type CardStatus = { key: string; text: string; error?: boolean };

const SLOTS: Slot[] = ["morning", "evening"];

function zones(): string[] {
  const supported = (Intl as unknown as { supportedValuesOf?: (key: string) => string[] }).supportedValuesOf;
  try {
    return supported ? supported("timeZone") : ["Asia/Ho_Chi_Minh", "Asia/Bangkok"];
  } catch {
    return ["Asia/Ho_Chi_Minh", "Asia/Bangkok"];
  }
}

export function CheckInsPage() {
  const { api, session } = useSession();
  const [params] = useSearchParams();
  const bots = useResource<BotPublicDTO[]>("/bots");
  // V3: names of legacy companions whose kept (paused) schedules are listed below the agents.
  const legacyBots = useResource<BotPublicDTO[]>("/bots/legacy", session.features.threeAgents);
  const [view, setView] = useState<View>();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>();
  const [saving, setSaving] = useState<string | null>(null);
  const [status, setStatus] = useState<CardStatus>();
  const [journalHelp, setJournalHelp] = useState(false);
  const [zoneOpen, setZoneOpen] = useState(false);
  const [removeBot, setRemoveBot] = useState<string>();
  const focused = useRef(false);

  const load = useCallback(async () => {
    setError(undefined);
    try {
      setView(await api.request<View>("/ai/proactive"));
    } catch (reason) {
      setError(reason);
    } finally {
      setLoading(false);
    }
  }, [api]);
  useEffect(() => {
    void load();
  }, [load]);
  useEffect(() => {
    // /check-ins?bot=nhip lands on that companion (the app already uses the URL hash for routing).
    const target = params.get("bot");
    if (!view || !target || focused.current) return;
    focused.current = true;
    requestAnimationFrame(() => document.getElementById(`checkin-${target}`)?.focus());
  }, [view, params]);

  const failure = useCallback(async (key: string, reason: unknown) => {
    const code = reason instanceof ApiError ? reason.code : undefined;
    if (code === "STALE_VERSION") await load();
    setStatus({
      key,
      text: checkInError(code, view?.limits.dailyCap, view?.limits.windows.evening?.[1]),
      error: true,
    });
  }, [load, view]);

  async function saveSchedule(schedule: Schedule, patch: SchedulePatch) {
    const key = schedule.botId;
    if (saving) return;
    setSaving(key);
    setStatus(undefined);
    const body = {
      enabled: schedule.enabled,
      localTime: schedule.localTime,
      weekdays: schedule.weekdays,
      pausedUntil: schedule.pausedUntil ?? null,
      expectedVersion: schedule.version,
      ...patch,
    };
    const before = view;
    // Optimistic: the control moves at once; the card stays locked until the server answers.
    setView((value) => value && {
      ...value,
      schedules: value.schedules.map((item) => (item === schedule ? { ...item, ...patch } : item)),
    });
    try {
      const next = await api.request<Schedule>(`/ai/proactive/schedules/${schedule.botId}/${schedule.slot}`, {
        method: "PUT",
        body,
      });
      setView((value) => {
        if (!value) return value;
        const schedules = value.schedules.map((item) =>
          item.botId === next.botId && item.slot === next.slot ? next : item,
        );
        return { ...value, schedules, limits: { ...value.limits, enabledSlots: schedules.filter((s) => s.enabled && !s.legacy).length } };
      });
      // The first saved schedule also creates the settings row on the server.
      if (before?.settings.version === 0) await load();
      setStatus({ key, text: "Đã lưu" });
    } catch (reason) {
      setView(before);
      await failure(key, reason);
    } finally {
      setSaving(null);
    }
  }

  /** V3: explicitly move a kept legacy schedule to the agent that took over its purpose. */
  async function migrateSchedule(schedule: Schedule) {
    const key = schedule.botId;
    if (saving || !schedule.migrateTo) return;
    setSaving(key);
    setStatus(undefined);
    try {
      await api.request<Schedule>(`/ai/proactive/schedules/${schedule.botId}/${schedule.slot}/migrate`, {
        method: "POST",
        body: { expectedVersion: schedule.version },
      });
      await load();
      const target = schedule.migrateTo;
      setStatus({ key: target, text: "Đã chuyển lịch sang đây" });
      requestAnimationFrame(() => document.getElementById(`checkin-${target}`)?.focus());
    } catch (reason) {
      await failure(key, reason);
    } finally {
      setSaving(null);
    }
  }

  async function saveSettings(patch: Partial<Settings>, key = "general") {
    if (!view || saving) return;
    setSaving(key);
    setStatus(undefined);
    const current = view.settings;
    setView((value) => value && { ...value, settings: { ...value.settings, ...patch } });
    const put = (base: Settings) => api.request<Settings>("/ai/proactive/settings", {
      method: "PUT",
      body: {
        timezone: base.timezone,
        quietStart: base.quietStart,
        quietEnd: base.quietEnd,
        badgesEnabled: base.badgesEnabled,
        journalContextEnabled: base.journalContextEnabled,
        policyVersion: base.policyVersion,
        ...patch,
        expectedVersion: base.version,
      },
    });
    try {
      let next: Settings;
      try {
        next = await put(current);
      } catch (reason) {
        if (!(reason instanceof ApiError && reason.code === "STALE_VERSION")) throw reason;
        // Another save moved the version (e.g. this page's own first schedule). The patch only
        // carries the one control the person changed, so apply it once on the fresh state.
        const fresh = await api.request<View>("/ai/proactive");
        next = await put(fresh.settings);
      }
      const timing = next.timezone !== current.timezone || next.quietStart !== current.quietStart || next.quietEnd !== current.quietEnd;
      setView((value) => (value ? { ...value, settings: next } : value));
      if (timing) await load(); // next delivery times move with the time zone
      setStatus({ key, text: "Đã lưu" });
    } catch (reason) {
      setView((value) => value && { ...value, settings: current });
      await failure(key, reason);
    } finally {
      setSaving(null);
    }
  }

  async function removeSchedules(botId: string) {
    if (!view || saving) return;
    setSaving(botId);
    setStatus(undefined);
    try {
      for (const schedule of view.schedules.filter((s) => s.botId === botId && s.version > 0)) {
        await api.request(`/ai/proactive/schedules/${botId}/${schedule.slot}`, {
          method: "DELETE",
          body: { expectedVersion: schedule.version },
        });
      }
      await load();
      setStatus({ key: botId, text: "Đã xóa lịch hỏi thăm" });
    } catch (reason) {
      await failure(botId, reason);
    } finally {
      setSaving(null);
      setRemoveBot(undefined);
    }
  }

  const botInfo = useMemo(
    () => new Map<string, BotPublicDTO>([...(legacyBots.data ?? []), ...(bots.data ?? [])].map((bot) => [bot.botId, bot])),
    [bots.data, legacyBots.data],
  );
  // The server orders the companions: the three agents first, then kept legacy schedules (V3).
  const order = view ? [...new Set(view.schedules.map((item) => item.botId))] : [...BOT_ORDER];

  if (loading) return <div className={cx.reading}><h1 tabIndex={-1}>Lời hỏi thăm từ trợ lý</h1><p role="status">Đang tải lịch hỏi thăm…</p></div>;
  if (!view) {
    return (
      <div className={cx.reading}>
        <h1 tabIndex={-1}>Lời hỏi thăm từ trợ lý</h1>
        <ErrorNotice error={error} retry={() => void load()} />
      </div>
    );
  }
  if (!view.available) {
    return (
      <div className={cx.reading}>
        <h1 tabIndex={-1}>Lời hỏi thăm từ trợ lý</h1>
        <StatePanel title="Lời hỏi thăm chưa mở cho tài khoản của bạn.">
          Khi tính năng sẵn sàng, bạn có thể hẹn giờ để trợ lý nhắn hỏi thăm.
        </StatePanel>
        <div className={cx.actions}><Link className={`${cx.button} ${cx.secondary}`} to="/assistants">Về trợ lý</Link></div>
      </div>
    );
  }
  const { settings, limits } = view;
  const capReached = limits.enabledSlots >= limits.dailyCap;
  return (
    <div className={`${cx.reading} checkins-page`}>
      <h1 tabIndex={-1}>Lời hỏi thăm từ trợ lý</h1>
      <p className="checkins-intro">
        Trợ lý chỉ nhắn vào giờ bạn chọn và không nhắn trong giờ yên lặng. Bạn có thể tắt bất cứ lúc nào.
        Tối đa {limits.dailyCap} lời mỗi ngày.
      </p>
      <p className="checkins-meta">
        <span>Đang dùng {limits.enabledSlots}/{limits.dailyCap}</span>
        <span aria-hidden="true">·</span>
        <span>Múi giờ: {zoneLabel(settings.timezone)}</span>
        <Button variant="text" onClick={() => setZoneOpen(true)} aria-disabled={Boolean(saving) || undefined}>Đổi múi giờ</Button>
      </p>
      {limits.enabledSlots === 0 ? (
        <p className="checkins-empty">Chưa có trợ lý nào hỏi thăm bạn. Bật buổi sáng hoặc buổi tối ở một trợ lý bạn thích.</p>
      ) : null}
      <ErrorNotice error={error} retry={() => void load()} />
      {order.map((botId) => {
        const info = botInfo.get(botId);
        const schedules = SLOTS.map((slot) => view.schedules.find((s) => s.botId === botId && s.slot === slot)!).filter(Boolean);
        if (!schedules.length) return null;
        if (schedules[0].legacy) {
          return (
            <LegacyCard
              key={botId}
              botId={botId}
              name={info?.name ?? botId}
              successor={schedules[0].migrateTo ? botInfo.get(schedules[0].migrateTo)?.name ?? null : null}
              schedules={schedules}
              busy={saving === botId}
              status={status?.key === botId ? status : undefined}
              onMigrate={(schedule) => void migrateSchedule(schedule)}
              onDisable={(schedule) => void saveSchedule(schedule, { enabled: false })}
              onRemove={() => setRemoveBot(botId)}
            />
          );
        }
        const reason = schedules[0].eligibility.reason;
        const busy = saving === botId;
        const cardStatus = status?.key === botId ? status : undefined;
        return (
          <section key={botId} className="checkin-card" aria-labelledby={`checkin-${botId}`} aria-busy={busy || undefined}>
            <div className="checkin-card-head">
              {botById(botId) ? <BotAvatar id={botById(botId)!.id} size={40} /> : null}
              <div>
                <h2 id={`checkin-${botId}`} tabIndex={-1}>{info?.name ?? botId}</h2>
                {info?.role ? <p>{info.role}</p> : null}
              </div>
            </div>
            {reason && !schedules.some((s) => s.enabled) ? (
              <Ineligible reason={reason} />
            ) : (
              schedules.map((schedule) => (
                <SlotRow
                  key={schedule.slot}
                  schedule={schedule}
                  settings={settings}
                  window={limits.windows[schedule.slot] ?? []}
                  step={limits.stepMinutes}
                  capReached={capReached && !schedule.enabled}
                  cap={limits.dailyCap}
                  disabled={Boolean(saving)}
                  onSave={(patch) => void saveSchedule(schedule, patch)}
                />
              ))
            )}
            {botId === "nhip" || botId === "nhatky" ? (
              <div className="checkin-journal">
                <label className="checkin-check">
                  <input
                    type="checkbox"
                    checked={settings.journalContextEnabled}
                    aria-disabled={Boolean(saving) || undefined}
                    onChange={(event) => void saveSettings({ journalContextEnabled: event.target.checked }, botId)}
                  />
                  <span>Dùng khoảnh khắc đã lưu hôm qua</span>
                </label>
                <p className="checkin-help">
                  Mỗi sáng, {info?.name ?? "Nhịp"} chỉ đọc khoảnh khắc đã lưu của ngày hôm qua để gợi ý một việc nhỏ. Không đọc bản nháp, ảnh, âm thanh.{" "}
                  <Button variant="text" onClick={() => setJournalHelp(true)}>Tìm hiểu thêm</Button>
                </p>
              </div>
            ) : null}
            {schedules.some((s) => s.version > 0) ? (
              <div className="checkin-card-actions">
                <Button variant="text" aria-disabled={Boolean(saving) || undefined} onClick={() => setRemoveBot(botId)}>Xóa lịch</Button>
              </div>
            ) : null}
            <p className={`checkin-status ${cardStatus?.error ? "is-error" : ""}`} role="status">{cardStatus?.text ?? ""}</p>
          </section>
        );
      })}
      <section className="checkin-card" aria-labelledby="checkin-general">
        <h2 id="checkin-general" tabIndex={-1}>Cài đặt chung</h2>
        <QuietHours settings={settings} disabled={Boolean(saving)} onSave={(quietStart, quietEnd) => void saveSettings({ quietStart, quietEnd })} />
        <label className="checkin-check">
          <input
            type="checkbox"
            checked={settings.badgesEnabled}
            aria-disabled={Boolean(saving) || undefined}
            onChange={(event) => void saveSettings({ badgesEnabled: event.target.checked })}
          />
          <span>Hiện chấm báo khi có lời nhắn mới</span>
        </label>
        <p className={`checkin-status ${status?.key === "general" && status.error ? "is-error" : ""}`} role="status">
          {status?.key === "general" ? status.text : ""}
        </p>
      </section>
      {journalHelp ? (
        <Dialog title="Nhịp dùng khoảnh khắc hôm qua như thế nào?" onClose={() => setJournalHelp(false)}>
          <p>
            Mỗi sáng bạn đã hẹn, Nhịp đọc tối đa 3 khoảnh khắc <strong>đã lưu</strong> của ngày hôm qua (chữ, cảm xúc, yếu tố bạn chọn) để gợi ý một việc nhỏ cho hôm nay.
            Nhịp không đọc bản nháp, ảnh, âm thanh, video, và không chia sẻ với trợ lý khác hay với bạn kết nối.
          </p>
          <p>Nếu hôm qua bạn không viết gì, Nhịp chỉ chào bình thường.</p>
          <p>
            Bạn tắt lúc nào cũng được; khi tắt, Nhịp ngừng dùng ngay cả những lời gợi ý cũ trong cuộc trò chuyện.
            Lời hỏi thăm đã nhận vẫn nằm trong lịch sử trò chuyện cho tới khi cuộc trò chuyện hết hạn hoặc bạn xóa.
          </p>
          <div className={cx.actions}><Button onClick={() => setJournalHelp(false)}>Đã hiểu</Button></div>
        </Dialog>
      ) : null}
      {zoneOpen ? (
        <ZoneDialog
          current={settings.timezone}
          onClose={() => setZoneOpen(false)}
          onChoose={(timezone) => {
            setZoneOpen(false);
            if (timezone !== settings.timezone) void saveSettings({ timezone });
          }}
        />
      ) : null}
      {removeBot ? (
        <Dialog destructive title={`Xóa lịch hỏi thăm của ${botInfo.get(removeBot)?.name ?? "trợ lý"}?`} onClose={() => setRemoveBot(undefined)}>
          <p>Các lời hỏi thăm đã nhận vẫn còn trong cuộc trò chuyện.</p>
          <div className={cx.actions}>
            <Button variant="secondary" data-cancel onClick={() => setRemoveBot(undefined)}>Giữ lại</Button>
            <Button variant="danger" disabled={Boolean(saving)} onClick={() => void removeSchedules(removeBot)}>Xóa lịch</Button>
          </div>
        </Dialog>
      ) : null}
    </div>
  );
}

function LegacyCard({
  botId, name, successor, schedules, busy, status, onMigrate, onDisable, onRemove,
}: {
  botId: string;
  name: string;
  successor: string | null;
  schedules: Schedule[];
  busy: boolean;
  status?: CardStatus;
  onMigrate: (schedule: Schedule) => void;
  onDisable: (schedule: Schedule) => void;
  onRemove: () => void;
}) {
  const slotName = (slot: string) => (slot === "morning" ? "Buổi sáng" : "Buổi tối");
  return (
    <section className="checkin-card checkin-legacy" aria-labelledby={`checkin-${botId}`} aria-busy={busy || undefined}>
      <div className="checkin-card-head">
        {botById(botId) ? <BotAvatar id={botById(botId)!.id} size={40} /> : null}
        <div>
          <h2 id={`checkin-${botId}`} tabIndex={-1}>{name} <span className="history-legacy">Lịch cũ</span></h2>
          <p>
            Lịch này đang tạm dừng và chưa bị xóa.{" "}
            {successor ? `Bạn có thể chuyển nó sang ${successor} với cùng giờ và ngày.` : "Tìm bạn giờ là một mục riêng, nên lịch này chỉ có thể tắt."}
          </p>
        </div>
      </div>
      <ul className="checkin-legacy-list">
        {schedules.map((schedule) => (
          <li key={schedule.slot}>
            <span>{slotName(schedule.slot)} · {schedule.localTime} · {schedule.enabled ? "đang tạm dừng" : "đã tắt"}</span>
            {schedule.enabled ? (
              <span className="checkin-legacy-actions">
                {successor ? (
                  <Button variant="secondary" aria-disabled={busy || undefined} onClick={() => !busy && onMigrate(schedule)}>
                    Chuyển sang {successor}
                  </Button>
                ) : null}
                <Button variant="text" aria-disabled={busy || undefined} onClick={() => !busy && onDisable(schedule)}>Tắt lịch</Button>
              </span>
            ) : null}
          </li>
        ))}
      </ul>
      {schedules.every((s) => !s.enabled) ? (
        <div className="checkin-card-actions">
          <Button variant="text" aria-disabled={busy || undefined} onClick={onRemove}>Xóa lịch</Button>
        </div>
      ) : null}
      <p className={`checkin-status ${status?.error ? "is-error" : ""}`} role="status">{status?.text ?? ""}</p>
    </section>
  );
}

function Ineligible({ reason }: { reason: string }) {
  if (reason === "teen_social_unavailable") return <p className="checkin-note">Cầu Nối chỉ dành cho tài khoản từ 18 tuổi.</p>;
  if (reason === "social_not_enabled") {
    return (
      <p className="checkin-note">
        Cần bật tính năng kết nối để Cầu Nối hỏi thăm. <Link to="/connect">Mở cài đặt kết nối</Link>
      </p>
    );
  }
  if (reason === "social_restricted") return <p className="checkin-note">Tính năng kết nối của bạn đang tạm bị hạn chế.</p>;
  return <p className="checkin-note">Trợ lý này chưa thể hỏi thăm với tài khoản hiện tại.</p>;
}

function SlotRow({
  schedule,
  settings,
  window,
  step,
  capReached,
  cap,
  disabled,
  onSave,
}: {
  schedule: Schedule;
  settings: Settings;
  window: string[];
  step: number;
  capReached: boolean;
  cap: number;
  disabled: boolean;
  onSave: (patch: SchedulePatch) => void;
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
            aria-disabled={capReached || disabled || undefined}
            aria-describedby={capReached ? `${id}-cap` : undefined}
            onChange={(event) => {
              if (capReached && event.target.checked) return;
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
              <Button variant="secondary" aria-disabled={disabled || undefined} onClick={() => onSave({ enabled: true })}>Bật lại</Button>
            </div>
          ) : null}
          <div className="checkin-controls">
            <label>
              <span>Giờ nhắn</span>
              <select value={schedule.localTime} aria-disabled={disabled || undefined} onChange={(event) => onSave({ localTime: event.target.value })}>
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
                value=""
                aria-disabled={disabled || undefined}
                onChange={(event) => {
                  const choice = event.target.value;
                  if (choice === "off") onSave({ enabled: false });
                  else if (choice) onSave({ pausedUntil: pauseUntil(Number(choice), settings.timezone) });
                }}
              >
                <option value="">Không tạm dừng</option>
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
                      disabled={checked && schedule.weekdays.length === 1}
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
              <Button variant="text" aria-disabled={disabled || undefined} onClick={() => onSave({ pausedUntil: null })}>Tiếp tục</Button>
            </p>
          ) : !schedule.autoPaused ? (
            <p className="checkin-next">{nextDeliveryText(schedule.nextDeliveryAt, settings.timezone)}</p>
          ) : null}
          {schedule.slot === "evening" && quietCuts ? (
            <p className="checkin-help"><a href="#checkin-general" onClick={(event) => { event.preventDefault(); document.getElementById("checkin-general")?.focus(); }}>Muốn chọn muộn hơn? Đổi giờ yên lặng</a></p>
          ) : null}
        </>
      ) : null}
    </div>
  );
}

function QuietHours({ settings, disabled, onSave }: { settings: Settings; disabled: boolean; onSave: (start: string, end: string) => void }) {
  const options = quietOptions();
  return (
    <fieldset className="checkin-quiet">
      <legend>Giờ yên lặng</legend>
      <p className="checkin-help">Trợ lý không nhắn trong khoảng này. Cần dài từ 4 đến 12 tiếng.</p>
      <div className="checkin-controls">
        <label>
          <span>Bắt đầu</span>
          <select value={settings.quietStart} aria-disabled={disabled || undefined} onChange={(event) => onSave(event.target.value, settings.quietEnd)}>
            {options.map((value) => <option key={value} value={value}>{value}</option>)}
          </select>
        </label>
        <label>
          <span>Kết thúc</span>
          <select value={settings.quietEnd} aria-disabled={disabled || undefined} onChange={(event) => onSave(settings.quietStart, event.target.value)}>
            {options.map((value) => <option key={value} value={value}>{value}</option>)}
          </select>
        </label>
      </div>
    </fieldset>
  );
}

function ZoneDialog({ current, onClose, onChoose }: { current: string; onClose: () => void; onChoose: (zone: string) => void }) {
  const device = deviceZone();
  const all = useMemo(zones, []);
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState(current);
  const matches = all.filter((zone) => zone.toLowerCase().includes(query.trim().toLowerCase().replace(/\s+/g, "_"))).slice(0, 200);
  return (
    <Dialog title="Đổi múi giờ hỏi thăm" onClose={onClose}>
      <p>Giờ hỏi thăm theo múi giờ này. Ngày của nhật ký vẫn theo múi giờ tài khoản.</p>
      {device !== current ? (
        <div className={cx.actions}>
          <Button variant="secondary" onClick={() => onChoose(device)}>Dùng múi giờ của thiết bị ({zoneLabel(device)})</Button>
        </div>
      ) : null}
      <label className="checkin-zone-search">
        <span>Tìm múi giờ</span>
        <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Ví dụ: Tokyo" />
      </label>
      <label className="checkin-zone-search">
        <span>Múi giờ</span>
        <select value={selected} onChange={(event) => setSelected(event.target.value)} size={6}>
          {[...new Set([selected, ...matches])].map((zone) => <option key={zone} value={zone}>{zoneLabel(zone)} — {zone}</option>)}
        </select>
      </label>
      <div className={cx.actions}>
        <Button variant="secondary" onClick={onClose}>Hủy</Button>
        <Button onClick={() => onChoose(selected)}>Lưu múi giờ</Button>
      </div>
    </Dialog>
  );
}
