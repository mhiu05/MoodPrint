import { useEffect, useRef, useState, type FormEvent } from "react";
import { useSearchParams } from "react-router-dom";
import { Button, StatePanel } from "../../../components/UI";
import { ApiError } from "../../../api/client";
import type { FeedbackAdminView, FeedbackPage, FeedbackStatusInput, FeedbackSummary } from "../../../api/contracts";
import { ErrorNotice, useSession } from "../RealApp";
import { ReauthForm } from "../Auth";
import { categories, contexts, statuses } from "../../feedback/feedbackLabels";
import "../../feedback/feedback.css";

const number = new Intl.NumberFormat("vi-VN", { maximumFractionDigits: 2 });
const dateTime = new Intl.DateTimeFormat("vi-VN", { dateStyle: "short", timeStyle: "short", timeZone: "Asia/Bangkok" });
const filterNames = ["fromDate", "toDate", "appVersion", "accountKind", "rating", "status", "category", "includeSpam"];

function ReviewRow({ row, busy, review }: { row: FeedbackAdminView; busy: boolean; review: (row: FeedbackAdminView, status: FeedbackStatusInput["status"]) => void }) {
  const [status, setStatus] = useState(row.status);
  useEffect(() => setStatus(row.status), [row.version, row.status]);
  return <tr>
    <td>{row.rating}/5<br /><time dateTime={row.createdAt}>{dateTime.format(new Date(row.createdAt))}</time></td>
    <td><p className="feedback-comment">{row.comment ?? "Không có bình luận"}</p><p>{row.categories.map((category) => categories[category]).join(", ") || "Không chọn nhóm"}</p></td>
    <td>{row.accountKind === "guest" ? "Dùng thử" : "Đã đăng ký"}<br />{row.appVersion}<br />{contexts[row.context]}</td>
    <td><label className="feedback-visually-hidden" htmlFor={`feedback-status-${row.id}`}>Trạng thái góp ý {row.id}</label>
      <select id={`feedback-status-${row.id}`} value={status} disabled={busy} onChange={(event) => setStatus(event.target.value as FeedbackStatusInput["status"])}>
        {Object.entries(statuses).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
      </select>
      <Button variant="secondary" aria-disabled={busy} aria-label={`Lưu trạng thái ${row.id}`} onClick={() => { if (!busy) review(row, status); }}>Lưu trạng thái</Button>
    </td>
  </tr>;
}

export default function FeedbackAdmin() {
  const { api, session } = useSession();
  const allowed = session.accountKind !== "guest" && session.staff === "admin";
  const [params, setParams] = useSearchParams();
  const filters = new URLSearchParams();
  for (const name of filterNames) { const value = params.get(name); if (value) filters.set(name, value); }
  const query = filters.toString();
  const [items, setItems] = useState<FeedbackAdminView[]>([]);
  const [summary, setSummary] = useState<FeedbackSummary>();
  const [cursor, setCursor] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>();
  const [denied, setDenied] = useState(false);
  const [revision, setRevision] = useState(0);
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const scope = useRef<AbortController | null>(null);
  const previousQuery = useRef(query);
  const generation = useRef(0);
  useEffect(() => {
    const controller = new AbortController();
    scope.current = controller;
    return () => controller.abort();
  }, []);
  const fail = (reason: unknown) => {
    setItems([]); setSummary(undefined); setCursor(null);
    if (reason instanceof ApiError && reason.status === 403 && reason.code !== "REAUTH_REQUIRED") setDenied(true);
    else setError(reason);
  };
  useEffect(() => {
    if (!allowed) return;
    const controller = new AbortController();
    const epoch = api.epoch;
    const currentGeneration = ++generation.current;
    const active = () => !controller.signal.aborted && api.epoch === epoch && generation.current === currentGeneration;
    if (previousQuery.current !== query) { setItems([]); setSummary(undefined); previousQuery.current = query; }
    setLoading(true); setError(undefined);
    void Promise.all([
      api.request<FeedbackPage>(`/admin/feedback?${query}`, { signal: controller.signal }),
      api.request<FeedbackSummary>(`/admin/feedback/summary?${query}`, { signal: controller.signal }),
    ]).then(([page, metrics]) => {
      if (active()) { setItems(page.items); setCursor(page.nextCursor); setSummary(metrics); }
    }).catch((reason) => { if (active()) fail(reason); })
      .finally(() => { if (active()) setLoading(false); });
    return () => controller.abort();
  }, [api, allowed, query, revision]);
  function apply(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const next = new URLSearchParams();
    for (const [key, value] of new FormData(event.currentTarget)) if (typeof value === "string" && value) next.set(key, value);
    setParams(next); setNotice("");
  }
  async function loadMore() {
    if (!cursor || busy || !scope.current) return;
    const controller = scope.current, epoch = api.epoch, version = generation.current;
    setBusy(true); setError(undefined);
    const active = () => !controller.signal.aborted && epoch === api.epoch && version === generation.current;
    try {
      const next = new URLSearchParams(query); next.set("cursor", cursor);
      const result = await api.request<FeedbackPage>(`/admin/feedback?${next}`, { signal: controller.signal });
      if (active()) { setItems((old) => [...old, ...result.items.filter((item) => !old.some((row) => row.id === item.id))]); setCursor(result.nextCursor); }
    } catch (reason) { if (active()) fail(reason); }
    finally { if (!controller.signal.aborted) setBusy(false); }
  }
  async function review(row: FeedbackAdminView, status: FeedbackStatusInput["status"]) {
    if (busy || !scope.current) return;
    const controller = scope.current, epoch = api.epoch, version = generation.current;
    const active = () => !controller.signal.aborted && epoch === api.epoch && version === generation.current;
    setBusy(true); setError(undefined); setNotice("");
    try {
      const updated = await api.request<FeedbackAdminView>(`/admin/feedback/${row.id}`, { method: "PATCH", body: { status, expectedVersion: row.version } satisfies FeedbackStatusInput, signal: controller.signal });
      if (active()) { setItems((old) => old.map((item) => item.id === updated.id ? updated : item)); setNotice("Đã cập nhật trạng thái góp ý."); setRevision((old) => old + 1); }
    } catch (reason) {
      if (active()) {
        if (reason instanceof ApiError && ["STALE_VERSION", "NOT_FOUND"].includes(reason.code)) {
          setNotice("Góp ý đã thay đổi. Danh sách được tải lại; hãy xem trạng thái mới trước khi cập nhật."); setRevision((old) => old + 1);
        } else fail(reason);
      }
    } finally { if (!controller.signal.aborted) setBusy(false); }
  }
  if (!allowed || denied) return <StatePanel title="Góp ý và đánh giá">Bạn không có quyền xem góp ý.</StatePanel>;
  const needsReauth = error instanceof ApiError && error.code === "REAUTH_REQUIRED";
  return <div className="feedback-admin">
    <h1 tabIndex={-1}>Góp ý và đánh giá</h1>
    <p>Chỉ có góp ý người dùng tự gửi. Không kèm cuộc trò chuyện, nhật ký hay đường dẫn tới lịch sử riêng.</p>
    {needsReauth ? <ReauthForm api={api} onConfirmed={() => { setError(undefined); setRevision((old) => old + 1); }} onCancel={() => setError(undefined)} /> : <>
      <form key={query} className="feedback-filters" onSubmit={apply}>
        <label>Từ ngày<input type="date" name="fromDate" defaultValue={params.get("fromDate") || ""} /></label>
        <label>Đến ngày<input type="date" name="toDate" defaultValue={params.get("toDate") || ""} /></label>
        <label>Phiên bản ứng dụng<input name="appVersion" autoComplete="off" maxLength={64} defaultValue={params.get("appVersion") || ""} /></label>
        <label>Loại tài khoản<select name="accountKind" defaultValue={params.get("accountKind") || ""}><option value="">Tất cả</option><option value="guest">Dùng thử</option><option value="registered">Đã đăng ký</option></select></label>
        <label>Điểm<select name="rating" defaultValue={params.get("rating") || ""}><option value="">Tất cả</option>{[1, 2, 3, 4, 5].map((value) => <option key={value} value={value}>{value}</option>)}</select></label>
        <label>Trạng thái<select name="status" defaultValue={params.get("status") || ""}><option value="">Tất cả trừ spam</option>{Object.entries(statuses).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
        <label>Nhóm góp ý<select name="category" defaultValue={params.get("category") || ""}><option value="">Tất cả</option>{Object.entries(categories).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
        <label className="feedback-spam"><input type="checkbox" name="includeSpam" value="true" defaultChecked={params.get("includeSpam") === "true"} />Bao gồm spam</label>
        <Button type="submit" disabled={busy}>Áp dụng bộ lọc</Button>
        <Button variant="secondary" onClick={() => setParams({})}>Xóa bộ lọc</Button>
      </form>
      <p className="feedback-filter-help">Ngày theo Asia/Bangkok, tối đa 180 ngày. Mặc định 30 ngày gần nhất. Chọn trạng thái Spam sẽ chỉ xem spam.</p>
      <ErrorNotice error={error} retry={() => setRevision((old) => old + 1)} />
      {notice ? <p role="status">{notice}</p> : null}
      {loading ? <p role="status">Đang tải góp ý…</p> : null}
      {summary ? <section aria-labelledby="feedback-metrics">
        <h2 id="feedback-metrics">Đánh giá trong bộ lọc</h2>
        <p>{number.format(summary.count)} góp ý</p>
        <p>Điểm trung bình: <strong>{summary.meanRating === null ? "Chưa có đánh giá" : `${number.format(summary.meanRating)}/5`}</strong></p>
        <ol className="feedback-rating-bars">{[1, 2, 3, 4, 5].map((rating) => {
          const count = summary.ratingCounts[String(rating) as keyof typeof summary.ratingCounts] || 0;
          return <li key={rating}><span>{rating} điểm</span><meter min={0} max={Math.max(1, summary.count)} value={count} aria-label={`${rating} điểm: ${count} góp ý`} /><span>{count}</span></li>;
        })}</ol>
        <p>Dùng thử: {summary.accountKindCounts.guest} · Đã đăng ký: {summary.accountKindCounts.registered}</p>
        <h3>Nhóm góp ý</h3><p>Có thể chọn nhiều nhóm; tổng các nhóm có thể lớn hơn số góp ý.</p>
        <ul>{Object.entries(summary.categoryCounts).map(([category, count]) => <li key={category}>{categories[category as keyof typeof categories]}: {count}</li>)}</ul>
        <details><summary>Theo ngày và phiên bản</summary>
          <ul>{summary.byDate.map((bucket) => <li key={bucket.date}>{bucket.date}: {bucket.count} góp ý, {bucket.meanRating === null ? "Chưa có đánh giá" : `${number.format(bucket.meanRating)}/5`}</li>)}</ul>
          <ul>{summary.byVersion.map((bucket) => <li key={bucket.appVersion}>{bucket.appVersion === "(other)" ? "Các phiên bản khác" : bucket.appVersion}: {bucket.count} góp ý, {bucket.meanRating === null ? "Chưa có đánh giá" : `${number.format(bucket.meanRating)}/5`}</li>)}</ul>
        </details>
      </section> : null}
      {!loading && !error && items.length === 0 ? <p>Không có góp ý trong bộ lọc này.</p> : null}
      {items.length ? <div className="feedback-table-region" role="region" aria-label="Danh sách góp ý, có thể cuộn ngang" tabIndex={0}>
        <table><caption>Góp ý gần đây — giờ Asia/Bangkok</caption><thead><tr><th scope="col">Điểm / thời gian</th><th scope="col">Góp ý</th><th scope="col">Ngữ cảnh</th><th scope="col">Xử lý</th></tr></thead><tbody>
          {items.map((row) => <ReviewRow key={row.id} row={row} busy={busy} review={(item, status) => void review(item, status)} />)}
        </tbody></table>
      </div> : null}
      {cursor ? <Button variant="secondary" disabled={busy} onClick={() => void loadMore()}>Xem thêm góp ý</Button> : null}
    </>}
  </div>;
}
