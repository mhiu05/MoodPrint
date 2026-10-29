import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { Button, cx, Dialog } from "../../components/UI";
import { ApiError } from "../../api/client";
import type {
  ActionReceipt,
  MoodDTO,
  MoodInput,
  MoodSummaryDTO,
  SessionView,
  VersionInput,
} from "../../api/contracts";
import { ErrorNotice, useResource, useSession } from "./RealApp";
import { useTourBlocker } from "../onboarding/tourActivity";

export const moodLabels = [
  "Rất khó khăn",
  "Hơi chùng xuống",
  "Bình thường",
  "Khá ổn",
  "Rất vui",
];

export function localDate(time: string | number | Date, timezone: string) {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: timezone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(new Date(time));
  return ["year", "month", "day"]
    .map((type) => parts.find((part) => part.type === type)?.value)
    .join("-");
}

function shiftDate(day: string, days: number) {
  const value = new Date(`${day}T00:00:00Z`);
  value.setUTCDate(value.getUTCDate() + days);
  return value.toISOString().slice(0, 10);
}

function displayDate(day: string) {
  const [year, month, date] = day.split("-");
  return `${date}/${month}/${year}`;
}

/** Account-timezone "today", corrected by the server clock and refreshed after midnight. */
function useAccountToday(session: SessionView) {
  const offset = useMemo(
    () => new Date(session.serverTime).getTime() - Date.now(),
    [session.serverTime],
  );
  const compute = () => localDate(Date.now() + offset, session.timezone);
  const [today, setToday] = useState(compute);
  useEffect(() => {
    const update = () => setToday(compute());
    const timer = window.setInterval(update, 60_000);
    document.addEventListener("visibilitychange", update);
    window.addEventListener("focus", update);
    return () => {
      window.clearInterval(timer);
      document.removeEventListener("visibilitychange", update);
      window.removeEventListener("focus", update);
    };
  }, [offset, session.timezone]);
  return today;
}

const newestFirst = (moods: MoodDTO[]) =>
  [...moods].sort((a, b) => b.localDate.localeCompare(a.localDate));

