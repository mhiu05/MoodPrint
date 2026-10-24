import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type FormEvent,
  type ReactNode,
} from "react";
import {
  HashRouter,
  Link,
  NavLink,
  Navigate,
  Route,
  Routes,
  useLocation,
  useParams,
} from "react-router-dom";
import {
  ArrowLeft,
  ArrowUpRight,
  LockKeyhole,
  MessageCircle,
  Search,
  Send,
  ShieldCheck,
  SlidersHorizontal,
  Sparkles,
  UserRound,
  Users,
} from "lucide-react";
import {
  Brand,
  Button,
  cx,
  Dialog,
  Motion,
  StatePanel,
  Typing,
} from "../../components/UI";
import { BrandMark, BotAvatar } from "../../companions/Avatar";
import { botById, type BotId } from "../../companions/registry";
import { ApiClient, ApiError, errorMessage } from "../../api/client";
import { consumeAIEvents, validCards } from "../../api/stream";
import { AdultEligibility, EligibilityGate } from "./Eligibility";
import type {
  AIRunAccepted,
  ActionReceipt,
  BotPublicDTO,
  ConsentPurpose,
  ConsentInput,
  ConversationInput,
  ConversationHeader,
  ConversationView,
  MoodDTO,
  MoodInput,
  LoginInput,
  PrivateItemDTO,
  PrivateItemInput,
  PrivateItemEdit,
  SessionView,
  StartRunInput,
  VersionInput,
} from "../../api/contracts";
import "./real.css";
import { Discovery, HumanChat, HumanMessages } from "./Social";
import { ApprovedMemories } from "./Memory";
import { VoiceRecorder } from "./Voice";
import { OwnIdentity } from "./Safety";
import { DataControls } from "./Privacy";

type SessionContextValue = {
  api: ApiClient;
  session: SessionView;
  receive: (session: SessionView) => void;
  logout: () => Promise<void>;
};
const SessionContext = createContext<SessionContextValue | null>(null);
export function useSession() {
  const context = useContext(SessionContext);
  if (!context) throw new Error("Session is required");
  return context;
}

function validateSession(value: SessionView): SessionView {
  if (
    !value ||
    typeof value.userId !== "string" ||
    typeof value.alias !== "string" ||
    typeof value.eligible !== "boolean" ||
    typeof value.csrfToken !== "string" ||
    !value.csrfToken ||
    typeof value.timezone !== "string" ||
    !value.features ||
    !value.consents ||
    !["AI", "MEM", "MATCH", "VOICE"].every((purpose) => {
      const consent = value.consents[purpose as ConsentPurpose];
      return (
        consent &&
        typeof consent.enabled === "boolean" &&
        Number.isInteger(consent.version)
      );
    })
  )
    throw new ApiError(
      502,
      "INVALID_SESSION",
      "Chưa thể xác minh phiên. Vui lòng thử lại.",
    );
  return value;
}

export function ErrorNotice({
  error,
  retry,
}: {
  error: unknown;
  retry?: () => void;
}) {
  if (!error) return null;
  return (
    <div className={cx.error} role="alert">
      <p>{errorMessage(error)}</p>
      {retry ? (
        <Button variant="secondary" onClick={retry}>
          Thử lại
        </Button>
      ) : null}
    </div>
  );
}

