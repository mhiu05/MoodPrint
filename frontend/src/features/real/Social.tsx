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

type Schema = components["schemas"];
type PublicProfile = Schema["PublicProfile"];
type Draft = Schema["DraftView"];
type Published = Schema["PublishedView"];
type Preview = Schema["PreviewView"];
type Taxonomy = Schema["TaxonomyDTO"];
type RequestView = Schema["RequestView"];
type ConnectionView = Schema["ConnectionView"];
type Message = Schema["MessageView"];
type Page = Schema["MessagePage"];

const requestStatus: Record<string, string> = {
  pending: "Đang chờ phản hồi",
  accepted: "Đã kết nối",
  declined: "Lời mời đã được từ chối",
  cancelled: "Lời mời đã được hủy",
  expired: "Lời mời đã hết hạn",
  invalidated:
    "Lời mời không còn hiệu lực vì quyền tìm bạn hoặc trạng thái kết nối đã thay đổi",
};

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
    [profile, setProfile] = useState<PublicProfile>();
  const [preview, setPreview] = useState<Preview>(),
    [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(),
    [notice, setNotice] = useState("");
  const [blocking, setBlocking] = useState<string>();
  const live =
    Boolean(published.data) && published.data?.state !== "needs_republish";
  useEffect(() => {
    if (draft.data && !profile) setProfile(draft.data.profile);
  }, [draft.data, profile]);
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
  async function save(event: FormEvent) {
    event.preventDefault();
    if (!profile) return;
    const currentProfile = profile;
    await act(async () => {
      const saved = await api.request<Draft>("/profiles/matching-draft", {
        method: "PUT",
        body: {
          ...currentProfile,
          expectedVersion: draft.data?.version || 0,
        } satisfies Schema["DraftInput"],
      });
      draft.setData(saved);
      setPreview(undefined);
    }, "Đã lưu bản nháp.");
  }
  const label = (key: string) =>
    taxonomy.data &&
    ({
      ...taxonomy.data.interests,
      ...taxonomy.data.values,
      ...taxonomy.data.styles,
      ...taxonomy.data.goals,
      ...taxonomy.data.languages,
    }[key] ||
      key);
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
      <Button
        variant="secondary"
        disabled={!draft.data || !taxonomy.data}
        onClick={() => setEditing((value) => !value)}
      >
        Chỉnh hồ sơ kết nối
      </Button>
      {editing && profile && taxonomy.data && (
        <section className="real-section">
          <h2>Những điều bạn muốn chia sẻ</h2>
          <p>
            Hồ sơ kết nối chỉ gồm các lựa chọn dưới đây. Ghi chép riêng và hội
            thoại không được đưa vào hồ sơ.
          </p>
          <form onSubmit={save}>
            {(
              [
                ["interests", "Sở thích · chọn ít nhất 3"],
                ["values", "Giá trị · chọn ít nhất 2"],
                ["languages", "Ngôn ngữ · chọn ít nhất 1"],
              ] as const
            ).map(([kind, title]) => (
              <fieldset className="real-choices" key={kind}>
                <legend>{title}</legend>
                {Object.entries(taxonomy.data![kind]).map(([value, name]) => (
                  <label key={value}>
                    <input
                      type="checkbox"
                      checked={(profile[kind] || []).includes(value)}
                      onChange={(event) => {
                        setPreview(undefined);
                        setProfile({
                          ...profile,
                          [kind]: event.target.checked
                            ? [...(profile[kind] || []), value]
                            : (profile[kind] || []).filter(
                                (tag) => tag !== value,
                              ),
                        });
                      }}
                    />
                    {name}
                  </label>
                ))}
              </fieldset>
            ))}
            {(
              [
                ["style", "Cách trò chuyện", "styles"],
                ["goal", "Bạn đang tìm kiếm", "goals"],
              ] as const
            ).map(([kind, title, source]) => (
              <label className="real-field" key={kind}>
                {title}
                <select
                  value={profile[kind]}
                  onChange={(event) => {
                    setPreview(undefined);
                    setProfile({ ...profile, [kind]: event.target.value });
                  }}
                >
                  {Object.entries(taxonomy.data![source]).map(
                    ([value, name]) => (
                      <option value={value} key={value}>
                        {name}
                      </option>
                    ),
                  )}
                </select>
              </label>
            ))}
            <div className={cx.actions}>
              <Button type="submit" disabled={busy}>
                Lưu bản nháp
              </Button>
              <Button
                variant="secondary"
                disabled={busy || !draft.data?.version}
                onClick={() =>
                  void act(async () => {
                    setPreview(
                      await api.request<Preview>(
                        "/profiles/matching-draft/preview",
                        { method: "POST" },
                      ),
                    );
                  }, "")
                }
              >
                Xem trước hồ sơ
              </Button>
            </div>
          </form>
        </section>
      )}
      {preview && (
        <Dialog
          title="Bạn muốn chia sẻ những điều này?"
          onClose={() => !busy && setPreview(undefined)}
        >
          <p>
            {[
              ...(preview.profile.interests || []),
              ...(preview.profile.values || []),
              ...(preview.profile.languages || []),
              preview.profile.style!,
              preview.profile.goal!,
            ]
              .map(label)
              .join(" · ")}
          </p>
          <p>Chỉ các lựa chọn này sẽ xuất hiện trong gợi ý kết nối.</p>
          {published.data && (
            <p className={cx.note}>
              Các kết nối hiện có vẫn được giữ. Hồ sơ mới chỉ thay đổi những gợi
              ý bạn nhận được.
            </p>
          )}
          <div className={cx.actions}>
            <Button
              variant="secondary"
              disabled={busy}
              onClick={() => setPreview(undefined)}
            >
              Chưa chia sẻ
            </Button>
            <Button
              disabled={busy}
              onClick={() =>
                void act(async () => {
                  const result = await api.request<Published>(
                    "/profiles/published",
                    {
                      method: "POST",
                      body: {
                        draftVersion: preview.draftVersion,
                        previewDigest: preview.previewDigest,
                        expectedPublishedVersion:
                          published.data?.profileVersion ??
                          draft.data?.publishedVersion ??
                          0,
                      } satisfies Schema["PublishInput"],
                    },
                  );
                  published.setData(result);
                  draft.setData(
                    (previous) =>
                      previous && {
                        ...previous,
                        publishedVersion: result.profileVersion,
                      },
                  );
                  setPreview(undefined);
                  setEditing(false);
                }, "Đã xuất bản hồ sơ.")
              }
            >
              Xuất bản hồ sơ
            </Button>
          </div>
        </Dialog>
      )}
      {published.data && (
        <section className="real-section">
          <h2>{live ? "Hồ sơ đang chia sẻ" : "Hồ sơ đang tạm ẩn"}</h2>
          {!live && (
            <p className={cx.note}>
              Hồ sơ này không xuất hiện trong gợi ý (ví dụ sau khi bạn tắt rồi
              bật lại quyền tìm bạn). Hãy xem lại và xuất bản lại nếu bạn muốn
              chia sẻ tiếp; hệ thống không tự chia sẻ lại.
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
          {suggestions.data?.candidates.map((candidate) => (
            <article className="real-item" key={candidate.candidateRef}>
              <h3>{candidate.alias}</h3>
              <p>{candidate.reasons.join(" · ")}</p>
              <p>{candidate.profile.interests?.map(label).join(" · ")}</p>
              <div className={cx.actions}>
                <Button
                  disabled={busy}
                  onClick={() =>
                    void act(
                      () =>
                        api.request("/connection-requests", {
                          method: "POST",
                          body: { candidateRef: candidate.candidateRef },
                        }),
                      "Đã gửi lời mời.",
                    )
                  }
                >
                  Gửi lời chào
                </Button>
                <Button
                  variant="text"
                  disabled={busy}
                  onClick={() =>
                    void act(
                      () =>
                        api.request("/matching/skips", {
                          method: "POST",
                          body: { candidateRef: candidate.candidateRef },
                        }),
                      "Đã bỏ qua gợi ý.",
                    )
                  }
                >
                  Bỏ qua
                </Button>
                <Button
                  variant="text"
                  disabled={busy}
                  onClick={() => setBlocking(candidate.candidateRef)}
                >
                  Chặn
                </Button>
              </div>
            </article>
          ))}
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
            <article className="real-item" key={item.id}>
              <h3>
                {item.direction === "incoming"
                  ? "Một lời chào dành cho bạn"
                  : "Lời chào bạn đã gửi"}
              </h3>
              <p>{requestStatus[item.status] || "Lời mời đã kết thúc"}</p>
              {item.status === "pending" && (
                <div className={cx.actions}>
                  {(item.direction === "incoming"
                    ? [
                        ["accept", "Đồng ý kết nối"],
                        ["decline", "Từ chối"],
                      ]
                    : [["cancel", "Hủy lời mời"]]
                  ).map(([decision, title]) => (
                    <Button
                      key={decision}
                      variant={decision === "accept" ? "primary" : "secondary"}
                      disabled={busy}
                      onClick={() =>
                        void act(
                          () =>
                            api.request(
                              `/connection-requests/${item.id}/${decision}`,
                              {
                                method: "POST",
                                body: { expectedVersion: item.version },
                              },
                            ),
                          decision === "accept"
                            ? "Đã kết nối. Bạn có thể bắt đầu trò chuyện."
                            : "Đã cập nhật lời mời.",
                        )
                      }
                    >
                      {title}
                    </Button>
                  ))}
                </div>
              )}
              {item.connectionId && item.status === "accepted" && (
                <Link to={`/chat/${item.connectionId}`}>
                  Mở cuộc trò chuyện
                </Link>
              )}
            </article>
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
          className={cx.messagePreview}
          key={room.id}
          to={`/chat/${room.id}`}
        >
          <div>
            <h2>{room.alias}</h2>
            <p>Mở cuộc trò chuyện</p>
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
    cursor = useRef("0");
  const loading = useRef(false),
    revoked = useRef(false),
    streamHealthy = useRef(false),
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
    cursor.current = "0";
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
  useEffect(() => {
    let source: EventSource | undefined,
      retry: number | undefined,
      attempt = 0,
      stopped = false;
    const connect = () => {
      if (stopped || revoked.current) return;
      // Resume from the newest message this tab has, so nothing is skipped.
      source = new EventSource(
        `/api/v1/connections/${connectionId}/events?afterSeq=${cursor.current}`,
      );
      source.addEventListener("messages_available", () => {
        attempt = 0;
        streamHealthy.current = true;
        void refresh();
      });
      source.addEventListener("access_revoked", () => {
        source?.close();
        streamHealthy.current = false;
        stopped = true;
        revoke(UNAVAILABLE);
      });
      source.onerror = () => {
        source?.close();
        streamHealthy.current = false;
        void refresh();
        attempt += 1;
        retry = window.setTimeout(
          connect,
          Math.min(30_000, 1000 * 2 ** attempt),
        );
      };
    };
    connect();
    return () => {
      stopped = true;
      streamHealthy.current = false;
      window.clearTimeout(retry);
      source?.close();
    };
  }, [connectionId, refresh, revoke]);
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
    <div className="bot-conversation real-human-chat">
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
      </div>
      <form className="bot-composer" onSubmit={send}>
        <textarea
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
