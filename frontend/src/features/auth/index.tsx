import { useState } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { ArrowRight, ShieldCheck } from "lucide-react";
import { Brand } from "../../components/layout/Brand";
import { Badge, Button, Field, Notice, Skeleton } from "../../components/ui";
import { useWorkspaceStore } from "../../app/store";
import { personas } from "../../mocks/data/seed";
import type { AgeBand } from "../../types";
import { getServices } from "../../services/composition";
import { enterDemo, restoreRealSession } from "../../services/workspace";
import { isRealAuthConfigured } from "../../services/supabase";
import "../onboarding/entry.css";
export function AuthPage() {
  const [mode, setMode] = useState("login");
  const [persona, setPersona] = useState("USER-AN");
  const [nickname, setNickname] = useState("");
  const [ageBand, setAgeBand] = useState<AgeBand>("11–13");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [interest, setInterest] = useState("Hiểu tình huống");
  const user = useWorkspaceStore((s) => s.user);
  const hydration = useWorkspaceStore((s) => s.hydration);
  const navigate = useNavigate();
  const location = useLocation();
  const next = (location.state as { from?: string } | null)?.from;
  const returnTo =
    next?.startsWith("/") &&
    !next.startsWith("//") &&
    !next.startsWith("/auth") &&
    !next.startsWith("/welcome")
      ? next
      : "/home";
  if (hydration.status === "initializing") return <Skeleton />;
  if (user && hydration.status === "ready")
    return <Navigate to={returnTo} replace />;
  async function enter(custom: boolean) {
    if (
      custom &&
      (nickname.trim().length < 2 ||
        !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email) ||
        password.length < 6)
    ) {
      setError(
        "Nhập bí danh ít nhất 2 ký tự, email demo đúng định dạng và mật khẩu demo ít nhất 6 ký tự.",
      );
      return;
    }
    setError("");
    setBusy(true);
    try {
      await enterDemo(
        persona,
        custom ? nickname.trim() : undefined,
        custom ? ageBand : undefined,
      );
      setPassword("");
      setEmail("");
      navigate(returnTo, { replace: true });
    } catch (error) {
      setError(error instanceof Error ? error.message : "Chưa mở được demo.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <main className="auth-layout">
      <div className="auth-intro">
        <Brand to="/welcome/1" />
        <div className="auth-demo-label">
          <ShieldCheck size={18} />
          <span className="caption">
            {isRealAuthConfigured()
              ? "Không gian của bạn · Chỉ dùng nội dung hư cấu"
              : "Tài khoản demo · Chỉ lưu trên trình duyệt"}
          </span>
        </div>
      </div>
      <section className="auth-card">
        {isRealAuthConfigured() && <RealAuthForm returnTo={returnTo} />}
        <h1>{mode === "login" ? "Chào bạn quay lại" : "Tạo tài khoản demo"}</h1>
        <p className="muted" style={{ fontSize: 14 }}>
          Chọn một nhân vật để khám phá không gian của mình.
        </p>
        <div className="segmented" style={{ marginTop: 16 }}>
          <button
            className={mode === "login" ? "active" : ""}
            aria-pressed={mode === "login"}
            onClick={() => setMode("login")}
          >
            Đăng nhập demo
          </button>
          <button
            className={mode === "register" ? "active" : ""}
            aria-pressed={mode === "register"}
            onClick={() => setMode("register")}
          >
            Đăng ký demo
          </button>
        </div>
        <div className="persona-list">
          {personas.map((p) => (
            <button
              className={`persona-button ${persona === p.id ? "active" : ""}`}
              aria-pressed={persona === p.id}
              key={p.id}
              onClick={() => setPersona(p.id)}
            >
              <span className="avatar">{p.nickname[0]}</span>
              <strong>{p.nickname}</strong>
              <span>{p.ageBand} tuổi</span>
            </button>
          ))}
        </div>
        {mode === "register" && (
          <form
            onSubmit={(e) => {
              e.preventDefault();
              void enter(true);
            }}
          >
            <Field
              label="Bí danh demo"
              placeholder="Ví dụ: Mây nhỏ"
              value={nickname}
              maxLength={32}
              onChange={(e) => setNickname(e.target.value)}
            />
            <div className="field">
              <label htmlFor="age">Nhóm tuổi</label>
              <select
                id="age"
                value={ageBand}
                onChange={(e) => setAgeBand(e.target.value as AgeBand)}
              >
                <option>11–13</option>
                <option>14–17</option>
              </select>
            </div>
            <Field
              label="Email demo"
              type="email"
              placeholder="ban@example.test"
              value={email}
              autoComplete="off"
              onChange={(e) => setEmail(e.target.value)}
              hint="Chỉ nhập địa chỉ giả. Không gửi email và không lưu địa chỉ này."
            />
            <Field
              label="Mật khẩu demo"
              type="password"
              placeholder="Chỉ nhập mật khẩu giả"
              value={password}
              autoComplete="new-password"
              onChange={(e) => setPassword(e.target.value)}
              hint="Không dùng mật khẩu thật. Nội dung này không được lưu."
            />
            <div className="field">
              <label htmlFor="interest">Bạn muốn bắt đầu với điều gì?</label>
              <select
                id="interest"
                value={interest}
                onChange={(e) => setInterest(e.target.value)}
              >
                <option>Hiểu tình huống</option>
                <option>Ghi lại sự việc</option>
                <option>Luyện cách nói</option>
                <option>Tìm hỗ trợ</option>
              </select>
            </div>
            {error && <Notice tone="error">{error}</Notice>}
            <Button type="submit" className="full" disabled={busy}>
              {busy ? "Đang mở demo…" : "Tạo tài khoản minh họa"}
              <ArrowRight size={17} />
            </Button>
          </form>
        )}
        <Notice>
          Đây là xác thực mô phỏng. Chưa có tài khoản nào được tạo trên server.
          Chỉ dùng nội dung hư cấu khi trải nghiệm.
        </Notice>
        <Button
          className="full"
          variant={mode === "register" ? "secondary" : "primary"}
          disabled={busy}
          onClick={() => void enter(false)}
        >
          {busy ? "Đang mở demo…" : "Vào thử với tài khoản demo"}
          <ArrowRight size={17} />
        </Button>
        <div style={{ textAlign: "center", marginTop: 18 }}>
          <Badge tone="gray">Không có chế độ khách</Badge>
        </div>
      </section>
    </main>
  );
}

function RealAuthForm({ returnTo }: { returnTo: string }) {
  const [mode, setMode] = useState<"login" | "register" | "forgot">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [nickname, setNickname] = useState("");
  const [ageBand, setAgeBand] = useState<AgeBand>("11–13");
  const [interest, setInterest] = useState("Hiểu tình huống");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const navigate = useNavigate();
  async function submit() {
    if (
      !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email) ||
      (mode !== "forgot" && password.length < 8) ||
      (mode === "register" && nickname.trim().length < 2)
    ) {
      setError(
        "Nhập email đúng định dạng, mật khẩu ít nhất 8 ký tự và bí danh ít nhất 2 ký tự khi đăng ký.",
      );
      return;
    }
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const auth = getServices().auth;
      if (mode === "forgot") {
        await auth.requestPasswordReset(email);
        setMessage(
          "Nếu địa chỉ phù hợp, bạn sẽ nhận được email đặt lại mật khẩu. Hãy kiểm tra email và thư mục thư rác.",
        );
        return;
      }
      if (mode === "register") {
        const result = await auth.signUp({
          email,
          password,
          nickname: nickname.trim(),
          ageBand,
          startInterest: interest,
        });
        setPassword("");
        if (result.needsEmailConfirmation) {
          setMessage(
            "Kiểm tra email để xác nhận tài khoản, sau đó quay lại đăng nhập. Hãy kiểm tra cả thư mục thư rác.",
          );
          return;
        }
      } else {
        await auth.signIn(email, password);
        setPassword("");
      }
      await restoreRealSession();
      setEmail("");
      navigate(returnTo, { replace: true });
    } catch (error) {
      setError(
        error instanceof Error
          ? error.message
          : "Chưa thể đăng nhập. Hãy thử lại.",
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <div style={{ marginBottom: 24 }}>
      <h1>
        {mode === "register"
          ? "Tạo tài khoản"
          : mode === "forgot"
            ? "Đặt lại mật khẩu"
            : "Đăng nhập tài khoản"}
      </h1>
      <div className="segmented" style={{ marginTop: 16 }}>
        <button
          aria-pressed={mode === "login"}
          className={mode === "login" ? "active" : ""}
          onClick={() => {
            setMode("login");
            setError("");
            setMessage("");
          }}
        >
          Đăng nhập
        </button>
        <button
          aria-pressed={mode === "register"}
          className={mode === "register" ? "active" : ""}
          onClick={() => {
            setMode("register");
            setError("");
            setMessage("");
          }}
        >
          Đăng ký
        </button>
      </div>
      <form
        onSubmit={(event) => {
          event.preventDefault();
          void submit();
        }}
      >
        {mode === "register" && (
          <>
            <Field
              label="Bí danh"
              value={nickname}
              maxLength={32}
              onChange={(event) => setNickname(event.target.value)}
            />
            <Field label="Nhóm tuổi">
              <select
                value={ageBand}
                onChange={(event) => setAgeBand(event.target.value as AgeBand)}
              >
                <option>11–13</option>
                <option>14–17</option>
              </select>
            </Field>
          </>
        )}
        <Field
          label="Email"
          type="email"
          autoComplete="email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          required
        />
        {mode !== "forgot" && (
          <Field
            label="Mật khẩu"
            type="password"
            autoComplete={
              mode === "register" ? "new-password" : "current-password"
            }
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            required
            minLength={8}
          />
        )}
        {mode === "register" && (
          <Field label="Bạn muốn bắt đầu với điều gì?">
            <select
              value={interest}
              onChange={(event) => setInterest(event.target.value)}
            >
              <option>Hiểu tình huống</option>
              <option>Ghi lại sự việc</option>
              <option>Tìm người hỗ trợ</option>
            </select>
          </Field>
        )}
        {error && <Notice tone="error">{error}</Notice>}
        {message && (
          <Notice>
            <span role="status">{message}</span>
          </Notice>
        )}
        <Button className="full" type="submit" disabled={busy}>
          {busy
            ? "Đang xử lý…"
            : mode === "register"
              ? "Tạo tài khoản"
              : mode === "forgot"
                ? "Gửi hướng dẫn đặt lại mật khẩu"
                : "Đăng nhập"}
        </Button>
      </form>
      {mode === "login" && (
        <Button
          variant="ghost"
          onClick={() => {
            setMode("forgot");
            setError("");
          }}
        >
          Quên mật khẩu?
        </Button>
      )}
    </div>
  );
}

export function ResetPasswordPage() {
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [done, setDone] = useState(false);
  const navigate = useNavigate();
  return (
    <main className="auth-layout">
      <div className="auth-intro">
        <Brand to="/auth" />
      </div>
      <section className="auth-card">
        <h1>Đặt mật khẩu mới</h1>
        {done ? (
          <>
            <Notice>Mật khẩu đã được cập nhật.</Notice>
            <Button onClick={() => navigate("/auth", { replace: true })}>
              Tiếp tục
            </Button>
          </>
        ) : (
          <form
            onSubmit={(event) => {
              event.preventDefault();
              if (password.length < 8) {
                setError("Mật khẩu cần ít nhất 8 ký tự.");
                return;
              }
              setBusy(true);
              setError("");
              void getServices()
                .auth.updatePassword(password)
                .then(() => {
                  setPassword("");
                  setDone(true);
                })
                .catch((error) =>
                  setError(
                    error instanceof Error
                      ? error.message
                      : "Chưa đổi được mật khẩu. Hãy mở lại liên kết từ email.",
                  ),
                )
                .finally(() => setBusy(false));
            }}
          >
            <Field
              label="Mật khẩu mới"
              type="password"
              value={password}
              autoComplete="new-password"
              minLength={8}
              required
              onChange={(event) => setPassword(event.target.value)}
            />
            {error && <Notice tone="error">{error}</Notice>}
            <Button type="submit" disabled={busy}>
              {busy ? "Đang lưu…" : "Lưu mật khẩu"}
            </Button>
          </form>
        )}
      </section>
    </main>
  );
}
