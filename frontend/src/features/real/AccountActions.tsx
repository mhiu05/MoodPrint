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
}: {
  onGuide: () => void;
  onDeleted: () => void;
}) {
  const { api, receive, logout, session } = useSession();
  const guest = useGuest();
  const [busy, setBusy] = useState<"logout" | "delete" | null>(null);
  const [error, setError] = useState<unknown>();
  const [confirm, setConfirm] = useState(false);
  const [understood, setUnderstood] = useState(false);
  const [reauth, setReauth] = useState(false);

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
        setReauth(true);
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
          disabled={Boolean(busy) || reauth}
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
      {session.accountKind !== "guest" && session.staff === "admin" ? (
        <p>
          <Link to="/admin/feedback">Xem và xử lý góp ý</Link>
        </p>
      ) : null}
      {reauth ? (
        <ReauthForm
          api={api}
          onCancel={() => setReauth(false)}
          onConfirmed={() => {
            setReauth(false);
            setConfirm(true);
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
