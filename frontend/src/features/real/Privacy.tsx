import { useEffect, useState } from "react";
import { Button, cx, Dialog } from "../../components/UI";
import type { components } from "../../api/generated/schema";
import { ErrorNotice, useSession } from "./RealApp";
import type { SessionView } from "../../api/contracts";
import { ApiError } from "../../api/client";
import { ReauthForm } from "./Auth";

type Job = components["schemas"]["DataJobView"];
type Scope = components["schemas"]["DeletionInput"]["scope"];
const choices = {
  memories: "Ghi nhớ đã duyệt",
  moods: "Nhật ký tâm trạng",
  private_items: "Mục trong hồ sơ riêng",
  all_private: "Toàn bộ dữ liệu riêng và hồ sơ kết nối",
} as const;

export function DataControls() {
  const { api, receive } = useSession();
  const [scope, setScope] = useState<Exclude<Scope, "account">>("memories"),
    [confirm, setConfirm] = useState(false),
    [busy, setBusy] = useState(false),
    [error, setError] = useState<unknown>(),
    [job, setJob] = useState<Job>(),
    [notice, setNotice] = useState(""),
    [reauthFor, setReauthFor] = useState<"export" | "account" | null>(null),
    [accountDialog, setAccountDialog] = useState(false),
    [understood, setUnderstood] = useState(false),
    [accountDeleted, setAccountDeleted] = useState(false);
  const needsReauth = (reason: unknown) =>
    reason instanceof ApiError && reason.code === "REAUTH_REQUIRED";
  useEffect(() => {
    if (!job || !["queued", "running"].includes(job.status)) return;
    let cancelled = false;
    const timer = setInterval(() => {
      void api
        .request<Job>(`/data-deletions/${job.id}`)
        .then((value) => {
          if (!cancelled) {
            setJob(value);
            if (value.status === "completed")
              setNotice("Đã xóa phạm vi dữ liệu bạn chọn trong ứng dụng.");
          }
        })
        .catch((reason) => {
          if (!cancelled) setError(reason);
        });
    }, 1000);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [api, job?.id, job?.status]);
  async function remove() {
    setBusy(true);
    setError(undefined);
    setNotice("");
    try {
      const snapshot = await api.request<SessionView>("/session");
      receive(snapshot);
      const accepted = await api.request<Job>("/data-deletions", {
        method: "POST",
        body: { scope, expectedVersion: snapshot.dataVersion || 1 },
      });
      setJob(accepted);
      setConfirm(false);
    } catch (reason) {
      setError(reason);
    } finally {
      setBusy(false);
    }
  }
  async function exportData() {
    setBusy(true);
    setError(undefined);
    setNotice("");
    try {
      const result = await api.request<Job>("/exports", {
        method: "POST",
        body: {
          scopes: [
            "account",
            "private_items",
            "memories",
            "moods",
            "consents",
            "social",
          ],
        },
      });
      const data = await api.request<unknown>(`/exports/${result.id}/download`);
      const url = URL.createObjectURL(
        new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }),
      );
      const link = document.createElement("a");
      link.href = url;
      link.download = "moodprint-data.json";
      link.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
      setNotice("Đã chuẩn bị tệp dữ liệu riêng của bạn.");
    } catch (reason) {
      if (needsReauth(reason)) setReauthFor("export");
      else setError(reason);
    } finally {
      setBusy(false);
    }
  }
  async function removeAccount() {
    setBusy(true);
    setError(undefined);
    setNotice("");
    try {
      const snapshot = await api.request<SessionView>("/session");
      receive(snapshot);
      await api.request<Job>("/data-deletions", {
        method: "POST",
        body: { scope: "account", expectedVersion: snapshot.dataVersion || 1 },
      });
      setAccountDialog(false);
      setAccountDeleted(true);
    } catch (reason) {
      if (needsReauth(reason)) {
        setAccountDialog(false);
        setReauthFor("account");
      } else setError(reason);
    } finally {
      setBusy(false);
    }
  }
  if (accountDeleted)
    return (
      <section className="real-section">
        <h2>Tài khoản đang được xóa</h2>
        <p role="status">
          Bạn đã được đăng xuất. Dữ liệu trong ứng dụng và tài khoản đăng nhập
          sẽ được xóa trong ít phút. Tin nhắn bạn đã gửi cho người khác sẽ hiển
          thị là “[Đã xóa]”.
        </p>
        <Button onClick={() => window.location.reload()}>Về trang đăng nhập</Button>
      </section>
    );
  return (
    <section className="real-section">
      <h2>Dữ liệu của bạn</h2>
      <p>
        Bản xuất gồm thông tin tuổi, hồ sơ riêng, tâm trạng, ghi nhớ, lịch sử
        bật/tắt quyền, hồ sơ kết nối, lời mời, tin nhắn bạn đã gửi, báo cáo và
        lượt chặn bạn đã tạo. Hội thoại AI đã lưu được xuất riêng trong lịch sử
        trò chuyện. Hội thoại AI tạm, tin nhắn và thông tin riêng của người khác
        không nằm trong bản xuất. Tệp chỉ tải được một lần trong 15 phút.
      </p>
      <ErrorNotice error={error} />
      {notice && <p role="status">{notice}</p>}
      {reauthFor && (
        <ReauthForm
          api={api}
          onCancel={() => setReauthFor(null)}
          onConfirmed={() => {
            const next = reauthFor;
            setReauthFor(null);
            if (next === "export") void exportData();
            else setAccountDialog(true);
          }}
        />
      )}
      <Button
        variant="secondary"
        disabled={busy}
        onClick={() => void exportData()}
      >
        Xuất dữ liệu riêng
      </Button>
      <div className="real-section">
        <label htmlFor="deletion-scope">Dữ liệu bạn muốn xóa</label>
        <select
          id="deletion-scope"
          value={scope}
          onChange={(event) =>
            setScope(event.target.value as Exclude<Scope, "account">)
          }
        >
          {Object.entries(choices).map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
        <Button
          variant="text"
          disabled={
            busy || Boolean(job && ["queued", "running"].includes(job.status))
          }
          onClick={() => setConfirm(true)}
        >
          Xóa dữ liệu đã chọn
        </Button>
        {job && (
          <p role="status">
            {job.status === "completed"
              ? "Yêu cầu đã hoàn tất trong ứng dụng."
              : job.status === "failed"
                ? "Chưa hoàn tất yêu cầu. Vui lòng thử lại hoặc liên hệ hỗ trợ."
                : "Đang xóa dữ liệu đã chọn. Dữ liệu này đã được chặn sử dụng."}
          </p>
        )}
      </div>
      <div className="real-section">
        <h3>Xóa tài khoản</h3>
        <p>
          Xóa vĩnh viễn tài khoản đăng nhập và toàn bộ dữ liệu của bạn trong
          ứng dụng. Thao tác này không thể hoàn tác.
        </p>
        <Button
          variant="danger"
          disabled={busy || Boolean(reauthFor)}
          onClick={() => {
            setUnderstood(false);
            setAccountDialog(true);
          }}
        >
          Xóa tài khoản
        </Button>
      </div>
      {accountDialog && (
        <Dialog
          title="Xóa vĩnh viễn tài khoản?"
          destructive
          onClose={() => !busy && setAccountDialog(false)}
        >
          <p>
            Hội thoại đã lưu, ghi nhớ, tâm trạng, hồ sơ riêng, hồ sơ kết nối và
            tài khoản đăng nhập sẽ bị xóa. Tin nhắn đã gửi cho người khác sẽ
            hiển thị là “[Đã xóa]”. Để giữ an toàn cộng đồng, ứng dụng vẫn giữ
            báo cáo bạn đã gửi, lịch sử bật/tắt quyền và một bản ghi tài khoản
            đã xóa không có tên hay email. Bản sao lưu của nhà cung cấp hạ tầng
            có thể còn dữ liệu cho đến khi bản sao lưu đó hết hạn.
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
              disabled={busy}
              onClick={() => setAccountDialog(false)}
            >
              Giữ tài khoản
            </Button>
            <Button
              variant="danger"
              disabled={busy || !understood}
              onClick={() => void removeAccount()}
            >
              Xóa vĩnh viễn
            </Button>
          </div>
        </Dialog>
      )}
      {confirm && (
        <Dialog
          title="Xóa phạm vi dữ liệu này?"
          destructive
          onClose={() => !busy && setConfirm(false)}
        >
          <p>{choices[scope]}</p>
          <p>
            Nội dung đã xóa sẽ không được khôi phục khi bật lại quyền. Nếu xóa
            toàn bộ dữ liệu riêng, hồ sơ đang chia sẻ và kết nối liên quan cũng
            sẽ mất hiệu lực.
          </p>
          <div className={cx.actions}>
            <Button
              variant="secondary"
              disabled={busy}
              onClick={() => setConfirm(false)}
            >
              Giữ dữ liệu
            </Button>
            <Button
              variant="danger"
              disabled={busy}
              onClick={() => void remove()}
            >
              Xác nhận xóa dữ liệu
            </Button>
          </div>
        </Dialog>
      )}
    </section>
  );
}
