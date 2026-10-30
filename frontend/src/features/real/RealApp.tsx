import {
  createContext,
  Fragment,
  lazy,
  Suspense,
  useCallback,
  useContext,
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
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
  ArrowUp,
  ArrowUpRight,
  Copy,
  Info,
  LockKeyhole,
  MessageCircle,
  NotebookPen,
  Pause,
  Search,
  Sparkles,
  UserRound,
  Users,
} from "lucide-react";
import {
  Brand,
  Button,
  cx,
  Dialog,
  StatePanel,
} from "../../components/UI";
import { BotAvatar } from "../../companions/Avatar";
import { botById, type BotId } from "../../companions/registry";
import { ApiClient, ApiError, errorMessage } from "../../api/client";
import { consumeAIEvents, validCards } from "../../api/stream";
import { AdultEligibility, EligibilityGate } from "./Eligibility";
import { AuthScreen } from "./Auth";
import type { AuthCallback } from "../auth/callback";
import { validateSession } from "../../api/session";
import { ErrorNotice } from "../../components/ErrorNotice";
import { GuestExpired } from "../guest/GuestExpired";
import { GuestStatus } from "../guest/GuestStatus";
import { useGuestLifecycle } from "../guest/useGuestLifecycle";
import { clearTourBlockers, useTourActivity, useTourBlocker } from "../onboarding/tourActivity";
import type {
  AIRunAccepted,
  BotPublicDTO,
  SessionView,
  StartRunInput,
  VersionInput,
} from "../../api/contracts";
import "./real.css";
import "./agent-chat.css";
import { Discovery } from "./social/Discovery";
import { OfflineBanner, useOnline } from "./OfflineBanner";
import {
  SESSION_GRACE_MS,
  graceExpired,
  rememberGraceStart,
  revalidateSession,
} from "../../api/sessionPolicy";
import { AssistantGuide } from "./AssistantGuide";
import { aiServiceMessage } from "./aiStatus";
import { HumanChat } from "./social/HumanChat";
import { HumanMessages } from "./social/HumanMessages";
import { badgeText, useSocialSummary } from "./social/useSocialSummary";
import { Moderation } from "./admin/Moderation";
import { ApprovedMemories } from "./Memory";
import { Moods } from "./Mood";
import { VoiceRecorder } from "./Voice";
import { AccountActions, AccountDeletionComplete } from "./AccountActions";
import { focusRouteHeading, useRouteFocus } from "./useRouteFocus";
import { AIActivityStatus } from "./AIActivityStatus";
import { ConversationInfo, useInfoPanelMounted } from "./ConversationInfo";
import { insertAtSelection } from "./draftInsert";
import { createMessageDateFormatter } from "./messageDates";
import { deriveAIActivity, type AIActivityPhase } from "./aiActivityView";
import { AIDataProvider, ConversationHistory, useAIData, type SavedConversation, type SavedConversationHeader } from "./AIData";

const MessageMarkdown = lazy(() => import("./MessageMarkdown"));
const FeedbackPage = lazy(() => import("../feedback/FeedbackPage"));
const FeedbackAdmin = lazy(() => import("./admin/Feedback"));
const TourController = lazy(() => import("../onboarding/TourController"));
const JournalPage = lazy(() => import("./journal/JournalPage").then(module => ({ default: module.JournalPage })));
const JournalCalendar = lazy(() => import("./journal/JournalCalendar").then(module => ({ default: module.JournalCalendar })));
const JournalTimeline = lazy(() => import("./journal/JournalTimeline").then(module => ({ default: module.JournalTimeline })));
const JournalEntryDetail = lazy(() => import("./journal/JournalEntryDetail").then(module => ({ default: module.JournalEntryDetail })));

type SessionContextValue = {
  api: ApiClient;
  session: SessionView;
  receive: (session: SessionView) => void;
  logout: () => Promise<void>;
  paused: boolean;
  link: "ready" | "degraded" | "recovered";
  retrySession: () => void;
};
const SessionContext = createContext<SessionContextValue | null>(null);
export function useSession() {
  const context = useContext(SessionContext);
  if (!context) throw new Error("Session is required");
  return context;
}

export { ErrorNotice };

export function useResource<T>(path: string, enabled = true) {
  const { api, paused } = useSession();
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
    if (paused) {
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
  }, [api, path, revision, enabled, paused]);
  // A failed read retries by itself when the browser comes back online.
  useEffect(() => {
    if (!error || !enabled || paused) return;
    window.addEventListener("online", refresh);
    return () => window.removeEventListener("online", refresh);
  }, [error, enabled, refresh, paused]);
  return { data, setData, error, loading, refresh };
}

type GuestContextValue = {
  remainingMs: number;
  end: () => void;
  register: () => void;
} | null;
const GuestContext = createContext<GuestContextValue>(null);
export function useGuest() {
  return useContext(GuestContext);
}

function authMode(): "login" | "signup" {
  return /[?&]mode=signup\b/.test(window.location.hash) ? "signup" : "login";
}

