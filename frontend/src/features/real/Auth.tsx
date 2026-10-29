import { type FormEvent, useState } from "react";
import { ApiError, type ApiClient } from "../../api/client";
import type { components } from "../../api/generated/schema";
import type { LoginInput, SessionView } from "../../api/contracts";
import { Brand, Button, cx } from "../../components/UI";
import { ErrorNotice } from "../../components/ErrorNotice";
import type { AuthCallback } from "../auth/callback";

type Schema = components["schemas"];
type Mode = "login" | "signup" | "recover" | "reset";

export type { AuthCallback } from "../auth/callback";

function Field({
  id,
  label,
  ...input
}: { id: string; label: string } & React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <>
      <label htmlFor={id}>{label}</label>
      <input id={id} required {...input} />
    </>
  );
}

export function AuthScreen({
  api,
  receive,
  callback,
  initialMode = "login",
}: {
  api: ApiClient;
  receive: (value: SessionView) => void;
  callback: AuthCallback;
  initialMode?: "login" | "signup" | "recover";
}) {
  const [mode, setMode] = useState<Mode>(
    callback?.kind === "recovery" ? "reset" : initialMode,
  );
  const [email, setEmail] = useState(""),
    [password, setPassword] = useState(""),
    [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false),
    [error, setError] = useState<unknown>(),
    [notice, setNotice] = useState(
      callback?.kind === "confirmed"
        ? "Email đã được xác nhận. Bạn có thể đăng nhập."
        : callback?.kind === "failed"
          ? callback.expired
            ? "Liên kết trong email đã hết hạn. Hãy yêu cầu gửi lại."
            : "Liên kết trong email không hợp lệ. Quay lại bước đăng ký hoặc quên mật khẩu để yêu cầu liên kết mới."
          : "",
    ),
    [unconfirmed, setUnconfirmed] = useState(false);

  function switchTo(next: Mode) {
    setMode(next);
    setError(undefined);
    setNotice("");
    setUnconfirmed(false);
    setPassword("");
    setConfirm("");
  }

  async function run(action: () => Promise<void>) {
    if (busy) return;
    setBusy(true);
    setError(undefined);
    setNotice("");
    try {
      await action();
    } catch (reason) {
      setUnconfirmed(reason instanceof ApiError && reason.code === "EMAIL_NOT_CONFIRMED");
      setError(reason);
    } finally {
      setBusy(false);
    }
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    if ((mode === "signup" || mode === "reset") && password !== confirm) {
      setError(new ApiError(422, "PASSWORD_MISMATCH", "Mật khẩu nhập lại chưa khớp. Hãy kiểm tra hai ô mật khẩu."));
      return;
    }
    void run(async () => {
      if (mode === "login") {
        receive(
          await api.request<SessionView>("/auth/login", {
            method: "POST",
            body: { email, password } satisfies LoginInput,
            publicWrite: true,
          }),
        );
      } else if (mode === "signup") {
        await api.request<Schema["AuthNotice"]>("/auth/signup", {
          method: "POST",
          body: { email, password } satisfies Schema["SignupInput"],
          publicWrite: true,
        });
        switchTo("login");
        setNotice(
          "Nếu email hợp lệ, chúng tôi đã gửi thư xác nhận. Hãy mở thư rồi quay lại đăng nhập.",
        );
      } else if (mode === "recover") {
        await api.request<Schema["AuthNotice"]>("/auth/password-recovery", {
          method: "POST",
          body: { email } satisfies Schema["EmailInput"],
          publicWrite: true,
        });
        switchTo("login");
        setNotice("Nếu email có tài khoản, thư hướng dẫn đặt lại mật khẩu đã được gửi.");
      } else if (callback?.kind === "recovery") {
        await api.request<Schema["AuthNotice"]>("/auth/password-reset", {
          method: "POST",
          body: { accessToken: callback.token, password } satisfies Schema["PasswordResetInput"],
          publicWrite: true,
        });
        switchTo("login");
        setNotice("Đã đổi mật khẩu. Mọi phiên cũ đã được đăng xuất; hãy đăng nhập lại.");
      }
    });
  }

  function resend() {
    void run(async () => {
      await api.request<Schema["AuthNotice"]>("/auth/confirmation", {
        method: "POST",
        body: { email } satisfies Schema["EmailInput"],
        publicWrite: true,
      });
      setUnconfirmed(false);
      setNotice("Nếu email chưa xác nhận, thư xác nhận mới đã được gửi.");
    });
  }

  const titles: Record<Mode, [string, string]> = {
    login: ["Chào bạn trở lại", "Đăng nhập để tiếp tục với MoodPrint."],
    signup: ["Tạo tài khoản", "Dùng email bạn đang sử dụng để nhận thư xác nhận tài khoản."],
    recover: ["Quên mật khẩu", "Nhập email đã đăng ký để nhận liên kết đặt lại mật khẩu."],
    reset: ["Đặt mật khẩu mới", "Mật khẩu mới cần ít nhất 8 ký tự."],
  };
  const submitLabels: Record<Mode, [string, string]> = {
    login: ["Đăng nhập", "Đang đăng nhập…"],
    signup: ["Tạo tài khoản", "Đang gửi…"],
    recover: ["Gửi liên kết đặt lại mật khẩu", "Đang gửi…"],
    reset: ["Lưu mật khẩu mới", "Đang lưu…"],
  };
  const newPassword = mode === "signup" || mode === "reset";
  return (
    <main id="main" className="real-auth">
      <Brand />
      <h1 tabIndex={-1}>{titles[mode][0]}</h1>
      {mode === "login" || mode === "signup" ? (
        <p>MoodPrint là nơi ghi lại cảm xúc, trò chuyện với trợ lý AI và kết nối với người khác qua những điểm chung bạn chọn chia sẻ.</p>
      ) : null}
      <p className={cx.lede}>{titles[mode][1]}</p>
      {notice && <p role="status">{notice}</p>}
      <ErrorNotice error={error} />
      {unconfirmed && (
        <Button variant="secondary" disabled={busy} onClick={resend}>
          Gửi lại thư xác nhận
        </Button>
      )}
      <form onSubmit={submit} aria-busy={busy}>
        {mode !== "reset" && (
          <Field
            id="email"
            label="Email"
            type="email"
            autoComplete="username"
            maxLength={254}
            value={email}
            onChange={(event) => setEmail(event.target.value)}
          />
        )}
        {mode !== "recover" && (
          <Field
            id="password"
            label={newPassword ? "Mật khẩu mới" : "Mật khẩu"}
            type="password"
            autoComplete={newPassword ? "new-password" : "current-password"}
            minLength={newPassword ? 8 : undefined}
            maxLength={newPassword ? 72 : 256}
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
        )}
        {newPassword && (
          <Field
            id="password-confirm"
            label="Nhập lại mật khẩu"
            type="password"
            autoComplete="new-password"
            minLength={8}
            maxLength={72}
            value={confirm}
            onChange={(event) => setConfirm(event.target.value)}
          />
        )}
        <Button type="submit" disabled={busy}>
          {submitLabels[mode][busy ? 1 : 0]}
        </Button>
      </form>
      <nav className="real-auth-links" aria-label="Lựa chọn tài khoản">
        {mode === "login" ? (
          <>
            <Button variant="text" onClick={() => switchTo("signup")}>
              Tạo tài khoản mới
            </Button>
            <Button variant="text" onClick={() => switchTo("recover")}>
              Quên mật khẩu?
            </Button>
          </>
        ) : (
          <Button variant="text" onClick={() => switchTo("login")}>
            Quay lại đăng nhập
          </Button>
        )}
      </nav>
    </main>
  );
}

