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
                          draft.data?.publishedVersion ||
                          published.data?.version ||
                          0,
                      } satisfies Schema["PublishInput"],
                    },
                  );
                  published.setData(result);
                  draft.setData(
                    (previous) =>
                      previous && {
                        ...previous,
                        publishedVersion: result.version,
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
          <h2>Hồ sơ đang chia sẻ</h2>
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
                  body: { expectedVersion: published.data!.version },
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
          {Boolean(suggestions.error) && published.data && (
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
                  onClick={() =>
                    void act(
                      () =>
                        api.request("/blocks", {
                          method: "POST",
                          body: { peerRef: candidate.candidateRef },
                        }),
                      "Đã chặn kết nối.",
                    )
                  }
                >
                  Chặn
                </Button>
              </div>
            </article>
          ))}
        </section>
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
              <p>
                {item.status === "pending"
                  ? "Đang chờ phản hồi"
                  : item.status === "accepted"
                    ? "Đã kết nối"
                    : "Lời mời đã kết thúc"}
              </p>
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
  const rooms = useResource<ConnectionView[]>(
    "/connections",
    session.ageBand === "adult" && session.consents.MATCH.enabled,
  );
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

export function HumanChat() {
  const { connectionId } = useParams();
  const { api } = useSession();
  const [room, setRoom] = useState<ConnectionView>(),
    [messages, setMessages] = useState<Message[]>([]);
  const [draft, setDraft] = useState(""),
    [error, setError] = useState<unknown>(),
    [busy, setBusy] = useState(false),
    [ready, setReady] = useState(false);
  const intent = useRef<{ text: string; id: string } | undefined>(undefined),
    cursor = useRef("0");
  const loading = useRef(false),
    log = useRef<HTMLDivElement>(null);
  const refresh = useCallback(async () => {
    if (loading.current) return;
    loading.current = true;
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
      setError(reason);
      setReady(false);
      if (
        reason instanceof ApiError &&
        [401, 403, 404, 410].includes(reason.status)
      ) {
        setMessages([]);
        setRoom(undefined);
      }
    } finally {
      loading.current = false;
    }
  }, [api, connectionId]);
  useEffect(() => {
    cursor.current = "0";
    setMessages([]);
    setReady(false);
    void refresh();
    const timer = setInterval(() => {
      if (document.visibilityState === "visible") void refresh();
    }, 3000);
    return () => clearInterval(timer);
  }, [refresh]);
  useEffect(() => {
    const source = new EventSource(
      `/api/v1/connections/${connectionId}/events?afterSeq=0`,
    );
    source.addEventListener("messages_available", () => void refresh());
    source.addEventListener("access_revoked", () => {
      source.close();
      setMessages([]);
      setRoom(undefined);
      setReady(false);
      setError(
        new ApiError(
          403,
          "CONNECTION_UNAVAILABLE",
          "Kết nối không còn khả dụng. Vui lòng tải lại.",
        ),
      );
    });
    source.onerror = () => {
      source.close();
      void refresh();
    };
    return () => source.close();
  }, [connectionId, refresh]);
  useEffect(() => {
    log.current?.scrollTo({ top: log.current.scrollHeight });
  }, [messages.length]);
  async function send(event: FormEvent) {
    event.preventDefault();
    if (!ready || busy || !draft.trim()) return;
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
      setError(reason);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="bot-conversation real-human-chat">
      <header className="conversation-header">
        <Link to="/messages" className="icon-button" aria-label="Về tin nhắn">
          <ArrowLeft size={20} />
        </Link>
        <h1 tabIndex={-1}>{room?.alias || "Cuộc trò chuyện"}</h1>
      </header>
      <ErrorNotice error={error} retry={() => void refresh()} />
      <div
        className="conversation-log"
        ref={log}
        role="log"
        aria-label="Tin nhắn trong kết nối"
      >
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
          placeholder="Gửi một lời hỏi thăm…"
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
        />
        <button
          className="send-button"
          type="submit"
          disabled={!ready || busy || !draft.trim()}
          aria-label="Gửi tin nhắn"
        >
          <Send size={20} />
        </button>
      </form>
      {room && (
        <Button
          variant="text"
          disabled={busy}
          onClick={() => {
            setBusy(true);
            void api
              .request(`/connections/${connectionId}/end`, {
                method: "POST",
                body: { expectedVersion: room.version },
              })
              .then(() => {
                setReady(false);
                setMessages([]);
                setRoom(undefined);
              })
              .catch(setError)
              .finally(() => setBusy(false));
          }}
        >
          Kết thúc kết nối
        </Button>
      )}
      {room && connectionId && (
        <ConnectionSafety
          connectionId={connectionId}
          messages={messages}
          onBlocked={() => {
            setReady(false);
            setMessages([]);
            setRoom(undefined);
          }}
        />
      )}
    </div>
  );
}