export function useResource<T>(path: string, enabled = true) {
  const { api } = useSession();
  const [data, setData] = useState<T>();
  const [error, setError] = useState<unknown>();
  const [loading, setLoading] = useState(true);
  const [revision, setRevision] = useState(0);
  const refresh = useCallback(() => setRevision((value) => value + 1), []);
  useEffect(() => {
    if (!enabled) {
      setData(undefined);
      setError(undefined);
      setLoading(false);
      return;
    }
    const controller = new AbortController();
    setLoading(true);
    setError(undefined);
    api
      .request<T>(path, { signal: controller.signal })
      .then((value) => {
        if (!controller.signal.aborted) setData(value);
      })
      .catch((reason) => {
        if (!controller.signal.aborted) setError(reason);
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [api, path, revision, enabled]);
  return { data, setData, error, loading, refresh };
}

function Login({
  api,
  receive,
}: {
  api: ApiClient;
  receive: (value: SessionView) => void;
}) {
  const [email, setEmail] = useState(""),
    [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false),
    [error, setError] = useState<unknown>();
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (busy) return;
    setBusy(true);
    setError(undefined);
    try {
      receive(
        await api.request<SessionView>("/auth/login", {
          method: "POST",
          body: { email, password } satisfies LoginInput,
          publicWrite: true,
        }),
      );
    } catch (reason) {
      setError(reason);
    } finally {
      setBusy(false);
    }
  }
  return (
    <main id="main" className="real-auth">
      <Brand />
      <h1 tabIndex={-1}>Chào bạn trở lại</h1>
      <p className={cx.lede}>Đăng nhập để tiếp tục không gian riêng của bạn.</p>
      <ErrorNotice error={error} />
      <form onSubmit={submit} aria-busy={busy}>
        <label htmlFor="email">Email</label>
        <input
          id="email"
          type="email"
          autoComplete="username"
          required
          maxLength={254}
          value={email}
          onChange={(event) => setEmail(event.target.value)}
        />
        <label htmlFor="password">Mật khẩu</label>
        <input
          id="password"
          type="password"
          autoComplete="current-password"
          required
          maxLength={256}
          value={password}
          onChange={(event) => setPassword(event.target.value)}
        />
        <Button type="submit" disabled={busy}>
          {busy ? "Đang đăng nhập…" : "Đăng nhập"}
        </Button>
      </form>
    </main>
  );
}

function SessionRoot() {
  const [api] = useState(() => new ApiClient());
  const [session, setSession] = useState<SessionView | null>();
  const [error, setError] = useState<unknown>();
  const [revision, setRevision] = useState(0);
  const receive = useCallback(
    (value: SessionView) => {
      const valid = validateSession(value);
      api.setCsrf(valid.csrfToken);
      setError(undefined);
      setSession(valid);
    },
    [api],
  );
  useEffect(() => {
    const controller = new AbortController();
    api.onUnauthorized = () => {
      api.reset();
      setSession(null);
    };
    api
      .request<SessionView>("/session", { signal: controller.signal })
      .then((value) => {
        if (!controller.signal.aborted) receive(value);
      })
      .catch((reason) => {
        if (controller.signal.aborted) return;
        if (reason instanceof ApiError && reason.status === 401) {
          api.reset();
          setSession(null);
        } else setError(reason);
      });
    return () => controller.abort();
  }, [api, receive, revision]);
  useEffect(() => {
    if (!session) return;
    let scheduled: number | undefined;
    const recheck = () => {
      if (document.visibilityState !== "visible") return;
      window.clearTimeout(scheduled);
      scheduled = window.setTimeout(
        () => setRevision((value) => value + 1),
        100,
      );
    };
    window.addEventListener("focus", recheck);
    document.addEventListener("visibilitychange", recheck);
    return () => {
      window.clearTimeout(scheduled);
      window.removeEventListener("focus", recheck);
      document.removeEventListener("visibilitychange", recheck);
    };
  }, [session?.userId]);
  async function logout() {
    await api.request<void>("/auth/logout", { method: "POST" });
    api.reset();
    setSession(null);
  }
  if (error)
    return (
      <main className="real-auth">
        <Brand />
        <h1 tabIndex={-1}>Chưa thể mở không gian của bạn</h1>
        <ErrorNotice
          error={error}
          retry={() => {
            setError(undefined);
            setRevision((value) => value + 1);
          }}
        />
      </main>
    );
  if (session === undefined)
    return (
      <main className="real-auth">
        <Brand />
        <p role="status">Đang kiểm tra phiên…</p>
      </main>
    );
  if (session === null) return <Login api={api} receive={receive} />;
  return (
    <SessionContext.Provider value={{ api, session, receive, logout }}>
      {session.eligible ? <Shell /> : <EligibilityGate />}
    </SessionContext.Provider>
  );
}

function Navigation() {
  return (
    <nav className={cx.navigation} aria-label="Điều hướng chính">
      {[
        { to: "/assistants", label: "Trợ lý", Icon: Sparkles },
        { to: "/connect", label: "Tìm bạn", Icon: Users },
        { to: "/messages", label: "Tin nhắn", Icon: MessageCircle },
        { to: "/profile", label: "Tôi", Icon: UserRound },
      ].map(({ to, label, Icon }) => (
        <NavLink
          key={to}
          className={({ isActive }) =>
            `${cx.navItem} ${isActive ? cx.navActive : ""}`
          }
          to={to}
        >
          <Icon size={21} strokeWidth={1.6} />
          <span>{label}</span>
        </NavLink>
      ))}
    </nav>
  );
}

function Shell() {
  const { session } = useSession();
  const location = useLocation();
  const assistants = location.pathname.startsWith("/assistants");
  const fullChat = assistants && location.pathname !== "/assistants";
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
    document.querySelector<HTMLElement>("h1")?.focus({ preventScroll: true });
    window.scrollTo(0, 0);
  }, [location.pathname]);
  return (
    <>
      <a
        className={cx.skipLink}
        href="#main"
        onClick={(event) => {
          event.preventDefault();
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
            <Link
              className="icon-button"
              to="/settings"
              aria-label="Quyền riêng tư"
            >
              <ShieldCheck size={21} />
            </Link>
            <Link
              className="self-avatar"
              to="/profile"
              aria-label="Hồ sơ của tôi"
            >
              {session.alias.charAt(0).toLocaleUpperCase("vi-VN")}
            </Link>
          </div>
        </aside>
        <main
          id="main"
          tabIndex={-1}
          className={`${cx.main} me-main ${assistants ? "me-assistants" : "me-page"}`}
        >
          {!assistants ? (
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
          ) : null}
          <Motion motionKey={location.pathname}>
            <Routes>
              <Route path="/assistants" element={<Assistants />} />
              <Route path="/assistants/:botId" element={<Assistants />} />
              <Route path="/settings" element={<Settings />} />
              <Route path="/self" element={<Moods />} />
              <Route path="/profile" element={<PrivateProfile />} />
              <Route path="/memory" element={<ApprovedMemories />} />
              <Route path="/connect" element={<Discovery />} />
              <Route path="/messages" element={<HumanMessages />} />
              <Route
                path="/chat/:connectionId"
                element={<HumanChat key={location.pathname} />}
              />
              <Route path="*" element={<Navigate replace to="/assistants" />} />
            </Routes>
          </Motion>
        </main>
      </div>
    </>
  );
}

function Unavailable({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <>
      <h1 tabIndex={-1}>{title}</h1>
      <StatePanel title="Bạn vẫn có không gian riêng">{children}</StatePanel>
      <div className={cx.actions}>
        <Link className={`${cx.button} ${cx.primary}`} to="/assistants">
          Về trợ lý
        </Link>
        <Link className={`${cx.button} ${cx.secondary}`} to="/self">
          Ghi tâm trạng
        </Link>
      </div>
    </>
  );
}

function avatarId(bot: BotPublicDTO): BotId | undefined {
  return botById(bot.avatarKey)?.id;
}
function PublicAvatar({ bot, size }: { bot: BotPublicDTO; size?: number }) {
  const id = avatarId(bot);
  return id ? (
    <BotAvatar id={id} size={size} />
  ) : (
    <span className="self-avatar" aria-hidden="true">
      {bot.name.charAt(0)}
    </span>
  );
}

function Assistants() {
  const { botId } = useParams();
  const resource = useResource<BotPublicDTO[]>("/bots");
  const [search, setSearch] = useState("");
  const bots = resource.data || [];
  const bot = bots.find((value) => value.botId === botId);
  const filtered = bots.filter((value) =>
    `${value.name} ${value.role}`
      .toLocaleLowerCase("vi-VN")
      .includes(search.toLocaleLowerCase("vi-VN")),
  );
  return (
    <div className={`companion-layout ${botId ? "has-conversation" : ""}`}>
      <section className="bot-roster" aria-label="Danh sách trợ lý">
        <div className="roster-brand">
          <Link to="/assistants" aria-label="Me2We — Trợ lý">
            <Brand />
          </Link>
          <Link
            className="icon-button"
            to="/settings"
            aria-label="Tùy chọn ứng dụng"
          >
            <SlidersHorizontal size={20} />
          </Link>
        </div>
        <div className="roster-heading">
          <h1 tabIndex={-1}>
            Bạn muốn kể gì
            <br />
            <span>hôm nay?</span>
          </h1>
        </div>
        <label className="bot-search">
          <Search size={18} />
          <input
            aria-label="Tìm trợ lý"
            placeholder="Tìm một người bạn AI…"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
        </label>
        <div className="roster-section-label">
          <h2>Trợ lý của bạn</h2>
          <span>{String(bots.length).padStart(2, "0")}</span>
        </div>
        {resource.loading ? <p role="status">Đang tải trợ lý…</p> : null}
        <ErrorNotice error={resource.error} retry={resource.refresh} />
        <div className="bot-list">
          {filtered.map((value) => (
            <Link
              key={value.botId}
              to={`/assistants/${value.botId}`}
              className={`bot-row ${botId === value.botId ? "selected" : ""}`}
              aria-label={`Trò chuyện với ${value.name}`}
              aria-current={botId === value.botId ? "page" : undefined}
            >
              <PublicAvatar bot={value} />
              <div className="bot-row-text">
                <div>
                  <strong>{value.name}</strong>
                  <span className="ai-tag">AI</span>
                </div>
                <small>{value.role}</small>
                <p>{value.description}</p>
              </div>
              <ArrowUpRight size={16} className="roster-arrow" />
            </Link>
          ))}
        </div>
        {!resource.loading && !resource.error && !filtered.length ? (
          <p className="search-empty">
            Chưa tìm thấy trợ lý. Thử tên khác nhé.
          </p>
        ) : null}
        <Link className="human-bridge" to="/connect">
          <span className="bridge-icon">
            <Users size={21} />
          </span>
          <span>
            <strong>Từ hiểu mình, đến hiểu mọi người xung quanh</strong>
          </span>
          <ArrowUpRight size={18} />
        </Link>
      </section>
      <section
        className="conversation-pane"
        aria-label={
          bot ? `Trò chuyện với ${bot.name}` : "Không gian trò chuyện"
        }
      >
        {bot ? (
          <Conversation key={bot.botId} bot={bot} />
        ) : botId ? (
          <div className="conversation-welcome">
            {resource.loading ? (
              <p role="status">Đang mở trợ lý…</p>
            ) : (
              <>
                <h2>Chưa thể mở trợ lý này</h2>
                <Link to="/assistants">Về danh sách trợ lý</Link>
              </>
            )}
          </div>
        ) : (
          <div className="conversation-welcome">
            <div className="welcome-orbit">
              <BotAvatar id="may" size={110} />
              <BotAvatar id="guong" size={69} />
              <BotAvatar id="rure" size={64} />
              <span className="orbit-spark">
                <Sparkles size={24} />
              </span>
            </div>
            <h2>
              Mỗi cuộc trò chuyện,
              <br />
              thêm một chút <em>hiểu mình.</em>
            </h2>
            <p>
              Một nơi để lắng nghe bản thân
              <br />
              và tìm những người cùng tần số.
            </p>
            {bots[0] ? (
              <Link
                to={`/assistants/${bots[0].botId}`}
                className="welcome-start"
              >
                Kể {bots[0].name} nghe nhé <ArrowUpRight size={18} />
              </Link>
            ) : null}
            <span className="welcome-signature">
              hiểu mình hơn · gần nhau hơn
            </span>
          </div>
        )}
      </section>
    </div>
  );
}

function Conversation({ bot }: { bot: BotPublicDTO }) {
  const { session } = useSession();
  const allowed = session.consents.AI.enabled && session.features.ai;
  return (
    <div className="bot-conversation">
      <header className="conversation-header">
        <Link
          to="/assistants"
          className="icon-button mobile-back"
          aria-label="Về danh sách trợ lý"
        >
          <ArrowLeft size={21} />
        </Link>
        <PublicAvatar bot={bot} size={43} />
        <div>
          <h1 tabIndex={-1}>
            {bot.name} <span className="ai-tag">AI</span>
          </h1>
          <p>{bot.role}</p>
        </div>
        <Link
          to="/settings"
          className="icon-button"
          aria-label="Quyền trò chuyện AI"
        >
          <ShieldCheck size={21} />
        </Link>
      </header>
      {allowed ? (
        <ConversationBody bot={bot} />
      ) : (
        <div className="chat-disabled">
          <StatePanel
            title={
              session.consents.AI.enabled
                ? "Trò chuyện AI chưa khả dụng"
                : "Trò chuyện AI đang tắt"
            }
            action={
              <div className={cx.actions}>
                <Link className={`${cx.button} ${cx.primary}`} to="/settings">
                  Xem quyền trò chuyện AI
                </Link>
                <Link className={`${cx.button} ${cx.secondary}`} to="/self">
                  Tự ghi tâm trạng
                </Link>
              </div>
            }
          >
            Bạn có thể ghi cảm xúc trong không gian riêng của mình.
          </StatePanel>
        </div>
      )}
    </div>
  );
}

function ConversationBody({ bot }: { bot: BotPublicDTO }) {
  const { api, session } = useSession();
  const [conversation, setConversation] = useState<ConversationView>();
  const current = useRef<ConversationView | undefined>(undefined);
  const [draft, setDraft] = useState(""),
    [error, setError] = useState<unknown>();
  const [loading, setLoading] = useState(true),
    [busy, setBusy] = useState(false);
  const [ready, setReady] = useState(false);
  const [run, setRun] = useState<{ id: string; version: number }>();
  const [revision, setRevision] = useState(0);
  const [atBottom, setAtBottom] = useState(true);
  const log = useRef<HTMLDivElement>(null),
    lifetime = useRef<AbortController | null>(null);
  const intent = useRef<{ text: string; scopeKey: string; clientMessageId: string } | null>(null);
  const [shareMood, setShareMood] = useState(false);
  const [moodFrom, setMoodFrom] = useState("");
  const [moodTo, setMoodTo] = useState("");
  const moodWindow = useMemo(() => {
    const parts = Object.fromEntries(new Intl.DateTimeFormat("en", {
      timeZone: session.timezone, year: "numeric", month: "2-digit", day: "2-digit",
    }).formatToParts(new Date(session.serverTime)).map(part => [part.type, part.value]));
    const today = `${parts.year}-${parts.month}-${parts.day}`;
    const earliest = new Date(`${today}T00:00:00Z`);
    earliest.setUTCDate(earliest.getUTCDate() - 89);
    return { today, earliest: earliest.toISOString().slice(0, 10) };
  }, [session.serverTime, session.timezone]);
  const moodSelected = bot.botId === "nhip" && shareMood;
  const moodInvalid = moodSelected && (!moodFrom || !moodTo || moodFrom > moodTo ||
    moodFrom < moodWindow.earliest || moodTo > moodWindow.today);
  const update = useCallback((value: ConversationView) => {
    current.current = value;
    setConversation(value);
  }, []);
  const stream = useCallback(
    async (
      id: string,
      version: number,
      eventsUrl: string,
      signal: AbortSignal,
    ) => {
      setRun({ id, version });
      setBusy(true);
      try {
        const final = await consumeAIEvents(eventsUrl, signal);
        if (!signal.aborted && current.current) {
          const before = current.current;
          update({
            ...before,
            activeRunId: null,
            activeRunVersion: null,
            messages: [
              ...before.messages,
              {
                id: `${id}-final`,
                actor: "bot",
                text: final.text,
                cards: final.cards,
              },
            ],
          });
          const stored = await api.request<ConversationView>(
            `/ai/conversations/${before.conversationId}`,
            { signal },
          );
          if (!signal.aborted) {
            update(stored);
            setReady(true);
          }
        }
      } catch (reason) {
        if (!signal.aborted) {
          setError(reason);
          setReady(false);
        }
      } finally {
        if (!signal.aborted) {
          setRun(undefined);
          setBusy(false);
        }
      }
    },
    [api, update],
  );
  useEffect(() => {
    const controller = new AbortController();
    lifetime.current = controller;
    setLoading(true);
    setReady(false);
    setError(undefined);
    api
      .request<ConversationHeader[]>("/ai/conversations", {
        signal: controller.signal,
      })
      .then(async (headers) => {
        const existing = headers.find((value) => value.botId === bot.botId);
        if (!existing) {
          current.current = undefined;
          setConversation(undefined);
          if (!controller.signal.aborted) setReady(true);
          return;
        }
        const value = await api.request<ConversationView>(
          `/ai/conversations/${existing.conversationId}`,
          { signal: controller.signal },
        );
        if (controller.signal.aborted) return;
        update(value);
        setReady(true);
        if (value.activeRunId)
          void stream(
            value.activeRunId,
            value.activeRunVersion || 1,
            `/api/v1/ai/runs/${value.activeRunId}/events`,
            controller.signal,
          );
      })
      .catch((reason) => {
        if (!controller.signal.aborted) setError(reason);
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [api, bot.botId, revision, stream, update]);
  useEffect(() => {
    if (atBottom && log.current)
      log.current.scrollTop = log.current.scrollHeight;
  }, [conversation?.messages.length, busy, atBottom]);
  async function send(value = draft) {
    const text = value.trim();
    if (
      !text ||
      busy ||
      loading ||
      !ready ||
      moodInvalid ||
      text.length > 500 ||
      !lifetime.current
    )
      return;
    const signal = lifetime.current.signal;
    setBusy(true);
    setError(undefined);
    const moodScope = moodSelected ? { fromDate: moodFrom, toDate: moodTo } : undefined;
    const scopeKey = moodScope ? `${moodScope.fromDate}/${moodScope.toDate}` : "";
    if (intent.current?.text !== text || intent.current?.scopeKey !== scopeKey)
      intent.current = { text, scopeKey, clientMessageId: crypto.randomUUID() };
    try {
      let thread = current.current;
      if (!thread) {
        const created = await api.request<ConversationHeader>(
          "/ai/conversations",
          {
            method: "POST",
            body: { botId: bot.botId } satisfies ConversationInput,
            signal,
          },
        );
        thread = {
          ...created,
          messages: [],
          activeRunId: null,
          activeRunVersion: null,
        };
        if (signal.aborted) return;
        update(thread);
      }
      const accepted = await api.request<AIRunAccepted>(
        `/ai/conversations/${thread.conversationId}/messages`,
        {
          method: "POST",
          body: {
            text,
            clientMessageId: intent.current!.clientMessageId,
            expectedConversationVersion: thread.version,
            ...(moodScope ? { moodScope } : {}),
          } satisfies StartRunInput,
          signal,
        },
      );
      if (signal.aborted) return;
      update({
        ...thread,
        version: accepted.version,
        activeRunId: accepted.runId,
        activeRunVersion: accepted.runVersion,
        messages: [
          ...thread.messages,
          { id: intent.current!.clientMessageId, actor: "self", text },
        ],
      });
      intent.current = null;
      setShareMood(false);
      setDraft("");
      setAtBottom(true);
      await stream(
        accepted.runId,
        accepted.runVersion,
        accepted.eventsUrl,
        signal,
      );
    } catch (reason) {
      if (!signal.aborted) setError(reason);
    } finally {
      if (!signal.aborted) setBusy(false);
    }
  }
  async function cancel() {
    if (!run) return;
    try {
      await api.request(`/ai/runs/${run.id}/cancel`, {
        method: "POST",
        body: { expectedVersion: run.version } satisfies VersionInput,
      });
    } catch (reason) {
      setError(reason);
    }
  }
  return (
    <>
      <div
        className="conversation-log"
        ref={log}
        role="log"
        aria-label={`Hội thoại với ${bot.name}`}
        aria-live="polite"
        onScroll={() => {
          const element = log.current!;
          setAtBottom(
            element.scrollHeight - element.scrollTop - element.clientHeight <
              90,
          );
        }}
      >
        <div className="chat-introduction">
          <PublicAvatar bot={bot} size={80} />
          <h3>Một chút thời gian với {bot.name}</h3>
          <p>{bot.description}</p>
          <small>
            <LockKeyhole size={11} /> Chỉ bạn xem
          </small>
        </div>
        {loading ? <p role="status">Đang mở cuộc trò chuyện…</p> : null}
        {conversation?.messages.map((message) => (
          <div
            key={message.id}
            className={`message-row ${message.actor === "self" ? "from-self" : "from-bot"}`}
          >
            <div className="message-content">
              <div className="chat-bubble">
                <p>{message.text}</p>
              </div>
              {validCards(message.cards) &&
                message.cards.map((card, index) => (
                  <div className="inline-card" key={`${message.id}-${index}`}>
                    {card.kind === "mood_form" ? (
                      <Link to="/self">Ghi lại cảm xúc</Link>
                    ) : card.kind === "navigate_bot" ? (
                      <Link to={`/assistants/${card.botId}`}>
                        Trò chuyện với {botById(card.botId)?.name}
                      </Link>
                    ) : (
                      <Link to="/connect">Tìm bạn đồng điệu</Link>
                    )}
                  </div>
                ))}
            </div>
          </div>
        ))}
        {busy ? (
          <div className="bot-pending">
            <Typing />
            {run ? (
              <Button variant="text" onClick={cancel}>
                Dừng
              </Button>
            ) : (
              <span>Đang gửi…</span>
            )}
          </div>
        ) : null}
        <ErrorNotice
          error={error}
          retry={() => setRevision((value) => value + 1)}
        />
      </div>
      <div className="chat-bottom">
        {bot.botId === "nhip" ? (
          <details className="mood-share-options">
            <summary>Chia sẻ thống kê tâm trạng cho lượt này</summary>
            <fieldset disabled={busy || loading || !ready}>
              <label className="mood-share-choice">
                <input type="checkbox" checked={shareMood} onChange={event => setShareMood(event.target.checked)} />
                Cho Nhịp đọc khoảng ngày mình chọn
              </label>
              <p>Chỉ chia sẻ điểm tâm trạng và những ngày đã ghi, không gửi ghi chú. Bạn chọn lại quyền này cho mỗi lượt.</p>
              {shareMood ? <div className="mood-share-dates">
                <label htmlFor="mood-share-from">Thống kê từ ngày
                  <input id="mood-share-from" type="date" min={moodWindow.earliest} max={moodWindow.today} value={moodFrom} onChange={event => setMoodFrom(event.target.value)} />
                </label>
                <label htmlFor="mood-share-to">Thống kê đến ngày
                  <input id="mood-share-to" type="date" min={moodFrom || moodWindow.earliest} max={moodWindow.today} value={moodTo} onChange={event => setMoodTo(event.target.value)} />
                </label>
                {moodInvalid ? <p role="alert">Chọn đủ ngày bắt đầu và kết thúc theo đúng thứ tự, trong 90 ngày gần đây.</p> : null}
              </div> : null}
            </fieldset>
          </details>
        ) : null}
        <VoiceRecorder onUse={setDraft} />
        <div className="quick-replies" aria-label="Gợi ý trò chuyện">
          {bot.starters.map((text) => (
            <button
              key={text}
              disabled={busy || loading || !ready || moodInvalid}
              onClick={() => {
                setDraft(text);
                void send(text);
              }}
            >
              {text}
            </button>
          ))}
        </div>
        <form
          className="bot-composer"
          onSubmit={(event) => {
            event.preventDefault();
            void send();
          }}
        >
          <textarea
            aria-label={`Tin nhắn cho ${bot.name}`}
            value={draft}
            maxLength={500}
            rows={1}
            onChange={(event) => setDraft(event.target.value)}
            placeholder={`Nhắn cho ${bot.name}…`}
            onKeyDown={(event) => {
              if (
                event.key === "Enter" &&
                !event.shiftKey &&
                !event.nativeEvent.isComposing
              ) {
                event.preventDefault();
                void send();
              }
            }}
          />
          <button
            type="submit"
            className="send-button"
            disabled={!draft.trim() || busy || loading || !ready || moodInvalid}
            aria-label="Gửi tin cho AI"
          >
            <Send size={19} />
          </button>
        </form>
      </div>
    </>
  );
}

const consentLabels: Record<ConsentPurpose, string> = {
  AI: "trò chuyện AI",
  MEM: "ghi nhớ đã duyệt",
  MATCH: "tìm bạn",
  VOICE: "giọng nói",
};
const consentDescriptions: Record<ConsentPurpose, string> = {
  AI: "Cho phép xử lý nội dung bạn gửi để trợ lý phản hồi. Hội thoại không tự trở thành hồ sơ hay ghi nhớ.",
  MEM: "Chỉ những mục bạn duyệt mới được ghi nhớ. Quyền này độc lập với trò chuyện AI.",
  MATCH:
    "Quyền tìm bạn không tự công khai hồ sơ riêng. Bạn xem trước và chủ động đăng hồ sơ kết nối.",
  VOICE:
    "Chỉ ghi âm sau thao tác của bạn khi tính năng giọng nói khả dụng. Bạn có thể sửa bản chép trước khi gửi.",
};
function Settings() {
  const { api, session, receive, logout } = useSession();
  const [busy, setBusy] = useState<string>(),
    [error, setError] = useState<unknown>();
  async function change(purpose: ConsentPurpose) {
    if (busy) return;
    setBusy(purpose);
    setError(undefined);
    try {
      receive(
        await api.request<SessionView>(`/consents/${purpose}`, {
          method: "PUT",
          body: {
            enabled: !session.consents[purpose].enabled,
            expectedVersion: session.consents[purpose].version,
            policyVersion: "v1",
          } satisfies ConsentInput,
        }),
      );
    } catch (reason) {
      setError(reason);
    } finally {
      setBusy(undefined);
    }
  }
  return (
    <div className={cx.reading}>
      <h1 tabIndex={-1}>Quyền riêng tư</h1>
      <p className={cx.lede}>
        Bạn quyết định cách dữ liệu của mình được dùng. Mỗi quyền được quản lý
        riêng.
      </p>
      <ErrorNotice error={error} />
      {(["AI", "MEM", "MATCH", "VOICE"] as ConsentPurpose[]).map((purpose) => (
        <section className="real-section" key={purpose}>
          <h2>
            {consentLabels[purpose].charAt(0).toLocaleUpperCase("vi-VN") +
              consentLabels[purpose].slice(1)}
          </h2>
          <p>{consentDescriptions[purpose]}</p>
          <p>
            <strong>
              {session.consents[purpose].enabled ? "Đang bật" : "Đang tắt"}
            </strong>
          </p>
          <Button
            variant="secondary"
            disabled={
              !!busy ||
              (purpose === "MATCH" &&
                session.ageBand !== "adult" &&
                !session.consents.MATCH.enabled)
            }
            onClick={() => void change(purpose)}
          >
            {busy === purpose
              ? "Đang cập nhật…"
              : `${session.consents[purpose].enabled ? "Tắt" : "Bật"} ${consentLabels[purpose]}`}
          </Button>
        </section>
      ))}
      <AdultEligibility />
      <section className="real-section">
        <h2>Phiên đăng nhập</h2>
        <p>{session.alias}</p>
        <Button
          variant="secondary"
          disabled={!!busy}
          onClick={async () => {
            setBusy("logout");
            setError(undefined);
            try {
              await logout();
            } catch (reason) {
              setError(reason);
            } finally {
              setBusy(undefined);
            }
          }}
        >
          {busy === "logout" ? "Đang đăng xuất…" : "Đăng xuất"}
        </Button>
      </section>
      <DataControls />
    </div>
  );
}

function localDate(time: string, timezone: string) {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: timezone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(new Date(time));
  return ["year", "month", "day"]
    .map((type) => parts.find((part) => part.type === type)?.value)
    .join("-");
}
function Moods() {
  const { api, session } = useSession();
  const resource = useResource<MoodDTO[]>("/moods");
  const [date, setDate] = useState(() =>
    localDate(session.serverTime, session.timezone),
  );
  const [value, setValue] = useState(3),
    [note, setNote] = useState("");
  const [busy, setBusy] = useState(false),
    [error, setError] = useState<unknown>(),
    [receipt, setReceipt] = useState("");
  async function save(event: FormEvent) {
    event.preventDefault();
    if (busy || !resource.data) return;
    setBusy(true);
    setError(undefined);
    setReceipt("");
    try {
      const saved = await api.request<MoodDTO>(`/moods/${date}`, {
        method: "PUT",
        body: {
          value,
          note,
          timezone: session.timezone,
          expectedVersion:
            resource.data.find((mood) => mood.localDate === date)?.version || 0,
        } satisfies MoodInput,
      });
      resource.setData((previous) =>
        [
          saved,
          ...(previous || []).filter(
            (mood) => mood.localDate !== saved.localDate,
          ),
        ].sort((a, b) => b.localDate.localeCompare(a.localDate)),
      );
      setReceipt("Đã lưu tâm trạng.");
    } catch (reason) {
      setError(reason);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className={cx.reading}>
      <h1 tabIndex={-1}>Cảm xúc của bạn</h1>
      <p className={cx.lede}>
        Dành một nhịp để lắng nghe bản thân. Chỉ bạn xem những ghi chép này.
      </p>
      <ErrorNotice error={resource.error} retry={resource.refresh} />
      <ErrorNotice error={error} />
      {resource.loading ? <p role="status">Đang tải tâm trạng…</p> : null}
      <form onSubmit={save}>
        <label htmlFor="mood-date">Ngày</label>
        <input
          id="mood-date"
          type="date"
          value={date}
          required
          onChange={(event) => {
            setDate(event.target.value);
            setReceipt("");
          }}
        />
        <label htmlFor="mood-value">Tâm trạng</label>
        <select
          id="mood-value"
          value={value}
          onChange={(event) => setValue(Number(event.target.value))}
        >
          {[
            "Rất khó khăn",
            "Hơi chùng xuống",
            "Bình thường",
            "Khá ổn",
            "Rất vui",
          ].map((label, index) => (
            <option key={label} value={index + 1}>
              {index + 1} — {label}
            </option>
          ))}
        </select>
        <label htmlFor="mood-note">Ghi chú</label>
        <textarea
          id="mood-note"
          value={note}
          maxLength={120}
          rows={3}
          onChange={(event) => setNote(event.target.value)}
        />
        <Button
          type="submit"
          disabled={busy || resource.loading || !resource.data}
        >
          {busy ? "Đang lưu…" : "Lưu tâm trạng"}
        </Button>
        {receipt ? <p role="status">{receipt}</p> : null}
      </form>
      <section className="real-section">
        <h2>Nhìn lại cảm xúc</h2>
        {resource.data?.length === 0 ? (
          <p>Chưa có ghi chép. Bạn có thể bắt đầu từ hôm nay.</p>
        ) : null}
        {resource.data?.map((mood) => (
          <article className="real-item" key={mood.id}>
            <h3>
              {mood.localDate} · {mood.value}/5
            </h3>
            <p>{mood.note}</p>
            <Button
              variant="text"
              onClick={() => {
                setDate(mood.localDate);
                setValue(mood.value);
                setNote(mood.note);
                setReceipt("");
                document.getElementById("mood-value")?.focus();
              }}
            >
              Sửa tâm trạng ngày {mood.localDate}
            </Button>
          </article>
        ))}
      </section>
    </div>
  );
}

function PrivateProfile() {
  const { api, session } = useSession();
  const resource = useResource<PrivateItemDTO[]>("/profiles/private-items");
  const [text, setText] = useState(""),
    [editing, setEditing] = useState<PrivateItemDTO>();
  const [deleting, setDeleting] = useState<PrivateItemDTO>();
  const [busy, setBusy] = useState(false),
    [error, setError] = useState<unknown>(),
    [receipt, setReceipt] = useState("");
  async function save(event: FormEvent) {
    event.preventDefault();
    if (busy || !text.trim() || !resource.data) return;
    setBusy(true);
    setError(undefined);
    setReceipt("");
    try {
      const saved = await api.request<PrivateItemDTO>(
        editing
          ? `/profiles/private-items/${editing.id}`
          : "/profiles/private-items",
        {
          method: editing ? "PATCH" : "POST",
          body: editing
            ? ({
                text: text.trim(),
                expectedVersion: editing.version,
              } satisfies PrivateItemEdit)
            : ({ text: text.trim() } satisfies PrivateItemInput),
        },
      );
      resource.setData((previous) => [
        saved,
        ...(previous || []).filter((item) => item.id !== saved.id),
      ]);
      setText("");
      setEditing(undefined);
      setReceipt("Đã lưu vào hồ sơ riêng.");
    } catch (reason) {
      setError(reason);
    } finally {
      setBusy(false);
    }
  }
  async function remove() {
    if (!deleting || busy) return;
    setBusy(true);
    setError(undefined);
    try {
      const confirmed = await api.request<ActionReceipt>(
        `/profiles/private-items/${deleting.id}`,
        {
          method: "DELETE",
          body: { expectedVersion: deleting.version } satisfies VersionInput,
        },
      );
      if (
        confirmed.status !== "succeeded" ||
        confirmed.resourceId !== deleting.id
      )
        throw new ApiError(
          502,
          "INVALID_RECEIPT",
          "Chưa xác nhận được thao tác xóa. Vui lòng tải lại hồ sơ riêng để kiểm tra.",
        );
      resource.setData((previous) =>
        previous?.filter((item) => item.id !== deleting.id),
      );
      if (editing?.id === deleting.id) {
        setEditing(undefined);
        setText("");
      }
      setDeleting(undefined);
      setReceipt("Đã xóa mục khỏi hồ sơ riêng.");
    } catch (reason) {
      setError(reason);
      setDeleting(undefined);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className={cx.reading}>
      <h1 tabIndex={-1}>Hồ sơ riêng của {session.alias}</h1>
      <p className={cx.lede}>
        Những điều bạn tự ghi lại về mình. Các mục này không tự chia sẻ cho
        người khác hay trở thành ghi nhớ AI.
      </p>
      <div className={cx.actions}>
        <Link className={`${cx.button} ${cx.secondary}`} to="/self">
          Cảm xúc của tôi
        </Link>
        <Link className={`${cx.button} ${cx.secondary}`} to="/memory">
          Ghi nhớ đã duyệt
        </Link>
        <Link className={`${cx.button} ${cx.secondary}`} to="/settings">
          Quyền riêng tư
        </Link>
      </div>
      <ErrorNotice error={resource.error} retry={resource.refresh} />
      <ErrorNotice error={error} />
      <form onSubmit={save}>
        <label htmlFor="private-text">Điều bạn muốn ghi lại</label>
        <textarea
          id="private-text"
          rows={3}
          maxLength={120}
          value={text}
          onChange={(event) => setText(event.target.value)}
          required
        />
        <div className={cx.actions}>
          <Button
            type="submit"
            disabled={
              busy || resource.loading || !resource.data || !text.trim()
            }
          >
            {busy
              ? "Đang lưu…"
              : editing
                ? "Lưu thay đổi"
                : "Lưu vào hồ sơ riêng"}
          </Button>
          {editing ? (
            <Button
              variant="text"
              onClick={() => {
                setEditing(undefined);
                setText("");
              }}
            >
              Hủy sửa
            </Button>
          ) : null}
        </div>
      </form>
      {receipt ? <p role="status">{receipt}</p> : null}
      {resource.loading ? <p role="status">Đang tải hồ sơ riêng…</p> : null}
      <section className="real-section">
        <h2>Những điều về bạn</h2>
        {resource.data?.length === 0 ? (
          <p>Chưa có mục nào. Ghi lại một điều bạn muốn hiểu thêm về mình.</p>
        ) : null}
        {resource.data?.map((item) => (
          <article className="real-item" key={item.id}>
            <p>{item.text}</p>
            <small>
              {item.origin === "ai"
                ? "AI đề xuất · Bạn đã duyệt"
                : "Bạn tự ghi"}{" "}
              · {item.status === "edited" ? "Đã chỉnh sửa" : "Đã xác nhận"}
            </small>
            <div className={cx.actions}>
              <Button
                variant="text"
                disabled={busy}
                aria-label={`Sửa mục ${item.text}`}
                onClick={() => {
                  setEditing(item);
                  setText(item.text);
                  setReceipt("");
                  document.getElementById("private-text")?.focus();
                }}
              >
                Sửa
              </Button>
              <Button
                variant="text"
                disabled={busy}
                aria-label={`Xóa mục ${item.text}`}
                onClick={() => setDeleting(item)}
              >
                Xóa
              </Button>
            </div>
          </article>
        ))}
      </section>
      {deleting ? (
        <Dialog
          title="Xóa mục khỏi hồ sơ riêng?"
          destructive
          onClose={() => {
            if (!busy) setDeleting(undefined);
          }}
        >
          <p>{deleting.text}</p>
          <p>Mục này sẽ bị xóa sau khi máy chủ xác nhận.</p>
          <div className={cx.actions}>
            <Button
              variant="secondary"
              data-cancel
              disabled={busy}
              onClick={() => setDeleting(undefined)}
            >
              Giữ lại
            </Button>
            <Button
              variant="danger"
              disabled={busy}
              onClick={() => void remove()}
            >
              Xác nhận xóa
            </Button>
          </div>
        </Dialog>
      ) : null}
      <OwnIdentity />
    </div>
  );
}

export default function RealApp() {
  return (
    <HashRouter>
      <SessionRoot />
    </HashRouter>
  );
}