/** Step-up check before exports and account deletion; never stores the password. */
export function ReauthForm({
  api,
  onConfirmed,
  onCancel,
}: {
  api: ApiClient;
  onConfirmed: () => void;
  onCancel: () => void;
}) {
  const [email, setEmail] = useState(""),
    [password, setPassword] = useState(""),
    [busy, setBusy] = useState(false),
    [error, setError] = useState<unknown>();
  function submit(event: FormEvent) {
    event.preventDefault();
    if (busy) return;
    setBusy(true);
    setError(undefined);
    api
      .request<Schema["AuthNotice"]>("/auth/reauthenticate", {
        method: "POST",
        body: { email, password } satisfies LoginInput,
      })
      .then(() => {
        setPassword("");
        onConfirmed();
      })
      .catch(setError)
      .finally(() => setBusy(false));
  }
  return (
    <form className="real-reauth" onSubmit={submit} aria-busy={busy} aria-labelledby="reauth-title">
      <h3 id="reauth-title">Xác nhận tài khoản</h3>
      <p>Nhập lại email và mật khẩu để tiếp tục thao tác này.</p>
      <ErrorNotice error={error} />
      <Field
        id="reauth-email"
        label="Email"
        type="email"
        autoComplete="username"
        maxLength={254}
        value={email}
        onChange={(event) => setEmail(event.target.value)}
      />
      <Field
        id="reauth-password"
        label="Mật khẩu"
        type="password"
        autoComplete="current-password"
        maxLength={256}
        value={password}
        onChange={(event) => setPassword(event.target.value)}
      />
      <div className="real-actions">
        <Button type="submit" disabled={busy}>
          {busy ? "Đang xác nhận…" : "Xác nhận"}
        </Button>
        <Button variant="secondary" disabled={busy} onClick={onCancel}>
          Hủy
        </Button>
      </div>
    </form>
  );
}