export function Moods() {
  const { api, session } = useSession();
  const resource = useResource<MoodDTO[]>("/moods");
  const today = useAccountToday(session);
  const earliest = shiftDate(today, -89);
  const [date, setDate] = useState(today);
  const [value, setValue] = useState(3),
    [note, setNote] = useState("");
  const [busy, setBusy] = useState(false),
    [error, setError] = useState<unknown>(),
    [receipt, setReceipt] = useState("");
  const [confirmDelete, setConfirmDelete] = useState<MoodDTO>();
  const [summaryRevision, setSummaryRevision] = useState(0);
  const [edited, setEdited] = useState(false);
  const moods = useMemo(
    () => newestFirst(resource.data || []),
    [resource.data],
  );
  const existing = moods.find((mood) => mood.localDate === date);
  useTourBlocker("draft", edited || busy);

  // Selecting a day that already has an entry loads it, so saving edits that
  // entry instead of silently overwriting it with whatever the form held.
  function choose(day: string, entries = moods) {
    const entry = entries.find((mood) => mood.localDate === day);
    setDate(day);
    setValue(entry?.value ?? 3);
    setNote(entry?.note ?? "");
    setEdited(false);
  }
  const synced = useRef(false);
  useEffect(() => {
    // Load the selected day's saved entry once; later refreshes never clobber typed input.
    if (!resource.data || synced.current) return;
    synced.current = true;
    const entry = resource.data.find((mood) => mood.localDate === date);
    if (entry) choose(date, [entry]);
  }, [resource.data]);

  async function save(event: FormEvent) {
    event.preventDefault();
    if (busy || !resource.data) return;
    if (date < earliest || date > today) {
      setError(
        new ApiError(
          422,
          "DATE_RANGE",
          "Chọn ngày trong 90 ngày gần đây, tính đến hôm nay.",
        ),
      );
      return;
    }
    setBusy(true);
    setError(undefined);
    setReceipt("");
    try {
      const saved = await api.request<MoodDTO>(`/moods/${date}`, {
        method: "PUT",
        body: {
          value,
          note,
          timezone: session.timezone,
          expectedVersion: existing?.version || 0,
        } satisfies MoodInput,
      });
      resource.setData((previous) => [
        saved,
        ...(previous || []).filter(
          (mood) => mood.localDate !== saved.localDate,
        ),
      ]);
      setNote(saved.note);
      setEdited(false);
      setSummaryRevision((n) => n + 1);
      setReceipt(`${existing ? "Đã cập nhật" : "Đã lưu"} cảm xúc ngày ${displayDate(saved.localDate)}.`);
    } catch (reason) {
      setError(reason);
      if (reason instanceof ApiError && reason.status === 409) {
        // Another tab or device changed this day: reload, keep the typed note.
        const kept = { value, note };
        try {
          const fresh = newestFirst(await api.request<MoodDTO[]>("/moods"));
          resource.setData(fresh);
          setValue(kept.value);
          setNote(kept.note);
          setError(
            new ApiError(
              409,
              "STALE_VERSION",
              "Ghi chép này vừa được thay đổi ở nơi khác. Nội dung mới đã được tải; phần bạn đang nhập vẫn được giữ. Kiểm tra rồi chọn lưu lại.",
            ),
          );
        } catch {
          /* keep the original error */
        }
      }
    } finally {
      setBusy(false);
    }
  }

  async function remove(mood: MoodDTO) {
    setBusy(true);
    setError(undefined);
    setReceipt("");
    try {
      await api.request<ActionReceipt>(`/moods/${mood.localDate}`, {
        method: "DELETE",
        body: { expectedVersion: mood.version } satisfies VersionInput,
      });
      resource.setData((previous) =>
        (previous || []).filter((item) => item.localDate !== mood.localDate),
      );
      if (date === mood.localDate) choose(date, []);
      setSummaryRevision((n) => n + 1);
      setReceipt(`Đã xóa tâm trạng ngày ${displayDate(mood.localDate)}.`);
    } catch (reason) {
      setError(reason);
      if (reason instanceof ApiError && [404, 409].includes(reason.status))
        resource.refresh();
    } finally {
      setBusy(false);
      setConfirmDelete(undefined);
    }
  }

  return (
    <div className={cx.reading}>
      <h1 tabIndex={-1} data-tour="mood-entry">Nhật ký cảm xúc</h1>
      <p className={cx.lede}>
        Ghi lại tâm trạng theo cách bạn cảm nhận. Chỉ bạn xem ghi chép và ghi chú này.
      </p>
      <ErrorNotice error={resource.error} retry={resource.refresh} />
      {resource.loading ? <p role="status">Đang tải tâm trạng…</p> : null}
      <form onSubmit={save} aria-describedby="mood-mode">
        {/* Inputs wait for the saved list so typing never races the day's entry. */}
        <fieldset className="real-plain" disabled={!resource.data}>
          <label htmlFor="mood-date">Ngày</label>
          <input
            id="mood-date"
            type="date"
            value={date}
            min={earliest}
            max={today}
            required
            onChange={(event) => {
              choose(event.target.value);
              setReceipt("");
              setError(undefined);
            }}
          />
          <p id="mood-mode" className={cx.footnote}>
            {existing
              ? `Đang sửa ghi chép đã lưu của ngày ${displayDate(date)}.`
              : `Ghi chép mới cho ngày ${displayDate(date)}. Mỗi ngày có một ghi chép.`}
          </p>
          <label htmlFor="mood-value">Tâm trạng</label>
          <select
            id="mood-value"
            value={value}
            onChange={(event) => { setValue(Number(event.target.value)); setEdited(true); }}
          >
            {moodLabels.map((label, index) => (
              <option key={label} value={index + 1}>
                {index + 1} — {label}
              </option>
            ))}
          </select>
          <label htmlFor="mood-note">Ghi chú</label>
          <textarea
            id="mood-note"
            value={note}
            maxLength={120}
            rows={3}
            aria-describedby="mood-note-count"
            onChange={(event) => { setNote(event.target.value); setEdited(true); }}
          />
          <p id="mood-note-count" className={cx.footnote}>
            Không bắt buộc · {note.length}/120 ký tự · Chỉ bạn xem; ghi chú
            không được gửi cho AI.
          </p>
        </fieldset>
        <ErrorNotice error={error} />
        <div className="actions">
          <Button
            type="submit"
            disabled={busy || resource.loading || !resource.data}
          >
            {busy
              ? "Đang lưu…"
              : existing
                ? "Cập nhật tâm trạng"
                : "Lưu tâm trạng"}
          </Button>
          {existing ? (
            <Button
              variant="secondary"
              disabled={busy}
              onClick={() => {
                choose(today);
                setReceipt("");
              }}
            >
              Hủy sửa
            </Button>
          ) : null}
        </div>
        <p role="status" aria-live="polite">
          {receipt}
        </p>
      </form>
      <MoodInsights revision={summaryRevision} />
      <section className="real-section" aria-labelledby="mood-history">
        <h2 id="mood-history">Những ngày đã ghi</h2>
        {resource.data && moods.length === 0 ? (
          <p>Chưa có ghi chép. Bạn có thể bắt đầu từ hôm nay.</p>
        ) : null}
        {moods.map((mood) => (
          <article className="real-item" key={mood.id}>
            <h3>
              {displayDate(mood.localDate)} · {mood.value}/5 ·{" "}
              {moodLabels[mood.value - 1]}
            </h3>
            {mood.note ? <p>{mood.note}</p> : null}
            <div className="actions">
              <Button
                variant="text"
                onClick={() => {
                  choose(mood.localDate);
                  setReceipt("");
                  document.getElementById("mood-value")?.focus();
                }}
              >
                Sửa{" "}
                <span className={cx.srOnly}>
                  tâm trạng ngày {displayDate(mood.localDate)}
                </span>
              </Button>
              <Button
                variant="text"
                disabled={busy}
                onClick={() => setConfirmDelete(mood)}
              >
                Xóa{" "}
                <span className={cx.srOnly}>
                  tâm trạng ngày {displayDate(mood.localDate)}
                </span>
              </Button>
            </div>
          </article>
        ))}
      </section>
      {confirmDelete ? (
        <Dialog
          title="Xóa ghi chép này?"
          destructive
          onClose={() => setConfirmDelete(undefined)}
        >
          <p>
            Ghi chép ngày {displayDate(confirmDelete.localDate)} và ghi chú của
            nó sẽ bị xóa vĩnh viễn và không còn xuất hiện trong phần nhìn lại.
          </p>
          <div className="actions">
            <Button
              variant="secondary"
              data-cancel
              onClick={() => setConfirmDelete(undefined)}
            >
              Giữ lại
            </Button>
            <Button
              variant="danger"
              disabled={busy}
              onClick={() => remove(confirmDelete)}
            >
              {busy ? "Đang xóa…" : "Xóa ghi chép"}
            </Button>
          </div>
        </Dialog>
      ) : null}
    </div>
  );
}

