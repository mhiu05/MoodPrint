import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import type { components } from "../../../api/generated/schema";
import { ApiError } from "../../../api/client";
import { cx, StatePanel } from "../../../components/UI";
import { ErrorNotice, useSession } from "../RealApp";
import { CAUNOI_NOTE, EDGE_COPY, EDGE_ORDER, sharingReason, type Edge } from "./collaborationCopy";
import "./collaboration.css";

type View = components["schemas"]["SharingView"];
type EdgeView = components["schemas"]["SharingEdgeView"];
type Status = { edge: Edge; text: string; error?: boolean };

function saveError(reason: unknown): string {
  if (reason instanceof ApiError) {
    if (reason.code === "SHARING_REQUIRES_JOURNAL_CONTEXT") return "Hãy bật \"Dùng khoảnh khắc đã lưu hôm qua\" ở Lịch hỏi thăm trước nhé.";
    if (reason.code === "STALE_VERSION") return "Cài đặt vừa thay đổi ở nơi khác. Mình đã tải lại để bạn xem.";
    if (reason.code === "ADULT_REQUIRED") return "Tính năng này chỉ dành cho tài khoản từ 18 tuổi.";
    if (reason.code === "COLLABORATION_UNAVAILABLE") return "Tính năng phối hợp đang tạm nghỉ. Bạn thử lại sau nhé.";
  }
  return "Chưa lưu được. Bạn thử lại nhé.";
}

/** /companion-sharing: one default-off switch per allowed edge, saved one at a time. */
export function SharingPage() {
  const { api } = useSession();
  const [view, setView] = useState<View>();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>();
  const [saving, setSaving] = useState<Edge | null>(null);
  const [status, setStatus] = useState<Status>();

  const load = useCallback(async () => {
    setError(undefined);
    try {
      setView(await api.request<View>("/ai/sharing"));
    } catch (reason) {
      setError(reason);
    } finally {
      setLoading(false);
    }
  }, [api]);
  useEffect(() => {
    void load();
  }, [load]);

  async function toggle(item: EdgeView, enabled: boolean) {
    const edge = item.edge as Edge;
    if (saving) return;
    setSaving(edge);
    setStatus(undefined);
    // Optimistic, reverted on failure (same pattern as the check-in page).
    setView((current) => current && { ...current, edges: current.edges.map((e) => (e.edge === edge ? { ...e, enabled } : e)) });
    try {
      const next = await api.request<View>(`/ai/sharing/${edge}`, {
        method: "PUT",
        body: { enabled, expectedVersion: item.version, policyVersion: "sharing-v1" },
      });
      setView(next);
      setStatus({ edge, text: enabled ? "Đã bật." : "Đã tắt. Việc chia sẻ dừng ngay." });
    } catch (reason) {
      setStatus({ edge, text: saveError(reason), error: true });
      await load();
    } finally {
      setSaving(null);
    }
  }

  const heading = <h1 tabIndex={-1}>Trợ lý phối hợp với nhau</h1>;
  if (loading) return <div className={cx.reading}>{heading}<p role="status">Đang tải cài đặt phối hợp…</p></div>;
  if (!view) return <div className={cx.reading}>{heading}<ErrorNotice error={error} retry={() => void load()} /></div>;
  const enabledAny = view.edges.some((edge) => edge.enabled);
  if (!view.available && !enabledAny) {
    const reason = sharingReason(view.edges[0]?.reason) ?? "Tính năng phối hợp chưa mở cho tài khoản của bạn.";
    return (
      <div className={cx.reading}>
        {heading}
        <StatePanel title={reason}>Mỗi trợ lý vẫn trò chuyện với bạn như bình thường.</StatePanel>
        <div className={cx.actions}><Link className={`${cx.button} ${cx.secondary}`} to="/profile">Về tài khoản</Link></div>
      </div>
    );
  }
  return (
    <div className={`${cx.reading} sharing-page`}>
      {heading}
      <p className="sharing-intro">
        Khi bạn cho phép, một trợ lý có thể nhờ trợ lý khác một việc nhỏ. Chỉ những gì ghi dưới đây được chia sẻ.
        Mặc định đều tắt.
      </p>
      <ErrorNotice error={error} retry={() => void load()} />
      {EDGE_ORDER.map((edge) => {
        const item = view.edges.find((e) => e.edge === edge);
        if (!item) return null;
        const copy = EDGE_COPY[edge];
        const reason = sharingReason(item.reason);
        // Turning off is always possible; turning on needs the edge to be available.
        const locked = !item.available && !item.enabled;
        const describedBy = `sharing-${edge}-shared sharing-${edge}-not${reason ? ` sharing-${edge}-reason` : ""}`;
        return (
          <section key={edge} className="sharing-card" aria-busy={saving === edge || undefined}>
            <label className="checkin-switch sharing-switch">
              <input
                type="checkbox"
                role="switch"
                checked={item.enabled}
                aria-disabled={locked || saving !== null || undefined}
                aria-describedby={describedBy}
                onChange={(event) => {
                  if (locked && event.target.checked) return;
                  void toggle(item, event.target.checked);
                }}
              />
              <span className="sharing-title">{copy.title}</span>
              <span className="checkin-switch-state" aria-hidden="true">{item.enabled ? "Bật" : "Tắt"}</span>
            </label>
            <p id={`sharing-${edge}-shared`} className="sharing-detail">{copy.shared}</p>
            <p id={`sharing-${edge}-not`} className="sharing-detail">{copy.notShared}</p>
            {reason ? (
              <p id={`sharing-${edge}-reason`} className="sharing-reason">
                {reason}{" "}
                {item.reason === "journal_context_off" ? <Link to="/check-ins?bot=nhip">Mở Lịch hỏi thăm</Link> : null}
              </p>
            ) : null}
            <p className={`sharing-status${status?.error ? " is-error" : ""}`} role="status">
              {status?.edge === edge ? status.text : ""}
            </p>
          </section>
        );
      })}
      <p className="sharing-note">{CAUNOI_NOTE}</p>
    </div>
  );
}
