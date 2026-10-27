import {
  createContext,
  lazy,
  Suspense,
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
  useSearchParams,
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
import { AuthScreen, readAuthCallback } from "./Auth";
import type {
  AIRunAccepted,
  ActionReceipt,
  BotPublicDTO,
  ConsentPurpose,
  ConsentInput,
  PrivateItemDTO,
  PrivateItemInput,
  PrivateItemEdit,
  SessionView,
  StartRunInput,
  VersionInput,
} from "../../api/contracts";
import "./real.css";
import { ConnectBridge, Discovery } from "./social/Discovery";
import { OfflineBanner } from "./OfflineBanner";
import { AssistantGuide } from "./AssistantGuide";
import { aiServiceMessage } from "./aiStatus";
import { HumanChat } from "./social/HumanChat";
import { HumanMessages } from "./social/HumanMessages";
import { badgeText, useSocialSummary } from "./social/useSocialSummary";
import { Moderation } from "./admin/Moderation";
import { ApprovedMemories } from "./Memory";
import { Moods } from "./Mood";
import { VoiceRecorder } from "./Voice";
import { OwnIdentity } from "./Safety";
import { DataControls } from "./Privacy";
import { AIDataProvider, AIDataControls, ConversationHistory, useAIData, downloadConversation, type SavedConversation, type SavedConversationHeader } from "./AIData";

const MessageMarkdown = lazy(() => import("./MessageMarkdown"));

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
  // A failed read retries by itself when the browser comes back online.
  useEffect(() => {
    if (!error || !enabled) return;
    window.addEventListener("online", refresh);
    return () => window.removeEventListener("online", refresh);
  }, [error, enabled, refresh]);
  return { data, setData, error, loading, refresh };
}

function SessionRoot() {
  const [api] = useState(() => new ApiClient());
  // Captured once before rendering so email-link tokens leave the URL immediately.
  const [callback] = useState(readAuthCallback);
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
  if (session === null || callback?.kind === "recovery")
    return <AuthScreen api={api} receive={receive} callback={callback} />;
  return (
    <SessionContext.Provider value={{ api, session, receive, logout }}>
      {session.eligible ? <AIDataProvider key={session.userId}><Shell /></AIDataProvider> : <EligibilityGate />}
    </SessionContext.Provider>
  );
}

/** Moderation notices from the session (warning until dismissed; restriction until it ends). */
function SessionNotices() {
  const { session } = useSession();
  const [dismissed, setDismissed] = useState(false);
  const notices = (session.notices ?? []).filter(
    (notice) => notice.kind === "restricted" || !dismissed,
  );
  if (!notices.length) return null;
  return (
    <div className={cx.note} role="status">
      {notices.map((notice) =>
        notice.kind === "restricted" ? (
          <p key="restricted">
            Tính năng kết nối của bạn đang tạm bị hạn chế
            {notice.until
              ? ` đến ${new Date(notice.until).toLocaleDateString("vi-VN")}`
              : ""}
            . Bạn vẫn dùng được các trợ lý và nhật ký cảm xúc.
          </p>
        ) : (
          <p key="warning">
            Tài khoản của bạn đã nhận một cảnh báo về quy tắc cộng đồng. Hãy trò
            chuyện tôn trọng để giữ cộng đồng an toàn.{" "}
            <Button variant="text" onClick={() => setDismissed(true)}>
              Đã hiểu
            </Button>
          </p>
        ),
      )}
    </div>
  );
}

/** Shown only when few AI turns remain today (Asia/Bangkok day). */
function QuotaHint() {
  const { session } = useSession();
  const remaining = session.features.aiQuotaRemaining;
  if (remaining == null || remaining > 10) return null;
  return (
    <p className={cx.footnote} role="status">
      {remaining === 0
        ? "Hôm nay bạn đã dùng hết lượt trò chuyện với trợ lý. Hẹn bạn ngày mai nhé."
        : `Hôm nay bạn còn ${remaining} lượt trò chuyện với trợ lý.`}
    </p>
  );
}

