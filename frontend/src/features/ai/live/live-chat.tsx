import {
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import {
  Link,
  useNavigate,
  useParams,
  useSearchParams,
} from "react-router-dom";
import {
  ArrowLeft,
  ArrowRight,
  LifeBuoy,
  MessageCircle,
  Plus,
  Send,
  Square,
} from "lucide-react";
import { Button, EmptyState, Notice, PageHeader } from "../../../components/ui";
import { AgentStatusOrb } from "../../../animations/AgentStatusOrb";
import type {
  LiveCompanion,
  ConversationSummary,
} from "../../../services/composition/companion-types";
import { ApprovalDialog } from "./approval-dialog";
import { CitationChips } from "./citation-chips";
import { MemoryCandidates } from "./memory-panel";
import { useLiveChat, type LiveMessage } from "./use-live-chat";
import { describeFailure } from "./use-live-chat";
import { hydrateWorkspace } from "../../../services/workspace";
import { formatDate } from "../../../lib/utils";
import { useWorkspaceStore } from "../../../app/store";
import { MessageList } from "../chat-presentation";
import "./live.css";

export function UrgentBlock() {
  return (
    <aside className="live-urgent" role="note" aria-label="Hỗ trợ khẩn cấp">
      <strong>Nếu bạn đang gặp nguy hiểm ngay lúc này</strong>
      <p>
        Hãy đến chỗ có người lớn bạn tin hoặc nhờ họ ở cạnh bạn. Tổng đài quốc
        gia bảo vệ trẻ em 111 miễn phí, 24/24.
      </p>
      <div className="actions">
        <a className="button" href="tel:111">
          Gọi 111
        </a>
        <Link className="button secondary" to="/support/urgent">
          Xem cách nhờ giúp đỡ
        </Link>
      </div>
    </aside>
  );
}

export function LiveMessageView({ message }: { message: LiveMessage }) {
  return (
    <li className={`live-message live-${message.role}`}>
      <div className="live-bubble" data-testid={`live-${message.role}`}>
        {message.role === "assistant" && (
          <span className="live-author">AI · không phải người thật</span>
        )}
        {/* Plain text only: model and citation text are never interpreted as HTML. */}
        <p className="live-text">
          {message.content || (message.streaming ? "…" : "")}
        </p>
        <CitationChips citations={message.citations} />
      </div>
      {message.urgency === "immediate" && <UrgentBlock />}
    </li>
  );
}

export function Thread({
  service,
  conversationId,
  heading = "Trò chuyện với AI",
  banner,
  withMemory = true,
  onSettled,
  navigation,
}: {
  service: LiveCompanion;
  conversationId: string;
  heading?: string;
  banner?: ReactNode;
  withMemory?: boolean;
  onSettled?: () => void;
  navigation?: ReactNode;
}) {
  const chat = useLiveChat(service, conversationId);
  const [draft, setDraft] = useState("");
  const [deferred, setDeferred] = useState<string | null>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const busy = chat.status === "streaming" || chat.status === "recovering";
  useLayoutEffect(() => {
    const input = inputRef.current;
    if (!input) return;
    const resize = () => {
      input.style.height = "auto";
      input.style.height = `${Math.min(input.scrollHeight || 44, 140)}px`;
    };
    resize();
    if (typeof ResizeObserver === "undefined") return;
    let width = input.clientWidth;
    const observer = new ResizeObserver(() => {
      if (input.clientWidth === width) return;
      width = input.clientWidth;
      resize();
    });
    observer.observe(input);
    return () => observer.disconnect();
  }, [draft]);
  // The dialog is open for any approval the user has not deferred; no effect needed.
  const dialog =
    chat.approval !== null && deferred !== chat.approval.approvalId;
  // Suggestions are re-read whenever a run settles (the candidate exists only after the tool ran).
  const memoryKey = `${chat.messages.length}:${chat.status}`;
  useEffect(() => {
    if (chat.status === "idle") onSettled?.();
  }, [chat.status, onSettled]);
  const submit = async () => {
    const text = draft.trim();
    if (!text || busy || chat.status === "awaiting_approval") return;
    setDraft("");
    await chat.send(text);
  };
  const orb = chat.tools.some((t) => !t.done)
    ? "searching"
    : chat.status === "streaming"
      ? "responding"
      : chat.status === "failed"
        ? "error"
        : "idle";
  return (
    <section
      className="live-thread"
      data-testid="chat-live"
      aria-label="Trò chuyện với AI"
    >
      <header className="live-thread-head">
        {navigation}
        <AgentStatusOrb state={orb} size={32} showLabel={false} />
        <div className="live-thread-identity">
          <h2>{heading}</h2>
          <small>
            AI Companion ·{" "}
            {busy
              ? "Đang phản hồi…"
              : chat.status === "awaiting_approval"
                ? "Chờ bạn duyệt"
                : "Không phải người thật"}
          </small>
        </div>
        <Link
          className="button ghost icon-button"
          to="/support/urgent"
          aria-label="Tìm hỗ trợ ngay"
        >
          <LifeBuoy size={20} />
        </Link>
      </header>
      {banner && <div className="live-thread-context">{banner}</div>}
      <MessageList
        sessionKey={conversationId}
        revision={`${chat.messages.length}:${chat.messages.at(-1)?.content.length ?? 0}:${chat.status}:${chat.tools.length}`}
        lastSpeaker={chat.messages.at(-1)?.role === "user" ? "user" : "ai"}
      >
        {chat.status === "recovering" && chat.loaded && (
          <p role="status">
            Đang khôi phục lượt trò chuyện. Bạn có thể dừng nếu không muốn chờ.
          </p>
        )}
        <ol className="live-messages">
          {!chat.loaded && (
            <li className="live-hint">Đang tải cuộc trò chuyện…</li>
          )}
          {chat.loaded && !chat.messages.length && (
            <li className="live-hint">
              <AgentStatusOrb state="idle" size={32} showLabel={false} />
              <h3>Bạn muốn kể điều gì?</h3>
              <p>
                Có thể bắt đầu từ một câu. Bạn quyết định điều nào được lưu.
              </p>
            </li>
          )}
          {chat.messages
            .filter((message) => !message.streaming || message.content)
            .map((message) => (
              <LiveMessageView key={message.id} message={message} />
            ))}
        </ol>
        {chat.status === "streaming" &&
          !chat.messages.some(
            (message) => message.streaming && message.content,
          ) && (
            <div
              className="live-working"
              role="status"
              aria-label="AI đang phản hồi"
            >
              <AgentStatusOrb state="processing" size={20} showLabel={false} />
              <span>Đang phản hồi…</span>
            </div>
          )}
        {chat.tools.length > 0 && (
          <ul className="live-tools" aria-label="AI đang làm">
            {chat.tools.map((tool) => (
              <li key={tool.callId} data-done={tool.done} data-ok={tool.ok}>
                {tool.label}
                {tool.done ? (tool.ok === false ? " · chưa được" : " ✓") : "…"}
              </li>
            ))}
          </ul>
        )}
        {chat.error && (
          <div className="live-error" role="alert">
            <span>{chat.error.message}</span>
            {chat.canRetry && chat.error.retryable && (
              <Button variant="secondary" onClick={() => void chat.retry()}>
                Thử lại
              </Button>
            )}
          </div>
        )}
        {chat.approval && !dialog && (
          <Notice>
            Có một đề xuất đang chờ bạn quyết định.{" "}
            <button className="link-button" onClick={() => setDeferred(null)}>
              Xem đề xuất
            </button>
            <Button variant="ghost" onClick={() => void chat.stop()}>
              Hủy lượt này
            </Button>
          </Notice>
        )}
        {chat.approval && (
          <ApprovalDialog
            approval={chat.approval}
            open={dialog}
            onDefer={() => {
              setDeferred(chat.approval?.approvalId ?? null);
              chat.dismissApproval();
            }}
            onDecide={(decision) => {
              void chat
                .decide(decision)
                .then(() => hydrateWorkspace({ background: true }))
                .catch(() => undefined);
            }}
          />
        )}
        {withMemory && (
          <MemoryCandidates service={service} refreshKey={memoryKey} />
        )}
      </MessageList>
      <footer className="live-composer-zone">
        <form
          className="live-composer"
          aria-label="Soạn tin nhắn"
          onSubmit={(event) => {
            event.preventDefault();
            void submit();
          }}
        >
          <label className="sr-only" htmlFor="live-input">
            Điều bạn muốn kể
          </label>
          <textarea
            id="live-input"
            ref={inputRef}
            value={draft}
            rows={1}
            maxLength={4000}
            placeholder="Viết điều bạn muốn nói…"
            aria-describedby="live-chat-note"
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={(event) => {
              if (
                event.key === "Enter" &&
                !event.shiftKey &&
                !event.nativeEvent.isComposing &&
                event.keyCode !== 229
              ) {
                event.preventDefault();
                void submit();
              }
            }}
          />
          {chat.status === "streaming" ||
          (chat.status === "recovering" && chat.loaded) ? (
            <Button
              type="button"
              variant="secondary"
              className="icon-button"
              aria-label="Dừng phản hồi"
              onClick={() => void chat.stop()}
            >
              <Square size={16} />
            </Button>
          ) : (
            <Button
              type="submit"
              className="icon-button"
              aria-label="Gửi"
              disabled={
                !draft.trim() || busy || chat.status === "awaiting_approval"
              }
            >
              <Send size={18} />
            </Button>
          )}
        </form>
        <p id="live-chat-note" className="live-chat-note">
          AI có thể sai. Với chuyện nghiêm trọng, hãy nói với người lớn bạn tin.
        </p>
      </footer>
    </section>
  );
}

export function LiveChatPage({ service }: { service: LiveCompanion }) {
  const { sessionId: id } = useParams();
  const [query] = useSearchParams();
  const [selectedCaseId, setSelectedCaseId] = useState(
    query.get("caseId") ?? "",
  );
  const user = useWorkspaceStore((s) => s.user);
  const cases = useWorkspaceStore((s) => s.cases).filter(
    (c) => c.ownerId === user?.id,
  );
  const navigate = useNavigate();
  const [items, setItems] = useState<ConversationSummary[] | null>(null);
  const [failed, setFailed] = useState(false);
  const [reload, setReload] = useState(0);
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState("");
  const selectedCase = cases.find((c) => c.id === selectedCaseId);
  const linkedCaseId = items?.find((item) => item.id === id)?.linkedCaseId;
  const linkedCase = cases.find((c) => c.id === linkedCaseId);
  useEffect(() => {
    let current = true;
    service.conversations
      .list()
      .then((list) => {
        if (current) {
          setItems(list);
          setFailed(false);
        }
      })
      .catch(() => {
        if (current) setFailed(true); // a failed API never falls back to sample chats
      });
    return () => {
      current = false;
    };
  }, [service, reload]);
  const create = async () => {
    if (creating) return;
    setCreating(true);
    setCreateError("");
    try {
      const created = await service.conversations.create({
        id: globalThis.crypto.randomUUID(),
        title: "",
        ...(selectedCase ? { linkedCaseId: selectedCase.id } : {}),
      });
      setItems((current) => [...(current ?? []), created]);
      navigate(`/ai/chat/${created.id}`);
    } catch (cause) {
      setCreateError(
        describeFailure((cause as { code?: string }).code ?? "network_error"),
      );
    } finally {
      setCreating(false);
    }
  };
  return (
    <div className="live-chat-page">
      {!id && (
        <nav className="live-navigation" aria-label="Điều hướng trò chuyện">
          <Link to={id ? "/ai/chat" : "/ai"}>
            {id ? "Lịch sử trò chuyện" : "Quay lại không gian AI"}
          </Link>
          <Link to="/support/urgent">Tìm hỗ trợ ngay</Link>
        </nav>
      )}
      {id ? (
        <>
          <h1 className="sr-only">Trò chuyện với AI</h1>
          <Thread
            key={id}
            service={service}
            conversationId={id}
            heading="MoodPrint"
            navigation={
              <Link
                className="button ghost icon-button"
                to="/ai/chat"
                aria-label="Lịch sử trò chuyện"
              >
                <ArrowLeft size={20} />
              </Link>
            }
            banner={
              linkedCase ? (
                <Notice>
                  <Link to={`/cases/${linkedCase.id}`}>
                    Trở lại hồ sơ: {linkedCase.title}
                  </Link>{" "}
                  ·{" "}
                  <Link to={`/cases/${linkedCase.id}/plan`}>
                    Kế hoạch ứng phó
                  </Link>
                </Notice>
              ) : (
                <Link className="button secondary" to="/cases/new">
                  Ghi lại sự việc trong hồ sơ
                </Link>
              )
            }
          />
        </>
      ) : (
        <div
          className="ai-feature stack live-list-content"
          data-testid="chat-live"
        >
          <PageHeader
            title="Trò chuyện với AI"
            description="Kể từng chút một. Bạn quyết định điều nào được lưu."
            action={
              <Button disabled={creating} onClick={() => void create()}>
                <Plus size={16} /> Cuộc trò chuyện mới
              </Button>
            }
          />
          {cases.length > 0 && (
            <label>
              Hồ sơ muốn trao đổi
              <select
                value={selectedCase?.id ?? ""}
                onChange={(event) => setSelectedCaseId(event.target.value)}
              >
                <option value="">Trò chuyện không gắn hồ sơ</option>
                {cases.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.title}
                  </option>
                ))}
              </select>
            </label>
          )}
          <Link to="/cases/new">
            Ghi lại sự việc trước khi trao đổi về hồ sơ
          </Link>
          {createError && (
            <div role="alert" className="live-error">
              {createError}
            </div>
          )}
          {!items && !failed && (
            <p role="status">Đang tải các cuộc trò chuyện…</p>
          )}
          {failed && (
            <Notice>
              Chưa tải được các cuộc trò chuyện.{" "}
              <button
                className="link-button"
                onClick={() => setReload((n) => n + 1)}
              >
                Thử lại
              </button>
            </Notice>
          )}
          {items?.length === 0 && (
            <EmptyState
              title="Một trang trò chuyện mới"
              description="Cuộc trò chuyện của bạn sẽ được lưu ở đây."
            />
          )}
          {items && items.length > 0 && (
            <div className="panel">
              {items.map((item) => (
                <Link
                  className="ai-recent-row"
                  key={item.id}
                  to={`/ai/chat/${item.id}`}
                >
                  <MessageCircle size={21} />
                  <div>
                    <strong>{item.title || "Cuộc trò chuyện"}</strong>
                    <small>
                      {formatDate(item.lastMessageAt ?? item.createdAt)}
                    </small>
                  </div>
                  <ArrowRight size={18} />
                </Link>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
