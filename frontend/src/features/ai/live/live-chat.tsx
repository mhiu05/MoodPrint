import { useEffect, useRef, useState, type ReactNode } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ArrowRight, MessageCircle, Plus, Send, Square } from "lucide-react";
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
    <li
      className={`live-message live-${message.role} ai-message ${message.role === "assistant" ? "ai" : "user"}`}
    >
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
}: {
  service: LiveCompanion;
  conversationId: string;
  heading?: string;
  banner?: ReactNode;
  withMemory?: boolean;
  onSettled?: () => void;
}) {
  const chat = useLiveChat(service, conversationId);
  const [draft, setDraft] = useState("");
  const [deferred, setDeferred] = useState<string | null>(null);
  const endRef = useRef<HTMLDivElement>(null);
  const busy = chat.status === "streaming" || chat.status === "recovering";
  useEffect(() => {
    endRef.current?.scrollIntoView?.({ block: "end" });
  }, [chat.messages]);
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
        <AgentStatusOrb state={orb} size={32} showLabel={false} />
        <div>
          <h2>{heading}</h2>
          <small>
            AI có thể sai và không phải người thật. Với chuyện nghiêm trọng, hãy
            nói với người lớn bạn tin.
          </small>
        </div>
      </header>
      {banner}
      {/* The live region wraps the list: an <li> must stay a direct child of a real list. */}
      <div role="log" aria-live="polite" aria-label="Tin nhắn">
        <ol className="live-messages">
          {!chat.loaded && (
            <li className="live-hint">Đang tải cuộc trò chuyện…</li>
          )}
          {chat.loaded && !chat.messages.length && (
            <li className="live-hint">
              Bạn muốn kể điều gì? Có thể bắt đầu từ một câu.
            </li>
          )}
          {chat.messages.map((message) => (
            <LiveMessageView key={message.id} message={message} />
          ))}
        </ol>
      </div>
      <div ref={endRef} />
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
          onDecide={(decision) => void chat.decide(decision)}
        />
      )}
      {withMemory && (
        <MemoryCandidates service={service} refreshKey={memoryKey} />
      )}
      <form
        className="live-composer"
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
          value={draft}
          rows={2}
          maxLength={4000}
          placeholder="Viết điều bạn muốn nói…"
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault();
              void submit();
            }
          }}
        />
        {chat.status === "streaming" ? (
          <Button
            type="button"
            variant="secondary"
            onClick={() => void chat.stop()}
          >
            <Square size={16} /> Dừng
          </Button>
        ) : (
          <Button
            type="submit"
            disabled={
              !draft.trim() || busy || chat.status === "awaiting_approval"
            }
          >
            <Send size={16} /> Gửi
          </Button>
        )}
      </form>
    </section>
  );
}

export function LiveChatPage({ service }: { service: LiveCompanion }) {
  const { sessionId: id } = useParams();
  const navigate = useNavigate();
  const [items, setItems] = useState<ConversationSummary[] | null>(null);
  const [failed, setFailed] = useState(false);
  const [reload, setReload] = useState(0);
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
    const created = await service.conversations.create({
      id: globalThis.crypto.randomUUID(),
      title: "",
    });
    navigate(`/ai/chat/${created.id}`);
  };
  if (id) return <Thread key={id} service={service} conversationId={id} />;
  return (
    <div className="ai-feature stack" data-testid="chat-live">
      <PageHeader
        title="Trò chuyện với AI"
        description="Kể từng chút một. Bạn quyết định điều nào được lưu."
        action={
          <Button onClick={() => void create()}>
            <Plus size={16} /> Cuộc trò chuyện mới
          </Button>
        }
      />
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
                <small>{item.lastMessageAt ?? item.createdAt}</small>
              </div>
              <ArrowRight size={18} />
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
