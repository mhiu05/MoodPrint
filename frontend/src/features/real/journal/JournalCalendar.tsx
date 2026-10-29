import { useEffect, useMemo, useState } from "react";
import { ChevronLeft, ChevronRight, Plus } from "lucide-react";
import { Link } from "react-router-dom";
import { Button } from "../../../components/UI";
import type { JournalCollection, JournalEntry } from "../../../api/journal";
import { ErrorNotice, useResource, useSession } from "../RealApp";
import { JournalEntryCard, JournalNav, MoodFace } from "./JournalShared";
import {
  calendarDays,
  entryQuery,
  formatJournalDate,
  journalMoodLabels,
  activeMonthBounds,
  journalDateWindow,
} from "./journalModel";
import { useJournalToday } from "./JournalPage";

export function JournalCalendar() {
  const today = useJournalToday();
  const { api } = useSession();
  const [month, setMonth] = useState(today.slice(0, 7)),
    [selected, setSelected] = useState(today);
  const [rest, setRest] = useState<JournalEntry[]>([]),
    [moreLoading, setMoreLoading] = useState(false),
    [moreError, setMoreError] = useState<unknown>();
  const [revision, setRevision] = useState(0);
  const bounds = activeMonthBounds(month, today);
  const { earliest } = journalDateWindow(today);
  const first = useResource<JournalCollection>(
    `/journal/entries?${entryQuery({ ...bounds, limit: 50 })}`,
  );
  useEffect(() => {
    setRest([]);
    setMoreError(undefined);
    if (
      !first.data ||
      first.loading ||
      first.data.total <= first.data.items.length
    ) {
      setMoreLoading(false);
      return;
    }
    const controller = new AbortController();
    setMoreLoading(true);
    const paths = Array.from(
      { length: Math.ceil((first.data.total - 50) / 50) },
      (_, index) =>
        `/journal/entries?${entryQuery({ ...bounds, offset: (index + 1) * 50, limit: 50 })}`,
    );
    Promise.all(
      paths.map((path) =>
        api.request<JournalCollection>(path, { signal: controller.signal }),
      ),
    )
      .then((pages) => {
        if (!controller.signal.aborted)
          setRest(pages.flatMap((page) => page.items));
      })
      .catch((reason) => {
        if (!controller.signal.aborted) setMoreError(reason);
      })
      .finally(() => {
        if (!controller.signal.aborted) setMoreLoading(false);
      });
    return () => controller.abort();
  }, [api, month, first.data, first.loading, revision]);
  const entries = [...(first.data?.items || []), ...rest];
  const byDay = useMemo(() => {
    const map = new Map<string, JournalEntry[]>();
    for (const entry of entries)
      map.set(entry.localDate, [...(map.get(entry.localDate) || []), entry]);
    return map;
  }, [first.data, rest]);
  const [year, number] = month.split("-").map(Number);
  const heading = `Tháng ${number}, ${year}`;
  function shift(amount: number) {
    const date = new Date(Date.UTC(year, number - 1 + amount, 1));
    const next = date.toISOString().slice(0, 7);
    setMonth(next);
    setSelected(next === today.slice(0, 7) ? today : `${next}-01`);
  }
  return (
    <div className="journal-page journal-calendar-page">
      <JournalNav back />
      <h1 tabIndex={-1}>Lịch nhật ký</h1>
      <p className="journal-page-lede">
        Mỗi ngày một cảm xúc, mỗi khoảnh khắc một câu chuyện.
      </p>
      <section className="journal-calendar-surface" aria-label="Lịch tháng">
        <div className="journal-calendar-heading">
          <Button
            variant="text"
            disabled={month <= earliest.slice(0, 7)}
            onClick={() => shift(-1)}
            aria-label="Tháng trước"
          >
            <ChevronLeft size={22} />
          </Button>
          <h2 aria-live="polite">{heading}</h2>
          <Button
            variant="text"
            disabled={month >= today.slice(0, 7)}
            onClick={() => shift(1)}
            aria-label="Tháng sau"
          >
            <ChevronRight size={22} />
          </Button>
        </div>
        <div
          className="journal-calendar-grid"
          role="group"
          aria-label={heading}
        >
          {["T2", "T3", "T4", "T5", "T6", "T7", "CN"].map((day) => (
            <span className="journal-weekday" key={day}>
              {day}
            </span>
          ))}
          {calendarDays(month).map((day, index) =>
            day ? (
              <button
                type="button"
                key={day}
                className={`journal-calendar-day ${day === selected ? "is-selected" : ""} ${day === today ? "is-today" : ""}`}
                disabled={day > today || day < earliest}
                aria-pressed={day === selected}
                aria-label={`${Number(day.slice(8))} tháng ${number} năm ${year}, ${(byDay.get(day) || []).length} khoảnh khắc`}
                onClick={() => setSelected(day)}
              >
                <span>{Number(day.slice(8))}</span>
                {byDay.has(day) ? (
                  <MoodFace value={byDay.get(day)![0].mood} size={25} />
                ) : null}
              </button>
            ) : (
              <span key={`empty-${index}`} />
            ),
          )}
        </div>
        <p className="journal-help">
          Biểu tượng thể hiện cảm xúc của khoảnh khắc gần nhất trong ngày.
        </p>
        <div className="journal-mood-legend">
          {journalMoodLabels.map((label, i) => (
            <span key={label}>
              <MoodFace value={i + 1} size={25} />
              {label}
            </span>
          ))}
        </div>
      </section>
      <ErrorNotice
        error={first.error || moreError}
        retry={() => {
          first.refresh();
          setRevision((value) => value + 1);
        }}
      />
      {first.loading || moreLoading ? (
        <p role="status">Đang tải lịch nhật ký…</p>
      ) : null}
      <section
        className="journal-calendar-entries"
        aria-labelledby="journal-selected-day"
      >
        <h2 id="journal-selected-day">
          Nhật ký ngày {formatJournalDate(selected)}
        </h2>
        {!first.loading && !moreLoading && !first.error && !moreError ? (
          <>
            {(byDay.get(selected) || []).length ? (
              <>
                <p>{byDay.get(selected)!.length} khoảnh khắc</p>
                {byDay.get(selected)!.map((entry) => (
                  <JournalEntryCard key={entry.id} entry={entry} />
                ))}
              </>
            ) : (
              <p className="journal-empty">
                Ngày này chưa có khoảnh khắc nào. Bạn muốn giữ lại điều gì?
              </p>
            )}
          </>
        ) : null}
        <Link className="journal-add-moment" to={`/self?date=${selected}`}>
          <Plus size={21} />
          Ghi thêm khoảnh khắc
        </Link>
      </section>
    </div>
  );
}
