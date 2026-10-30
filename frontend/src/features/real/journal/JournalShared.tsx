import {
  CalendarDays,
  ChevronRight,
  BookOpen,
  ArrowLeft,
  PenLine,
  Trash2,
  MoreHorizontal,
  Pencil,
} from "lucide-react";
import { useEffect, useId, useRef, useState } from "react";
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

export function JournalMomentMenu({
  menuLabel,
  onEdit,
  editTo,
  onDelete,
  onNavigate,
}: {
  menuLabel: string;
  onEdit?: () => void;
  editTo?: string;
  onDelete: () => void;
  onNavigate?: () => void;
}) {
  const [open, setOpen] = useState(false);
  const menuId = useId();
  const rootRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    panelRef.current?.querySelector<HTMLElement>('[role="menuitem"]')?.focus();
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setOpen(false);
        triggerRef.current?.focus();
        return;
      }
      if (event.key !== "ArrowDown" && event.key !== "ArrowUp") return;
      const panel = panelRef.current;
      if (!panel) return;
      const items = [
        ...panel.querySelectorAll<HTMLElement>('[role="menuitem"]'),
      ];
      if (!items.length) return;
      const current = items.indexOf(document.activeElement as HTMLElement);
      const next =
        event.key === "ArrowDown"
          ? items[(current + 1) % items.length]
          : items[(current - 1 + items.length) % items.length];
      next?.focus();
      event.preventDefault();
    }
    function onPointer(event: PointerEvent) {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false);
    }
    document.addEventListener("keydown", onKey);
    document.addEventListener("pointerdown", onPointer);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("pointerdown", onPointer);
    };
  }, [open]);

  function close() {
    setOpen(false);
  }

  return (
    <div className="journal-moment-menu" ref={rootRef}>
      <button
        ref={triggerRef}
        type="button"
        className="journal-moment-menu-trigger"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls={menuId}
        aria-label={menuLabel}
        onClick={() => setOpen((value) => !value)}
      >
        <MoreHorizontal size={18} aria-hidden="true" />
        Thao tác
      </button>
      {open ? (
        <div
          ref={panelRef}
          id={menuId}
          role="menu"
          aria-label={menuLabel}
          className="journal-moment-menu-panel"
        >
          {editTo ? (
            <Link
              role="menuitem"
              to={editTo}
              aria-label="Chỉnh sửa khoảnh khắc"
              onClick={() => {
                onNavigate?.();
                close();
              }}
            >
              <Pencil size={16} aria-hidden="true" />
              Chỉnh sửa
            </Link>
          ) : (
            <button
              type="button"
              role="menuitem"
              aria-label="Chỉnh sửa khoảnh khắc"
              onClick={() => {
                close();
                onEdit?.();
              }}
            >
              <Pencil size={16} aria-hidden="true" />
              Chỉnh sửa
            </button>
          )}
          <button
            type="button"
            role="menuitem"
            className="is-destructive"
            onClick={() => {
              close();
              onDelete();
            }}
          >
            <Trash2 size={16} aria-hidden="true" />
            Xóa khoảnh khắc
          </button>
        </div>
      ) : null}
    </div>
  );
}

export function JournalEntryCard({
  entry,
  variant = "compact",
  onChange,
  onRemember,
}: {
  entry: JournalEntry;
  variant?: "compact" | "feed";
  onChange?: () => void;
  onRemember?: () => void;
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
  const textId = useId();
  const openLabel = `Mở khoảnh khắc ngày ${formatJournalDate(entry.localDate)} lúc ${time}`;
  function rememberScroll() {
    onRemember?.();
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
      className={`journal-entry-card${variant === "feed" ? ` is-feed journal-mood-${entry.mood}` : ""}`}
      id={`journal-entry-${entry.id}`}
    >
      {variant !== "feed" ? <MoodFace value={entry.mood} size={36} /> : null}
      <div className="journal-entry-excerpt">
        {variant === "feed" ? (
          <div className="journal-moment-heading">
            <div className="journal-moment-date-mood">
              <time
                dateTime={`${entry.localDate}T${time}:00`}
                aria-label={`${formatJournalDate(entry.localDate)} lúc ${time}`}
              >
                {entry.localDate.slice(8, 10)}/{entry.localDate.slice(5, 7)} ·{" "}
                {time}
              </time>
              <span className="journal-moment-mood">
                <span aria-hidden="true">
                  {["😞", "😔", "😐", "🙂", "😄"][entry.mood - 1]}
                </span>
                {journalMoodLabels[entry.mood - 1]}
              </span>
            </div>
            <JournalMomentMenu
              menuLabel={`Thao tác với khoảnh khắc ngày ${formatJournalDate(entry.localDate)} lúc ${time}`}
              editTo={`/self/entry/${entry.id}?edit=1`}
              onNavigate={rememberScroll}
              onDelete={() => setDeleting(true)}
            />
          </div>
        ) : (
          <div className="journal-entry-meta">
            <strong>
              {formatJournalDate(entry.localDate)} · {time}
            </strong>
            <span>{journalMoodLabels[entry.mood - 1]}</span>
            {entry.status === "draft" ? (
              <span className="journal-draft-badge">Bản nháp</span>
            ) : null}
          </div>
        )}
        <p id={textId} className={expanded || !long ? "is-open" : undefined}>
          {entry.text || "Khoảnh khắc không có lời viết."}
        </p>
        {long ? (
          <button
            type="button"
            className="journal-expand"
            aria-expanded={expanded}
            aria-controls={textId}
            onClick={() => setExpanded((value) => !value)}
          >
            {expanded ? "Thu gọn" : "Xem thêm"}
          </button>
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
