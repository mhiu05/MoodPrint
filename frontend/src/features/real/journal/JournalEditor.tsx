import { useRef, useState, type FormEvent } from "react";
import { useGSAP } from "@gsap/react";
import gsap from "gsap";
import { useMotionPolicy } from "../../../components/motion/useMotionPolicy";
import { Bookmark, Check, ChevronDown, Leaf, PenLine } from "lucide-react";
import { Button } from "../../../components/UI";
import { ApiError } from "../../../api/client";
import type { JournalEntry, JournalInput } from "../../../api/journal";
import { ErrorNotice, useSession } from "../RealApp";
import { useTourBlocker } from "../../onboarding/tourActivity";
import {
  JournalAttachments,
  type JournalAttachmentsHandle,
} from "./JournalAttachments";
import { MoodFace } from "./JournalShared";
import {
  emotionChoices,
  factorChoices,
  formatJournalDate,
  journalMoodLabels,
  toggleChoice,
  journalDateWindow,
  isActiveJournalDate,
} from "./journalModel";
import { useJournalGuard } from "./useJournalGuard";

type Props = {
  today: string;
  initial?: JournalEntry;
  seedDate?: string;
  prompt?: string;
  onSaved?: (entry: JournalEntry) => void;
};

export function JournalEditor({
  today,
  initial,
  seedDate,
  prompt,
  onSaved,
}: Props) {
  const { api } = useSession();
  const { earliest } = journalDateWindow(today);
  const [date, setDate] = useState(initial?.localDate || seedDate || today);
  const [mood, setMood] = useState(initial?.mood || 3);
  const [text, setText] = useState(initial?.text || "");
  const [emotions, setEmotions] = useState(initial?.emotions || []);
  const [factors, setFactors] = useState(initial?.factors || []);
  const [server, setServer] = useState(initial);
  const serverRef = useRef(initial);
  const receiptRef = useRef<HTMLParagraphElement>(null);
  const { animate } = useMotionPolicy();
  const attachments = useRef<JournalAttachmentsHandle>(null);
  const fingerprint = JSON.stringify({ date, mood, text, emotions, factors });
  const [savedFingerprint, setSavedFingerprint] = useState(fingerprint);
  const [pendingMedia, setPendingMedia] = useState(false),
    [mediaBusy, setMediaBusy] = useState(false);
  const [saving, setSaving] = useState(false),
    [error, setError] = useState<unknown>(),
    [receipt, setReceipt] = useState("");
  const [conflict, setConflict] = useState(false),
    [conflictEntry, setConflictEntry] = useState<JournalEntry>();
  const dirty = fingerprint !== savedFingerprint || pendingMedia;
  const guard = useJournalGuard(dirty || saving || mediaBusy);
  useTourBlocker("draft", dirty || saving);
  useTourBlocker("voice", mediaBusy);
  function receive(entry: JournalEntry) {
    serverRef.current = entry;
    setServer(entry);
  }
  function receiveMedia(entry: JournalEntry) {
    if (serverRef.current && entry.version !== serverRef.current.version) {
      setConflict(true);
      const reason = new ApiError(
        409,
        "STALE_VERSION",
        "Khoảnh khắc vừa thay đổi ở nơi khác. Phần đang viết của bạn vẫn được giữ.",
      );
      throw reason;
    }
    receive(entry);
  }
  useGSAP(
    () => {
      if (receipt && animate)
        gsap.fromTo(
          receiptRef.current,
          { y: 4 },
          { y: 0, duration: 0.22, ease: "power2.out", clearProps: "transform" },
        );
    },
    {
      scope: receiptRef,
      dependencies: [receipt, animate],
      revertOnUpdate: true,
    },
  );
  async function persist(
    status: JournalInput["status"],
  ): Promise<JournalEntry> {
    if (!isActiveJournalDate(date, today))
      throw new ApiError(
        422,
        "JOURNAL_DATE_RANGE",
        "Chọn ngày trong 90 ngày gần đây, tính đến hôm nay.",
      );
    const previous = serverRef.current;
    const input = {
      localDate: date,
      mood,
      text,
      emotions,
      factors,
      status,
    } satisfies JournalInput;
    const saved = await api.request<JournalEntry>(
      previous ? `/journal/entries/${previous.id}` : "/journal/entries",
      {
        method: previous ? "PUT" : "POST",
        body: previous
          ? { ...input, expectedVersion: previous.version }
          : input,
      },
    );
    receive(saved);
    setSavedFingerprint(fingerprint);
    onSaved?.(saved);
    return saved;
  }
  async function save(status: "draft" | "saved", event?: FormEvent) {
    event?.preventDefault();
    if (saving || mediaBusy) return;
    setSaving(true);
    setError(undefined);
    setReceipt("");
    try {
      const hasFiles = attachments.current?.hasPending();
      let saved = await persist(
        hasFiles ? serverRef.current?.status || "draft" : status,
      );
      if (hasFiles) {
        saved = await attachments.current!.flush(saved);
        receive(saved);
        if (saved.status !== status) saved = await persist(status);
      }
      setConflict(false);
      setConflictEntry(undefined);
      setReceipt(
        status === "draft"
          ? `Đã lưu bản nháp ngày ${formatJournalDate(saved.localDate)}.`
          : `Đã lưu khoảnh khắc ngày ${formatJournalDate(saved.localDate)}.`,
      );
    } catch (reason) {
      setError(reason);
      if (reason instanceof ApiError && reason.status === 409)
        setConflict(true);
    } finally {
      setSaving(false);
    }
  }
  async function ensureEntry() {
    setSaving(true);
    setError(undefined);
    try {
      return await persist(serverRef.current?.status || "draft");
    } catch (reason) {
      setError(reason);
      if (reason instanceof ApiError && reason.status === 409)
        setConflict(true);
      throw reason;
    } finally {
      setSaving(false);
    }
  }
  async function inspectConflict() {
    if (!serverRef.current) return;
    try {
      setConflictEntry(
        await api.request<JournalEntry>(
          `/journal/entries/${serverRef.current.id}`,
        ),
      );
    } catch (reason) {
      setError(reason);
    }
  }
  const busy = saving || mediaBusy;
  return (
    <form
      className="journal-editor"
      onSubmit={(event) => void save("saved", event)}
    >
      <div className="journal-editor-top">
        <div className="journal-date-control">
          <label htmlFor="journal-date">Ngày của khoảnh khắc</label>
          <input
            id="journal-date"
            type="date"
            required
            min={earliest}
            max={today}
            value={date}
            disabled={busy}
            onChange={(event) => {
              setDate(event.target.value);
              setReceipt("");
            }}
          />
        </div>
        {server?.status === "draft" ? (
          <span className="journal-draft-badge">
            <PenLine size={14} />
            Bản nháp đã lưu
          </span>
        ) : server ? (
          <span className="journal-saved-label">
            <Check size={15} />
            Đã lưu
          </span>
        ) : (
          <span className="journal-private">
            <Leaf size={15} />
            Một khoảng riêng cho bạn
          </span>
        )}
      </div>
      <fieldset className="journal-checkin" disabled={busy}>
        <legend>Hôm nay bạn thế nào?</legend>
        <p>Không có cảm xúc nào là sai cả.</p>
        <div className="journal-mood-options">
          {journalMoodLabels.map((label, index) => (
            <label
              className={`journal-mood-option ${mood === index + 1 ? "is-selected" : ""}`}
              key={label}
            >
              <input
                type="radio"
                name="journal-mood"
                value={index + 1}
                checked={mood === index + 1}
                onChange={() => {
                  setMood(index + 1);
                  setReceipt("");
                }}
              />
              <MoodFace value={index + 1} />
              <span>{label}</span>
            </label>
          ))}
        </div>
      </fieldset>
      <fieldset className="journal-choices" disabled={busy}>
        <legend>Cảm xúc nào gần với bạn nhất?</legend>
        <p>Bạn có thể chọn nhiều cảm xúc.</p>
        <div className="journal-chip-options">
          {[...new Set([...emotionChoices, ...emotions])].map((label) => (
            <label
              key={label}
              className={emotions.includes(label) ? "is-selected" : ""}
            >
              <input
                type="checkbox"
                checked={emotions.includes(label)}
                onChange={() =>
                  setEmotions((previous) => toggleChoice(previous, label))
                }
              />
              <span>{label}</span>
              {emotions.includes(label) ? <Check size={15} /> : null}
            </label>
          ))}
        </div>
      </fieldset>
      <fieldset className="journal-choices journal-factors" disabled={busy}>
        <legend>Điều gì đã ảnh hưởng đến bạn?</legend>
        <div className="journal-chip-options">
          {[...new Set([...factorChoices, ...factors])].map((label) => (
            <label
              key={label}
              className={factors.includes(label) ? "is-selected" : ""}
            >
              <input
                type="checkbox"
                checked={factors.includes(label)}
                onChange={() =>
                  setFactors((previous) => toggleChoice(previous, label))
                }
              />
              <span>{label}</span>
              {factors.includes(label) ? <Check size={15} /> : null}
            </label>
          ))}
        </div>
      </fieldset>
      <section
        className="journal-writing"
        aria-labelledby="journal-writing-title"
      >
        <h2 id="journal-writing-title">Ghi lại khoảnh khắc</h2>
        <label htmlFor="journal-text">Khoảnh khắc của bạn</label>
        <textarea
          id="journal-text"
          value={text}
          maxLength={10000}
          rows={7}
          disabled={busy}
          placeholder={
            prompt || "Hôm nay có điều gì khiến bạn suy nghĩ nhiều nhất?"
          }
          aria-describedby="journal-text-help"
          onChange={(event) => {
            setText(event.target.value);
            setReceipt("");
          }}
        />
        <div id="journal-text-help" className="journal-text-help">
          <span>Viết một chút, hoặc giữ lại bằng hình ảnh và âm thanh.</span>
          <span>{Array.from(text).length.toLocaleString("vi-VN")}/10.000</span>
        </div>
      </section>
      <JournalAttachments
        ref={attachments}
        entry={server}
        ensureEntry={ensureEntry}
        onEntry={receiveMedia}
        onPending={setPendingMedia}
        onBusy={setMediaBusy}
        disabled={saving}
      />
      <p className="journal-help">
        Chỉ bạn xem nhật ký. Khi bạn trò chuyện với Nhịp, Nhịp có thể đọc các
        khoảnh khắc đã lưu để đồng hành cùng bạn. Tệp đính kèm không tự động
        được gửi cho AI.
      </p>
      <ErrorNotice error={error} />
      {conflict ? (
        <div className="journal-conflict">
          <p>
            Khoảnh khắc vừa thay đổi ở nơi khác. Phần bạn đang viết vẫn được
            giữ. Xem phiên bản mới trước khi quyết định lưu lại.
          </p>
          <Button variant="secondary" onClick={() => void inspectConflict()}>
            Xem phiên bản mới
          </Button>
          {conflictEntry ? (
            <>
              <blockquote>
                {conflictEntry.text || "Phiên bản này không có lời viết."}
              </blockquote>
              <Button
                variant="secondary"
                onClick={() => {
                  receive(conflictEntry);
                  setConflict(false);
                  setConflictEntry(undefined);
                  setError(undefined);
                }}
              >
                Dùng phiên bản mới làm mốc và giữ phần đang viết
              </Button>
            </>
          ) : null}
        </div>
      ) : null}
      <div className="journal-save-actions">
        <Button type="submit" disabled={busy || !date || conflict}>
          <Bookmark size={18} />
          {saving ? "Đang lưu…" : "Lưu khoảnh khắc"}
        </Button>
        <Button
          variant="secondary"
          disabled={busy || !date || conflict}
          onClick={() => void save("draft")}
        >
          Lưu bản nháp
        </Button>
      </div>
      <p
        ref={receiptRef}
        className="journal-save-receipt"
        role="status"
        aria-live="polite"
      >
        {receipt}
      </p>
      {server && !dirty && !busy ? (
        <Button
          variant="text"
          onClick={() =>
            guard.guard(() => {
              setDate(today);
              setMood(3);
              setText("");
              setEmotions([]);
              setFactors([]);
              serverRef.current = undefined;
              setServer(undefined);
              setSavedFingerprint(
                JSON.stringify({
                  date: today,
                  mood: 3,
                  text: "",
                  emotions: [],
                  factors: [],
                }),
              );
              setReceipt("");
            })
          }
        >
          Viết khoảnh khắc mới
        </Button>
      ) : null}
      {guard.dialog}
    </form>
  );
}
