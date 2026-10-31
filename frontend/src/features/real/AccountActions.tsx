import { useState } from "react";
import {
  ChevronRight,
  CircleHelp,
  LogOut,
  MessageSquare,
  Trash2,
} from "lucide-react";
import { Link } from "react-router-dom";
import { Button, cx, Dialog } from "../../components/UI";
import type { components } from "../../api/generated/schema";
import type { SessionView } from "../../api/contracts";
import { ApiError } from "../../api/client";
import { ReauthForm } from "./Auth";
import { ErrorNotice, useGuest, useSession } from "./RealApp";

type Job = components["schemas"]["DataJobView"];

export function AccountDeletionComplete() {
  return (
    <section className="real-section">
      <h1 tabIndex={-1}>Tài khoản đang được xóa</h1>
      <p role="status">
        Bạn đã được đăng xuất. Tài khoản và dữ liệu trong ứng dụng sẽ được xóa
        trong ít phút.
      </p>
      <Button onClick={() => window.location.reload()}>
        Về trang đăng nhập
      </Button>
    </section>
  );
}

export function AccountActions({
  onGuide,
  onDeleted,
  restricted = false,
}: {
  onGuide: () => void;
  onDeleted: () => void;
  restricted?: boolean;
}) {
  const { api, receive, logout, session } = useSession();
  const guest = useGuest();
  const [busy, setBusy] = useState<"logout" | "delete" | "export" | null>(null);
  const [error, setError] = useState<unknown>();
  const [confirm, setConfirm] = useState(false);
  const [confirmExport, setConfirmExport] = useState(false);
  const [understood, setUnderstood] = useState(false);
  const [reauth, setReauth] = useState<"delete" | "export" | null>(null);

  async function exportData() {
    if (busy) return;
    setBusy("export");
    setError(undefined);
    try {
      const job = await api.request<Job>("/exports", {
        method: "POST",
        body: {
          scopes: [
            "account",
            "memories",
            "moods",
            "journal",
            "consents",
            ...(!guest ? ["social"] : []),
            "conversations",
          ],
          ...(guest ? { guestConfirmation: "guest-data-v1" } : {}),
        },
      });
      const data = await api.request<unknown>(`/exports/${job.id}/download`);
      const url = URL.createObjectURL(
        new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }),
      );
      const link = document.createElement("a");
      link.href = url;
      link.download = "moodprint-data.json";
      link.click();
      setConfirmExport(false);
      setTimeout(() => URL.revokeObjectURL(url), 0);
    } catch (reason) {
      if (!guest && reason instanceof ApiError && reason.code === "REAUTH_REQUIRED")
        setReauth("export");
      else setError(reason);
    } finally {
      setBusy(null);
    }
  }

  async function signOut() {
    if (busy) return;
    setBusy("logout");
    setError(undefined);
    try {
      await logout();
    } catch (reason) {
      setError(reason);
    } finally {
      setBusy(null);
    }
  }

  async function removeAccount() {
    if (busy || !understood) return;
    setBusy("delete");
    setError(undefined);
    try {
      const snapshot = await api.request<SessionView>("/session");
      receive(snapshot);
      await api.request<Job>("/data-deletions", {
        method: "POST",
        body: { scope: "account", expectedVersion: snapshot.dataVersion || 1 },
      });
      setConfirm(false);
      onDeleted();
    } catch (reason) {
      setConfirm(false);
      if (reason instanceof ApiError && reason.code === "REAUTH_REQUIRED")
        setReauth("delete");
      else setError(reason);
    } finally {
      setBusy(null);
    }
  }

  return (
    <section className="account-section" aria-labelledby="account-heading">
      <h2 id="account-heading">Tài khoản & hỗ trợ</h2>
      <ErrorNotice error={error} />
      <div className="account-actions">
        {!restricted ? (
          <>
            <Link className="account-action" to="/feedback">
              <MessageSquare size={20} aria-hidden="true" />
              <span>Góp ý cho MoodPrint</span>
              <ChevronRight size={18} aria-hidden="true" />
            </Link>
            <button type="button" className="account-action" onClick={onGuide}>
              <CircleHelp size={20} aria-hidden="true" />
              <span>Xem hướng dẫn</span>
              <ChevronRight size={18} aria-hidden="true" />
            </button>
          </>
        ) : null}
        {restricted ? (
          <button
            type="button"
            className="account-action"
            disabled={Boolean(busy) || Boolean(reauth)}
            onClick={() => guest ? setConfirmExport(true) : void exportData()}
          >
            <span>
              {busy === "export"
                ? "Đang chuẩn bị dữ liệu…"
                : "Tải dữ liệu của tôi"}
            </span>
            <ChevronRight size={18} aria-hidden="true" />
          </button>
        ) : null}
        {!guest ? (
          <button
            type="button"
            className="account-action"
            disabled={Boolean(busy)}
            onClick={() => void signOut()}
          >
            <LogOut size={20} aria-hidden="true" />
            <span>{busy === "logout" ? "Đang đăng xuất…" : "Đăng xuất"}</span>
            <ChevronRight size={18} aria-hidden="true" />
          </button>
        ) : null}
        <button
          type="button"
          className="account-action account-action-danger"
          disabled={Boolean(busy) || Boolean(reauth)}
          onClick={() => {
            if (guest) {
              guest.end();
              return;
            }
            setError(undefined);
            setUnderstood(false);
            setConfirm(true);
          }}
        >
          <Trash2 size={20} aria-hidden="true" />
          <span>
            {guest ? "Kết thúc và xóa lượt dùng thử" : "Xóa tài khoản"}
          </span>
          <ChevronRight size={18} aria-hidden="true" />
        </button>
      </div>
      {confirmExport ? <Dialog title="Tải dữ liệu lượt dùng thử?" onClose={() => !busy && setConfirmExport(false)}>
        <p>Bản sao chứa dữ liệu riêng của lượt dùng thử đang mở. Chỉ lưu trên thiết bị bạn tin tưởng và tải trước khi lượt dùng thử kết thúc.</p>
        <ErrorNotice error={error} />
        <div className={cx.actions}>
          <Button variant="secondary" disabled={Boolean(busy)} onClick={() => setConfirmExport(false)}>Để sau</Button>
          <Button disabled={Boolean(busy)} onClick={() => void exportData()}>{busy === "export" ? "Đang chuẩn bị dữ liệu…" : "Xác nhận và tải dữ liệu"}</Button>
        </div>
      </Dialog> : null}
      {!restricted &&
      session.accountKind !== "guest" &&
      session.staff === "admin" ? (
        <p>
          <Link to="/admin/feedback">Xem và xử lý góp ý</Link>
        </p>
      ) : null}
      {reauth ? (
        <ReauthForm
          api={api}
          onCancel={() => setReauth(null)}
          onConfirmed={() => {
            const action = reauth;
            setReauth(null);
            if (action === "export") void exportData();
            else setConfirm(true);
          }}
        />
      ) : null}
      {confirm ? (
        <Dialog
          title="Xóa vĩnh viễn tài khoản?"
          destructive
          onClose={() => !busy && setConfirm(false)}
        >
          <p>
            Tài khoản, hội thoại đã lưu, ghi nhớ, nhật ký, tâm trạng và hồ sơ
            của bạn sẽ bị xóa vĩnh viễn. Tin nhắn đã gửi cho người khác sẽ hiển
            thị là “[Đã xóa]”.
          </p>
          <p>
            Báo cáo cộng đồng và bản ghi tài khoản đã xóa không có tên hay email
            vẫn được giữ. Dữ liệu trong bản sao lưu được giữ đến khi bản sao lưu
            hết hạn.
          </p>
          <label className="real-check">
            <input
              type="checkbox"
              checked={understood}
              onChange={(event) => setUnderstood(event.target.checked)}
            />
            Tôi hiểu tài khoản không thể khôi phục.
          </label>
          <div className={cx.actions}>
            <Button
              variant="secondary"
              data-cancel
              disabled={Boolean(busy)}
              onClick={() => setConfirm(false)}
            >
              Giữ tài khoản
            </Button>
            <Button
              variant="danger"
              disabled={Boolean(busy) || !understood}
              onClick={() => void removeAccount()}
            >
              {busy === "delete"
                ? "Đang yêu cầu xóa…"
                : "Xóa vĩnh viễn tài khoản"}
            </Button>
          </div>
        </Dialog>
      ) : null}
    </section>
  );
}