function SessionRoot({ api, callback }: { api: ApiClient; callback: AuthCallback }) {
  const entryLocation = useLocation();
  const [session, setSession] = useState<SessionView | null>();
  const [bootstrapError, setBootstrapError] = useState<unknown>();
  const [unavailable, setUnavailable] = useState(false);
  const [checking, setChecking] = useState(false);
  const [link, setLink] = useState<"ready" | "degraded" | "recovered">("ready");
  // Set when a guest trial ends so private state is replaced by a content-free screen.
  const [ended, setEnded] = useState<"expired" | "ended" | null>(null);
  const knewGuest = useRef(false);
  const sessionRef = useRef(session);
  const graceAnchor = useRef<number | null>(null);
  const graceTimer = useRef<number | undefined>(undefined);
  const generation = useRef(0);
  const inflight = useRef<Promise<void> | null>(null);
  const autoUsed = useRef(false);
  const probeAbort = useRef<AbortController | null>(null);
  const debounce = useRef<number | undefined>(undefined);
  sessionRef.current = session;
  useEffect(() => {
    knewGuest.current = session?.accountKind === "guest";
  }, [session]);
  useEffect(() => {
    if (link !== "recovered") return;
    const timer = window.setTimeout(() => setLink("ready"), 4000);
    return () => window.clearTimeout(timer);
  }, [link]);
  const clearGrace = useCallback(() => {
    window.clearTimeout(graceTimer.current);
    graceTimer.current = undefined;
    graceAnchor.current = null;
    api.setPrivateHold(null);
  }, [api]);
  const dropPrivate = useCallback(() => {
    generation.current += 1;
    probeAbort.current?.abort();
    clearGrace();
    api.reset();
  }, [api, clearGrace]);
  const receive = useCallback(
    (value: SessionView) => {
      const valid = validateSession(value);
      api.setCsrf(valid.csrfToken);
      setBootstrapError(undefined);
      setUnavailable(false);
      setSession(valid);
    },
    [api],
  );
  const receiveRef = useRef(receive);
  receiveRef.current = receive;
  const lose = useCallback(
    (failure?: ApiError) => {
      const guestEnded = failure?.code === "GUEST_EXPIRED" || knewGuest.current;
      dropPrivate();
      autoUsed.current = false;
      setLink("ready");
      setUnavailable(false);
      setBootstrapError(undefined);
      setChecking(false);
      if (guestEnded) {
        try {
          new BroadcastChannel("moodprint-guest").postMessage({ type: "expired" });
        } catch {
          /* the other tab reaches the same server verdict on its own read */
        }
        setEnded("expired");
      }
      setSession(null);
    },
    [dropPrivate],
  );
  const loseRef = useRef(lose);
  loseRef.current = lose;
  const block = useCallback(
    (failure: unknown) => {
      dropPrivate();
      autoUsed.current = true;
      setLink("ready");
      setUnavailable(false);
      setChecking(false);
      setSession(null);
      setBootstrapError(failure);
    },
    [dropPrivate],
  );
  const expireGrace = useCallback(() => {
    if (graceAnchor.current === null) return;
    dropPrivate();
    autoUsed.current = true;
    setLink("ready");
    setBootstrapError(undefined);
    setChecking(false);
    setSession(null);
    setUnavailable(true);
  }, [dropPrivate]);
  const expireGraceRef = useRef(expireGrace);
  expireGraceRef.current = expireGrace;
  const armGrace = useCallback(() => {
    const now = Date.now();
    graceAnchor.current = rememberGraceStart(graceAnchor.current, now);
    api.setPrivateHold(() => graceAnchor.current !== null);
    if (graceTimer.current === undefined) {
      const remaining = SESSION_GRACE_MS - (now - graceAnchor.current);
      graceTimer.current = window.setTimeout(
        () => expireGraceRef.current(),
        Math.max(0, remaining),
      );
    }
    setLink("degraded");
    if (graceExpired(graceAnchor.current, Date.now())) expireGraceRef.current();
  }, [api]);
  const scheduleRef = useRef<(kind: "auto" | "manual") => Promise<void>>(async () => {});
  scheduleRef.current = (kind) => {
    if (kind === "auto" && autoUsed.current) return inflight.current ?? Promise.resolve();
    if (inflight.current) return inflight.current;
    const gen = generation.current;
    const epoch = api.epoch;
    const controller = new AbortController();
    probeAbort.current = controller;
    let lastFailure: unknown;
    const run = revalidateSession({
      signal: controller.signal,
      isCurrent: () => generation.current === gen && api.epoch === epoch && !controller.signal.aborted,
      request: async (timeoutMs, signal) => {
        const value = await api.request<SessionView>("/session", { signal, timeoutMs });
        if (generation.current !== gen || api.epoch !== epoch || signal.aborted)
          throw new DOMException("Aborted", "AbortError");
        receiveRef.current(value);
      },
      onTransient: (reason) => {
        lastFailure = reason;
        if (sessionRef.current) armGrace();
      },
      onSuccess: () => {
        const degraded = graceAnchor.current !== null;
        clearGrace();
        autoUsed.current = false;
        setChecking(false);
        setUnavailable(false);
        setBootstrapError(undefined);
        setLink(degraded ? "recovered" : "ready");
      },
      onUnauthorized: (reason) => loseRef.current(reason),
      onForbidden: (reason) => block(reason),
      onInvalid: (reason) => block(reason),
    }).then((status) => {
      if (generation.current !== gen || api.epoch !== epoch) return;
      if (status === "failed") {
        autoUsed.current = true;
        if (!sessionRef.current) {
          setBootstrapError(
            lastFailure ??
              new ApiError(
                503,
                "DATABASE_UNAVAILABLE",
                "MoodPrint chưa thể kết nối. Bạn có thể thử lại sau ít phút.",
                null,
                true,
              ),
          );
        }
      }
    });
    inflight.current = run;
    void run.finally(() => {
      if (inflight.current === run) inflight.current = null;
    });
    return run;
  };
  useEffect(() => {
    api.onUnauthorized = (failure) => loseRef.current(failure);
    const onAuto = () => {
      if (document.visibilityState === "hidden") return;
      window.clearTimeout(debounce.current);
      debounce.current = window.setTimeout(() => void scheduleRef.current("auto"), 100);
    };
    window.addEventListener("focus", onAuto);
    window.addEventListener("online", onAuto);
    document.addEventListener("visibilitychange", onAuto);
    void scheduleRef.current("auto");
    return () => {
      generation.current += 1;
      probeAbort.current?.abort();
      inflight.current = null;
      window.clearTimeout(debounce.current);
      window.clearTimeout(graceTimer.current);
      graceTimer.current = undefined;
      window.removeEventListener("focus", onAuto);
      window.removeEventListener("online", onAuto);
      document.removeEventListener("visibilitychange", onAuto);
      api.setPrivateHold(null);
    };
  }, [api]);
  const retrySession = useCallback(() => {
    setChecking(true);
    if (!unavailable) setBootstrapError(undefined);
    void scheduleRef.current("manual").finally(() => setChecking(false));
  }, [unavailable]);
  const recheck = useCallback(() => void scheduleRef.current("auto"), []);
  async function logout() {
    const wasGuest = session?.accountKind === "guest";
    await api.request<void>("/auth/logout", { method: "POST" });
    dropPrivate();
    autoUsed.current = false;
    setLink("ready");
    setUnavailable(false);
    setBootstrapError(undefined);
    if (wasGuest) setEnded("ended");
    setSession(null);
  }
  function expireGuest(reason: "expired" | "ended") {
    // Abort every in-flight request and drop the private tree before anything can repopulate it.
    dropPrivate();
    autoUsed.current = false;
    setLink("ready");
    setUnavailable(false);
    setBootstrapError(undefined);
    setEnded(reason);
    setSession(null);
  }
  // Only asks the server; the lifecycle hook then aborts, tells the other tabs and ends the UI.
  async function requestEnd() {
    await api.request<void>("/auth/guest/end", { method: "POST", body: {} });
  }
  if (checking && session == null && !unavailable)
    return (
      <main className="real-auth">
        <Brand />
        <p role="status">Đang kiểm tra đăng nhập…</p>
      </main>
    );
  if (bootstrapError && session == null)
    return (
      <main className="real-auth">
        <Brand />
        <h1 tabIndex={-1}>Chưa thể mở MoodPrint</h1>
        <ErrorNotice error={bootstrapError} retry={retrySession} />
      </main>
    );
  if (unavailable)
    return (
      <main className="real-auth">
        <Brand />
        <h1 tabIndex={-1}>MoodPrint chưa thể kết nối</h1>
        <p role="status">Bạn có thể thử lại sau ít phút. Phần đang mở đã được ẩn cho đến khi kết nối lại.</p>
        <Button onClick={retrySession} disabled={checking}>
          {checking ? "Đang thử lại…" : "Thử lại"}
        </Button>
      </main>
    );
  if (session === undefined)
    return (
      <main className="real-auth">
        <Brand />
        <p role="status">Đang kiểm tra đăng nhập…</p>
      </main>
    );
  if (ended && session === null)
    return (
      <GuestExpired
        reason={ended}
        onNewTrial={() => {
          setEnded(null);
          window.location.assign("/");
        }}
        onRegister={() => {
          setEnded(null);
          window.location.hash = "#/login?mode=signup";
        }}
      />
    );
  if (session === null && entryLocation.pathname === "/feedback" && !callback)
    return (
      <main className="real-auth">
        <Brand />
        <h1 tabIndex={-1}>Góp ý cho MoodPrint</h1>
        <p>Bạn cần một lượt dùng thử đang hoạt động hoặc đăng nhập để gửi góp ý.</p>
        <a href="/">Tìm hiểu và dùng thử MoodPrint</a>
        <Link to="/login">Đăng nhập / Đăng ký</Link>
      </main>
    );
  if (session === null || callback?.kind === "recovery")
    return (
      <AuthScreen api={api} receive={receive} callback={callback} initialMode={authMode()} />
    );
  const content = session.eligible ? (
    <AIDataProvider key={session.userId}>
      <Shell />
    </AIDataProvider>
  ) : (
    <EligibilityGate />
  );
  return (
    <SessionContext.Provider value={{ api, session, receive, logout, paused: link === "degraded", link, retrySession }}>
      {session.accountKind === "guest" ? (
        <GuestHost session={session} onExpired={expireGuest} onEnd={requestEnd} onRecheck={recheck}
          onRegisterAfterEnd={() => {
            // expire() already aborted requests, broadcast the end and discarded
            // the private tree. Choose signup explicitly over the terminal screen.
            knewGuest.current = false;
            setEnded(null);
            window.location.hash = "#/login?mode=signup";
          }}>
          {content}
        </GuestHost>
      ) : (
        content
      )}
    </SessionContext.Provider>
  );
}

