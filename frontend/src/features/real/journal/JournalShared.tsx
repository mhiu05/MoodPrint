import {
  CalendarDays,
  ChevronRight,
  BookOpen,
  ArrowLeft,
  PenLine,
  Sparkles,
  Trash2,
} from "lucide-react";
import { useEffect, useState } from "react";
import { Link, NavLink } from "react-router-dom";
import type { JournalEntry, JournalMedia } from "../../../api/journal";
import { Button, Dialog } from "../../../components/UI";
import { ErrorNotice, useResource, useSession } from "../RealApp";
import { JournalFeedMedia } from "./JournalGallery";
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

export function JournalNav() {
  return (
    <nav className="journal-section-nav" aria-label="Nhật ký">
      <NavLink to="/self" end>
        <PenLine size={17} />
        Hôm nay
      </NavLink>
      <NavLink to="/self/memories">
        <BookOpen size={17} />
        Khoảnh khắc của bạn
      </NavLink>
      <NavLink to="/self/companion">
        <Sparkles size={17} />
        Nhìn lại
      </NavLink>
      <NavLink to="/self/calendar">
        <CalendarDays size={17} />
        Lịch nhật ký
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

export function JournalEntryCard({
  entry,
  variant = "compact",
  onChange,
}: {
  entry: JournalEntry;
  variant?: "compact" | "feed";
  onChange?: () => void;
}) {
  const { api } = useSession();
  const [expanded, setExpanded] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>();
  const time = new Intl.DateTimeFormat("vi-VN", {
    hour: "2-digit",
    minute: "2-digit",
    timeZone: entry.timezone,
  }).format(new Date(entry.createdAt));
  const long = entry.text.length > 220;
  const openLabel = `Mở khoảnh khắc ngày ${formatJournalDate(entry.localDate)} lúc ${time}`;
  function rememberScroll() {
    sessionStorage.setItem("journal-feed-scroll", String(window.scrollY));
  }
  async function remove() {
    if (busy) return;
    setBusy(true);
    setError(undefined);
    try {
      await api.request(`/journal/entries/${entry.id}`, {
        method: "DELETE",
        body: { expectedVersion: entry.version },
      });
      setDeleting(false);
      onChange?.();
    } catch (reason) {
      setError(reason);
      setDeleting(false);
    } finally {
      setBusy(false);
    }
  }
  return (
    <article
      className={`journal-entry-card${variant === "feed" ? " is-feed" : ""}`}
      id={`journal-entry-${entry.id}`}
    >
      <MoodFace value={entry.mood} size={variant === "feed" ? 44 : 36} />
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
        <p className={expanded || !long ? "is-open" : undefined}>
          {entry.text || "Khoảnh khắc không có lời viết."}
        </p>
        {long ? (
          <button
            type="button"
            className="journal-expand"
            onClick={() => setExpanded((value) => !value)}
          >
            {expanded ? "Thu gọn" : "Xem thêm"}
          </button>
        ) : null}
        {variant === "feed" &&
        (entry.emotions.length || entry.factors.length) ? (
          <ul className="journal-card-tags">
            {[...entry.emotions, ...entry.factors].map((tag, index) => (
              <li key={`${tag}-${index}`}>{tag}</li>
            ))}
          </ul>
        ) : null}
        {variant === "feed" && entry.media.length ? (
          <JournalFeedMedia entryId={entry.id} media={entry.media} />
        ) : null}
        <div className="journal-card-actions">
          <Link
            className="journal-entry-open"
            to={`/self/entry/${entry.id}`}
            aria-label={openLabel}
            onClick={rememberScroll}
          >
            Xem khoảnh khắc
            <ChevronRight size={17} />
          </Link>
          {variant === "feed" ? (
            <>
              <Link
                to={`/self/entry/${entry.id}?edit=1`}
                aria-label={`Chỉnh sửa khoảnh khắc lúc ${time}`}
                onClick={rememberScroll}
              >
                Chỉnh sửa
              </Link>
              <button
                type="button"
                aria-label={`Xóa khoảnh khắc lúc ${time}`}
                onClick={() => setDeleting(true)}
              >
                <Trash2 size={16} />
                Xóa
              </button>
            </>
          ) : null}
        </div>
        <ErrorNotice error={error} />
      </div>
      {deleting ? (
        <Dialog
          title="Xóa khoảnh khắc này?"
          destructive
          onClose={() => {
            if (!busy) setDeleting(false);
          }}
        >
          <p>
            Nội dung và các tệp đính kèm sẽ bị xóa. Bạn không thể khôi phục
            khoảnh khắc này sau khi xóa.
          </p>
          <div className="actions">
            <Button
              variant="secondary"
              data-cancel
              disabled={busy}
              onClick={() => setDeleting(false)}
            >
              Giữ lại
            </Button>
            <Button
              variant="danger"
              disabled={busy}
              onClick={() => void remove()}
            >
              {busy ? "Đang xóa…" : "Xóa vĩnh viễn"}
            </Button>
          </div>
        </Dialog>
      ) : null}
    </article>
  );
}
