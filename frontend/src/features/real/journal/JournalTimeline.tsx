import { useEffect } from "react";
import { Link } from "react-router-dom";
import { ChevronDown, PenLine } from "lucide-react";
import { Button } from "../../../components/UI";
import { ErrorNotice } from "../RealApp";
import { JournalEntryCard, JournalNav } from "./JournalShared";
import { groupEntriesByMonth } from "./journalModel";
import { useJournalTimeline } from "./useJournalTimeline";

export function JournalTimeline() {
  const entries = useJournalTimeline();
  const groups = groupEntriesByMonth(entries.items);
  useEffect(() => {
    if (entries.loading || entries.total === undefined) return;
    const saved = sessionStorage.getItem("journal-feed-scroll");
    if (!saved) return;
    sessionStorage.removeItem("journal-feed-scroll");
    sessionStorage.removeItem("journal-feed-depth");
    const y = Number(saved);
    if (Number.isFinite(y)) requestAnimationFrame(() => window.scrollTo(0, y));
  }, [entries.loading, entries.total]);

  return (
    <div className="journal-page journal-timeline-page">
      <JournalNav />
      <header className="journal-timeline-heading">
        <h1 tabIndex={-1}>Khoảnh khắc của bạn</h1>
      </header>
      {entries.loading && entries.total === undefined ? (
        <div className="journal-timeline-loading" role="status">
          <span className="journal-loading-line" aria-hidden="true" />
          Đang mở những khoảnh khắc của bạn…
        </div>
      ) : null}
      {entries.total === 0 && !entries.loading && !entries.error ? (
        <section className="journal-empty journal-timeline-empty">
          <h2>Chưa có khoảnh khắc nào</h2>
          <Link className="journal-first-moment" to="/self">
            <PenLine size={18} aria-hidden="true" />
            Viết khoảnh khắc đầu tiên
          </Link>
        </section>
      ) : null}
      {groups.length ? (
        <div className="journal-timeline" aria-label="Dòng thời gian cảm xúc">
          {groups.map((group) => (
            <section
              key={group.key}
              className="journal-month-group"
              aria-labelledby={`month-${group.key}`}
            >
              <h2 className="journal-month-label" id={`month-${group.key}`}>
                {group.label}
              </h2>
              <div className="journal-month-moments">
                {group.items.map((entry) => (
                  <JournalEntryCard
                    key={entry.id}
                    entry={entry}
                    variant="feed"
                    onRemember={entries.remember}
                    onChange={() => entries.remove(entry.id)}
                  />
                ))}
              </div>
            </section>
          ))}
        </div>
      ) : null}
      <div className="journal-timeline-footer">
        <ErrorNotice error={entries.error} retry={entries.refresh} />
        <p className="journal-timeline-status" role="status" aria-atomic="true">
          {entries.loading && entries.total !== undefined
            ? "Đang mở thêm khoảnh khắc…"
            : entries.total
              ? `Đã mở ${entries.items.length} trong ${entries.total} khoảnh khắc`
              : ""}
        </p>
        {entries.hasMore ? (
          <Button
            variant="secondary"
            disabled={entries.loading || entries.paused}
            onClick={entries.loadMore}
          >
            Xem thêm khoảnh khắc
            <ChevronDown size={17} aria-hidden="true" />
          </Button>
        ) : null}
      </div>
    </div>
  );
}