const ranges = [7, 30, 90] as const;

function MoodInsights({ revision }: { revision: number }) {
  const [days, setDays] = useState<(typeof ranges)[number]>(7);
  const summary = useResource<MoodSummaryDTO>(`/moods/summary?days=${days}`);
  const { refresh } = summary;
  useEffect(() => {
    if (revision) refresh();
  }, [revision, refresh]);
  const data = summary.data;
  const width = 640,
    left = 40,
    right = 620;
  const step = data ? (right - left) / Math.max(data.buckets.length, 1) : 0;
  const labelEvery = data ? Math.ceil(data.buckets.length / 7) : 1;
  return (
    <section className="real-section" aria-labelledby="mood-insights">
      <div className={cx.sectionHeading}>
        <div>
          <h2 id="mood-insights">Nhìn lại tâm trạng</h2>
          <p>Chỉ từ dữ liệu bạn tự ghi. Đây không phải đánh giá sức khỏe.</p>
        </div>
      </div>
      <div className={cx.chips} role="group" aria-label="Khoảng thời gian">
        {ranges.map((range) => (
          <Button
            key={range}
            variant="secondary"
            aria-pressed={days === range}
            onClick={() => setDays(range)}
          >
            {range} ngày
          </Button>
        ))}
      </div>
      <ErrorNotice error={summary.error} retry={summary.refresh} />
      {summary.loading && !data ? <p role="status">Đang tải thống kê tâm trạng…</p> : null}
      {data ? (
        <>
          <div className={cx.weekSummary}>
            <span className="mood-mean">
              <strong>
                {data.mean === null
                  ? "—"
                  : data.mean.toLocaleString("vi-VN", {
                      minimumFractionDigits: 1,
                      maximumFractionDigits: 1,
                    })}
              </strong>{" "}
              / 5
            </span>
            <p>
              Trung bình từ {data.count}/{data.buckets.length} ngày có ghi (
              {displayDate(data.from)} – {displayDate(data.to)}).
              <br />
              Ngày chưa ghi được để trống, không được ước đoán.
            </p>
          </div>
          {data.count === 0 ? (
            <p className={cx.note}>Bạn chưa ghi tâm trạng trong khoảng này. Chọn khoảng khác hoặc ghi lại hôm nay.</p>
          ) : (
            <>
              <svg
                viewBox={`0 0 ${width} 230`}
                role="img"
                aria-label={`Biểu đồ tâm trạng ${data.buckets.length} ngày: ${data.count} ngày có ghi${
                  data.min !== null
                    ? `, từ ${data.min} đến ${data.max} trên 5`
                    : ""
                }. Bảng dữ liệu đầy đủ ở bên dưới.`}
                className={cx.chart}
              >
                {[1, 2, 3, 4, 5].map((v) => (
                  <g key={v}>
                    <line
                      x1={left}
                      x2={right}
                      y1={190 - (v - 1) * 40}
                      y2={190 - (v - 1) * 40}
                      stroke="var(--color-divider)"
                    />
                    <text x="12" y={195 - (v - 1) * 40}>
                      {v}
                    </text>
                  </g>
                ))}
                {data.buckets.map((bucket, index) => {
                  const x = left + step * (index + 0.5);
                  return (
                    <g key={bucket.localDate}>
                      {bucket.value !== null ? (
                        <>
                          <line
                            x1={x}
                            x2={x}
                            y1="190"
                            y2={190 - (bucket.value - 1) * 40}
                            stroke="var(--color-border)"
                            strokeWidth="2"
                          />
                          <circle
                            cx={x}
                            cy={190 - (bucket.value - 1) * 40}
                            r={data.buckets.length > 30 ? 3 : 7}
                            fill="var(--color-primary)"
                          />
                        </>
                      ) : null}
                      {index % labelEvery === 0 ? (
                        <text x={x} y="220" textAnchor="middle">
                          {bucket.localDate.slice(8)}/
                          {bucket.localDate.slice(5, 7)}
                        </text>
                      ) : null}
                    </g>
                  );
                })}
              </svg>
              <p className={cx.note}>
                {data.insightAvailable
                  ? `Bạn đã ghi tâm trạng trong ${data.count}/${data.buckets.length} ngày. Điểm bạn tự chọn từ ${data.min} đến ${data.max}/5.`
                  : "Cần ghi tâm trạng ít nhất 3 ngày để xem phần nhìn lại."}
              </p>
              <details>
                <summary>Xem từng ngày</summary>
                <table className={`${cx.table} mood-table`}>
                  <caption className={cx.srOnly}>
                    Tâm trạng tự ghi theo ngày; ngày thiếu là chưa ghi
                  </caption>
                  <thead>
                    <tr>
                      <th scope="col">Ngày</th>
                      <th scope="col">Tâm trạng tự chọn</th>
                    </tr>
                  </thead>
                  <tbody>
                    {[...data.buckets].reverse().map((bucket) => (
                      <tr key={bucket.localDate}>
                        <th scope="row">{displayDate(bucket.localDate)}</th>
                        <td>
                          {bucket.value !== null
                            ? `${bucket.value} · ${moodLabels[bucket.value - 1]}`
                            : "Chưa ghi"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </details>
            </>
          )}
        </>
      ) : null}
    </section>
  );
}