function GuestHost({
  session,
  onExpired,
  onEnd,
  onRegisterAfterEnd,
  onRecheck,
  children,
}: {
  session: SessionView;
  onExpired: (reason: "expired" | "ended") => void;
  onEnd: () => void | Promise<void>;
  onRegisterAfterEnd: () => void;
  onRecheck: () => void;
  children: ReactNode;
}) {
  const { remainingMs, expire } = useGuestLifecycle({ session, onExpired, onRecheck });
  const [confirm, setConfirm] = useState<"end" | "register" | null>(null);
  const [ending, setEnding] = useState(false);
  const [endError, setEndError] = useState<unknown>();
  return (
    <GuestContext.Provider
      value={{
        remainingMs,
        end: () => { setEndError(undefined); setConfirm("end"); },
        register: () => { setEndError(undefined); setConfirm("register"); },
      }}
    >
      {children}
      {confirm ? (
        <Dialog
          title={confirm === "end" ? "Kết thúc và xóa lượt dùng thử?" : "Tạo tài khoản?"}
          destructive
          onClose={() => !ending && setConfirm(null)}
        >
          <p>
            {confirm === "end"
              ? "Dữ liệu của lượt này sẽ bị xóa và không thể mở lại."
              : "Dữ liệu của lượt dùng thử sẽ không chuyển sang tài khoản mới. Lượt dùng thử hiện tại sẽ kết thúc."}
          </p>
          <ErrorNotice error={endError} />
          <div className={cx.actions}>
            <Button variant="secondary" data-cancel disabled={ending} onClick={() => setConfirm(null)}>
              Giữ lượt dùng thử
            </Button>
            <Button
              variant="danger"
              disabled={ending}
              onClick={async () => {
                if (ending) return;
                const next = confirm;
                setEnding(true);
                setEndError(undefined);
                try {
                  await onEnd();
                  setConfirm(null);
                  expire("ended");
                  if (next === "register") onRegisterAfterEnd();
                } catch (reason) {
                  setEndError(reason);
                } finally { setEnding(false); }
              }}
            >
              {confirm === "end" ? "Kết thúc và xóa" : "Kết thúc và tạo tài khoản"}
            </Button>
          </div>
        </Dialog>
      ) : null}
    </GuestContext.Provider>
  );
}

function GuestBanner() {
  const guest = useGuest();
  const { pathname } = useLocation();
  if (!guest) return null;
  // The personal tab already has the trial-ending action.
  return (
    <GuestStatus
      remainingMs={guest.remainingMs}
      onEnd={pathname === "/profile" ? undefined : guest.end}
    />
  );
}

/** Registered-only explanation. It makes no API call, so a guest never polls or probes social data. */
function GuestLocked() {
  const guest = useGuest();
  return (
    <>
      <h1 tabIndex={-1}>Tìm bạn và nhắn tin</h1>
      <StatePanel title="Tạo tài khoản để tìm bạn và nhắn tin.">
        Tính năng này dành cho người từ 18 tuổi, khi bạn chủ động bật chia sẻ.
      </StatePanel>
      <div className={cx.actions}>
        <Link className={`${cx.button} ${cx.primary}`} to="/assistants">
          Về trợ lý
        </Link>
        <Button variant="secondary" onClick={() => guest?.register()}>
          Tạo tài khoản
        </Button>
      </div>
    </>
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
  const guest = session.accountKind === "guest";
  const remaining = guest
    ? (session.guestQuota?.aiTurnsRemaining ?? null)
    : session.features.aiQuotaRemaining;
  if (remaining == null || remaining > 10) return null;
  if (guest)
    return (
      <p className={cx.footnote} role="status">
        {remaining === 0
          ? "Bạn đã dùng hết lượt trò chuyện của lượt dùng thử."
          : `Lượt dùng thử còn ${remaining} lượt trò chuyện với trợ lý.`}
      </p>
    );
  return (
    <p className={cx.footnote} role="status">
      {remaining === 0
        ? "Bạn đã dùng hết lượt trò chuyện AI hôm nay. Bạn có thể tiếp tục vào ngày mai."
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
        { to: "/self", label: "Nhật ký", Icon: NotebookPen, count: 0, what: "" },
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
        { to: "/profile", label: "Tài khoản", Icon: UserRound, count: 0, what: "" },
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

function ConnectionBanner() {
  const online = useOnline();
  const { link, retrySession } = useSession();
  if (!online || link === "ready") return null;
  const degraded = link === "degraded";
  return (
    <div className="connection-status" role="status" data-testid="connection-status" data-state={link}>
      <p>
        {degraded
          ? "Kết nối đang gián đoạn. MoodPrint đang thử kết nối lại…"
          : "Đã kết nối lại. Bạn có thể tiếp tục."}
      </p>
      {degraded ? (
        <button type="button" onClick={retrySession}>
          Thử lại
        </button>
      ) : null}
    </div>
  );
}

function Shell() {
  const { session } = useSession();
  const [guideOpen, setGuideOpen] = useState(false);
  const activity = useTourActivity();
  useEffect(() => () => clearTourBlockers(), []);
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
    window.scrollTo(0, 0);
  }, [location.pathname]);
  useRouteFocus(location.pathname);
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
          <Navigation />
        </aside>
        <main
          id="main"
          tabIndex={-1}
          className={`${cx.main} me-main ${assistants ? "me-assistants" : "me-page"}`}
        >
          <OfflineBanner />
          <ConnectionBanner />
          <GuestBanner />
          <SessionNotices />
          {guideOpen ? <Suspense fallback={<p role="status">Đang mở hướng dẫn…</p>}><TourController session={session} activity={activity} onClose={() => setGuideOpen(false)} /></Suspense> : null}
          <Routes>
              <Route path="/admin/feedback" element={<Suspense fallback={<p role="status">Đang mở góp ý…</p>}><FeedbackAdmin /></Suspense>} />
              <Route path="/feedback" element={<Suspense fallback={<p role="status">Đang mở góp ý…</p>}><FeedbackPage /></Suspense>} />
              {session.staff && (
                <Route path="/admin/reports" element={<Moderation />} />
              )}
              <Route path="/assistants" element={<Assistants />} />
              <Route path="/assistants/:botId" element={<Assistants />} />
              <Route path="/settings" element={<Navigate replace to="/profile" />} />
              <Route path="/self" element={<Suspense fallback={<p role="status">Đang mở nhật ký…</p>}><JournalPage /></Suspense>} />
              <Route path="/self/calendar" element={<Suspense fallback={<p role="status">Đang mở lịch nhật ký…</p>}><JournalCalendar /></Suspense>} />
              <Route path="/self/memories" element={<Suspense fallback={<p role="status">Đang mở khoảnh khắc…</p>}><JournalTimeline /></Suspense>} />
              <Route path="/self/entry/:id" element={<Suspense fallback={<p role="status">Đang mở khoảnh khắc…</p>}><JournalEntryDetail /></Suspense>} />
              <Route path="/self/daily" element={<Moods />} />
              <Route path="/profile" element={<AccountPage onGuide={() => setGuideOpen(true)} />} />
              <Route path="/memory" element={<ApprovedMemories />} />
              <Route path="/connect" element={session.accountKind === "guest" ? <GuestLocked /> : <Discovery />} />
              <Route path="/messages" element={session.accountKind === "guest" ? <GuestLocked /> : <HumanMessages />} />
              <Route
                path="/chat/:connectionId"
                element={session.accountKind === "guest" ? <GuestLocked /> : <HumanChat key={location.pathname} />}
              />
              <Route path="*" element={<Navigate replace to="/assistants" />} />
          </Routes>
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
          Ghi lại tâm trạng
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
        <label className="bot-search">
          <Search size={18} />
          <input
            aria-label="Tìm trợ lý"
            placeholder="Tìm theo tên hoặc vai trò"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
        </label>
        <div className="roster-section-label">
          <h1>Chọn một trợ lý</h1>
          {search.trim() && bots.length ? <span role="status">{filtered.length} kết quả</span> : null}
        </div>
        {resource.loading ? <p role="status">Đang tải trợ lý…</p> : null}
        <ErrorNotice error={resource.error} retry={resource.refresh} />
        <div className="bot-list" data-tour="assistants-list">
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
              </div>
              <ArrowUpRight size={16} className="roster-arrow" />
            </Link>
          ))}
        </div>
        {!resource.loading && !resource.error && !bots.length ? (
          <p className="search-empty">Chưa có trợ lý nào sẵn sàng. Bạn hãy thử lại sau.</p>
        ) : !resource.loading && !resource.error && !filtered.length ? (
          <div className="search-empty">
            <p>Không có trợ lý nào khớp với “{search.trim()}”.</p>
            <Button variant="text" onClick={() => setSearch("")}>Xóa tìm kiếm</Button>
          </div>
        ) : null}
        <ConversationHistory />
      </section>
      <section
        className="conversation-pane"
        aria-label={
          bot ? `Trò chuyện với ${bot.name}` : "Cuộc trò chuyện"
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
              và kết nối từ những điểm chung.
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
  return (
    <div className="bot-conversation ai-conversation">
      <ConversationBody bot={bot} />
    </div>
  );
}

type RunOutcome = "completed" | "cancelled" | "failed" | "unknown";
const UNCONFIRMED = "Chưa xác nhận được trạng thái. Kiểm tra lại cuộc trò chuyện.";
const compactLayout = () => !window.matchMedia("(min-width: 1100px)").matches;

