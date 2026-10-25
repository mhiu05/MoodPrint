import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type FormEvent,
} from "react";
import { Link, useParams } from "react-router-dom";
import { ArrowLeft, Send } from "lucide-react";
import { Button, cx, Dialog, StatePanel } from "../../components/UI";
import type { components } from "../../api/generated/schema";
import { ApiError } from "../../api/client";
import { ErrorNotice, useResource, useSession } from "./RealApp";
import { ConnectionSafety } from "./Safety";
import { CandidateCard } from "./social/CandidateCard";
import { ProfileEditor } from "./social/ProfileEditor";
import { RequestCard } from "./social/RequestCard";
import { previewLine, relativeTime } from "./social/format";
import { badgeText } from "./social/useSocialSummary";
import { useConnectionEvents } from "./social/useConnectionEvents";
import { ActivityCatalog, ActivityEntryButton } from "./activities/ActivityCatalog";
import { ActivityDock } from "./activities/ActivityDock";
import { InviteCard } from "./activities/InviteCard";
import { useActivity } from "./activities/useActivity";

type Schema = components["schemas"];
type Draft = Schema["DraftView"];
type Published = Schema["PublishedView"];
type Taxonomy = Schema["TaxonomyDTO"];
type RequestView = Schema["RequestView"];
type ConnectionView = Schema["ConnectionView"];
type Message = Schema["MessageView"];
type Page = Schema["MessagePage"];


