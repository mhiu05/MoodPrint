import { useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { Button, Dialog } from "../../../components/UI";
import type { JournalEntry } from "../../../api/journal";
import { ErrorNotice, useResource, useSession } from "../RealApp";
import { JournalEditor } from "./JournalEditor";
import {
  JournalMediaPreview,
  JournalMomentMenu,
  JournalNav,
  MoodFace,
} from "./JournalShared";
import { formatJournalDate, journalMoodLabels } from "./journalModel";
import { useJournalToday } from "./JournalPage";

export function JournalEntryDetail() {
  const { id } = useParams();
  const { api } = useSession();
  const navigate = useNavigate();
  const validId =
    /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(
      id || "",
    );
  const entry = useResource<JournalEntry>(`/journal/entries/${id}`, validId);
  const today = useJournalToday();
  const [params] = useSearchParams();
  const [editing, setEditing] = useState(params.get("edit") === "1"),
    [deleting, setDeleting] = useState(false),
    [busy, setBusy] = useState(false),
    [error, setError] = useState<unknown>();
  async function remove() {
    if (!entry.data || busy) return;
    setBusy(true);
    setError(undefined);
    try {
      await api.request(`/journal/entries/${id}`, {
        method: "DELETE",
        body: { expectedVersion: entry.data.version },
      });
      setDeleting(false);
      navigate("/self/memories", { replace: true });
    } catch (reason) {
      setError(reason);
      setDeleting(false);
    } finally {
      setBusy(false);
    }
  }
  const data = entry.data?.id === id && !entry.loading ? entry.data : undefined;
  return (
    <div className="journal-page journal-detail-page">
      <JournalNav />
      {entry.loading ? <p role="status">Đang mở khoảnh khắc…</p> : null}
      <ErrorNotice error={entry.error} retry={entry.refresh} />
      {!validId || (!entry.loading && !data) ? (
        <section className="journal-empty">
          <h1 tabIndex={-1}>Khoảnh khắc chưa mở được</h1>
          <p>Ghi chép có thể đã bị xóa hoặc không thuộc tài khoản của bạn.</p>
          <Link to="/self/memories">Về khoảnh khắc của bạn</Link>
        </section>
      ) : null}
      {data ? (
        <>
          <header className="journal-detail-heading">
            <div>
              <h1 tabIndex={-1}>
                Khoảnh khắc ngày {formatJournalDate(data.localDate)}
              </h1>
              <p>
                {data.status === "draft"
                  ? "Bản nháp · Chỉ bạn xem"
                  : "Đã lưu · Chỉ bạn xem"}
              </p>
            </div>
            <MoodFace value={data.mood} size={58} />
          </header>
          {editing || data.status === "draft" ? (
            <JournalEditor
              key={data.id}
              initial={data}
              today={today}
              onSaved={(saved) => {
                setEditing(true);
                entry.setData(saved);
              }}
            />
          ) : (
            <>
              <div className="journal-detail-actions">
                <JournalMomentMenu
                  menuLabel="Thao tác với khoảnh khắc"
                  onEdit={() => setEditing(true)}
                  onDelete={() => setDeleting(true)}
                />
              </div>
              <article className="journal-detail-content">
                <div className="journal-detail-tags">
                  <strong>{journalMoodLabels[data.mood - 1]}</strong>
                  {[...data.emotions, ...data.factors].map((tag, index) => (
                    <span key={`${tag}-${index}`}>{tag}</span>
                  ))}
                </div>
                <p className="journal-detail-text">
                  {data.text ||
                    "Bạn đã giữ lại cảm xúc mà không cần thêm lời viết."}
                </p>
                {data.media.length ? (
                  <section
                    className="journal-detail-media"
                    aria-label="Tệp đính kèm"
                  >
                    {data.media.map((media) => (
                      <JournalMediaPreview
                        key={media.id}
                        entryId={data.id}
                        media={media}
                      />
                    ))}
                  </section>
                ) : null}
              </article>
            </>
          )}
        </>
      ) : null}
      <ErrorNotice error={error} />
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
    </div>
  );
}
