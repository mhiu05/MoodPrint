import { useState } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { ArrowRight, ShieldCheck } from "lucide-react";
import { Brand } from "../../components/layout/Brand";
import { Badge, Button, Field, Notice } from "../../components/ui";
import { useDemoStore } from "../../app/store";
import { personas } from "../../mocks/data/seed";
import type { AgeBand } from "../../types";
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
  const user = useDemoStore((s) => s.user);
  const login = useDemoStore((s) => s.login);
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
  if (user) return <Navigate to={returnTo} replace />;
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
    await new Promise((resolve) => setTimeout(resolve, 300));
    login(
      persona,
      custom ? nickname.trim() : undefined,
      custom ? ageBand : undefined,
    );
    setPassword("");
    setEmail("");
    navigate(returnTo, { replace: true });
  }
  return (
    <main className="auth-layout">
      <div className="auth-intro">
        <Brand to="/welcome/1" />
        <div className="auth-demo-label">
          <ShieldCheck size={18} />
          <span className="caption">
            Tài khoản demo · Chỉ lưu trên trình duyệt
          </span>
        </div>
      </div>
      <section className="auth-card">
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
