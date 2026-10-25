import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type FormEvent,
} from "react";
import { Link, useParams } from "react-router-dom";
import { ArrowLeft, Send } from "lucide-react";
import { Button, cx, Dialog } from "../../../components/UI";
import type { components } from "../../../api/generated/schema";
import { ApiError } from "../../../api/client";
import { ErrorNotice, useResource, useSession } from "../RealApp";
import { ConnectionSafety } from "../Safety";
import { useConnectionEvents } from "./useConnectionEvents";
import { looksLikeContact } from "./pii";
import { ActivityCatalog, ActivityEntryButton } from "../activities/ActivityCatalog";
import { ActivityDock } from "../activities/ActivityDock";
import { HistoryCard, InviteCard } from "../activities/InviteCard";
import { useActivity } from "../activities/useActivity";
import { useOnline } from "../OfflineBanner";

type Schema = components["schemas"];
type ConnectionView = Schema["ConnectionView"];
type Message = Schema["MessageView"];
type Page = Schema["MessagePage"];

const REVOKED = [403, 404, 410];
const UNAVAILABLE =
  "Cuộc trò chuyện này không còn khả dụng. Kết nối có thể đã kết thúc, bị chặn, hoặc một bên đã tắt quyền tìm bạn.";

export function HumanChat() {
  const { connectionId } = useParams();
  const { api } = useSession();
  const [room, setRoom] = useState<ConnectionView>(),
    [messages, setMessages] = useState<Message[]>([]);
  const [draft, setDraft] = useState(""),
    [error, setError] = useState<unknown>(),
    [busy, setBusy] = useState(false),
    [ready, setReady] = useState(false);
  // closed: this tab no longer has access, so nothing is polled or streamed.
  const [closed, setClosed] = useState<string>();
  // Messages this user saw before they blocked or ended, kept only for a report.
  const [evidence, setEvidence] = useState<Message[]>();
  const [ending, setEnding] = useState(false);
  const intent = useRef<{ text: string; id: string } | undefined>(undefined),
    cursor = useRef("0"),
    lastRead = useRef("0");
  const [visible, setVisible] = useState(
    () => document.visibilityState === "visible",
  );
  const loading = useRef(false),
    revoked = useRef(false),
    lastRefresh = useRef(0),
    log = useRef<HTMLDivElement>(null);
  // The last history this tab showed; the event stream may revoke access (and
  // clear the view) before the user's own block/end request has returned.
  const seen = useRef<Message[]>([]);
  useEffect(() => {
    if (messages.length) seen.current = messages;
  }, [messages]);
  const revoke = useCallback((reason: string, own = false) => {
    revoked.current = true;
    setMessages([]);
    setRoom(undefined);
    setReady(false);
    // The user's own action explains the closure best; a server-side revocation
    // arriving in the same moment must not replace it.
    setClosed((current) => (own ? reason : (current ?? reason)));
  }, []);
  const refresh = useCallback(async () => {
    if (loading.current || revoked.current) return;
    loading.current = true;
    lastRefresh.current = Date.now();
    try {
      const access = await api.request<ConnectionView>(
        `/connections/${connectionId}`,
      );
      setRoom(access);
      let more = true;
      while (more) {
        const page = await api.request<Page>(
          `/connections/${connectionId}/messages?afterSeq=${cursor.current}`,
        );
        if (page.messages.length) {
          cursor.current = page.messages.at(-1)!.seq;
          setMessages((current) =>
            [
              ...new Map(
                [...current, ...page.messages].map((message) => [
                  message.id,
                  message,
                ]),
              ).values(),
            ].sort((a, b) => (BigInt(a.seq) < BigInt(b.seq) ? -1 : 1)),
          );
        }
        more =
          page.messages.length > 0 &&
          BigInt(cursor.current) < BigInt(page.highWaterSeq);
      }
      setReady(true);
      setError(undefined);
    } catch (reason) {
      if (reason instanceof ApiError && REVOKED.includes(reason.status)) {
        setError(undefined);
        revoke(UNAVAILABLE);
      } else {
        setError(reason);
        setReady(false);
      }
    } finally {
      loading.current = false;
    }
  }, [api, connectionId, revoke]);
  useEffect(() => {
    const change = () => setVisible(document.visibilityState === "visible");
    document.addEventListener("visibilitychange", change);
    return () => document.removeEventListener("visibilitychange", change);
  }, []);
  // Private read marker (never shown to the peer): the log keeps the newest
  // message in view, so mark it read once the tab is visible for a second.
  useEffect(() => {
    const newest = messages.at(-1)?.seq;
    if (!newest || closed || !visible) return;
    if (BigInt(newest) <= BigInt(lastRead.current)) return;
    const timer = window.setTimeout(() => {
      const previous = lastRead.current;
      lastRead.current = newest;
      api
        .request(`/connections/${connectionId}/read`, {
          method: "POST",
          body: { seq: newest } satisfies Schema["ReadInput"],
        })
        .catch(() => {
          lastRead.current = previous;
        });
    }, 1000);
    return () => window.clearTimeout(timer);
  }, [messages, closed, visible, api, connectionId]);
  useEffect(() => {
    cursor.current = "0";
    lastRead.current = "0";
    revoked.current = false;
    seen.current = [];
    setClosed(undefined);
    setEvidence(undefined);
    setMessages([]);
    setReady(false);
    void refresh();
    // Fallback polling: every 3s while the event stream is down, otherwise a
    // slow 15s safety net for anything the stream could have missed.
    const timer = setInterval(() => {
      if (document.visibilityState !== "visible" || revoked.current) return;
      const interval = streamHealthy.current ? 15_000 : 3_000;
      if (Date.now() - lastRefresh.current >= interval - 100) void refresh();
    }, 3000);
    return () => clearInterval(timer);
  }, [refresh]);
  const streamHealthy = useConnectionEvents(connectionId, {
    onMessages: () => void refresh(),
    onActivity: () => void activity.refresh(),
    onRevoked: () => revoke(UNAVAILABLE),
    onError: () => void refresh(),
    afterSeq: () => cursor.current,
    stopped: () => revoked.current,
  });
  const activity = useActivity(connectionId, streamHealthy, !closed);
  const [catalogOpen, setCatalogOpen] = useState(false);
  const [advising, setAdvising] = useState(false);
  const advised = useRef("");
  const composer = useRef<HTMLTextAreaElement>(null);
  const online = useOnline();
  const wasOnline = useRef(online);
  useEffect(() => {
    // Catch up once when the connection returns; the stream may have missed events.
    if (online && !wasOnline.current) void refresh();
    wasOnline.current = online;
  }, [online, refresh]);
  const alias = room?.alias || "bạn kia";
  const docked =
    !closed && Boolean(activity.session) && activity.session?.state !== "invited";
  // The last ten finished sessions sit in the log where they ended (H-02); the
  // current one is shown by its own card.
  const history = useResource<Schema["ActivitySessionView"][]>(
    `/connections/${connectionId}/activities?limit=10`,
    ready && !closed,
  );
  const { refresh: refreshHistory } = history;
  const ended =
    activity.session && !["invited", "active", "paused"].includes(activity.session.state);
  useEffect(() => {
    if (ended) refreshHistory();
  }, [ended, activity.session?.id, refreshHistory]);
  const timeline = [
    ...messages.map((message) => ({ at: message.acceptedAt, message, past: undefined })),
    ...(history.data ?? [])
      .filter((past) => past.id !== activity.session?.id)
      .map((past) => ({ at: past.endedAt ?? past.createdAt, message: undefined, past })),
  ].sort((a, b) => Date.parse(a.at) - Date.parse(b.at));
  useEffect(() => {
    log.current?.scrollTo({ top: log.current.scrollHeight });
  }, [messages.length]);
  async function send(event: FormEvent) {
    event.preventDefault();
    if (!ready || busy || closed || !draft.trim() || !online) return;
    // Advisory only (I-06): never blocks, never leaves the browser.
    if (looksLikeContact(draft) && advised.current !== draft.trim()) {
      setAdvising(true);
      return;
    }
    setBusy(true);
    setError(undefined);
    if (intent.current?.text !== draft.trim())
      intent.current = { text: draft.trim(), id: crypto.randomUUID() };
    try {
      const receipt = await api.request<Message>(
        `/connections/${connectionId}/messages`,
        {
          method: "POST",
          body: {
            text: intent.current.text,
            clientMessageId: intent.current.id,
          } satisfies Schema["MessageInput"],
        },
      );
      setMessages((current) => [
        ...new Map(
          [...current, receipt].map((message) => [message.id, message]),
        ).values(),
      ]);
      setDraft("");
      intent.current = undefined;
      void refresh();
    } catch (reason) {
      // The typed text stays in the composer; a stale tab learns it lost access.
      setError(reason);
      if (reason instanceof ApiError && REVOKED.includes(reason.status))
        void refresh();
    } finally {
      setBusy(false);
    }
  }
  const leave = (reason: string) => {
    setEvidence(seen.current);
    revoke(reason, true);
  };
  return (
    <div
      className="bot-conversation real-human-chat"
      data-dock={docked || undefined}
    >
      <header className="conversation-header">
        <Link to="/messages" className="icon-button" aria-label="Về tin nhắn">
          <ArrowLeft size={20} />
        </Link>
        <h1 tabIndex={-1}>{room?.alias || "Cuộc trò chuyện"}</h1>
      </header>
      <ErrorNotice
        error={error}
        retry={closed ? undefined : () => void refresh()}
      />
      {closed && (
        <div className={cx.note} role="status">
          <p>{closed}</p>
          <p>Bạn không thể gửi thêm tin nhắn trong cuộc trò chuyện này.</p>
          <Link to="/messages">Về danh sách tin nhắn</Link>
        </div>
      )}
      {!closed && !ready && !error && (
        <p role="status">Đang tải cuộc trò chuyện…</p>
      )}
      <div
        className="conversation-log"
        ref={log}
        role="log"
        aria-label="Tin nhắn trong kết nối"
      >
        {ready && messages.length === 0 && (
          <p className={cx.footnote}>Hãy bắt đầu bằng một lời hỏi thăm.</p>
        )}
        {timeline.map(({ message, past }) =>
          message ? (
            <div
              className={`message-row ${message.sender === "self" ? "from-self" : "from-bot"}`}
              key={message.id}
            >
              <div className="message-content">
                <div className="chat-bubble">
                  <p>{message.text}</p>
                </div>
              </div>
            </div>
          ) : (
            past && <HistoryCard key={past.id} session={past} alias={alias} />
          ),
        )}
        {!closed && activity.session && (
          <InviteCard
            session={activity.session}
            alias={alias}
            catalog={activity.catalog}
            busy={activity.busy}
            onAccept={() => void activity.act("accept")}
            onDecline={() => void activity.act("decline")}
            onCancel={() => void activity.act("cancel")}
          />
        )}
        {!closed && activity.session?.state === "invited" && activity.notice && (
          <p role="status">{activity.notice}</p>
        )}
      </div>
      {docked && (
        <ActivityDock
          activity={activity}
          alias={alias}
          onContinue={() => composer.current?.focus()}
        />
      )}
      <form className="bot-composer" onSubmit={send}>
        {ready && !closed && activity.catalog.length > 0 && (
          <ActivityEntryButton
            disabled={activity.open || activity.busy}
            onOpen={() => setCatalogOpen(true)}
          />
        )}
        <textarea
          ref={composer}
          rows={1}
          maxLength={500}
          aria-label="Tin nhắn cho bạn kết nối"
          placeholder={
            closed ? "Cuộc trò chuyện đã đóng" : "Gửi một lời hỏi thăm…"
          }
          value={draft}
          disabled={Boolean(closed)}
          onChange={(event) => setDraft(event.target.value)}
        />
        <button
          className="send-button"
          type="submit"
          disabled={!ready || busy || Boolean(closed) || !draft.trim() || !online}
          title={online ? undefined : "Đang mất kết nối mạng"}
          aria-label="Gửi tin nhắn"
        >
          <Send size={20} />
        </button>
      </form>
      {advising && (
        <Dialog
          title="Tin nhắn có vẻ chứa thông tin liên hệ"
          onClose={() => setAdvising(false)}
        >
          <p>
            Bạn chắc chắn muốn chia sẻ? Chỉ nên gửi số điện thoại, email hay liên
            kết khi bạn đã đủ tin tưởng người kia.
          </p>
          <div className={cx.actions}>
            <Button
              variant="secondary"
              onClick={() => {
                setAdvising(false);
                composer.current?.focus();
              }}
            >
              Sửa lại
            </Button>
            <Button
              onClick={() => {
                advised.current = draft.trim();
                setAdvising(false);
                composer.current?.form?.requestSubmit();
              }}
            >
              Vẫn gửi
            </Button>
          </div>
        </Dialog>
      )}
      {catalogOpen && (
        <ActivityCatalog
          catalog={activity.catalog}
          current={activity.open ? activity.session : null}
          cooldown={activity.cooldown}
          busy={activity.busy}
          onInvite={(kind, options) =>
            void activity.invite(kind, options).then((sent) => {
              if (sent) setCatalogOpen(false);
            })
          }
          onClose={() => setCatalogOpen(false)}
        />
      )}
      {room && !closed && (
        <Button variant="text" disabled={busy} onClick={() => setEnding(true)}>
          Kết thúc kết nối
        </Button>
      )}
      {ending && room && (
        <Dialog
          title="Kết thúc kết nối này?"
          destructive
          onClose={() => !busy && setEnding(false)}
        >
          <p>
            Cả hai sẽ không thể gửi thêm tin nhắn trong cuộc trò chuyện này, và
            hai bạn sẽ không được gợi ý lại cho nhau trong 30 ngày.
          </p>
          <div className={cx.actions}>
            <Button
              variant="secondary"
              data-cancel
              disabled={busy}
              onClick={() => setEnding(false)}
            >
              Giữ kết nối
            </Button>
            <Button
              variant="danger"
              disabled={busy}
              onClick={() => {
                setBusy(true);
                void api
                  .request(`/connections/${connectionId}/end`, {
                    method: "POST",
                    body: { expectedVersion: room.version },
                  })
                  .then(() => {
                    setEnding(false);
                    leave("Bạn đã kết thúc kết nối này.");
                  })
                  .catch(setError)
                  .finally(() => setBusy(false));
              }}
            >
              Xác nhận kết thúc
            </Button>
          </div>
        </Dialog>
      )}
      {room && connectionId && !closed && (
        <ConnectionSafety
          connectionId={connectionId}
          messages={messages}
          onBlocked={() => leave("Bạn đã chặn kết nối này.")}
        />
      )}
      {closed && evidence && connectionId && (
        <ConnectionSafety
          connectionId={connectionId}
          messages={evidence}
          onBlocked={() => undefined}
          reportOnly
        />
      )}
    </div>
  );
}
