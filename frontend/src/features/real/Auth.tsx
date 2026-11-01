import { type FormEvent, type InputHTMLAttributes, type ReactNode, useState } from "react";
import { ArrowRight, Eye, EyeOff, LockKeyhole, Mail } from "lucide-react";
import { ApiError, type ApiClient } from "../../api/client";
import type { components } from "../../api/generated/schema";
import type { LoginInput, SessionView } from "../../api/contracts";
import { BrandMark } from "../../companions/Avatar";
import { Brand, Button, cx } from "../../components/UI";
import { ErrorNotice } from "../../components/ErrorNotice";
import { AgeFields } from "../auth/AgeFields";
import { ageDeclaration, bangkokYear } from "../auth/ageDeclaration";
import type { AuthCallback } from "../auth/callback";

type Schema = components["schemas"];
type Mode = "login" | "signup" | "recover" | "reset";

export type { AuthCallback } from "../auth/callback";

function Field({
  id,
  label,
  leading,
  trailing,
  wrapperClassName,
  ...input
}: {
  id: string;
  label: string;
  leading?: ReactNode;
  trailing?: ReactNode;
  wrapperClassName?: string;
} & InputHTMLAttributes<HTMLInputElement>) {
  const field = (
    <>
      <label htmlFor={id}>{label}</label>
      {leading || trailing ? (
        <div className="landing-input-shell">
          {leading}
          <input id={id} required {...input} />
          {trailing}
        </div>
      ) : (
        <input id={id} required {...input} />
      )}
    </>
  );
  return wrapperClassName ? <div className={wrapperClassName}>{field}</div> : field;
}

export function AuthScreen({
  api,
  receive,
  callback,
  initialMode = "login",
  presentation = "default",
  footerActions,
}: {
  api: ApiClient;
  receive: (value: SessionView) => void;
  callback: AuthCallback;
  initialMode?: "login" | "signup" | "recover";
  presentation?: "default" | "landing";
  footerActions?: ReactNode | ((mode: Mode) => ReactNode);
}) {
  const landing = presentation === "landing";
  const [mode, setMode] = useState<Mode>(
    callback?.kind === "recovery" ? "reset" : initialMode,
  );
  const [email, setEmail] = useState(""),
    [password, setPassword] = useState(""),
    [confirm, setConfirm] = useState("");
  const [birthYear, setBirthYear] = useState("");
  const [adultConfirmed, setAdultConfirmed] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
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
          body: { email, password, eligibility: ageDeclaration(birthYear, adultConfirmed, bangkokYear()) } satisfies Schema["SignupInput"],
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
  const renderedFooterActions = typeof footerActions === "function" ? footerActions(mode) : footerActions;
  return (
    <main id="main" className={`real-auth${landing ? " landing-auth" : ""}`}>
      {landing ? (
        <div className="landing-brand">
          <BrandMark />
          <span>MoodPrint</span>
        </div>
      ) : <Brand />}
      <h1 tabIndex={-1}>{landing && mode === "login" ? "Bắt đầu với MoodPrint" : titles[mode][0]}</h1>
      {landing && mode === "login" ? (
        <p className="landing-auth-lede">MoodPrint là nơi ghi lại cảm xúc, trò chuyện với trợ lý AI và kết nối với người khác qua những điểm chung bạn chọn chia sẻ.</p>
      ) : null}
      {!landing && (mode === "login" || mode === "signup") ? (
        <p>MoodPrint là nơi ghi lại cảm xúc, trò chuyện với trợ lý AI và kết nối với người khác qua những điểm chung bạn chọn chia sẻ.</p>
      ) : null}
      {(!landing || mode !== "login") && <p className={cx.lede}>{titles[mode][1]}</p>}
      {(mode === "login" || mode === "signup") && <p>MoodPrint dành cho người từ đủ 18 tuổi.</p>}
      {notice && <p role="status">{notice}</p>}
      <ErrorNotice error={error} />
      {unconfirmed && (
        <Button variant="secondary" disabled={busy} onClick={resend}>
          Gửi lại thư xác nhận
        </Button>
      )}
      <form className={landing ? "landing-auth-form" : undefined} onSubmit={submit} aria-busy={busy}>
        {mode !== "reset" && (
          <Field
            id="email"
            label="Email"
            type="email"
            autoComplete="username"
            maxLength={254}
            placeholder={landing ? "Nhập email" : undefined}
            leading={landing ? <Mail size={21} aria-hidden="true" /> : undefined}
            wrapperClassName={landing ? "landing-auth-field" : undefined}
            value={email}
            onChange={(event) => setEmail(event.target.value)}
          />
        )}
        {mode !== "recover" && (
          <Field
            id="password"
            label={newPassword ? "Mật khẩu mới" : "Mật khẩu"}
            type={showPassword ? "text" : "password"}
            autoComplete={newPassword ? "new-password" : "current-password"}
            minLength={newPassword ? 8 : undefined}
            maxLength={newPassword ? 72 : 256}
            placeholder={landing ? "Nhập mật khẩu" : undefined}
            leading={landing ? <LockKeyhole size={21} aria-hidden="true" /> : undefined}
            trailing={landing ? (
              <button
                type="button"
                className="landing-password-toggle"
                aria-label={showPassword ? "Ẩn mật khẩu" : "Hiện mật khẩu"}
                aria-pressed={showPassword}
                onClick={() => setShowPassword((visible) => !visible)}
              >
                {showPassword ? <EyeOff size={21} aria-hidden="true" /> : <Eye size={21} aria-hidden="true" />}
              </button>
            ) : undefined}
            wrapperClassName={landing ? "landing-auth-field" : undefined}
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
            wrapperClassName={landing ? "landing-auth-field" : undefined}
            value={confirm}
            onChange={(event) => setConfirm(event.target.value)}
          />
        )}
        {mode === "signup" && <AgeFields prefix="signup" year={birthYear} confirmed={adultConfirmed}
          currentYear={bangkokYear()} onYear={setBirthYear} onConfirmed={setAdultConfirmed} />}
        {landing && mode === "login" && (
          <div className="landing-auth-tools">
            <Button variant="text" onClick={() => switchTo("recover")}>
              Quên mật khẩu?
            </Button>
          </div>
        )}
        <Button className={landing ? "landing-submit" : ""} type="submit" disabled={busy}>
          {submitLabels[mode][busy ? 1 : 0]}
          {landing && mode === "login" && !busy ? <ArrowRight size={20} aria-hidden="true" /> : null}
        </Button>
      </form>
      {landing ? (
        <>
          <div className="landing-divider" aria-hidden="true"><span>hoặc</span></div>
          <div className="landing-auth-actions">{renderedFooterActions}</div>
          <p className="landing-auth-note">
            {mode === "login" ? "Chưa có tài khoản? Tạo ngay hoặc dùng thử trước." : "Đã có tài khoản? Đăng nhập hoặc dùng thử trước."}
          </p>
          {mode !== "login" ? (
            <Button variant="text" onClick={() => switchTo("login")}>
              Quay lại đăng nhập
            </Button>
          ) : null}
        </>
      ) : (
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
      )}
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