function ConversationBody({ bot }: { bot: BotPublicDTO }) {
  const { api, session, paused } = useSession();
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
  const historyWritable = !conversation?.persistent || !!preferences?.historyAvailable;
  const canSend = allowed && historyWritable && !!preferences && !preferencesError;
  const [draft, setDraft] = useState(""),
    [error, setError] = useState<unknown>();
  const [loading, setLoading] = useState(true),
    [busy, setBusy] = useState(false);
  useTourBlocker("ai", busy);
  useTourBlocker("draft", draft.length > 0);
  const [ready, setReady] = useState(false);
  const [run, setRun] = useState<{ id: string; version: number; key: string }>();
  // Stop is a request until the run's own terminal event confirms the outcome.
  const [stopRequested, setStopRequested] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [stopped, setStopped] = useState(false);
  const activeRun = useRef<string | undefined>(undefined);
  const [revision, setRevision] = useState(0);
  const loadedRevision = useRef(0);
  const loadedSelection = useRef<string | undefined>(undefined);
  const openedFor = useRef<string | undefined>(undefined);
  const [atBottom, setAtBottom] = useState(true);
  const log = useRef<HTMLDivElement>(null),
    lifetime = useRef<AbortController | null>(null);
  const intent = useRef<{ text: string; scopeKey: string; clientMessageId: string } | null>(null);
  const composer = useRef<HTMLTextAreaElement>(null);
  const composerAction = useRef<HTMLButtonElement>(null);
  const restoreActionFocus = useRef(false);
  const [draftNotice, setDraftNotice] = useState("");
  const [infoOpen, setInfoOpen] = useState(false);
  const infoTrigger = useRef<HTMLButtonElement>(null);
  const infoId = useId();
  const [historyOpen, setHistoryOpen] = useState(false);
  const [newConfirmOpen, setNewConfirmOpen] = useState(false);
  // The trigger may only reference a panel that is actually mounted.
  const infoMounted = useInfoPanelMounted(infoOpen, historyOpen || renameOpen || deleteOpen || newConfirmOpen);
  // "Dừng và mở mới" waits for the run's real terminal outcome before switching.
  const pendingNew = useRef(false);
  const [awaitingNew, setAwaitingNew] = useState(false);
  const [previousConversation, setPreviousConversation] = useState<string>();
  const [copyStatus, setCopyStatus] = useState<{ id: string; ok: boolean }>();
  const [revealedMessage, setRevealedMessage] = useState<string>();
  const [messageClock, setMessageClock] = useState(() => Date.now());
  useEffect(() => {
    // Refresh calendar labels when a conversation stays open overnight.
    const timer = window.setInterval(() => setMessageClock(Date.now()), 60_000);
    return () => window.clearInterval(timer);
  }, []);
  useEffect(() => {
    setRevealedMessage(undefined);
  }, [conversation?.conversationId]);
  useEffect(() => {
    if (!revealedMessage) return;
    const dismiss = (event: PointerEvent) => {
      if (!(event.target instanceof Element) || !event.target.closest(".ai-message-row .message-content")) {
        setRevealedMessage(undefined);
      }
    };
    const escape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setRevealedMessage(undefined);
    };
    document.addEventListener("pointerdown", dismiss);
    document.addEventListener("keydown", escape);
    return () => {
      document.removeEventListener("pointerdown", dismiss);
      document.removeEventListener("keydown", escape);
    };
  }, [revealedMessage]);
  const datedMessages = useMemo(() => {
    const format = createMessageDateFormatter(session.timezone, new Date(messageClock));
    let previousDay: string | undefined;
    return conversation?.messages.map(message => {
      const date = format(message.createdAt);
      const showDate = date && date.dayKey !== previousDay;
      if (date) previousDay = date.dayKey;
      return { message, date, showDate };
    });
  }, [conversation?.messages, session.timezone, messageClock]);
  const [unseen, setUnseen] = useState(false);
  const [manageError, setManageError] = useState<unknown>();
  const [deleteError, setDeleteError] = useState<unknown>();
  const renameField = useRef<HTMLInputElement>(null);
  const onTerminal = useRef<((outcome: RunOutcome) => void) | undefined>(undefined);
  // Run whose cancel request is already on its way; a second request reuses it.
  const cancelRequested = useRef<string | undefined>(undefined);
  // Draft edits are counted so a stale closure comparison never decides what to clear.
  const draftRevision = useRef(0);
  // Text a failed run may hand back belongs to one conversation, request and view generation.
  const recovery = useRef<{ requestKey: string; conversationId: string; generation: number; text: string; revision: number } | undefined>(undefined);
  // Bumped on every real selection change, New and unmount; URL canonicalisation does not bump it.
  const viewGeneration = useRef(0);
  // Where a pending New will land, so applying its URL is not mistaken for a selection.
  const newMarker = useRef<string | undefined>(undefined);
  // Terminal outcome of the last run that finished in this view, for a late New confirmation.
  const settled = useRef<{ runId: string; conversationId: string; outcome: RunOutcome } | undefined>(undefined);
  const confirmTarget = useRef<{ runId: string; conversationId: string } | undefined>(undefined);
  const editDraft = useCallback((value: string) => {
    draftRevision.current += 1;
    setDraft(value);
  }, []);
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
  const hasUserMessages = conversation?.messages.some((message) => message.actor === "self") ?? false;
  const showStarters = !loading && !busy && !hasUserMessages;
  const update = useCallback((value: SavedConversation) => {
    current.current = value;
    setConversation(value);
  }, []);
  /** The server copy replaces the latest page; older pages the reader loaded stay. */
  const withOlder = useCallback((stored: SavedConversation): SavedConversation => {
    const latest = current.current;
    if (!latest || latest.conversationId !== stored.conversationId || !stored.messages.length) return stored;
    const first = latest.messages.findIndex((message) => message.id === stored.messages[0].id);
    if (first <= 0) return stored;
    return { ...stored, hasMoreMessages: latest.hasMoreMessages, messages: [...latest.messages.slice(0, first), ...stored.messages] };
  }, []);
  const stream = useCallback(
    async (
      id: string,
      version: number,
      eventsUrl: string,
      signal: AbortSignal,
      requestKey: string,
    ) => {
      activeRun.current = id;
      setRun({ id, version, key: requestKey });
      setStopped(false);
      setBusy(true);
      let outcome: RunOutcome = "unknown";
      const ownerId = current.current?.conversationId;
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
                createdAt: new Date().toISOString(),
              },
            ],
          });
          // The validated reply is already on screen; only reconciliation remains.
          setSyncing(true);
          const stored = await api.request<SavedConversation>(
            `/ai/conversations/${before.conversationId}`,
            { signal },
          );
          if (!signal.aborted) {
            update(withOlder(stored));
            setReady(true);
            refreshHistory();
            setProposalRevision((value) => value + 1);
            outcome = "completed";
          }
        }
      } catch (reason) {
        if (!signal.aborted && reason instanceof ApiError && reason.code === "RUN_CANCELLED") {
          // A confirmed terminal cancellation is a neutral outcome, not an error.
          setStopped(true);
          setSyncing(true);
          try {
            const thread = current.current;
            if (thread) {
              const stored = await api.request<SavedConversation>(`/ai/conversations/${thread.conversationId}`, { signal });
              if (!signal.aborted) { update(withOlder(stored)); refreshHistory(); outcome = "cancelled"; setReady(true); }
            }
          } catch (readError) {
            // Only a successful authoritative read restores readiness; Retry reloads and reattaches.
            if (!signal.aborted) { setError(readError); setReady(false); }
          }
        } else if (!signal.aborted) {
          if (reason instanceof ApiError && ["RUN_FAILED", "RUN_INTERRUPTED"].includes(reason.code)) outcome = "failed";
          setError(reason);
          setReady(false);
          const owned = recovery.current;
          if (reason instanceof ApiError && reason.code === "RUN_FAILED" && owned &&
              owned.requestKey === requestKey && owned.conversationId === current.current?.conversationId &&
              owned.generation === viewGeneration.current && owned.revision === draftRevision.current) {
            // Restore only this run's confirmed terminal failure, and only over the
            // empty draft it left behind. A transport interruption can still complete
            // on the server and must be reconciled by reload.
            editDraft(owned.text);
          }
        }
      } finally {
        if (!signal.aborted) {
          if (recovery.current?.requestKey === requestKey) recovery.current = undefined;
          if (ownerId) settled.current = { runId: id, conversationId: ownerId, outcome };
          activeRun.current = undefined; cancelRequested.current = undefined;
          setRun(undefined);
          setBusy(false);
          setStopRequested(false);
          setSyncing(false);
          onTerminal.current?.(outcome);
        }
      }
    },
    [api, update, withOlder, refreshHistory, editDraft],
  );
  useEffect(() => () => {
    lifetime.current?.abort();
    viewGeneration.current += 1; recovery.current = undefined; newMarker.current = undefined;
    // An aborted open must run again if this view mounts again (StrictMode).
    openedFor.current = undefined;
  }, []);
  useEffect(() => {
    // A newly created thread receives a URL without interrupting its active stream.
    // That URL can commit before New's own marker URL ever renders here. The view
    // New opened still owns the selection, exactly as if the marker had applied;
    // otherwise Back to the previous chat matches its stale key and is skipped.
    if (selectedId && selectedId === current.current?.conversationId && loadedRevision.current === revision) {
      if (newMarker.current) { openedFor.current = newMarker.current; newMarker.current = undefined; }
      return;
    }
    // A fresh login must wait for the saved-history preference before selecting
    // the latest thread. Otherwise the first render silently skips saved threads.
    if (!selectedId && preferencesLoading) return;
    // Preferences reload on every tab focus; that alone must not reopen (and abort)
    // the selection already on screen, an in-flight send or a pending stop-and-new.
    const openKey = `${bot.botId}/${selectedId || searchParams.get("new") || "latest"}#${revision}`;
    if (openedFor.current === openKey) return;
    if (newMarker.current === openKey) {
      // Applying the URL of a New this view already opened is not a selection: its
      // lifetime, draft and any send it owns stay as they are.
      newMarker.current = undefined;
      openedFor.current = openKey;
      loadedRevision.current = revision;
      return;
    }
    newMarker.current = undefined;
    openedFor.current = openKey;
    loadedRevision.current = revision;
    lifetime.current?.abort();
    const controller = new AbortController();
    lifetime.current = controller;
    viewGeneration.current += 1; recovery.current = undefined; settled.current = undefined; confirmTarget.current = undefined;
    setNewConfirmOpen(false);
    setLoading(true); setReady(false); setBusy(false); setRun(undefined); setError(undefined);
    setNotice(""); setPreviousConversation(undefined);
    activeRun.current = undefined; cancelRequested.current = undefined; setStopRequested(false); setSyncing(false); setStopped(false);
    pendingNew.current = false; setAwaitingNew(false); setCopyStatus(undefined);
    current.current = undefined; setConversation(undefined);
    const selection = `${bot.botId}/${selectedId || searchParams.get("new") || "latest"}`;
    // A different thread chosen in this conversation (not first open, not a new chat) moves focus to its heading once loaded.
    const switched = Boolean(selectedId) && loadedSelection.current !== undefined && loadedSelection.current !== selection;
    if (loadedSelection.current !== selection) { intent.current = null; editDraft(""); setDraftNotice(""); setManageError(undefined); setShareMood(false); }
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
      if (!id) {
        setReady(true); return;
      }
      const value = await api.request<SavedConversation>(`/ai/conversations/${encodeURIComponent(id)}`, { signal: controller.signal });
      if (controller.signal.aborted) return;
      if (value.botId !== bot.botId) throw new ApiError(409, "CONVERSATION_BOT_MISMATCH", "Cuộc trò chuyện thuộc trợ lý khác. Chọn lại trong lịch sử.");
      update(value); setReady(true); setAtBottom(true);
      if (switched) requestAnimationFrame(() => focusRouteHeading());
      if (value.activeRunId && allowed) void stream(value.activeRunId, value.activeRunVersion || 1, `/api/v1/ai/runs/${value.activeRunId}/events`, controller.signal, `resume:${value.activeRunId}`);
    }
    void open().catch(reason => { if (!controller.signal.aborted) setError(reason); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    // Lifetime is aborted above on a real selection and on unmount. URL updates
    // for the current thread must leave its in-flight request running.
  }, [api, bot.botId, selectedId, searchParams.get("new"), revision, stream, update, preferencesLoading, preferences?.historyEnabled, editDraft]);
  useEffect(() => {
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
  }, [api, proposalRevision, conversation?.conversationId]);
  useEffect(() => {
    if (atBottom && log.current)
      log.current.scrollTop = log.current.scrollHeight;
  }, [conversation?.messages.length, busy, atBottom, run?.id, stopRequested, syncing]);
  useEffect(() => {
    const element = log.current;
    if (!atBottom || !element) return;
    // Textarea growth and the on-screen keyboard can shrink the log without a
    // new message. Keep the current status in view only for readers at the end.
    const observer = new ResizeObserver(() => {
      element.scrollTop = element.scrollHeight;
    });
    observer.observe(element);
    return () => observer.disconnect();
  }, [atBottom]);
  useEffect(() => {
    // A disabled submitting button loses focus in some browsers. Restore it
    // only if the person has not moved to another control while waiting.
    if (run && restoreActionFocus.current) {
      if (document.activeElement === document.body || document.activeElement === composerAction.current) {
        composerAction.current?.focus();
      }
      restoreActionFocus.current = false;
    }
  }, [run]);
  const lastMessageId = conversation?.messages.at(-1)?.id;
  useEffect(() => {
    if (lastMessageId && !atBottom) setUnseen(true);
    // Only a new last message counts; prepending older history does not.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lastMessageId]);
  useEffect(() => {
    if (atBottom) setUnseen(false);
  }, [atBottom]);
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
      paused ||
      text.length > 500 ||
      !lifetime.current
    )
      return;
    const signal = lifetime.current.signal;
    const submittedRevision = draftRevision.current, generation = viewGeneration.current;
    setBusy(true);
    setStopped(false);
    setError(undefined);
    const moodScope = moodSelected ? { fromDate: moodFrom, toDate: moodTo } : undefined;
    const scopeKey = moodScope ? `${moodScope.fromDate}/${moodScope.toDate}` : "";
    if (intent.current?.text !== text || intent.current?.scopeKey !== scopeKey)
      intent.current = { text, scopeKey, clientMessageId: crypto.randomUUID() };
    try {
      let thread = current.current;
      if (!thread) {
        const created = await api.request<SavedConversationHeader>(
          "/ai/conversations",
          {
            method: "POST",
            body: { botId: bot.botId, persistent: !!preferences?.historyAvailable },
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
      update({
        ...thread,
        version: accepted.version,
        activeRunId: accepted.runId,
        activeRunVersion: accepted.runVersion,
        messages: [
          ...thread.messages,
          { id: intent.current!.clientMessageId, actor: "self", text, createdAt: new Date().toISOString() },
        ],
      });
      const requestKey = intent.current!.clientMessageId;
      intent.current = null;
      if (moodScope) setLastMoodRange({ conversationId: thread.conversationId, ...moodScope });
      setShareMood(false);
      // Only the snapshot that was submitted is cleared; anything typed while the
      // request was pending (even text equal to the old draft) stays.
      const untouched = draftRevision.current === submittedRevision;
      if (untouched) editDraft("");
      recovery.current = { requestKey, conversationId: thread.conversationId, generation, text, revision: untouched ? draftRevision.current : -1 };
      setAtBottom(true);
      await stream(
        accepted.runId,
        accepted.runVersion,
        accepted.eventsUrl,
        signal,
        requestKey,
      );
    } catch (reason) {
      if (!signal.aborted) setError(reason);
    } finally {
      if (!signal.aborted) setBusy(false);
    }
  }
  /** A suggestion only edits the draft; sending stays an explicit choice. */
  function insertStarter(text: string) {
    const field = composer.current;
    const result = insertAtSelection(draft, field?.selectionStart ?? draft.length, field?.selectionEnd ?? draft.length, text);
    if (!result.ok) {
      setDraftNotice("Gợi ý này sẽ làm tin nhắn dài hơn 500 ký tự. Hãy rút gọn trước khi thêm.");
      return;
    }
    editDraft(result.next);
    setDraftNotice("");
    requestAnimationFrame(() => {
      field?.focus();
      field?.setSelectionRange(result.caret, result.caret);
    });
  }
  /** "pending" means this run's cancel request already exists; its outcome is the stream's terminal event. */
  async function cancel(): Promise<"accepted" | "pending" | "failed"> {
    if (!run) return "failed";
    const runId = run.id;
    if (stopRequested || cancelRequested.current === runId) return "pending";
    cancelRequested.current = runId;
    setStopRequested(true);
    setError(undefined);
    try {
      // Keep reading the stream: only its terminal event says whether the run
      // was cancelled or had already completed.
      await api.request(`/ai/runs/${runId}/cancel`, {
        method: "POST",
        body: { expectedVersion: run.version } satisfies VersionInput,
      });
      return "accepted";
    } catch (reason) {
      if (activeRun.current === runId) {
        cancelRequested.current = undefined;
        setStopRequested(false);
        setError(reason);
        // A New that was waiting on this cancellation cannot proceed; stay put.
        if (pendingNew.current) {
          pendingNew.current = false;
          setAwaitingNew(false);
          setError(new ApiError(0, "RUN_STATE_UNCONFIRMED", UNCONFIRMED));
        }
      }
      return "failed";
    }
  }
  function newConversation() {
    lifetime.current?.abort();
    lifetime.current = new AbortController();
    viewGeneration.current += 1; recovery.current = undefined; settled.current = undefined; confirmTarget.current = undefined;
    current.current = undefined; setConversation(undefined); editDraft(""); setDraftNotice(""); setManageError(undefined); setError(undefined); setNotice("");
    setReady(true); setLoading(false); setBusy(false); setRun(undefined); intent.current = null; setShareMood(false); setLastMoodRange(undefined);
    activeRun.current = undefined; cancelRequested.current = undefined; setStopRequested(false); setSyncing(false); setStopped(false);
    pendingNew.current = false; setAwaitingNew(false); setPreviousConversation(undefined); setCopyStatus(undefined);
    // An explicit new marker prevents latest-thread auto-resume. This view is
    // already reset, so the router applying the marker URL (in a transition) must
    // neither abort the fresh lifetime nor wipe a draft or send made since the click.
    const marker = crypto.randomUUID();
    loadedSelection.current = `${bot.botId}/${marker}`;
    newMarker.current = `${bot.botId}/${marker}#${revision}`;
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
      setRenameOpen(false); refreshHistory(); setNotice("Đã đổi tên cuộc trò chuyện.");
    } catch (reason) { setRenameError(reason); }
    finally { setManageBusy(false); }
  }
  async function removeConversation() {
    const thread = current.current;
    if (!thread || manageBusy) return;
    setManageBusy(true); setDeleteError(undefined);
    try {
      await api.request(`/ai/conversations/${thread.conversationId}`, { method: "DELETE" });
      setDeleteOpen(false); setInfoOpen(false); newConversation(); refreshHistory(); setNotice("Đã xóa cuộc trò chuyện.");
    } catch (reason) { setDeleteError(reason); }
    finally { setManageBusy(false); }
  }
  // Child dialogs replace a compact (modal) info sheet; on desktop the modeless
  // panel stays and the dialog returns focus to the panel action.
  function openRename() {
    const thread = current.current;
    if (!thread) return;
    setRenameText(thread.title || ""); setRenameError(undefined);
    if (compactLayout()) setInfoOpen(false);
    setRenameOpen(true);
  }
  function openDelete() {
    setDeleteError(undefined);
    if (compactLayout()) setInfoOpen(false);
    setDeleteOpen(true);
  }
  function openHistory() {
    if (compactLayout()) setInfoOpen(false);
    setHistoryOpen(true);
  }
  function closeInfo(restoreFocus: boolean) {
    setInfoOpen(false);
    if (restoreFocus) requestAnimationFrame(() => infoTrigger.current?.focus());
  }
  function requestNew() {
    if (syncing || awaitingNew || (busy && !run)) return;
    if (run) {
      // The confirmation is about this run in this conversation; confirming later
      // re-checks what became of it rather than assuming it is still active.
      confirmTarget.current = current.current ? { runId: run.id, conversationId: current.current.conversationId } : undefined;
      if (compactLayout()) setInfoOpen(false);
      setNewConfirmOpen(true);
      return;
    }
    setInfoOpen(false);
    newConversation();
  }
  function openNewAfter(outcome: Exclude<RunOutcome, "unknown">) {
    const previous = current.current?.conversationId;
    setInfoOpen(false);
    newConversation();
    setPreviousConversation(outcome === "completed" ? previous : undefined);
    setNotice(
      outcome === "cancelled" ? "Đã dừng phản hồi và mở cuộc trò chuyện mới."
        : outcome === "completed" ? "Câu trả lời vừa hoàn tất trước khi dừng. Đã mở cuộc trò chuyện mới."
          : "Phản hồi đã kết thúc vì lỗi trước khi dừng. Đã mở cuộc trò chuyện mới.",
    );
  }
  async function stopAndNew() {
    setNewConfirmOpen(false);
    const target = confirmTarget.current;
    confirmTarget.current = undefined;
    const thread = current.current;
    if (!target || !thread || target.conversationId !== thread.conversationId) return;
    if (run?.id !== target.runId) {
      // The run being confirmed is no longer the active one. A missing run proves
      // neither completion nor cancellation: use only an outcome this view validated.
      const known = settled.current;
      if (!run && known && known.runId === target.runId && known.conversationId === target.conversationId && known.outcome !== "unknown") {
        openNewAfter(known.outcome);
        return;
      }
      // Never cancel a newer run on behalf of an older confirmation.
      setError(new ApiError(0, "RUN_STATE_UNCONFIRMED", UNCONFIRMED));
      return;
    }
    pendingNew.current = true;
    setAwaitingNew(true);
    const result = await cancel();
    // A failed cancel already cleared the pending New; "pending" reuses the Stop in flight.
    if (result === "failed" && pendingNew.current) {
      pendingNew.current = false;
      setAwaitingNew(false);
      setError(new ApiError(0, "RUN_STATE_UNCONFIRMED", UNCONFIRMED));
    }
  }
  onTerminal.current = (outcome) => {
    if (!pendingNew.current) return;
    pendingNew.current = false;
    setAwaitingNew(false);
    if (outcome === "unknown") {
      // Keep this conversation and its draft; nothing is replayed automatically.
      setError(new ApiError(0, "RUN_STATE_UNCONFIRMED", UNCONFIRMED));
      return;
    }
    openNewAfter(outcome);
  };
  async function copyReply(id: string, bubble: Element | null | undefined) {
    // Plain text of the rendered, validated reply; never cards or metadata.
    const root = bubble?.querySelector<HTMLElement>(".ai-markdown") ?? (bubble as HTMLElement | null | undefined);
    const text = root?.innerText.trim() ?? "";
    try {
      if (!text || !navigator.clipboard) throw new Error("clipboard unavailable");
      await navigator.clipboard.writeText(text);
      setCopyStatus({ id, ok: true });
    } catch {
      setCopyStatus({ id, ok: false });
    }
  }
  function jumpToLatest() {
    const element = log.current;
    if (!element) return;
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    element.scrollTo({ top: element.scrollHeight, behavior: reduced ? "auto" : "smooth" });
    setAtBottom(true);
    setUnseen(false);
  }
  const lastSelf = conversation?.messages.filter((message) => message.actor === "self").at(-1);
  const phase: AIActivityPhase = stopRequested ? "cancelling"
    : syncing ? "reconciling"
    : run ? "accepted"
    : busy ? "submitting"
    // The transcript turn status already says a reconciled turn stopped.
    : stopped && lastSelf?.status !== "cancelled" ? "cancelled"
    : "idle";
  const activity = deriveAIActivity({ phase, requestKey: run?.key ?? intent.current?.clientMessageId, runId: run?.id });
  const canStop = Boolean(run && !syncing);
  const stopDisabled = stopRequested || awaitingNew;
  const actionLabel = canStop ? (stopRequested ? "Đang yêu cầu dừng" : "Dừng phản hồi") : "Gửi tin cho AI";
  const historyOnForNew = Boolean(preferences?.historyEnabled && preferences.historyAvailable);
  const modeLabel = conversation ? (conversation.persistent ? "Đã lưu" : "Tạm thời") : historyOnForNew ? "Sẽ được lưu" : "Tạm thời";
  const TEMPORARY = "Không lưu vào lịch sử. Phiên tạm có thể kết thúc khi phiên đăng nhập hoặc máy chủ thay đổi.";
  let retentionLabel = TEMPORARY;
  if (conversation?.persistent)
    retentionLabel = conversation.expiresAt
      ? `Đã lưu trong lịch sử đến ngày ${new Intl.DateTimeFormat("vi-VN", { timeZone: session.timezone, dateStyle: "short" }).format(new Date(conversation.expiresAt))}.`
      : `Đã lưu trong lịch sử tối đa ${preferences?.retentionDays ?? 30} ngày.`;
  else if (!conversation && historyOnForNew)
    retentionLabel = `Cuộc trò chuyện này sẽ được lưu trong lịch sử tối đa ${preferences!.retentionDays} ngày khi bạn gửi tin đầu tiên.`;

  let historyStatus = "Lịch sử chưa sẵn sàng.";
  if (preferencesLoading) historyStatus = "Đang kiểm tra lịch sử…";
  else if (!preferences) historyStatus = "Chưa kiểm tra được lựa chọn lưu lịch sử.";
  else if (!preferences.historyAvailable) historyStatus = "Lưu lịch sử chưa sẵn sàng.";
  else if (preferences.historyEnabled) historyStatus = `Đang lưu cuộc trò chuyện mới tối đa ${preferences.retentionDays} ngày.`;
  if (session.accountKind === "guest") {
    // The trial never keeps a long-term history: everything ends with the trial.
    retentionLabel = "Cuộc trò chuyện chỉ tồn tại trong lượt dùng thử. Khi hết giờ hoặc khi bạn kết thúc, dữ liệu bị xóa và không thể mở lại.";
    historyStatus = "Lịch sử dài hạn không có trong lượt dùng thử.";
  }

  let readOnlyMessage = "Đang kiểm tra cài đặt trò chuyện AI…";
  if (!session.features.ai) readOnlyMessage = aiServiceMessage(session.features);
  else if (!preferences && !preferencesLoading)
    readOnlyMessage = "Chưa tải được cài đặt trò chuyện AI. Tải lại trước khi gửi tin nhắn.";
  else if (preferences && !historyWritable)
    readOnlyMessage = "Lưu lịch sử hiện chưa sẵn sàng. Cuộc trò chuyện đã lưu chỉ để xem; bạn có thể mở một cuộc trò chuyện tạm thời mới.";
  const newDisabledReason = busy && !run ? "Đang xác nhận tin nhắn vừa gửi."
    : syncing ? "Đang cập nhật cuộc trò chuyện…"
      : awaitingNew ? "Đang chờ phản hồi hiện tại dừng lại…"
        : undefined;
  const infoTitle = conversation?.title?.trim() || "Cuộc trò chuyện mới";
  return (
    <>
      <header className="conversation-header">
        <Link
          to="/assistants"
          className="icon-button mobile-back"
          aria-label="Về danh sách trợ lý"
        >
          <ArrowLeft size={21} />
        </Link>
        <PublicAvatar bot={bot} size={36} />
        <div>
          <h1 tabIndex={-1} data-route-heading>
            {bot.name} <span className="ai-tag">AI</span>
          </h1>
          <p>
            {bot.role} · <span className="conversation-mode">{modeLabel}</span>
          </p>
        </div>
        <button
          ref={infoTrigger}
          type="button"
          className="icon-button"
          aria-label="Thông tin cuộc trò chuyện"
          aria-expanded={infoOpen}
          aria-controls={infoMounted ? infoId : undefined}
          onClick={() => (infoOpen ? closeInfo(true) : setInfoOpen(true))}
        >
          <Info size={21} />
        </button>
      </header>
      {historyOpen ? <Dialog title="Lịch sử trò chuyện" returnFocus={infoTrigger} onClose={() => setHistoryOpen(false)}><ConversationHistory onSelect={() => setHistoryOpen(false)} /></Dialog> : null}
      {renameOpen ? <Dialog title="Đổi tên cuộc trò chuyện" initialFocus={renameField} returnFocus={infoTrigger} onClose={() => !manageBusy && setRenameOpen(false)}><form className="conversation-rename" onSubmit={(event) => { event.preventDefault(); void rename(); }}><label htmlFor="conversation-title">Tên cuộc trò chuyện</label><input id="conversation-title" ref={renameField} value={renameText} maxLength={100} required onChange={(event) => setRenameText(event.target.value)} /><p>Tên chỉ hiển thị cho bạn và không được gửi tới trợ lý.</p><ErrorNotice error={renameError} /><div className={cx.actions}><Button type="button" variant="secondary" disabled={manageBusy} onClick={() => setRenameOpen(false)}>Hủy</Button><Button type="submit" disabled={manageBusy || !renameText.trim()}>{manageBusy ? "Đang lưu tên…" : "Lưu tên"}</Button></div></form></Dialog> : null}
      {deleteOpen ? <Dialog title="Xóa cuộc trò chuyện này?" destructive returnFocus={infoTrigger} onClose={() => !manageBusy && setDeleteOpen(false)}><p>Cuộc trò chuyện và các tin nhắn trong đó sẽ bị xóa. Thao tác này không thể hoàn tác.</p><ErrorNotice error={deleteError} /><div className={cx.actions}><Button variant="secondary" data-cancel disabled={manageBusy} onClick={() => setDeleteOpen(false)}>Giữ cuộc trò chuyện</Button><Button variant="danger" disabled={manageBusy} onClick={() => void removeConversation()}>{manageBusy ? "Đang xóa…" : "Xóa cuộc trò chuyện"}</Button></div></Dialog> : null}
      {newConfirmOpen ? <Dialog title="Dừng phản hồi và mở cuộc trò chuyện mới?" destructive returnFocus={infoTrigger} onClose={() => setNewConfirmOpen(false)}><p>Phản hồi hiện tại sẽ được yêu cầu dừng. Cuộc trò chuyện mới chỉ mở sau khi xác nhận được kết quả; cuộc trò chuyện đã lưu vẫn được giữ.</p><div className={cx.actions}><Button variant="secondary" data-cancel onClick={() => setNewConfirmOpen(false)}>Tiếp tục trò chuyện</Button><Button onClick={() => void stopAndNew()}>Dừng và mở mới</Button></div></Dialog> : null}
      <div className="conversation-stage">
      <div
        className="conversation-log"
        ref={log}
        role="log"
        aria-live="off"
        tabIndex={0}
        aria-label={`Cuộc trò chuyện với ${bot.name}`}
        onScroll={() => {
          const element = log.current!;
          setAtBottom(
            element.scrollHeight - element.scrollTop - element.clientHeight <
              90,
          );
        }}
      >
        {!conversation?.messages.length && !loading ? <div className="chat-introduction">
          <PublicAvatar bot={bot} size={64} />
          <h2>Một chút thời gian với {bot.name}</h2>
          <p>{bot.description}</p>
          {!conversation?.messages.length && <AssistantGuide botId={bot.botId} />}
          <small>
            <LockKeyhole size={13} /> Không chia sẻ với bạn kết nối
          </small>
        </div> : null}
        {notice ? <p role="status"><span>{notice}</span>{previousConversation ? <> <Link to={`/assistants/${bot.botId}?conversation=${encodeURIComponent(previousConversation)}`}>Xem cuộc trò chuyện trước</Link></> : null}</p> : null}
        {preferencesError ? <><p>Chưa xác minh được lựa chọn lưu dữ liệu. Tải lại trước khi gửi tin nhắn.</p><ErrorNotice error={preferencesError} retry={reloadPreferences} /></> : null}
        {loading ? <p role="status">Đang mở cuộc trò chuyện…</p> : null}
        {conversation?.hasMoreMessages ? <Button variant="secondary" disabled={olderBusy || loading} onClick={() => void olderMessages()}>{olderBusy ? "Đang tải tin nhắn…" : "Tải tin nhắn cũ hơn"}</Button> : null}
        <div className="conversation-messages" aria-live="polite" aria-relevant="additions text">
        {datedMessages?.map(({ message, date, showDate }) => (
          <Fragment key={message.id}>
            {showDate && date ? <div className="message-date-separator"><time dateTime={message.createdAt!}>{date.dayLabel}</time></div> : null}
            <div
              className={`message-row ai-message-row ${message.actor === "self" ? "from-self" : "from-bot"} ${revealedMessage === message.id ? "message-details-open" : ""}`}
            >
              <div
                className="message-content"
                role="group"
                aria-label={message.actor === "self" ? "Tin nhắn của bạn" : `Tin nhắn từ ${bot.name}`}
                tabIndex={date || message.actor === "bot" ? 0 : undefined}
                onFocus={(event) => {
                  if (event.target.matches(":focus-visible")) setRevealedMessage(message.id);
                }}
                onBlur={(event) => {
                  if (!event.currentTarget.contains(event.relatedTarget)) {
                    setRevealedMessage(value => value === message.id ? undefined : value);
                  }
                }}
                onPointerUp={(event) => {
                  if (event.pointerType === "mouse" || !(event.target instanceof Element) ||
                    event.target.closest("a, button") || !window.getSelection()?.isCollapsed) return;
                  setRevealedMessage(value => value === message.id ? undefined : message.id);
                }}
              >
                <div className="chat-bubble">
                  {message.actor === "bot" ? (
                    <Suspense fallback={<p>{message.text}</p>}>
                      <MessageMarkdown text={message.text} />
                    </Suspense>
                  ) : <p>{message.text}</p>}
                </div>
                {validCards(message.cards) &&
                  message.cards.map((card, index) => (
                    <div className="inline-card" key={`${message.id}-${index}`}>
                      {card.kind === "mood_form" ? (
                        <Link to="/self">Ghi lại cảm xúc <ArrowUpRight size={15} aria-hidden="true" /></Link>
                      ) : card.kind === "navigate_bot" ? (
                        <Link to={`/assistants/${card.botId}`}>
                          Trò chuyện với {botById(card.botId)?.name} <ArrowUpRight size={15} aria-hidden="true" />
                        </Link>
                      ) : (
                        <Link to="/connect">Tìm bạn đồng điệu <ArrowUpRight size={15} aria-hidden="true" /></Link>
                      )}
                    </div>
                  ))}
                {date || message.actor === "bot" ? (
                  <div className="message-actions">
                    {date ? <time dateTime={message.createdAt!}>{date.time}</time> : null}
                    {message.actor === "bot" ? <>
                    <button
                      type="button"
                      className="message-action"
                      aria-label="Sao chép câu trả lời"
                      title="Sao chép câu trả lời"
                      onClick={(event) => void copyReply(message.id, event.currentTarget.closest(".message-content")?.querySelector(".chat-bubble"))}
                    >
                      <Copy size={15} aria-hidden="true" />
                    </button>
                    {copyStatus?.id === message.id ? <span role="status">{copyStatus.ok ? "Đã sao chép câu trả lời." : "Chưa sao chép được. Bạn có thể chọn và sao chép nội dung."}</span> : null}
                    </> : null}
                  </div>
                ) : null}
                {message.actor === "self" && message.status && ["failed", "interrupted", "cancelled"].includes(message.status) ? <small className="message-turn-status" role="status">{message.status === "interrupted" ? "Phản hồi bị gián đoạn; lượt này không tự chạy lại." : message.status === "cancelled" ? "Đã dừng phản hồi." : "Phản hồi chưa hoàn tất."}</small> : null}
              </div>
            </div>
          </Fragment>
        ))}
        </div>
        <AIActivityStatus
          view={activity}
          phase={phase}
          identity={`${conversation?.conversationId ?? "new"}/${run?.key ?? intent.current?.clientMessageId ?? "idle"}`}
          onStop={!canSend && canStop ? () => void cancel() : undefined}
          stopDisabled={stopDisabled}
        />
        {pendingProposals > 0 && !busy ? (
          <p className="chat-proposal-notice" role="status">
            Có {pendingProposals} đề xuất đang chờ bạn duyệt. Chưa có gì được lưu cho đến khi bạn duyệt.{" "}
            <Link to="/memory">Xem đề xuất</Link>
          </p>
        ) : null}

        <ErrorNotice
          error={error}
          retry={() => setRevision((value) => value + 1)}
        />
      </div>
      {unseen && !atBottom ? <button type="button" className="jump-latest" onClick={jumpToLatest}>Về tin mới</button> : null}
      <ConversationInfo
        open={infoOpen}
        suspended={historyOpen || renameOpen || deleteOpen || newConfirmOpen}
        onClose={closeInfo}
        triggerRef={infoTrigger}
        panelId={infoId}
        title={infoTitle}
        botName={bot.name}
        persistent={Boolean(conversation?.persistent)}
        modeLabel={modeLabel}
        retentionLabel={retentionLabel}
        historyStatus={historyStatus}
        pendingProposals={pendingProposals}
        manageBusy={manageBusy}
        manageError={<ErrorNotice error={manageError} />}
        newDisabledReason={newDisabledReason}
        onHistory={openHistory}
        onRename={openRename}
        onDelete={openDelete}
        onNew={requestNew}
      />
      </div>
      {session.features.aiStatus === "test_provider" ? <p className={cx.footnote} role="note">Môi trường kiểm thử · phản hồi từ model giả, không phải OpenAI.</p> : null}
      {!canSend ? <div className="chat-readonly" role="status"><p>{readOnlyMessage}</p>{allowed && preferences && !historyWritable ? <div className={cx.actions}><Button variant="secondary" onClick={requestNew}>Mở cuộc trò chuyện mới</Button></div> : null}</div> : <div className="chat-bottom">
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
                Cho Nhịp xem thống kê trong khoảng ngày đã chọn
              </label>
              <p>Chỉ chia sẻ điểm tâm trạng và những ngày đã ghi, không gửi ghi chú. Bạn chọn lại quyền này cho mỗi lượt.</p>
              {shareMood ? <div className="mood-share-dates">
                <label htmlFor="mood-share-from">Thống kê từ ngày
                  <input id="mood-share-from" type="date" min={moodWindow.earliest} max={moodWindow.today} value={moodFrom} onChange={event => setMoodFrom(event.target.value)} />
                </label>
                <label htmlFor="mood-share-to">Thống kê đến ngày
                  <input id="mood-share-to" type="date" min={moodFrom || moodWindow.earliest} max={moodWindow.today} value={moodTo} onChange={event => setMoodTo(event.target.value)} />
                </label>
                {moodInvalid ? <p role="alert">Chọn ngày bắt đầu và kết thúc trong 90 ngày gần đây. Ngày kết thúc phải từ ngày bắt đầu trở đi.</p> : null}
              </div> : null}
            </fieldset>
          </details>
          </>
        ) : null}
        {showStarters ? (
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
        ) : null}
        {draftNotice ? <p className={cx.footnote} role="status">{draftNotice}</p> : null}
        <QuotaHint />
        <form
          className="bot-composer"
          onSubmit={(event) => {
            event.preventDefault();
            restoreActionFocus.current = document.activeElement === composerAction.current;
            void send();
          }}
        >
          <textarea
            aria-label={`Tin nhắn cho ${bot.name}`}
            ref={composer}
            value={draft}
            maxLength={500}
            rows={1}
            onChange={(event) => { editDraft(event.target.value); setDraftNotice(""); }}
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
          <VoiceRecorder
            draft={draft}
            onUse={(text) => {
              editDraft(text);
              setDraftNotice("");
              requestAnimationFrame(() => composer.current?.focus());
            }}
          />
          <button
            ref={composerAction}
            type={canStop ? "button" : "submit"}
            className="send-button"
            disabled={canStop ? stopDisabled : !draft.trim() || busy || loading || !ready || moodInvalid || preferencesLoading || paused}
            aria-label={actionLabel}
            title={actionLabel}
            onClick={canStop ? () => void cancel() : undefined}
          >
            {canStop ? <Pause size={18} fill="currentColor" strokeWidth={1.5} aria-hidden="true" /> : <ArrowUp size={20} strokeWidth={2} aria-hidden="true" />}
          </button>
        </form>
      </div>}
    </>
  );
}

function AccountPage({ onGuide }: { onGuide: () => void }) {
  const [accountDeleted, setAccountDeleted] = useState(false);
  if (accountDeleted) return <AccountDeletionComplete />;
  return (
    <div className={cx.reading}>
      <h1 tabIndex={-1} data-tour="personal-account">Tài khoản</h1>
      <AdultEligibility />
      <AccountActions onGuide={onGuide} onDeleted={() => setAccountDeleted(true)} />
    </div>
  );
}
export default function RealApp({ api, callback }: { api: ApiClient; callback: AuthCallback }) {
  return (
    <HashRouter>
      <SessionRoot api={api} callback={callback} />
    </HashRouter>
  );
}
