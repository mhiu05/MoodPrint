import { useState } from "react";
import { Navigate } from "react-router-dom";
import { Button, cx, Dialog, StatePanel } from "../../../components/UI";
import type { components } from "../../../api/generated/schema";
import { ErrorNotice, useResource, useSession } from "../RealApp";

type Schema = components["schemas"];
type Row = Schema["AdminReportView"];
type Action = Schema["ResolveInput"]["action"];

const ACTIONS: { action: Action; label: string; days?: boolean; danger?: boolean }[] = [
  { action: "dismiss", label: "Không phát hiện vi phạm" },
  { action: "warn", label: "Cảnh báo" },
  { action: "restrict", label: "Hạn chế kết nối", days: true, danger: true },
  { action: "suspend", label: "Tạm khóa tài khoản", days: true, danger: true },
];
const STATUS: Record<string, string> = {
  received: "Mới",
  in_review: "Đang xem xét",
  resolved: "Đã xử lý",
};
const RESOLUTION: Record<string, string> = {
  dismissed: "Không vi phạm",
  warned: "Đã cảnh báo",
  restricted: "Đã hạn chế kết nối",
  suspended: "Đã tạm khóa tài khoản",
};

/** Staff-only queue (DR-11). The server re-checks the role on every request. */
export function Moderation() {
  const { api, session } = useSession();
  const [status, setStatus] = useState<"open" | "resolved">("open");
  const queue = useResource<Row[]>(
    status === "open" ? "/admin/reports" : "/admin/reports?status=resolved",
    Boolean(session.staff),
  );
  const [busy, setBusy] = useState(false),
    [error, setError] = useState<unknown>(),
    [notice, setNotice] = useState("");
  const [pending, setPending] = useState<{ row: Row; action: Action }>();
  const [days, setDays] = useState(7),
    [note, setNote] = useState("");
  if (!session.staff) return <Navigate replace to="/assistants" />;
  async function run(work: () => Promise<unknown>, done: string) {
    if (busy) return;
    setBusy(true);
    setError(undefined);
    setNotice("");
    try {
      await work();
      setNotice(done);
      queue.refresh();
    } catch (reason) {
      setError(reason);
      queue.refresh();
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className={cx.reading}>
      <h1 tabIndex={-1}>Kiểm duyệt báo cáo</h1>
      <p className={cx.lede}>
        Chỉ xem phần bằng chứng người báo cáo đã chọn. Mọi quyết định đều được ghi
        lại. Mục tiêu phản hồi trong 48 giờ.
      </p>
      <div className={cx.actions} role="group" aria-label="Lọc báo cáo">
        <Button
          variant={status === "open" ? "primary" : "secondary"}
          aria-pressed={status === "open"}
          onClick={() => setStatus("open")}
        >
          Đang chờ
        </Button>
        <Button
          variant={status === "resolved" ? "primary" : "secondary"}
          aria-pressed={status === "resolved"}
          onClick={() => setStatus("resolved")}
        >
          Đã xử lý
        </Button>
      </div>
      <ErrorNotice error={error || queue.error} retry={queue.refresh} />
      {notice && <p role="status">{notice}</p>}
      {queue.loading && <p role="status">Đang tải báo cáo…</p>}
      {queue.data?.length === 0 && (
        <StatePanel title="Không có báo cáo nào">Thử chuyển bộ lọc để xem các báo cáo khác.</StatePanel>
      )}
      {queue.data?.map((row) => (
        <article className="real-item" key={row.id} aria-label={`Báo cáo ${row.subjectRef}`}>
          <h2>
            {row.reason} <small>· {STATUS[row.status] ?? row.status}</small>
          </h2>
          <p className={cx.footnote}>
            Nhận lúc {new Date(row.createdAt).toLocaleString("vi-VN")} · Đối tượng{" "}
            {row.subjectRef.slice(0, 10)}… · {row.priorActions} quyết định trước đó
            {row.resolution ? ` · Kết quả: ${RESOLUTION[row.resolution] ?? "Đã xử lý"}` : ""}
          </p>
          {row.evidence.length === 0 ? (
            <p>Không có bằng chứng được chọn.</p>
          ) : (
            <ul>
              {row.evidence.map((item, index) => (
                <li key={index}>
                  <strong>{item.kind === "activity" ? "Câu trả lời hoạt động" : "Tin nhắn"}:</strong>{" "}
                  {item.text}
                </li>
              ))}
            </ul>
          )}
          {row.status !== "resolved" && (
            <div className={cx.actions}>
              {row.status === "received" && (
                <Button
                  variant="secondary"
                  disabled={busy}
                  onClick={() =>
                    void run(async () => {
                      const claimed = await api.request<Row>(`/admin/reports/${row.id}/claim`, {
                        method: "POST",
                        body: { expectedVersion: row.version },
                      });
                      // Use the claimed version at once; a decision made before the
                      // refetch lands would otherwise carry a stale version (409).
                      queue.setData((rows) =>
                        rows?.map((item) => (item.id === claimed.id ? claimed : item)),
                      );
                    }, "Bạn đang xem xét báo cáo này.")
                  }
                >
                  Nhận xử lý
                </Button>
              )}
              {ACTIONS.map(({ action, label, danger }) => (
                <Button
                  key={action}
                  variant={danger ? "danger" : "secondary"}
                  disabled={busy}
                  onClick={() => {
                    setNote("");
                    setPending({ row, action });
                  }}
                >
                  {label}
                </Button>
              ))}
            </div>
          )}
        </article>
      ))}
      {pending && (
        <Dialog
          title={`Xác nhận: ${ACTIONS.find((item) => item.action === pending.action)?.label}`}
          destructive={["restrict", "suspend"].includes(pending.action)}
          onClose={() => !busy && setPending(undefined)}
        >
          {ACTIONS.find((item) => item.action === pending.action)?.days && (
            <label className="real-field">
              Số ngày (1–90)
              <input
                type="number"
                min={1}
                max={90}
                value={days}
                onChange={(event) => setDays(Number(event.target.value))}
              />
            </label>
          )}
          <label className="real-field">
            Ghi chú xử lý (chỉ nội bộ)
            <textarea maxLength={500} value={note} onChange={(event) => setNote(event.target.value)} />
          </label>
          <div className={cx.actions}>
            <Button variant="secondary" data-cancel disabled={busy} onClick={() => setPending(undefined)}>
              Hủy
            </Button>
            <Button
              variant={["restrict", "suspend"].includes(pending.action) ? "danger" : "primary"}
              disabled={busy}
              onClick={() =>
                void run(async () => {
                  await api.request(`/admin/reports/${pending.row.id}/resolve`, {
                    method: "POST",
                    body: {
                      expectedVersion: pending.row.version,
                      action: pending.action,
                      note,
                      ...(["restrict", "suspend"].includes(pending.action) ? { days } : {}),
                    } satisfies Schema["ResolveInput"],
                  });
                  setPending(undefined);
                }, "Đã ghi nhận quyết định.")
              }
            >
              Xác nhận
            </Button>
          </div>
        </Dialog>
      )}
    </div>
  );
}
