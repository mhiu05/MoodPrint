import {
  CalendarDays,
  ChevronRight,
  BookOpen,
  ArrowLeft,
  PenLine,
} from "lucide-react";
import { useEffect, useState } from "react";
import { Link, NavLink } from "react-router-dom";
import type { JournalEntry, JournalMedia } from "../../../api/journal";
import { useResource } from "../RealApp";
import { formatJournalDate, journalMoodLabels } from "./journalModel";

export function MoodFace({
  value,
  size = 42,
}: {
  value: number;
  size?: number;
}) {
  return (
    <svg
      className={`journal-face mood-${value}`}
      width={size}
      height={size}
      viewBox="0 0 48 48"
      fill="none"
      aria-hidden="true"
    >
      <circle cx="24" cy="24" r="21" fill="currentColor" />
      <g stroke="#514229" strokeWidth="2.1" strokeLinecap="round">
        <path d="M17 19v2m14-2v2" />
        {value <= 2 ? (
          <path
            d={
              value === 1
                ? "M16 33q8-10 16 0M14 15l6 2m8 0 6-2"
                : "M17 31q7-7 14 0"
            }
          />
        ) : value === 3 ? (
          <path d="M18 30h12" />
        ) : (
          <path d={value === 5 ? "M16 27q8 13 16 0Z" : "M17 28q7 9 14 0"} />
        )}
      </g>
    </svg>
  );
}

export function JournalNav({ back = false }: { back?: boolean }) {
  return (
    <nav className="journal-section-nav" aria-label="Nhật ký">
      <NavLink to="/self" end>
        <PenLine size={17} />
        {back ? "Viết khoảnh khắc" : "Viết nhật ký"}
      </NavLink>
      <NavLink to="/self/calendar">
        <CalendarDays size={17} />
        Lịch nhật ký
      </NavLink>
      <NavLink to="/self/memories">
        <BookOpen size={17} />
        Khoảnh khắc của bạn
      </NavLink>
    </nav>
  );
}

export function JournalBack() {
  return (
    <Link className="journal-back" to="/self">
      <ArrowLeft size={18} />
      Nhật ký cảm xúc
    </Link>
  );
}

export function JournalMediaPreview({
  entryId,
  media,
}: {
  entryId: string;
  media: JournalMedia;
}) {
  const access = useResource<{ url: string; expiresIn: number }>(
    `/journal/entries/${entryId}/media/${media.id}/access`,
    media.status === "ready",
  );
  const [failed, setFailed] = useState(false);
  useEffect(() => setFailed(false), [access.data?.url]);
  if (media.status === "pending")
    return (
      <p className="journal-media-unavailable">
        Tệp đang chờ tải lên. Mở chỉnh sửa để tải lại hoặc gỡ tệp.
      </p>
    );
  if (access.error || failed)
    return (
      <div className="journal-media-unavailable">
        <p>Chưa mở được tệp đính kèm hoặc đường dẫn đã hết hạn.</p>
        <button
          type="button"
          onClick={() => {
            setFailed(false);
            access.refresh();
          }}
        >
          Thử mở lại
        </button>
      </div>
    );
  if (!access.data) return <p role="status">Đang mở tệp…</p>;
  if (media.type === "image")
    return (
      <img
        className="journal-owned-photo"
        src={access.data.url}
        alt="Ảnh trong khoảnh khắc của bạn"
        loading="lazy"
        onError={() => setFailed(true)}
      />
    );
  return media.type === "audio" ? (
    <audio
      controls
      preload="none"
      src={access.data.url}
      aria-label="Bản ghi âm của khoảnh khắc"
      onError={() => setFailed(true)}
    />
  ) : (
    <video
      controls
      preload="none"
      src={access.data.url}
      aria-label="Video của khoảnh khắc"
      onError={() => setFailed(true)}
    />
  );
}

export function JournalEntryCard({ entry }: { entry: JournalEntry }) {
  const [showMedia, setShowMedia] = useState(false);
  const time = new Intl.DateTimeFormat("vi-VN", {
    hour: "2-digit",
    minute: "2-digit",
    timeZone: entry.timezone,
  }).format(new Date(entry.createdAt));
  return (
    <article className="journal-entry-card">
      <MoodFace value={entry.mood} size={36} />
      <div className="journal-entry-excerpt">
        <div className="journal-entry-meta">
          <strong>
            {formatJournalDate(entry.localDate)} · {time}
          </strong>
          <span>{journalMoodLabels[entry.mood - 1]}</span>
          {entry.status === "draft" ? (
            <span className="journal-draft-badge">Bản nháp</span>
          ) : null}
        </div>
        <p>{entry.text || "Khoảnh khắc không có lời viết."}</p>
        {entry.media.length ? (
          <small>
            {entry.media.filter((item) => item.type === "image").length
              ? "Có hình ảnh · "
              : ""}
            {entry.media.some((item) => item.type === "audio")
              ? "Có ghi âm · "
              : ""}
            {entry.media.some((item) => item.type === "video")
              ? "Có video"
              : ""}
          </small>
        ) : null}
        {entry.media.some((item) => item.status === "ready") ? (
          <div className="journal-card-media">
            <button
              type="button"
              aria-expanded={showMedia}
              onClick={() => setShowMedia((value) => !value)}
            >
              {showMedia ? "Ẩn tệp đính kèm" : "Xem tệp đính kèm"}
            </button>
            {showMedia ? (
              <div>
                {entry.media
                  .filter((item) => item.status === "ready")
                  .slice(0, 3)
                  .map((media) => (
                    <JournalMediaPreview
                      entryId={entry.id}
                      media={media}
                      key={media.id}
                    />
                  ))}
                {entry.media.length > 3 ? (
                  <p>Mở khoảnh khắc để xem toàn bộ {entry.media.length} tệp.</p>
                ) : null}
              </div>
            ) : null}
          </div>
        ) : null}
        <Link
          className="journal-entry-open"
          to={`/self/entry/${entry.id}`}
          aria-label={`Mở khoảnh khắc ngày ${formatJournalDate(entry.localDate)} lúc ${time}`}
        >
          Xem khoảnh khắc
          <ChevronRight size={17} />
        </Link>
      </div>
    </article>
  );
}
