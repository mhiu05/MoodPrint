import { useEffect, useRef, useState, type ReactNode } from "react";
import { ChevronLeft, ChevronRight, X } from "lucide-react";
import type { JournalMedia } from "../../../api/journal";
import { useResource } from "../RealApp";

function useInView<T extends HTMLElement>() {
  const ref = useRef<T>(null);
  const [seen, setSeen] = useState(false);
  useEffect(() => {
    const node = ref.current;
    if (!node || seen) return;
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry?.isIntersecting) setSeen(true);
      },
      { rootMargin: "240px" },
    );
    observer.observe(node);
    return () => observer.disconnect();
  }, [seen]);
  return [ref, seen] as const;
}

function MediaAccess({
  entryId,
  media,
  enabled,
  children,
}: {
  entryId: string;
  media: JournalMedia;
  enabled: boolean;
  children: (url: string, onError: () => void) => ReactNode;
}) {
  const access = useResource<{ url: string; expiresIn: number }>(
    `/journal/entries/${entryId}/media/${media.id}/access`,
    enabled && media.status === "ready",
  );
  const [failed, setFailed] = useState(false);
  useEffect(() => setFailed(false), [access.data?.url]);
  if (media.status === "pending")
    return <p className="journal-media-unavailable">Tệp đang chờ tải lên.</p>;
  if (!enabled)
    return <span className="journal-media-pending">Đang chuẩn bị tệp…</span>;
  if (access.error || failed)
    return (
      <div className="journal-media-unavailable">
        <p>Chưa mở được tệp đính kèm.</p>
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
  if (!access.data) return <span role="status">Đang mở tệp…</span>;
  return <>{children(access.data.url, () => setFailed(true))}</>;
}

function GalleryThumb({
  entryId,
  media,
  extra,
  onOpen,
}: {
  entryId: string;
  media: JournalMedia;
  extra?: number;
  onOpen: () => void;
}) {
  const [ref, seen] = useInView<HTMLDivElement>();
  return (
    <div ref={ref} className="journal-gallery-cell">
      <MediaAccess entryId={entryId} media={media} enabled={seen}>
        {(url, onError) => (
          <button
            type="button"
            className="journal-gallery-thumb"
            onClick={onOpen}
            aria-label={
              extra ? `Xem ảnh lớn hơn, còn ${extra} ảnh` : "Xem ảnh lớn hơn"
            }
          >
            <img
              src={url}
              alt="Ảnh trong khoảnh khắc của bạn"
              loading="lazy"
              decoding="async"
              onError={onError}
            />
            {extra ? (
              <span className="journal-gallery-more">+{extra}</span>
            ) : null}
          </button>
        )}
      </MediaAccess>
    </div>
  );
}

function JournalLightbox({
  entryId,
  images,
  index,
  onClose,
  onIndex,
}: {
  entryId: string;
  images: JournalMedia[];
  index: number;
  onClose: () => void;
  onIndex: (index: number) => void;
}) {
  const closeRef = useRef<HTMLButtonElement>(null);
  const dialogRef = useRef<HTMLDialogElement>(null);
  const onCloseRef = useRef(onClose);
  const onIndexRef = useRef(onIndex);
  onCloseRef.current = onClose;
  onIndexRef.current = onIndex;
  const media = images[index];
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    const dialog = dialogRef.current;
    const overflow = document.body.style.overflow;
    dialog?.showModal();
    document.body.style.overflow = "hidden";
    closeRef.current?.focus();
    return () => {
      dialog?.close();
      document.body.style.overflow = overflow;
      previous?.focus();
    };
  }, []);
  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key === "ArrowRight")
        onIndexRef.current((index + 1) % images.length);
      if (event.key === "ArrowLeft")
        onIndexRef.current((index - 1 + images.length) % images.length);
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [images.length, index]);
  if (!media) return null;
  return (
    <dialog
      ref={dialogRef}
      className="journal-lightbox"
      aria-modal="true"
      aria-label="Ảnh trong khoảnh khắc"
      onClick={onClose}
      onKeyDown={(event) => {
        if (event.key !== "Tab") return;
        const buttons = [
          ...event.currentTarget.querySelectorAll<HTMLButtonElement>("button"),
        ];
        const first = buttons[0],
          last = buttons.at(-1);
        if (event.shiftKey && document.activeElement === first) {
          event.preventDefault();
          last?.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault();
          first?.focus();
        }
      }}
      onCancel={(event) => {
        event.preventDefault();
        onCloseRef.current();
      }}
    >
      <div
        className="journal-lightbox-frame"
        onClick={(event) => event.stopPropagation()}
      >
        <button
          ref={closeRef}
          type="button"
          className="journal-lightbox-close"
          onClick={onClose}
        >
          <X size={20} aria-hidden="true" />
          Đóng
        </button>
        <MediaAccess key={media.id} entryId={entryId} media={media} enabled>
          {(url, onError) => (
            <img
              src={url}
              alt={`Ảnh ${index + 1} trên ${images.length}`}
              onError={onError}
            />
          )}
        </MediaAccess>
        {images.length > 1 ? (
          <div className="journal-lightbox-nav">
            <button
              type="button"
              onClick={() =>
                onIndex((index - 1 + images.length) % images.length)
              }
            >
              <ChevronLeft size={20} aria-hidden="true" />
              Ảnh trước
            </button>
            <span>
              {index + 1} / {images.length}
            </span>
            <button
              type="button"
              onClick={() => onIndex((index + 1) % images.length)}
            >
              Ảnh sau
              <ChevronRight size={20} aria-hidden="true" />
            </button>
          </div>
        ) : null}
      </div>
    </dialog>
  );
}