export function Discovery() {
  const { api, session } = useSession();
  const canMatch =
    session.features.matching &&
    session.ageBand === "adult" &&
    session.consents.MATCH.enabled;
  const draft = useResource<Draft>("/profiles/matching-draft");
  const taxonomy = useResource<Taxonomy>("/taxonomy");
  const published = useResource<Published | null>(
    "/profiles/published/current",
  );
  const suggestions = useResource<Schema["CandidateListDTO"]>(
    "/matching/candidates",
    canMatch,
  );
  const requests = useResource<RequestView[]>("/connection-requests", canMatch);
  useEffect(() => {
    if (!canMatch) return;
    const timer = setInterval(() => {
      if (document.visibilityState === "visible") requests.refresh();
    }, 5000);
    return () => clearInterval(timer);
  }, [requests.refresh, canMatch]);
  const [editing, setEditing] = useState(false),
    [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(),
    [notice, setNotice] = useState("");
  const [blocking, setBlocking] = useState<string>();
  const [sent, setSent] = useState<string[]>([]);
  const live = published.data?.state === "live";
  const refresh = () => {
    published.refresh();
    suggestions.refresh();
    requests.refresh();
  };
  async function act(action: () => Promise<unknown>, success: string) {
    if (busy) return;
    setBusy(true);
    setError(undefined);
    setNotice("");
    try {
      await action();
      setNotice(success);
      refresh();
    } catch (reason) {
      setError(reason);
    } finally {
      setBusy(false);
    }
  }
  const label = (key: string) =>
    (taxonomy.data &&
      {
        ...taxonomy.data.interests,
        ...taxonomy.data.values,
        ...taxonomy.data.styles,
        ...taxonomy.data.goals,
        ...taxonomy.data.languages,
        ...taxonomy.data.activities,
        ...taxonomy.data.availability,
      }[key]) ||
    key;
  if (!session.features.matching)
    return (
      <StatePanel title="Tìm bạn chưa khả dụng">
        Dịch vụ tìm bạn chưa sẵn sàng. Bạn có thể tiếp tục ghi lại cảm xúc.
      </StatePanel>
    );
  if (session.ageBand !== "adult")
    return (
      <StatePanel title="Tính năng kết nối chưa khả dụng">
        Tìm bạn và nhắn tin người thật dành cho người đã đủ 18 tuổi.
      </StatePanel>
    );
  return (
    <div className={cx.reading}>
      <h1 tabIndex={-1}>Tìm bạn đồng điệu</h1>
      <p className={cx.lede}>
        Bắt đầu từ những điểm chung bạn chủ động chia sẻ.
      </p>
      <ErrorNotice
        error={error || draft.error || taxonomy.error || published.error}
        retry={() => {
          draft.refresh();
          taxonomy.refresh();
          refresh();
        }}
      />
      {notice && <p role="status">{notice}</p>}
      {!session.consents.MATCH.enabled && (
        <StatePanel title="Bạn đang tắt quyền tìm bạn">
          <Link to="/settings">Xem quyền tìm bạn</Link>
        </StatePanel>
      )}
      {!editing && (
        <Button
          variant="secondary"
          disabled={!draft.data || !taxonomy.data}
          onClick={() => setEditing(true)}
        >
          Chỉnh hồ sơ kết nối
        </Button>
      )}
      {editing && taxonomy.data && draft.data && (
        <ProfileEditor
          taxonomy={taxonomy.data}
          draft={draft.data}
          published={published.data}
          onDraft={(saved) => draft.setData(saved)}
          onPublished={(result) => {
            published.setData(result);
            draft.setData(
              (previous) =>
                previous && { ...previous, publishedVersion: result.profileVersion },
            );
            setEditing(false);
            setNotice("Đã xuất bản hồ sơ.");
            suggestions.refresh();
            requests.refresh();
          }}
          onClose={() => setEditing(false)}
        />
      )}
      {published.data && (
        <section className="real-section">
          <h2>{live ? "Hồ sơ đang chia sẻ" : "Hồ sơ đang tạm ẩn"}</h2>
          {published.data.state === "needs_republish" && (
            <p className={cx.note}>
              Hồ sơ này không xuất hiện trong gợi ý (ví dụ sau khi bạn tắt rồi
              bật lại quyền tìm bạn). Hãy xem lại và xuất bản lại nếu bạn muốn
              chia sẻ tiếp; hệ thống không tự chia sẻ lại.
            </p>
          )}
          {published.data.state === "stale" && (
            <p className={cx.note}>
              Hồ sơ tạm ẩn vì lâu chưa cập nhật. Mở “Chỉnh hồ sơ kết nối”, xem
              lại và xuất bản để xác nhận hồ sơ vẫn đúng.
            </p>
          )}
          <p>
            {[
              ...(published.data.profile.interests || []),
              ...(published.data.profile.values || []),
            ]
              .map(label)
              .join(" · ")}
          </p>
          <Button
            variant="text"
            disabled={busy}
            onClick={() =>
              void act(async () => {
                await api.request("/profiles/published/current", {
                  method: "DELETE",
                  body: { expectedVersion: published.data!.profileVersion },
                });
                published.setData(null);
                draft.refresh();
              }, "Đã ngừng chia sẻ hồ sơ.")
            }
          >
            Ngừng chia sẻ hồ sơ
          </Button>
        </section>
      )}
      {canMatch && (
        <section className="real-section">
          <h2>Người cùng điểm chung</h2>
          <Button
            variant="text"
            disabled={suggestions.loading}
            onClick={suggestions.refresh}
          >
            Tải lại gợi ý
          </Button>
          {suggestions.loading && <p role="status">Đang tìm điểm chung…</p>}
          {!suggestions.loading && !live && (
            <p>Hãy xuất bản hồ sơ kết nối để nhận gợi ý.</p>
          )}
          {Boolean(suggestions.error) && live && (
            <ErrorNotice
              error={suggestions.error}
              retry={suggestions.refresh}
            />
          )}
          {suggestions.data?.candidates.length === 0 && (
            <p>Chưa có gợi ý phù hợp.</p>
          )}
          <div className="peer-grid">
            {suggestions.data?.candidates.map((candidate) => (
              <CandidateCard
                key={candidate.candidateRef}
                card={candidate}
                label={label}
                busy={busy}
                sent={sent.includes(candidate.candidateRef)}
                onGreet={() =>
                  void act(async () => {
                    await api.request("/connection-requests", {
                      method: "POST",
                      body: { candidateRef: candidate.candidateRef },
                    });
                    setSent((value) => [...value, candidate.candidateRef]);
                  }, "Đã gửi lời mời.")
                }
                onSkip={() =>
                  void act(
                    () =>
                      api.request("/matching/skips", {
                        method: "POST",
                        body: { candidateRef: candidate.candidateRef },
                      }),
                    "Đã bỏ qua gợi ý.",
                  )
                }
                onBlock={() => setBlocking(candidate.candidateRef)}
              />
            ))}
          </div>
          {Boolean(suggestions.data?.candidates.length) && (
            <p className="discovery-footnote">
              Gợi ý dựa trên những điểm chung bạn và họ tự chọn chia sẻ — không
              phải đánh giá mức độ hợp nhau.
            </p>
          )}
        </section>
      )}
      {blocking && (
        <Dialog
          title="Chặn người này?"
          destructive
          onClose={() => !busy && setBlocking(undefined)}
        >
          <p>
            Hai bạn sẽ không được gợi ý cho nhau và không thể gửi lời mời hay
            tin nhắn cho nhau nữa. Việc chặn không thể hoàn tác trong ứng dụng.
          </p>
          <div className={cx.actions}>
            <Button
              variant="secondary"
              data-cancel
              disabled={busy}
              onClick={() => setBlocking(undefined)}
            >
              Không chặn
            </Button>
            <Button
              variant="danger"
              disabled={busy}
              onClick={() =>
                void act(async () => {
                  await api.request("/blocks", {
                    method: "POST",
                    body: { peerRef: blocking },
                  });
                  setBlocking(undefined);
                }, "Đã chặn kết nối.")
              }
            >
              Xác nhận chặn
            </Button>
          </div>
        </Dialog>
      )}
      {canMatch && (
        <section className="real-section">
          <h2>Lời mời kết nối</h2>
          <ErrorNotice error={requests.error} retry={requests.refresh} />
          {requests.data?.length === 0 && <p>Bạn chưa có lời mời nào.</p>}
          {requests.data?.map((item) => (
            <RequestCard
              key={item.id}
              item={item}
              label={label}
              busy={busy}
              onDecide={(row, decision) =>
                void act(
                  () =>
                    api.request(`/connection-requests/${row.id}/${decision}`, {
                      method: "POST",
                      body: { expectedVersion: row.version },
                    }),
                  decision === "accept"
                    ? "Đã kết nối. Bạn có thể bắt đầu trò chuyện."
                    : "Đã cập nhật lời mời.",
                )
              }
            />
          ))}
          <Button variant="text" onClick={requests.refresh}>
            Tải lại lời mời
          </Button>
        </section>
      )}
    </div>
  );
}

export function HumanMessages() {
  const { session } = useSession();
  const enabled = session.ageBand === "adult" && session.consents.MATCH.enabled;
  const rooms = useResource<ConnectionView[]>("/connections", enabled);
  const { refresh } = rooms;
  useEffect(() => {
    if (!enabled) return;
    const timer = setInterval(() => {
      if (document.visibilityState === "visible") refresh();
    }, 15_000);
    return () => clearInterval(timer);
  }, [enabled, refresh]);
  if (session.ageBand !== "adult")
    return (
      <StatePanel title="Tính năng kết nối chưa khả dụng">
        Nhắn tin người thật dành cho người đã đủ 18 tuổi.
      </StatePanel>
    );
  if (!session.consents.MATCH.enabled)
    return (
      <StatePanel title="Bạn đang tắt quyền tìm bạn">
        <Link to="/settings">Xem quyền tìm bạn</Link>
      </StatePanel>
    );
  return (
    <div className={cx.reading}>
      <h1 tabIndex={-1}>Tin nhắn</h1>
      <p className={cx.lede}>Trò chuyện bắt đầu khi cả hai cùng đồng ý.</p>
      <ErrorNotice error={rooms.error} retry={rooms.refresh} />
      {rooms.loading && <p role="status">Đang tải kết nối…</p>}
      {rooms.data?.length === 0 && (
        <p>
          Chưa có cuộc trò chuyện.{" "}
          <Link to="/connect">Tìm người cùng điểm chung</Link>
        </p>
      )}
      {rooms.data?.map((room) => (
        <Link
          className={`${cx.messagePreview} ${room.unreadCount ? cx.messageUnread : ""}`}
          key={room.id}
          to={`/chat/${room.id}`}
        >
          <div>
            <h2>
              {room.alias}
              {room.unreadCount > 0 && (
                <span className={cx.srOnly}>
                  {`, ${room.unreadCount} tin nhắn chưa đọc`}
                </span>
              )}
            </h2>
            <p>{previewLine(room.lastMessagePreview, room.lastMessageSender)}</p>
          </div>
          <div className={cx.messageMeta}>
            {room.lastMessageAt && (
              <time dateTime={room.lastMessageAt}>
                {relativeTime(room.lastMessageAt)}
              </time>
            )}
            {room.unreadCount > 0 && (
              <span className={cx.unreadCount} aria-hidden="true">
                {badgeText(room.unreadCount)}
              </span>
            )}
          </div>
        </Link>
      ))}
      <Button variant="text" onClick={rooms.refresh}>
        Tải lại kết nối
      </Button>
    </div>
  );
}

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
  const composer = useRef<HTMLTextAreaElement>(null);
  const alias = room?.alias || "bạn kia";
  const docked =
    !closed && Boolean(activity.session) && activity.session?.state !== "invited";
  useEffect(() => {
    log.current?.scrollTo({ top: log.current.scrollHeight });
  }, [messages.length]);
  async function send(event: FormEvent) {
    event.preventDefault();
    if (!ready || busy || closed || !draft.trim()) return;
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
        {messages.map((message) => (
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
        ))}
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
          disabled={!ready || busy || Boolean(closed) || !draft.trim()}
          aria-label="Gửi tin nhắn"
        >
          <Send size={20} />
        </button>
      </form>
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
