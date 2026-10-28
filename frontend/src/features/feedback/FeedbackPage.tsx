import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { Button, cx, StatePanel } from "../../components/UI";
import { ApiError } from "../../api/client";
import type { FeedbackInput, FeedbackReceipt, FeedbackSubmissionState } from "../../api/contracts";
import { ErrorNotice, useResource, useSession } from "../real/RealApp";
import { categories, ratingLabels } from "./feedbackLabels";
import "./feedback.css";

function sameBangkokDay(first: string, second: string): boolean {
  const format = new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Bangkok", year: "numeric", month: "2-digit", day: "2-digit" });
  return format.format(new Date(first)) === format.format(new Date(second));
}

export default function FeedbackPage() {
  const { api, session } = useSession();
  const enabled = session.features.feedback === true;
  const submission = useResource<FeedbackSubmissionState>("/feedback/submission-state", enabled);
  const [rating, setRating] = useState<number | null>(null);
  const [selected, setSelected] = useState<NonNullable<FeedbackInput["categories"]>>([]);
  const [comment, setComment] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>();
  const [receipt, setReceipt] = useState<FeedbackReceipt>();
  const controller = useRef<AbortController | null>(null);
  const sending = useRef(false);
  const guest = session.accountKind === "guest";
  const count = Array.from(comment).length;
  useEffect(() => {
    const active = new AbortController();
    controller.current = active;
    return () => active.abort();
  }, []);
  async function submit(event: FormEvent) {
    event.preventDefault();
    const active = controller.current;
    if (!enabled || sending.current || rating === null || count > 1000 || !active || active.signal.aborted) return;
    sending.current = true;
    setBusy(true);
    setError(undefined);
    const epoch = api.epoch;
    const current = () => !active.signal.aborted && api.epoch === epoch;
    try {
      const result = await api.request<FeedbackReceipt>("/feedback", {
        method: "POST", signal: active.signal,
        body: { rating, categories: selected, comment: comment.trim() || null, context: "general", disclosureVersion: "feedback-v1" } satisfies FeedbackInput,
      });
      if (!result || result.status !== "received" ||
        typeof result.feedbackId !== "string" || !/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(result.feedbackId) ||
        typeof result.createdAt !== "string" || !Number.isFinite(Date.parse(result.createdAt)))
        throw new ApiError(503, "FEEDBACK_UNCONFIRMED", "Chưa xác nhận được góp ý. Vui lòng thử lại.");
      if (current()) { setReceipt(result); setComment(""); setSelected([]); }
    } catch (reason) {
      if (current()) {
        setError(reason);
        if (reason instanceof ApiError && ["FEEDBACK_ALREADY_SUBMITTED", "FEEDBACK_DAILY_LIMIT"].includes(reason.code)) submission.refresh();
      }
    } finally {
      sending.current = false;
      if (current()) setBusy(false);
    }
  }
  if (!enabled) return <StatePanel title="Góp ý cho MoodPrint">MoodPrint chưa mở nhận góp ý.</StatePanel>;
  if (submission.loading) return <p role="status">Đang kiểm tra góp ý đã gửi…</p>;
  if (submission.error) return <ErrorNotice error={submission.error} retry={submission.refresh} />;
  if (receipt) return (
    <section className="feedback-page" aria-labelledby="feedback-thanks">
      <h1 id="feedback-thanks" tabIndex={-1}>Góp ý cho MoodPrint</h1>
      <p role="status">Cảm ơn bạn. MoodPrint đã nhận góp ý.</p>
      <p>Bạn có thể giữ mã này để xác định góp ý nếu cần yêu cầu xử lý thông tin đã gửi:</p>
      <p className="feedback-receipt">{receipt.feedbackId}</p>
      <Link to="/assistants">Về trợ lý</Link>
    </section>
  );
  const alreadySubmitted = submission.data?.submitted && (guest || (
    submission.data.lastSubmittedAt && sameBangkokDay(submission.data.lastSubmittedAt, session.serverTime)
  ));
  if (alreadySubmitted) return <StatePanel title="Cảm ơn bạn đã góp ý.">{guest ? "Bạn đã gửi góp ý trong lượt dùng thử này." : "Bạn đã gửi góp ý hôm nay. Bạn có thể gửi góp ý mới vào ngày mai (Asia/Bangkok)."}</StatePanel>;
  return (
    <div className="feedback-page">
      <h1 tabIndex={-1}>Góp ý cho MoodPrint</h1>
      <p className={cx.lede}>Một đánh giá ngắn giúp MoodPrint hiểu trải nghiệm của bạn. Bạn có thể bỏ qua và tiếp tục sử dụng.</p>
      <form onSubmit={(event) => void submit(event)} aria-busy={busy}>
        <fieldset disabled={busy} className="feedback-rating">
          <legend>Bạn thấy MoodPrint thế nào?</legend>
          {ratingLabels.map((label, index) => (
            <label key={label}>
              <input type="radio" name="feedback-rating" required value={index + 1} checked={rating === index + 1} onChange={() => setRating(index + 1)} />
              <span>{index + 1} {label}</span>
            </label>
          ))}
        </fieldset>
        <fieldset disabled={busy} className="feedback-categories">
          <legend>Bạn muốn góp ý về điều gì? <span>(không bắt buộc)</span></legend>
          {Object.entries(categories).map(([code, label]) => (
            <label key={code}>
              <input type="checkbox" checked={selected.includes(code as keyof typeof categories)} onChange={(event) => setSelected((previous) => event.target.checked ? [...previous, code as keyof typeof categories] : previous.filter((value) => value !== code))} />
              {label}
            </label>
          ))}
        </fieldset>
        <label htmlFor="feedback-comment" className="feedback-comment-label">Chia sẻ thêm nếu bạn muốn</label>
        <textarea id="feedback-comment" name="feedback-comment" autoComplete="off" value={comment} disabled={busy} rows={5} aria-describedby="feedback-help feedback-count" aria-invalid={count > 1000 || undefined} onChange={(event) => setComment(event.target.value)} />
        <p id="feedback-count" className={cx.footnote} aria-live="polite">{count}/1000 ký tự</p>
        <p id="feedback-help">Bạn không cần viết thêm để gửi đánh giá. Đừng gửi thông tin liên hệ, nội dung trò chuyện hay nhật ký riêng tư.</p>
        <ErrorNotice error={error} />
        <p className="feedback-disclosure">Góp ý bạn chủ động gửi sẽ được lưu riêng tối đa 180 ngày để cải thiện MoodPrint, kể cả sau khi lượt dùng thử kết thúc. Góp ý không kèm cuộc trò chuyện, nhật ký hay thông tin đăng nhập.</p>
        <Button type="submit" disabled={busy || rating === null || count > 1000}>{busy ? "Đang gửi…" : "Gửi góp ý"}</Button>
      </form>
    </div>
  );
}
