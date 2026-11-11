import { useLayoutEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import {
  ArrowDown,
  ArrowLeft,
  ArrowRight,
  FileImage,
  History,
  LifeBuoy,
  MoreHorizontal,
  Paperclip,
  Send,
} from "lucide-react";
import { AgentStatusOrb } from "../../animations/AgentStatusOrb";
import { Button } from "../../components/ui";
import { useReducedMotion } from "../../hooks/useReducedMotion";
import { useWorkspaceStore } from "../../app/store";
import type { ChatMessage } from "../../types";
import "./chat.css";

export type ChatPhase = "idle" | "processing" | "responding" | "error";
const phaseLabels: Record<ChatPhase, string> = {
  idle: "AI mô phỏng",
  processing: "Đang mở phản hồi mẫu…",
  responding: "Đang hiển thị phản hồi mẫu…",
  error: "Phản hồi mẫu đã dừng",
};

export function ChatTopBar({
  phase,
  onHistory,
  onMenu,
}: {
  phase: ChatPhase;
  onHistory: () => void;
  onMenu: () => void;
}) {
  return (
    <header className="chat-topbar">
      <Link
        to="/ai"
        className="button ghost icon-button"
        aria-label="Quay lại không gian AI"
      >
        <ArrowLeft size={21} />
      </Link>
      <div className="chat-identity">
        <AgentStatusOrb state={phase} size={32} showLabel={false} />
        <div>
          <h1>SafeVoice</h1>
          <span className="chat-identity-status">AI mô phỏng</span>
          <span className="sr-only" role="status">
            {phaseLabels[phase]}
          </span>
        </div>
      </div>
      <Link
        to="/support/urgent"
        className="button ghost icon-button chat-urgent"
        aria-label="Tìm hỗ trợ ngay"
      >
        <LifeBuoy size={20} />
      </Link>
      <Button
        variant="ghost"
        className="icon-button"
        aria-label="Lịch sử trò chuyện"
        aria-haspopup="dialog"
        onClick={onHistory}
      >
        <History size={20} />
      </Button>
      <Button
        variant="ghost"
        className="icon-button"
        aria-label="Tùy chọn cuộc trò chuyện"
        aria-haspopup="dialog"
        onClick={onMenu}
      >
        <MoreHorizontal size={22} />
      </Button>
    </header>
  );
}

/** Owns one scrolling surface. Streaming never pulls a reader away from older messages. */
export function MessageList({
  children,
  revision,
  sessionKey,
  lastSpeaker,
}: {
  children: ReactNode;
  revision: string;
  sessionKey: string;
  lastSpeaker?: ChatMessage["speaker"];
}) {
  const scroll = useRef<HTMLDivElement>(null);
  const content = useRef<HTMLDivElement>(null);
  const follow = useRef(true);
  const [away, setAway] = useState(false);
  const reduced = useReducedMotion();
  const preference = useWorkspaceStore((s) => s.preferences.reducedMotion);
  const previous = useRef(sessionKey);
  const previousRevision = useRef("");
  useLayoutEffect(() => {
    if (previous.current !== sessionKey) {
      follow.current = true;
      previous.current = sessionKey;
    }
    const newUserMessage =
      lastSpeaker === "user" &&
      revision.split(":")[0] !== previousRevision.current.split(":")[0];
    previousRevision.current = revision;
    if (newUserMessage) follow.current = true;
    if (follow.current && scroll.current)
      scroll.current.scrollTop = scroll.current.scrollHeight;
  }, [revision, sessionKey, lastSpeaker]);
  useLayoutEffect(() => {
    const viewport = scroll.current;
    if (!viewport || typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(() => {
      if (follow.current) viewport.scrollTop = viewport.scrollHeight;
    });
    observer.observe(viewport);
    if (content.current) observer.observe(content.current);
    return () => observer.disconnect();
  }, []);
  return (
    <div className="chat-scroll-region">
      <div
        ref={scroll}
        className="ai-transcript chat-transcript"
        role="log"
        aria-label="Tin nhắn theo thứ tự"
        aria-live="polite"
        aria-relevant="additions"
        onScroll={() => {
          const viewport = scroll.current!;
          follow.current =
            viewport.scrollHeight - viewport.clientHeight - viewport.scrollTop <
            70;
          setAway(!follow.current);
        }}
      >
        <div ref={content} className="chat-reading-column">
          {children}
        </div>
      </div>
      {away && (
        <Button
          variant="secondary"
          className="chat-jump"
          onClick={() => {
            follow.current = true;
            setAway(false);
            scroll.current?.scrollTo({
              top: scroll.current.scrollHeight,
              behavior: reduced || preference ? "instant" : "smooth",
            });
          }}
        >
          <ArrowDown size={16} />
          Tin nhắn mới nhất
        </Button>
      )}
    </div>
  );
}

export function MessageBubble({
  message,
  grouped,
  children,
}: {
  message: ChatMessage;
  grouped: boolean;
  children?: ReactNode;
}) {
  return (
    <div
      className={`ai-message ${message.speaker} ${grouped ? "is-grouped" : ""}`}
    >
      {message.speaker === "ai" && !grouped && (
        <span className="chat-message-avatar" aria-hidden="true">
          <AgentStatusOrb state="idle" size={20} showLabel={false} />
        </span>
      )}
      {!grouped && (
        <small>
          {message.speaker === "user"
            ? "Bạn"
            : message.speaker === "system"
              ? "Thông tin mẫu"
              : "SafeVoice · mô phỏng"}
        </small>
      )}
      <p>{message.body}</p>
      {children}
      {message.createdAt && !Number.isNaN(Date.parse(message.createdAt)) && (
        <time dateTime={message.createdAt} className="chat-message-time">
          {new Intl.DateTimeFormat("vi-VN", {
            hour: "2-digit",
            minute: "2-digit",
          }).format(new Date(message.createdAt))}
        </time>
      )}
    </div>
  );
}

export function AttachmentPreview({ analysisId }: { analysisId: string }) {
  const analysis = useWorkspaceStore((s) =>
    s.analyses.find(
      (item) => item.id === analysisId && item.ownerId === s.user?.id,
    ),
  );
  const evidence = useWorkspaceStore((s) => s.evidence);
  const previews =
    analysis?.evidenceIds
      .slice(0, 2)
      .flatMap((id) => evidence.find((item) => item.id === id) ?? []) ?? [];
  return (
    <Link
      className="ai-analysis-attachment chat-attachment"
      to={`/ai/analysis/${analysisId}`}
    >
      {previews.length > 0 && (
        <span className="chat-attachment-images" aria-hidden="true">
          {previews.map((item) => (
            <img key={item.id} src={item.assetPath} alt="" />
          ))}
        </span>
      )}
      <span className="chat-attachment-label">
        <FileImage size={20} />
        <span>
          <strong>{analysis?.evidenceIds.length ?? 0} ảnh chat mẫu</strong>
          <small>
            Phân tích mô phỏng · {analysis?.confirmedIds.length ?? 0}/
            {analysis?.evidenceIds.length ?? 0} nguồn bạn xác nhận
          </small>
          <small>
            Ảnh có thể bị cắt, sai mốc giờ hoặc trùng. Mở để kiểm tra và sửa
            từng nguồn.
          </small>
        </span>
        <ArrowRight size={17} />
      </span>
    </Link>
  );
}

export function ChatComposer({
  value,
  onChange,
  onSend,
  onAttach,
  blocked,
  busy,
  suggestions,
}: {
  value: string;
  onChange: (value: string) => void;
  onSend: () => void;
  onAttach: () => void;
  blocked: boolean;
  busy: boolean;
  suggestions?: ReactNode;
}) {
  const textarea = useRef<HTMLTextAreaElement>(null);
  useLayoutEffect(() => {
    if (!textarea.current) return;
    textarea.current.style.height = "auto";
    textarea.current.style.height = `${Math.min(textarea.current.scrollHeight || 44, 140)}px`;
  }, [value]);
  return (
    <footer className="chat-composer-zone">
      <div className="chat-composer-column">
        {suggestions}
        <form
          className="chat-composer"
          aria-label="Soạn tin nhắn"
          onSubmit={(event) => {
            event.preventDefault();
            if (!blocked && value.trim()) onSend();
          }}
        >
          <Button
            type="button"
            variant="ghost"
            className="icon-button"
            aria-label="Đính kèm dữ liệu mẫu"
            disabled={blocked}
            onClick={onAttach}
          >
            <Paperclip size={21} />
          </Button>
          <label className="sr-only" htmlFor="chat-message">
            Điều bạn muốn kể
          </label>
          <textarea
            ref={textarea}
            id="chat-message"
            rows={1}
            value={value}
            placeholder="Kể từng chút một…"
            onChange={(event) => onChange(event.target.value)}
            onKeyDown={(event) => {
              if (
                event.key === "Enter" &&
                !event.shiftKey &&
                !event.nativeEvent.isComposing &&
                event.keyCode !== 229
              ) {
                event.preventDefault();
                if (!blocked && value.trim()) onSend();
              }
            }}
            aria-describedby="chat-demo-note"
          />
          <Button
            type="submit"
            className="icon-button"
            disabled={!value.trim() || blocked}
            aria-label="Gửi tin nhắn trong bản demo"
          >
            <Send size={19} />
          </Button>
        </form>
        <p id="chat-demo-note" className="chat-demo-note">
          {busy ? "Bạn vẫn có thể viết tin tiếp theo. " : ""}AI theo kịch bản
          mẫu · Chỉ lưu trên trình duyệt.
        </p>
      </div>
    </footer>
  );
}

export function TypingIndicator({
  phase,
  partial,
  onComplete,
}: {
  phase: ChatPhase;
  partial: string;
  onComplete: () => void;
}) {
  return (
    <div className="ai-message ai ai-stream" aria-busy="true" aria-live="off">
      <small>Phản hồi dựng sẵn</small>
      <p>
        {partial || (
          <span className="chat-typing">
            <i />
            <i />
            <i />
            <span>Đang mở câu trả lời mẫu…</span>
          </span>
        )}
      </p>
      {phase === "responding" && (
        <Button variant="ghost" onClick={onComplete}>
          Hiện toàn bộ phản hồi
        </Button>
      )}
    </div>
  );
}