export function JournalFeedMedia({
  entryId,
  media,
}: {
  entryId: string;
  media: JournalMedia[];
}) {
  const [open, setOpen] = useState<number | null>(null);
  const images = media.filter(
    (item) => item.type === "image" && item.status === "ready",
  );
  const pendingImages = media.some(
    (item) => item.type === "image" && item.status !== "ready",
  );
  const other = media.filter((item) => item.type !== "image");
  const shown = images.slice(0, 4);
  const extra = images.length > 4 ? images.length - 4 : 0;
  if (!media.length) return null;
  return (
    <div className="journal-feed-media">
      {shown.length ? (
        <div className={`journal-gallery count-${shown.length}`}>
          {shown.map((item, index) => (
            <GalleryThumb
              key={item.id}
              entryId={entryId}
              media={item}
              extra={
                extra > 0 && index === shown.length - 1 ? extra : undefined
              }
              onOpen={() => setOpen(index)}
            />
          ))}
        </div>
      ) : null}
      {pendingImages ? (
        <p className="journal-media-unavailable">Một ảnh đang chờ tải lên.</p>
      ) : null}
      {other.map((item) => (
        <LazyPlayback key={item.id} entryId={entryId} media={item} />
      ))}
      {open !== null ? (
        <JournalLightbox
          entryId={entryId}
          images={images}
          index={open}
          onClose={() => setOpen(null)}
          onIndex={setOpen}
        />
      ) : null}
    </div>
  );
}

function LazyPlayback({
  entryId,
  media,
}: {
  entryId: string;
  media: JournalMedia;
}) {
  const [ref, seen] = useInView<HTMLDivElement>();
  return (
    <div
      ref={ref}
      className={`journal-playback journal-playback-${media.type}`}
    >
      <MediaAccess entryId={entryId} media={media} enabled={seen}>
        {(url, onError) =>
          media.type === "audio" ? (
            <audio
              controls
              preload="none"
              src={url}
              aria-label="Bản ghi âm của khoảnh khắc"
              onError={onError}
            />
          ) : (
            <video
              controls
              preload="none"
              playsInline
              src={url}
              aria-label="Video của khoảnh khắc"
              onError={onError}
            />
          )
        }
      </MediaAccess>
    </div>
  );
}
