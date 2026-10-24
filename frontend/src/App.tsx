import { useEffect, useState } from "react";
import {
  HashRouter,
  Link,
  NavLink,
  Navigate,
  Route,
  Routes,
  useLocation,
  useNavigate,
  type Location,
} from "react-router-dom";
import {
  Users,
  UserRound,
  ShieldCheck,
  MessageCircle,
  Sparkles,
} from "lucide-react";
import { Provider, useDemo } from "./state/Provider";
import { sessionAllowed, canChat } from "./domain/policies";
import { Brand, Button, cx, Dialog, Motion } from "./components/UI";
import { CompanionsPage } from "./companions/Companions";
import { BrandMark } from "./companions/Avatar";
import { Avatar } from "./components/UI";
import { SelfPage } from "./pages/Self";
import { ProfilePage } from "./pages/Profile";
import { ConnectPage } from "./pages/Connect";
import { ChatPage } from "./pages/Chat";
import { SettingsPage } from "./pages/Settings";
function ScreenGate({ children }: { children: React.ReactNode }) {
  const { state } = useDemo();
  return sessionAllowed(state) ? (
    children
  ) : (
    <div className={cx.statePanel}>
      <h1>Phiên chưa được khởi tạo</h1>
      <p>Hãy mở lại bản trải nghiệm.</p>
    </div>
  );
}
function Navigation() {
  const { pathname } = useLocation();
  return (
    <nav className={cx.navigation} aria-label="Điều hướng chính">
      {[
        ["/assistants", "Trợ lý", Sparkles],
        ["/connect", "Tìm bạn", Users],
        ["/messages", "Tin nhắn", MessageCircle],
        ["/profile", "Tôi", UserRound],
      ].map(([to, name, Icon]) => {
        const I = Icon as typeof Sparkles;
        return (
          <NavLink
            key={to as string}
            className={({ isActive }) =>
              `${cx.navItem} ${isActive || (to === "/messages" && pathname.startsWith("/chat/")) ? cx.navActive : ""}`
            }
            to={to as string}
          >
            <I size={21} strokeWidth={1.6} />
            <span>{name as string}</span>
          </NavLink>
        );
      })}
    </nav>
  );
}
function Shell() {
  const { state, dispatch } = useDemo();
  const location = useLocation();
  const navigate = useNavigate();
  const [showSample, setShowSample] = useState(true);
  const [about, setAbout] = useState(false);
  useEffect(() => {
    const viewport = window.visualViewport;
    const resize = () =>
      document.documentElement.style.setProperty(
        "--app-height",
        `${viewport?.height || window.innerHeight}px`,
      );
    resize();
    viewport?.addEventListener("resize", resize);
    return () => {
      viewport?.removeEventListener("resize", resize);
      document.documentElement.style.removeProperty("--app-height");
    };
  }, []);
  useEffect(() => {
    if (!state.notice) return;
    const timer = setTimeout(
      () => dispatch({ type: "NOTICE", text: "" }),
      3000,
    );
    return () => clearTimeout(timer);
  }, [state.notice, dispatch]);
  const [accepted, setAccepted] = useState<Location>(location);
  const [pending, setPending] = useState<Location>();
  const active = state.activities.find(
    (a) =>
      a.status === "active" &&
      canChat(
        state,
        state.connections.find((c) => c.id === a.connectionId),
      ),
  );
  const playingLocation =
    !!active &&
    accepted.pathname === `/chat/${active.connectionId}` &&
    new URLSearchParams(accepted.search).get("panel") === "activity";
  const guarded =
    playingLocation &&
    location.pathname + location.search !== accepted.pathname + accepted.search;
  useEffect(() => {
    if (location.key === accepted.key) return;
    if (
      playingLocation &&
      location.pathname + location.search !==
        accepted.pathname + accepted.search
    ) {
      setPending(location);
      return;
    }
    setAccepted(location);
    setPending(undefined);
  }, [location, active?.id, playingLocation, accepted]);
  const displayed = guarded ? accepted : location;
  const isChat = displayed.pathname.startsWith("/chat/");
  const assistants = displayed.pathname.startsWith("/assistants");
  const fullChat =
    isChat || (assistants && displayed.pathname !== "/assistants");
  useEffect(() => {
    const panelHeading =
      displayed.pathname.startsWith("/chat/") &&
      displayed.search.includes("panel=")
        ? document.querySelector<HTMLElement>("[data-question-heading]") ||
          document.querySelector<HTMLElement>("[data-activity-heading]")
        : null;
    (
      panelHeading ||
      Array.from(document.querySelectorAll<HTMLElement>("h1")).find(
        (el) => el.getClientRects().length,
      )
    )?.focus({
      preventScroll: true,
    });
    if (panelHeading)
      panelHeading.scrollIntoView({ block: "start", behavior: "instant" });
    else window.scrollTo(0, 0);
  }, [displayed.pathname, displayed.search, state.epoch]);
  useEffect(() => {
    const escape = (e: KeyboardEvent) => {
      if (
        e.key === "Escape" &&
        active &&
        !document.querySelector("dialog[open]")
      ) {
        navigate({ pathname: displayed.pathname, search: "" });
      }
    };
    document.addEventListener("keydown", escape);
    return () => document.removeEventListener("keydown", escape);
  }, [active?.id, displayed.pathname, navigate]);
  return (
    <>
      <a
        className={cx.skipLink}
        href="#main"
        onClick={(e) => {
          e.preventDefault();
          document.getElementById("main")?.focus();
        }}
      >
        Đến nội dung chính
      </a>

      <div
        className={`me-shell ${assistants ? "assistant-shell" : ""} ${fullChat ? "full-chat" : ""}`}
      >
        <aside className="me-rail">
          <Link
            className="rail-brand"
            aria-label="Me2We — Trợ lý"
            to="/assistants"
          >
            <BrandMark />
          </Link>
          <Navigation />
          <div className="rail-bottom">
            <button
              className="icon-button"
              aria-label="Thông tin Me2We"
              onClick={() => setAbout(true)}
            >
              <ShieldCheck size={21} />
            </button>
            <Link
              className="self-avatar"
              aria-label="Hồ sơ của tôi"
              to="/profile"
            >
              A
            </Link>
          </div>
        </aside>
        <main
          id="main"
          tabIndex={-1}
          className={`${cx.main} me-main ${assistants ? "me-assistants" : "me-page"}`}
        >
          {!assistants && (
            <header className="page-app-header">
              <Link to="/assistants" aria-label="Me2We — Trợ lý">
                <Brand />
              </Link>
              <Link
                className="icon-button"
                to="/settings"
                aria-label="Quyền riêng tư"
              >
                <ShieldCheck size={21} />
              </Link>
            </header>
          )}
          {state.notice && (
            <div role="status" className={cx.statusBar}>
              <span>{state.notice}</span>
              <Button
                variant="text"
                aria-label="Đóng thông báo"
                onClick={() => dispatch({ type: "NOTICE", text: "" })}
              >
                ×
              </Button>
            </div>
          )}
          <Motion
            key={state.epoch}
            motionKey={`${displayed.pathname}-${displayed.search}`}
          >
            <Routes location={displayed}>
              <Route path="/" element={<Navigate replace to="/assistants" />} />
              <Route
                path="/start"
                element={<Navigate replace to="/assistants" />}
              />
              <Route
                path="/messages"
                element={
                  <ScreenGate>
                    <MessagesPage />
                  </ScreenGate>
                }
              />
              <Route
                path="/home"
                element={<Navigate replace to="/assistants" />}
              />
              <Route
                path="/assistants"
                element={
                  <ScreenGate>
                    <CompanionsPage />
                  </ScreenGate>
                }
              />
              <Route
                path="/assistants/:botId"
                element={
                  <ScreenGate>
                    <CompanionsPage />
                  </ScreenGate>
                }
              />
              <Route
                path="/self"
                element={
                  <ScreenGate>
                    <SelfPage />
                  </ScreenGate>
                }
              />
              <Route
                path="/profile"
                element={
                  <ScreenGate>
                    <ProfilePage />
                  </ScreenGate>
                }
              />
              <Route
                path="/connect"
                element={
                  <ScreenGate>
                    <ConnectPage />
                  </ScreenGate>
                }
              />
              <Route
                path="/chat/:connectionId"
                element={
                  <ScreenGate>
                    <ChatPage />
                  </ScreenGate>
                }
              />
              <Route
                path="/settings"
                element={
                  <ScreenGate>
                    <SettingsPage />
                  </ScreenGate>
                }
              />
              <Route
                path="*"
                element={<Navigate replace to={"/assistants"} />}
              />
            </Routes>
          </Motion>
        </main>
      </div>
      {showSample && (
        <aside className="sample-toast" role="status">
          <span>
            Đây là bản trải nghiệm với nội dung mẫu, chưa kết nối thật.
          </span>
          <button
            aria-label="Đóng giới thiệu bản mẫu"
            onClick={() => setShowSample(false)}
          >
            ×
          </button>
        </aside>
      )}
      {about && (
        <Dialog title="Me2We" onClose={() => setAbout(false)}>
          <p>Hiểu mình hơn. Tìm người cùng tần số.</p>
          <p>
            Bản trải nghiệm dùng nhân vật hư cấu và phản hồi soạn sẵn. Chưa kết
            nối người thật hay AI thật. Nội dung chỉ tồn tại trong phiên, không
            được tải lên hoặc lưu sau khi tải lại.
          </p>
          <GoAbout />
          <Button onClick={() => setAbout(false)}>Đóng thông tin</Button>
        </Dialog>
      )}
      {pending && guarded && active && (
        <Dialog
          destructive
          title="Dừng hoạt động trước khi rời đi?"
          onClose={() => {
            navigate(accepted.pathname + accepted.search, { replace: true });
            setPending(undefined);
          }}
        >
          <p>
            Thẻ câu hỏi đang chơi sẽ dừng. Hủy để giữ nguyên câu và tiếp tục
            chơi.
          </p>
          <div className={cx.actions}>
            <Button
              data-cancel
              variant="secondary"
              onClick={() => {
                navigate(accepted.pathname + accepted.search, {
                  replace: true,
                });
                setPending(undefined);
              }}
            >
              Ở lại chơi tiếp
            </Button>
            <Button
              variant="danger"
              onClick={() => {
                dispatch({ type: "ACTIVITY_STOP", id: active.id });
                setAccepted(pending);
                setPending(undefined);
              }}
            >
              Dừng và rời đi
            </Button>
          </div>
        </Dialog>
      )}
    </>
  );
}
function GoAbout() {
  return (
    <p>
      <Link to="/settings">Quyền riêng tư & đặt lại</Link>
    </p>
  );
}
function MessagesPage() {
  const { state } = useDemo();
  const rooms = state.connections.filter((c) => canChat(state, c));
  return (
    <>
      <p className="overline">MỘT CHÚT GẦN NHAU</p>
      <h1 tabIndex={-1}>Tin nhắn</h1>
      <p className={cx.lede}>Một lời chào có thể là khởi đầu.</p>
      {rooms.map((c) => (
        <Link className={cx.messagePreview} key={c.id} to={`/chat/${c.id}`}>
          <Avatar
            name={
              state.candidates.find((p) => p.id === c.candidateId)?.alias ||
              "Bạn"
            }
          />
          <div>
            <h2>
              {state.candidates.find((p) => p.id === c.candidateId)?.alias}
            </h2>
            <small>Bạn kết nối · Nhân vật mẫu</small>
            <p>{c.messages.at(-1)?.text}</p>
          </div>
          <span>↗</span>
        </Link>
      ))}
      {!rooms.length && (
        <div className={cx.statePanel}>
          <MessageCircle size={38} />
          <h2>Một người bạn mới đang chờ</h2>
          <p>Tìm điểm chung, gửi lời chào.</p>
          <Link className={`${cx.button} ${cx.primary}`} to="/connect">
            Khám phá người đồng điệu ↗
          </Link>
        </div>
      )}
    </>
  );
}
export default function App() {
  return (
    <Provider>
      <HashRouter>
        <Shell />
      </HashRouter>
    </Provider>
  );
}