function Navigation() {
  const location = useLocation();
  const summary = useSocialSummary(location.pathname);
  const unread = summary.unreadConnections + summary.activityInvites;
  return (
    <nav className={cx.navigation} aria-label="Điều hướng chính">
      {[
        { to: "/assistants", label: "Trợ lý", Icon: Sparkles, count: 0, what: "" },
        {
          // Pending invitations open their tab directly (08 section 2).
          to: summary.pendingIncomingRequests ? "/connect?tab=requests" : "/connect",
          label: "Tìm bạn",
          Icon: Users,
          count: summary.pendingIncomingRequests,
          what: "lời mời kết nối mới",
        },
        {
          to: "/messages",
          label: "Tin nhắn",
          Icon: MessageCircle,
          count: unread,
          what: "cuộc trò chuyện chưa đọc",
        },
        { to: "/profile", label: "Tôi", Icon: UserRound, count: 0, what: "" },
      ].map(({ to, label, Icon, count, what }) => (
        <NavLink
          key={label}
          className={({ isActive }) =>
            `${cx.navItem} ${isActive ? cx.navActive : ""}`
          }
          to={to}
          aria-label={count ? `${label}, ${count} ${what}` : undefined}
        >
          <span className={cx.navIcon}>
            <Icon size={21} strokeWidth={1.6} />
            {count > 0 && (
              <span className={cx.navBadge} aria-hidden="true">
                {badgeText(count)}
              </span>
            )}
          </span>
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
  // Conversations use the whole small screen; each has its own back button.
  const fullChat =
    (assistants && location.pathname !== "/assistants") ||
    location.pathname.startsWith("/chat/");
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
            aria-label="MoodPrint — Trợ lý"
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
              <Link to="/assistants" aria-label="MoodPrint — Trợ lý">
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
          <OfflineBanner />
          <SessionNotices />
          <Motion motionKey={location.pathname}>
            <Routes>
              {session.staff && (
                <Route path="/admin/reports" element={<Moderation />} />
              )}
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
          <Link to="/assistants" aria-label="MoodPrint — Trợ lý">
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
        <ConversationHistory />
        <ConnectBridge />
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
  const [historyOpen, setHistoryOpen] = useState(false);
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
        <button className="icon-button history-mobile-button" aria-label="Mở lịch sử hội thoại" onClick={() => setHistoryOpen(true)}><MessageCircle size={20} /></button>
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
      {historyOpen ? <Dialog title="Lịch sử hội thoại" onClose={() => setHistoryOpen(false)}><ConversationHistory onSelect={() => setHistoryOpen(false)} /></Dialog> : null}
      <ConversationBody bot={bot} />

    </div>
  );
}

function ConversationBody({ bot }: { bot: BotPublicDTO }) {
  const { api, session, receive } = useSession();
  const { preferences, loading: preferencesLoading, error: preferencesError, reload: reloadPreferences, refreshHistory } = useAIData();
  const [searchParams, setSearchParams] = useSearchParams();
  const selectedId = searchParams.get("conversation");
  const [conversation, setConversation] = useState<SavedConversation>();
  const current = useRef<SavedConversation | undefined>(undefined);
  const [olderBusy, setOlderBusy] = useState(false), [manageBusy, setManageBusy] = useState(false), [deleteOpen, setDeleteOpen] = useState(false);
  const [renameOpen, setRenameOpen] = useState(false), [renameText, setRenameText] = useState(""), [renameError, setRenameError] = useState<unknown>();
  const [notice, setNotice] = useState("");
  const [pendingProposals, setPendingProposals] = useState(0), [proposalRevision, setProposalRevision] = useState(0);
  const allowed = session.features.ai;
  const historyWritable = !conversation?.persistent || !!(preferences?.historyEnabled && preferences.historyAvailable);
  const canSend = allowed && historyWritable && !!preferences && !preferencesError;
  const [draft, setDraft] = useState(""),
    [error, setError] = useState<unknown>();
  const [loading, setLoading] = useState(true),
    [busy, setBusy] = useState(false);
  const [ready, setReady] = useState(false);
  const [run, setRun] = useState<{ id: string; version: number }>();
  const [revision, setRevision] = useState(0);
  const loadedRevision = useRef(0);
  const loadedSelection = useRef<string | undefined>(undefined);
  const [atBottom, setAtBottom] = useState(true);
  const log = useRef<HTMLDivElement>(null),
    lifetime = useRef<AbortController | null>(null);
  const intent = useRef<{ text: string; scopeKey: string; clientMessageId: string } | null>(null);
  const composer = useRef<HTMLTextAreaElement>(null);
  const [draftNotice, setDraftNotice] = useState("");
  const submittedText = useRef<string | undefined>(undefined);
  const [shareMood, setShareMood] = useState(false);
  const [moodFrom, setMoodFrom] = useState("");
  const [moodTo, setMoodTo] = useState("");
  const [lastMoodRange, setLastMoodRange] = useState<{
    conversationId: string; fromDate: string; toDate: string;
  }>();
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
  const update = useCallback((value: SavedConversation) => {
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
          const stored = await api.request<SavedConversation>(
            `/ai/conversations/${before.conversationId}`,
            { signal },
          );
          if (!signal.aborted) {
            update(stored);
            setReady(true);
            refreshHistory();
            setProposalRevision((value) => value + 1);
          }
        }
      } catch (reason) {
        if (!signal.aborted) {
          setError(reason);
          setReady(false);
          if (reason instanceof ApiError && reason.code === "RUN_FAILED") {
            // Restore only a confirmed terminal failure. A transport interruption
            // can still complete on the server and must be reconciled by reload.
            setDraft(value => value || submittedText.current || "");
          }
        }
      } finally {
        if (!signal.aborted) {
          setRun(undefined);
          setBusy(false);
        }
      }
    },
    [api, update, refreshHistory],
  );
  useEffect(() => () => lifetime.current?.abort(), []);
  useEffect(() => {
    // A newly created thread receives a URL without interrupting its active stream.
    if (selectedId && selectedId === current.current?.conversationId && loadedRevision.current === revision) return;
    // A fresh login must wait for the saved-history preference before selecting
    // the latest thread. Otherwise the first render silently skips saved threads.
    if (!selectedId && preferencesLoading) return;
    loadedRevision.current = revision;
    lifetime.current?.abort();
    const controller = new AbortController();
    lifetime.current = controller;
    setLoading(true); setReady(false); setBusy(false); setRun(undefined); setError(undefined); setNotice("");
    current.current = undefined; setConversation(undefined);
    const selection = `${bot.botId}/${selectedId || searchParams.get("new") || "latest"}`;
    if (loadedSelection.current !== selection) { intent.current = null; setDraft(""); setShareMood(false); }
    loadedSelection.current = selection;
    async function open() {
      // Explicit selection is authoritative; otherwise resume the latest temporary
      // or saved thread for this assistant. No chat content enters browser storage.
      let id = selectedId;
      if (!id && !searchParams.has("new")) {
        const headers = await api.request<SavedConversationHeader[]>(`/ai/conversations?limit=30&botId=${bot.botId}`, { signal: controller.signal });
        id = headers.find(value => value.botId === bot.botId && (!value.persistent || preferences?.historyEnabled))?.conversationId || null;
      }
      if (controller.signal.aborted) return;
      if (!id) { setReady(true); return; }
      const value = await api.request<SavedConversation>(`/ai/conversations/${encodeURIComponent(id)}`, { signal: controller.signal });
      if (controller.signal.aborted) return;
      if (value.botId !== bot.botId) throw new ApiError(409, "CONVERSATION_BOT_MISMATCH", "Hội thoại thuộc một trợ lý khác. Chọn lại hội thoại trong lịch sử.");
      update(value); setReady(true); setAtBottom(true);
      if (value.activeRunId && allowed) void stream(value.activeRunId, value.activeRunVersion || 1, `/api/v1/ai/runs/${value.activeRunId}/events`, controller.signal);
    }
    void open().catch(reason => { if (!controller.signal.aborted) setError(reason); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    // Lifetime is aborted above on a real selection and on unmount. URL updates
    // for the current thread must leave its in-flight request running.
  }, [api, bot.botId, selectedId, searchParams.get("new"), revision, stream, update, preferencesLoading, preferences?.historyEnabled]);
  useEffect(() => {
    if (!session.consents.AI.enabled) {
      setPendingProposals(0);
      return;
    }
    const controller = new AbortController();
    void api
      .request<{ status: string; expiresAt: string }[]>("/proposals", { signal: controller.signal })
      .then((items) => {
        if (!controller.signal.aborted)
          setPendingProposals(items.filter((item) => item.status === "pending" && new Date(item.expiresAt).getTime() > Date.now()).length);
      })
      .catch(() => {
        // The count is a convenience link; the memory page reports real errors.
        if (!controller.signal.aborted) setPendingProposals(0);
      });
    return () => controller.abort();
  }, [api, proposalRevision, conversation?.conversationId, session.consents.AI.enabled, session.consents.MEM.enabled]);
  useEffect(() => {
    if (atBottom && log.current)
      log.current.scrollTop = log.current.scrollHeight;
  }, [conversation?.messages.length, busy, atBottom]);
  async function send(value = draft) {
    const text = value.trim();
    if (
      !text ||
      !canSend ||
      preferencesLoading ||
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
    let grantedSession: SessionView | undefined;
    try {
      if (!session.consents.AI.enabled) {
        // Sending is the explicit processing choice. No private text is sent
        // until the server has recorded the consent decision.
        grantedSession = await api.request<SessionView>("/consents/AI", {
          method: "PUT",
          body: { enabled: true, expectedVersion: session.consents.AI.version,
                  policyVersion: "v1" } satisfies ConsentInput,
          signal,
        });
      }
      let thread = current.current;
      if (!thread) {
        const created = await api.request<SavedConversationHeader>(
          "/ai/conversations",
          {
            method: "POST",
            body: { botId: bot.botId, persistent: !!(preferences?.historyEnabled && preferences.historyAvailable) },
            signal,
          },
        );
        thread = {
          ...created,
          messages: [],
          hasMoreMessages: false,
          activeRunId: null,
          activeRunVersion: null,
        };
        if (signal.aborted) return;
        update(thread);
        setSearchParams({ conversation: thread.conversationId }, { replace: true });
        refreshHistory();
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
      if (grantedSession) receive(grantedSession);
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
      submittedText.current = text;
      if (moodScope) setLastMoodRange({ conversationId: thread.conversationId, ...moodScope });
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
      if (grantedSession) receive(grantedSession);
      if (!signal.aborted) setError(reason);
    } finally {
      if (!signal.aborted) setBusy(false);
    }
  }
  /** A suggestion only edits the draft; sending stays an explicit choice. */
  function insertStarter(text: string) {
    const field = composer.current;
    const start = field?.selectionStart ?? draft.length;
    const end = field?.selectionEnd ?? draft.length;
    const before = draft.slice(0, start), after = draft.slice(end);
    const head = before && !/\s$/.test(before) ? `${before} ${text}` : `${before}${text}`;
    const next = head + (after && !/^\s/.test(after) ? ` ${after}` : after);
    if (next.length > 500) {
      setDraftNotice("Gợi ý này sẽ làm tin nhắn dài hơn 500 ký tự. Hãy rút gọn trước khi thêm.");
      return;
    }
    setDraft(next);
    setDraftNotice("Đã thêm gợi ý vào ô nhắn.");
    requestAnimationFrame(() => {
      field?.focus();
      field?.setSelectionRange(head.length, head.length);
    });
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
  function newConversation() {
    lifetime.current?.abort();
    lifetime.current = new AbortController();
    current.current = undefined; setConversation(undefined); setDraft(""); setError(undefined); setNotice("");
    setReady(true); setLoading(false); setBusy(false); setRun(undefined); intent.current = null; setShareMood(false); setLastMoodRange(undefined);
    // An explicit new marker prevents latest-thread auto-resume. Record it now:
    // the router applies the URL in a transition, and its effect must not wipe a
    // draft typed after this click.
    const marker = crypto.randomUUID();
    loadedSelection.current = `${bot.botId}/${marker}`;
    setSearchParams({ new: marker });
  }
  async function olderMessages() {
    const thread = current.current;
    if (!thread || olderBusy || !thread.messages.length) return;
    const signal = lifetime.current?.signal;
    setOlderBusy(true); setError(undefined); setAtBottom(false);
    const beforeHeight = log.current?.scrollHeight || 0;
    const beforeTop = log.current?.scrollTop || 0;
    try {
      const page = await api.request<SavedConversation>(`/ai/conversations/${thread.conversationId}?limit=50&before=${encodeURIComponent(thread.messages[0].id)}`, { signal });
      if (signal?.aborted || current.current?.conversationId !== thread.conversationId) return;
      const latest = current.current;
      update({ ...latest, hasMoreMessages: page.hasMoreMessages, messages: [...page.messages.filter(item => !latest.messages.some(old => old.id === item.id)), ...latest.messages] });
      requestAnimationFrame(() => { if (log.current) log.current.scrollTop = beforeTop + log.current.scrollHeight - beforeHeight; });
    } catch (reason) { if (!signal?.aborted) setError(reason); }
    finally { setOlderBusy(false); }
  }
  async function rename() {
    const thread = current.current;
    const title = renameText.trim();
    if (!thread || manageBusy || !title) return;
    setManageBusy(true); setRenameError(undefined);
    try {
      const header = await api.request<SavedConversationHeader>(`/ai/conversations/${thread.conversationId}`, { method: "PATCH", body: { title } });
      if (current.current?.conversationId === thread.conversationId) update({ ...current.current, title: header.title });
      setRenameOpen(false); refreshHistory(); setNotice("Đã đổi tên hội thoại.");
    } catch (reason) { setRenameError(reason); }
    finally { setManageBusy(false); }
  }
  async function manage(deleting: boolean) {
    const thread = current.current;
    if (!thread || manageBusy) return;
    setManageBusy(true); setError(undefined);
    try {
      if (deleting) {
        await api.request(`/ai/conversations/${thread.conversationId}`, { method: "DELETE" });
        setDeleteOpen(false); newConversation(); refreshHistory(); setNotice("Đã xóa hội thoại.");
      } else {
        const exported = await api.request<unknown>(`/ai/conversations/${thread.conversationId}/export`);
        downloadConversation(exported, thread.conversationId);
      }
    } catch (reason) { setError(reason); }
    finally { setManageBusy(false); }
  }
  let conversationLabel = "Hội thoại tạm thời · không lưu vào lịch sử";
  if (conversation?.persistent) conversationLabel = "Hội thoại đã lưu";
  else if (!conversation && preferences?.historyEnabled && preferences.historyAvailable)
    conversationLabel = "Hội thoại mới sẽ được lưu";

  let historyAction = "Bật lưu lịch sử trong cài đặt";
  if (preferencesLoading) historyAction = "Đang kiểm tra lịch sử…";
  else if (!preferences) historyAction = "Kiểm tra quyền lưu lịch sử";
  else if (!preferences.historyAvailable) historyAction = "Lưu lịch sử chưa sẵn sàng";
  else if (preferences.historyEnabled) historyAction = `Lưu tối đa ${preferences.retentionDays} ngày`;

  let readOnlyMessage = "Đang kiểm tra lựa chọn dữ liệu AI…";
  if (!session.features.ai) readOnlyMessage = aiServiceMessage(session.features);
  else if (!preferences && !preferencesLoading)
    readOnlyMessage = "Chưa tải được lựa chọn dữ liệu AI. Hãy thử tải lại trước khi nhắn.";
  else if (preferences && !historyWritable)
    readOnlyMessage = preferences.historyAvailable
      ? "Bạn đang tắt lưu lịch sử. Bật lại trong cài đặt để tiếp tục hội thoại đã lưu, hoặc mở hội thoại tạm thời mới."
      : "Lưu lịch sử hiện chưa sẵn sàng. Hội thoại đã lưu chỉ để xem; bạn có thể mở hội thoại tạm thời mới.";
  return (
    <>
      <div className="chat-history-toolbar">
        <div><span>{conversationLabel}</span>
        <Link to="/settings">{historyAction}</Link></div>
        <div className={cx.actions}>
          <Button variant="text" onClick={newConversation}>Cuộc trò chuyện mới</Button>
          {conversation?.persistent ? <><Button variant="text" disabled={manageBusy} onClick={() => { setRenameText(conversation.title || ""); setRenameError(undefined); setRenameOpen(true); }}>Đổi tên</Button><Button variant="text" disabled={manageBusy} onClick={() => void manage(false)}>Xuất hội thoại</Button><Button variant="text" disabled={manageBusy} onClick={() => setDeleteOpen(true)}>Xóa hội thoại</Button></> : null}
        </div>
      </div>
      {renameOpen ? <Dialog title="Đổi tên hội thoại" onClose={() => !manageBusy && setRenameOpen(false)}><form className="conversation-rename" onSubmit={(event) => { event.preventDefault(); void rename(); }}><label htmlFor="conversation-title">Tên hội thoại</label><input id="conversation-title" value={renameText} maxLength={100} required onChange={(event) => setRenameText(event.target.value)} /><p>Tên chỉ hiển thị cho bạn và không được gửi tới trợ lý.</p><ErrorNotice error={renameError} /><div className={cx.actions}><Button type="button" variant="secondary" disabled={manageBusy} onClick={() => setRenameOpen(false)}>Hủy</Button><Button type="submit" disabled={manageBusy || !renameText.trim()}>Lưu tên</Button></div></form></Dialog> : null}
      {deleteOpen ? <Dialog title="Xóa hội thoại này?" destructive onClose={() => !manageBusy && setDeleteOpen(false)}><p>Hội thoại và các tin nhắn trong đó sẽ bị xóa. Thao tác này không thể hoàn tác.</p><ErrorNotice error={error} /><div className={cx.actions}><Button variant="secondary" data-cancel disabled={manageBusy} onClick={() => setDeleteOpen(false)}>Giữ hội thoại</Button><Button disabled={manageBusy} onClick={() => void manage(true)}>Xác nhận xóa hội thoại</Button></div></Dialog> : null}
      <div
        className="conversation-log"
        ref={log}
        role="log"
        tabIndex={0}
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
          <h2>Một chút thời gian với {bot.name}</h2>
          <p>{bot.description}</p>
          {!conversation?.messages.length && <AssistantGuide botId={bot.botId} />}
          <small>
            <LockKeyhole size={11} /> Không chia sẻ với bạn kết nối
          </small>
        </div>
        {notice ? <p role="status">{notice}</p> : null}
        {preferencesError ? <><p>Lựa chọn dữ liệu chưa xác minh được; cuộc trò chuyện mới chỉ là tạm thời.</p><ErrorNotice error={preferencesError} retry={reloadPreferences} /></> : null}
        {loading ? <p role="status">Đang mở cuộc trò chuyện…</p> : null}
        {conversation?.hasMoreMessages ? <Button variant="secondary" disabled={olderBusy || loading} onClick={() => void olderMessages()}>{olderBusy ? "Đang tải tin nhắn…" : "Tải tin nhắn cũ hơn"}</Button> : null}
        {conversation?.messages.map((message) => (
          <div
            key={message.id}
            className={`message-row ${message.actor === "self" ? "from-self" : "from-bot"}`}
          >
            <div className="message-content">
              <div className="chat-bubble">
                {message.actor === "bot" ? (
                  <Suspense fallback={<p>{message.text}</p>}>
                    <MessageMarkdown text={message.text} />
                  </Suspense>
                ) : <p>{message.text}</p>}
              </div>
              {message.actor === "self" && message.status && ["failed", "interrupted", "cancelled"].includes(message.status) ? <small className="message-turn-status" role="status">{message.status === "interrupted" ? "Phản hồi bị gián đoạn; lượt này không tự chạy lại." : message.status === "cancelled" ? "Đã dừng phản hồi." : "Phản hồi chưa hoàn tất."}</small> : null}
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
        {pendingProposals > 0 && !busy ? (
          <p className="chat-proposal-notice" role="status">
            Có {pendingProposals} đề xuất đang chờ bạn duyệt. Chưa có gì được lưu cho đến khi bạn duyệt.{" "}
            <Link to="/memory">Xem đề xuất</Link>
          </p>
        ) : null}
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
      {session.features.aiStatus === "test_provider" ? <p className={cx.footnote} role="note">Môi trường kiểm thử · phản hồi từ model giả, không phải OpenAI.</p> : null}
      {!canSend ? <div className="chat-readonly" role="status"><p>{readOnlyMessage}</p>{allowed && preferences && !historyWritable && preferences.historyAvailable ? <Link to="/settings">Mở cài đặt lưu lịch sử</Link> : null}</div> : <div className="chat-bottom">
        <p className={cx.footnote}>Tin nhắn chỉ được gửi cho nhà cung cấp AI khi bạn chọn Gửi. Lịch sử máy chủ và ghi nhớ lâu dài là các lựa chọn riêng.</p>
        {!session.consents.AI.enabled ? <p role="note">Khi chọn Gửi, bạn đồng ý để dịch vụ AI xử lý tin nhắn này. Bạn có thể rút quyền trong Quyền riêng tư.</p> : null}
        <details><summary>Lưu lịch sử trò chuyện</summary><AIDataControls historyOnly /></details>
        {bot.botId === "nhip" ? (
          <>
          {lastMoodRange && lastMoodRange.conversationId === conversation?.conversationId && !shareMood ? (
            <Button variant="secondary" disabled={busy || loading || !ready}
              onClick={() => {
                setMoodFrom(lastMoodRange.fromDate);
                setMoodTo(lastMoodRange.toDate);
                setShareMood(true);
              }}>
              Chia sẻ lại {lastMoodRange.fromDate} – {lastMoodRange.toDate} cho lượt tiếp
            </Button>
          ) : null}
          {shareMood ? <p role="status">Đã chọn chia sẻ {moodFrom || "…"} – {moodTo || "…"}. Nhịp chỉ đọc khi bạn gửi tin nhắn; bạn có thể bỏ chọn trước khi gửi.</p> : null}
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
          </>
        ) : null}
        <VoiceRecorder onUse={setDraft} />
        <div className="quick-replies" aria-label="Gợi ý trò chuyện">
          {bot.starters.map((text) => (
            <button
              type="button"
              key={text}
              disabled={loading || !ready}
              onClick={() => insertStarter(text)}
            >
              {text}
            </button>
          ))}
        </div>
        {draftNotice ? <p className={cx.footnote} role="status">{draftNotice}</p> : null}
        <QuotaHint />
        <form
          className="bot-composer"
          onSubmit={(event) => {
            event.preventDefault();
            void send();
          }}
        >
          <textarea
            aria-label={`Tin nhắn cho ${bot.name}`}
            ref={composer}
            value={draft}
            maxLength={500}
            rows={1}
            onChange={(event) => { setDraft(event.target.value); setDraftNotice(""); }}
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
            disabled={!draft.trim() || busy || loading || !ready || moodInvalid || preferencesLoading}
            aria-label="Gửi tin cho AI"
          >
            <Send size={19} />
          </button>
        </form>
      </div>}
    </>
  );
}

const consentLabels: Record<ConsentPurpose, string> = {
  AI: "trò chuyện AI",
  MEM: "ghi nhớ đã duyệt",
  MATCH: "tìm bạn",
  VOICE: "giọng nói",
};
/** What withdrawing each permission does, matching backend/app/modules/consent/routes.py. */
const consentWithdrawal: Record<ConsentPurpose, string> = {
  AI: "Khi tắt: dừng ngay các lượt AI đang chạy, hủy đề xuất ghi nhớ chưa duyệt và xóa chỉ mục tìm kiếm ghi nhớ. Vẫn giữ: lịch sử trò chuyện đã lưu (chỉ đọc) và các ghi nhớ bạn đã duyệt — bạn có thể xuất hoặc xóa chúng bên dưới.",
  MEM: "Khi tắt: trợ lý ngừng nhắc lại ghi nhớ, hủy đề xuất chưa duyệt và xóa chỉ mục tìm kiếm. Vẫn giữ: các ghi nhớ đã duyệt để bạn xem, sửa hoặc xóa.",
  MATCH:
    "Khi tắt: đóng mọi cuộc trò chuyện với người thật, hủy lời mời đang chờ, và hồ sơ kết nối bị ẩn. Bật lại không tự chia sẻ lại hồ sơ — bạn cần xem lại và xuất bản lại. Những người đang trò chuyện hoặc có lời mời chờ với bạn sẽ không được gợi ý lại cho nhau trong 30 ngày. Mọi hoạt động chung đang diễn ra cũng dừng lại.",
  VOICE: "Khi tắt: không thể ghi âm nữa. Âm thanh không bao giờ được lưu lại.",
};
function Settings() {
  const { api, session, receive, logout } = useSession();
  const published = useResource<{ state: string; profileVersion: number } | null>("/profiles/published/current");
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
            enabled: false,
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
  async function unpublish() {
    if (!published.data || busy) return;
    setBusy("unpublish");
    setError(undefined);
    try {
      await api.request("/profiles/published/current", {
        method: "DELETE",
        body: { expectedVersion: published.data.profileVersion },
      });
      published.refresh();
    } catch (reason) { setError(reason); }
    finally { setBusy(undefined); }
  }
  return (
    <div className={cx.reading}>
      <h1 tabIndex={-1}>Quyền riêng tư</h1>
      <p className={cx.lede}>Bạn chọn nội dung được lưu, dùng để ghi nhớ hoặc chia sẻ với người khác.</p>
      <ErrorNotice error={error} />
      <section className="real-section">
        <h2>AI và ghi nhớ</h2>
        <p>Trợ lý xử lý tin nhắn khi bạn chọn Gửi. Ghi nhớ chỉ được lưu sau khi bạn duyệt từng đề xuất.</p>
        <Link to="/memory">Xem và quản lý ghi nhớ đã duyệt</Link>
        <AIDataControls />
      </section>
      <section className="real-section">
        <h2>Kết nối và khám phá</h2>
        {published.loading ? <p role="status">Đang kiểm tra hồ sơ kết nối…</p> : published.error ? null :
          <p role="status">{published.data?.state === "live" ? "Hồ sơ đang chia sẻ" : "Hồ sơ chưa hiển thị trong gợi ý"}</p>}
        <ErrorNotice error={published.error} retry={published.refresh} />
        <p>Chỉ thẻ kết nối bạn xem trước và xuất bản mới hiển thị với người khác. Nhật ký, cảm xúc và hội thoại AI không dùng để gợi ý.</p>
        <Link to="/connect?tab=profile">Xem hoặc sửa hồ sơ kết nối</Link>
        {published.data?.state === "live" ? <Button variant="secondary" disabled={!!busy} onClick={() => void unpublish()}>{busy === "unpublish" ? "Đang ngừng chia sẻ…" : "Ngừng chia sẻ hồ sơ"}</Button> : null}
      </section>
      <details className="real-section">
        <summary>Rút quyền xử lý đã cấp</summary>
        <p>Các lựa chọn đã rút vẫn được ghi nhận. Bạn có thể tiếp tục dùng tính năng sau khi chọn hành động có thông báo phù hợp.</p>
        {(["AI", "MEM", "MATCH", "VOICE"] as ConsentPurpose[]).filter(purpose => session.consents[purpose].enabled).map(purpose =>
          <div key={purpose}>
            <p>{consentWithdrawal[purpose]}</p>
            <Button variant="secondary" disabled={!!busy} onClick={() => void change(purpose)}>{busy === purpose ? "Đang cập nhật…" : `Rút quyền ${consentLabels[purpose]}`}</Button>
          </div>
        )}
      </details>
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
