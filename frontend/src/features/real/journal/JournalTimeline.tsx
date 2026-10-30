import { useEffect, useRef, useState, type FormEvent } from "react";
import { Search, ChevronLeft, ChevronRight } from "lucide-react";
import { useGSAP } from "@gsap/react";
import gsap from "gsap";
import { Button } from "../../../components/UI";
import { useMotionPolicy } from "../../../components/motion/useMotionPolicy";
import type { JournalCollection } from "../../../api/journal";
import { ErrorNotice, useResource } from "../RealApp";
import { JournalEntryCard, JournalNav } from "./JournalShared";
import { useJournalToday } from "./JournalPage";
import {
  entryQuery,
  groupEntriesByDay,
  journalMoodLabels,
  type JournalFilters,
} from "./journalModel";

export function JournalTimeline() {
  const today = useJournalToday();
  const feed = useRef<HTMLDivElement>(null);
  const { animate } = useMotionPolicy();
  const [filters, setFilters] = useState<JournalFilters>({
    offset: 0,
    limit: 12,
  });
  const [q, setQ] = useState("");
  const entries = useResource<JournalCollection>(
    `/journal/entries?${entryQuery(filters)}`,
  );
  function filter(patch: Partial<JournalFilters>) {
    setFilters((previous) => ({ ...previous, ...patch, offset: 0 }));
  }
  function search(event: FormEvent) {
    event.preventDefault();
    filter({ q });
  }
  const data = entries.data;
  const groups = data ? groupEntriesByDay(data.items, today) : [];
  useEffect(() => {
    if (!data) return;
    const saved = sessionStorage.getItem("journal-feed-scroll");
    if (!saved) return;
    sessionStorage.removeItem("journal-feed-scroll");
    const y = Number(saved);
    if (Number.isFinite(y))
      requestAnimationFrame(() => window.scrollTo(0, y));
  }, [data]);
  useGSAP(
    () => {
      if (!animate || !data?.items.length) return;
      gsap.from(".journal-entry-card", {
        y: 8,
        duration: 0.28,
        stagger: 0.03,
        ease: "power2.out",
        clearProps: "transform",
      });
    },
    { scope: feed, dependencies: [data?.offset, data?.items.length, animate], revertOnUpdate: true },
  );
  return (
    <div className="journal-page journal-timeline-page">
      <JournalNav />
      <h1 tabIndex={-1}>Khoảnh khắc của bạn</h1>
      <form className="journal-search" onSubmit={search}>
        <label htmlFor="journal-search">Tìm trong nhật ký</label>
        <div>
          <input
            id="journal-search"
            type="search"
            value={q}
            maxLength={200}
            onChange={(event) => setQ(event.target.value)}
            placeholder="Một từ, một cảm xúc, một kỷ niệm…"
          />
          <Button type="submit">
            <Search size={18} />
            Tìm kiếm
          </Button>
        </div>
      </form>
      <div className="journal-timeline-filters">
        <label>
          Tâm trạng
          <select
            value={filters.mood || ""}
            onChange={(event) => filter({ mood: event.target.value })}
          >
            <option value="">Tất cả cảm xúc</option>
            {journalMoodLabels.map((label, i) => (
              <option key={label} value={i + 1}>
                {label}
              </option>
            ))}
          </select>
        </label>
        <label>
          Loại nội dung
          <select
            value={filters.media || ""}
            onChange={(event) => filter({ media: event.target.value })}
          >
            <option value="">Tất cả nội dung</option>
            <option value="image">Hình ảnh</option>
            <option value="audio">Ghi âm</option>
            <option value="video">Video</option>
          </select>
        </label>
        <label>
          Trạng thái
          <select
            value={filters.status || "saved"}
            onChange={(event) => filter({ status: event.target.value })}
          >
            <option value="saved">Đã lưu</option>
            <option value="draft">Bản nháp</option>
          </select>
        </label>
        <label>
          Từ ngày
          <input
            type="date"
            value={filters.from || ""}
            onChange={(event) => filter({ from: event.target.value })}
            max={filters.to || undefined}
          />
        </label>
        <label>
          Đến ngày
          <input
            type="date"
            value={filters.to || ""}
            onChange={(event) => filter({ to: event.target.value })}
            min={filters.from || undefined}
          />
        </label>
      </div>
      <ErrorNotice error={entries.error} retry={entries.refresh} />
      {entries.loading ? <p role="status">Đang tìm khoảnh khắc…</p> : null}
      {data && !entries.loading ? (
        <>
          <p className="journal-result-count" role="status">
            {data.total} khoảnh khắc{filters.q ? ` cho “${filters.q}”` : ""}
          </p>
          {data.items.length ? (
            <div className="journal-timeline" ref={feed}>
              {groups.map((group, index) => (
                <section key={group.day} className="journal-day-group">
                  {index === 0 || groups[index - 1].monthKey !== group.monthKey ? (
                    <h2 className="journal-month-label">{group.monthLabel}</h2>
                  ) : null}
                  <h3 className="journal-day-label">
                    {group.label}
                    {group.items.length > 1
                      ? ` · ${group.items.length} khoảnh khắc`
                      : ""}
                  </h3>
                  {group.items.map((entry) => (
                    <JournalEntryCard
                      entry={entry}
                      key={entry.id}
                      variant="feed"
                      onChange={entries.refresh}
                    />
                  ))}
                </section>
              ))}
            </div>
          ) : (
            <div className="journal-empty">
              <h2>Chưa có khoảnh khắc phù hợp</h2>
              <p>Thử một từ khác hoặc bỏ bớt bộ lọc để tìm lại.</p>
              <Button
                variant="secondary"
                onClick={() => {
                  setQ("");
                  setFilters({ offset: 0, limit: 12 });
                }}
              >
                Xóa bộ lọc
              </Button>
            </div>
          )}
          <nav className="journal-pagination" aria-label="Trang khoảnh khắc">
            <Button
              variant="secondary"
              disabled={!data.offset}
              aria-label="Trang trước"
              onClick={() =>
                setFilters((previous) => ({
                  ...previous,
                  offset: Math.max(0, data.offset - data.limit),
                }))
              }
            >
              <ChevronLeft size={19} />
              Trước
            </Button>
            <span>
              Trang {Math.floor(data.offset / data.limit) + 1} /{" "}
              {Math.max(1, Math.ceil(data.total / data.limit))}
            </span>
            <Button
              variant="secondary"
              disabled={data.offset + data.limit >= data.total}
              aria-label="Trang sau"
              onClick={() =>
                setFilters((previous) => ({
                  ...previous,
                  offset: data.offset + data.limit,
                }))
              }
            >
              Sau
              <ChevronRight size={19} />
            </Button>
          </nav>
        </>
      ) : null}
    </div>
  );
}
