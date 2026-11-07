import { useEffect } from "react";
import { NavLink, Outlet, Link, useLocation } from "react-router-dom";
import {
  Home,
  Sparkles,
  FolderOpen,
  HandHeart,
  ArrowUpRight,
  Settings,
  ShieldCheck,
  X,
} from "lucide-react";
import { useDemoStore } from "../../app/store";
import { Brand } from "./Brand";
import { PageMotion } from "../../animations/PageMotion";
const nav = [
  { to: "/home", label: "Home", Icon: Home },
  { to: "/ai", label: "AI", Icon: Sparkles },
  { to: "/cases", label: "Hồ sơ", Icon: FolderOpen },
  { to: "/support", label: "Support", Icon: HandHeart },
];
export function StudentShell() {
  const user = useDemoStore((s) => s.user);
  const location = useLocation();
  useEffect(() => {
    window.scrollTo({ top: 0 });
  }, [location.pathname]);
  const immersive =
    location.pathname === "/ai/chat" ||
    location.pathname.startsWith("/ai/chat/");
  if (immersive)
    return (
      <>
        <a href="#main" className="skip-link">
          Đến nội dung chính
        </a>
        <main id="main" className="chat-workspace">
          <Outlet />
        </main>
      </>
    );
  return (
    <>
      <a href="#main" className="skip-link">
        Đến nội dung chính
      </a>
      <aside className="app-sidebar">
        <Brand />
        <nav aria-label="Điều hướng chính">
          {nav.map(({ to, label, Icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                `nav-link ${isActive || (to === "/support" && location.pathname.startsWith("/knowledge")) ? "active" : ""}`
              }
            >
              <Icon size={21} />
              {label}
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="sidebar-help">
            <HandHeart size={23} />
            <h3>Bạn không cần một mình.</h3>
            <p>Một người tin cậy có thể cùng bạn tìm bước tiếp theo.</p>
            <Link to="/support/find-help" className="button secondary full">
              Tìm người hỗ trợ <ArrowUpRight size={14} />
            </Link>
          </div>
          <Link className="sidebar-profile" to="/settings">
            <span className="avatar">{user?.nickname.charAt(0)}</span>
            <span>
              <strong>{user?.nickname}</strong>
              <br />
              <span className="muted">Tài khoản demo</span>
            </span>
            <Settings size={18} style={{ marginLeft: "auto" }} />
          </Link>
        </div>
      </aside>
      <div className="app-main">
        <main id="main" className="page-content">
          <PageMotion>
            <Outlet />
          </PageMotion>
        </main>
      </div>
      <nav className="bottom-nav" aria-label="Điều hướng chính trên di động">
        {nav.map(({ to, label, Icon }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              isActive ||
              (to === "/support" && location.pathname.startsWith("/knowledge"))
                ? "active"
                : ""
            }
          >
            <Icon size={21} />
            <span>{label}</span>
          </NavLink>
        ))}
      </nav>
      <Link
        to="/support/urgent"
        className="urgent-global"
        aria-label="Tìm hỗ trợ ngay"
      >
        <ShieldCheck size={21} />
      </Link>
    </>
  );
}
export function Toast() {
  const toast = useDemoStore((s) => s.toast);
  const notify = useDemoStore((s) => s.notify);
  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(() => notify(""), 6500);
    return () => clearTimeout(timer);
  }, [toast, notify]);
  return toast ? (
    <div className="toast" role="status">
      <span>{toast}</span>
      <button onClick={() => notify("")} aria-label="Đóng thông báo">
        <X size={18} />
      </button>
    </div>
  ) : null;
}
