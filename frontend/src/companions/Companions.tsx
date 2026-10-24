import { useEffect, useRef, useState } from "react";
import { Link, Navigate, useParams } from "react-router-dom";
import {
  ArrowLeft,
  ArrowUpRight,
  ArrowDown,
  Search,
  Send,
  LockKeyhole,
  MoreHorizontal,
  Sparkles,
  Users,
  SlidersHorizontal,
} from "lucide-react";
import { useDemo } from "../state/Provider";
import { effectiveAI } from "../domain/policies";
import {
  Brand,
  Button,
  Dialog,
  Motion,
  StatePanel,
  Go,
  Typing,
} from "../components/UI";
import { bots, botById, type BotId } from "./registry";
import { BotAvatar } from "./Avatar";
import { InlineCardView } from "./Cards";

export function CompanionsPage() {
  const { botId } = useParams();
  const { state } = useDemo();
  const [search, setSearch] = useState("");
  const bot = botById(botId);
  if (botId && !bot) return <Navigate replace to="/assistants" />;
  return (
    <div className={`companion-layout ${bot ? "has-conversation" : ""}`}>
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
            onChange={(e) => setSearch(e.target.value)}
          />
        </label>
        <div className="roster-section-label">
          <h2>Trợ lý của bạn</h2>
          <span>05</span>
        </div>
        <div className="bot-list">
          {bots
            .filter((b) =>
              `${b.name} ${b.role}`
                .toLocaleLowerCase("vi-VN")
                .includes(search.toLocaleLowerCase("vi-VN")),
            )
            .map((b) => {
              const thread = state.bots[b.id];
              return (
                <Link
                  key={b.id}
                  to={`/assistants/${b.id}`}
                  className={`bot-row ${bot?.id === b.id ? "selected" : ""}`}
                  aria-label={`Trò chuyện với ${b.name}`}
                  aria-current={bot?.id === b.id ? "page" : undefined}
                >
                  <BotAvatar id={b.id} />
                  <div className="bot-row-text">
                    <div>
                      <strong>{b.name}</strong>
                      <span className="ai-tag">AI</span>
                    </div>
                    <small>{b.role}</small>
                    <p>
                      {thread.messages.length > 1
                        ? thread.messages.at(-1)!.text
                        : b.description}
                    </p>
                  </div>
                  {thread.unread && b.id !== bot?.id ? (
                    <span className="unread-dot" aria-label="Có tin mới" />
                  ) : (
                    <ArrowUpRight size={16} className="roster-arrow" />
                  )}
                </Link>
              );
            })}
        </div>
        {search &&
          !bots.some((b) =>
            `${b.name} ${b.role}`
              .toLocaleLowerCase("vi-VN")
              .includes(search.toLocaleLowerCase("vi-VN")),
          ) && (
            <p className="search-empty">
              Chưa tìm thấy trợ lý. Thử tên khác nhé.
            </p>
          )}
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
          <BotConversation key={`${state.epoch}-${bot.id}`} botId={bot.id} />
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
            <p className="overline">CHÀO BẠN, MÌNH LÀ ME2WE</p>
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
            <Link to="/assistants/may" className="welcome-start">
              Kể Mây nghe nhé <ArrowUpRight size={18} />
            </Link>
            <span className="welcome-signature">
              hiểu mình hơn · gần nhau hơn
            </span>
          </div>
        )}
      </section>
    </div>
  );
}

function BotConversation({ botId }: { botId: BotId }) {
  const { state, dispatch } = useDemo();
  const bot = botById(botId)!;
  const thread = state.bots[botId];
  const [text, setText] = useState(""),
    [info, setInfo] = useState(false),
    [atBottom, setAtBottom] = useState(true);
  const log = useRef<HTMLDivElement>(null);
  useEffect(() => {
    dispatch({ type: "AI_BOT_READ", botId });
  }, [botId, thread.messages.length, dispatch]);
  useEffect(() => {
    if (atBottom && log.current)
      log.current.scrollTop = log.current.scrollHeight;
  }, [thread.messages.length, thread.pending, atBottom]);
  const send = (value = text) => {
    if (
      !effectiveAI(state) ||
      thread.pending ||
      !value.trim() ||
      value.trim().length > 500
    )
      return;
    dispatch({ type: "AI_BOT_SEND", botId, text: value });
    setText("");
    setAtBottom(true);
  };
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
        <BotAvatar id={botId} size={43} />
        <div>
          <h1 tabIndex={-1}>
            {bot.name} <span className="ai-tag">AI</span>
          </h1>
          <p>{bot.role}</p>
        </div>
        <button
          className="icon-button"
          aria-label={`Thông tin về ${bot.name}`}
          onClick={() => setInfo(true)}
        >
          <MoreHorizontal size={22} />
        </button>
      </header>
      {!effectiveAI(state) ? (
        <div className="chat-disabled">
          <StatePanel
            title="Trò chuyện AI đang tắt"
            action={
              <>
                <Go to="/settings">Xem quyền trò chuyện AI</Go>
                <Go secondary to="/self?tab=mood">
                  Tự ghi tâm trạng
                </Go>
              </>
            }
          >
            Bạn vẫn có thể ghi cảm xúc và tìm bạn.
          </StatePanel>
        </div>
      ) : (
        <>
          <div
            className="conversation-log"
            ref={log}
            role="log"
            aria-label={`Hội thoại với ${bot.name}`}
            aria-live="polite"
            onScroll={() => {
              const e = log.current!;
              setAtBottom(e.scrollHeight - e.scrollTop - e.clientHeight < 90);
            }}
          >
            <div className="chat-introduction">
              <BotAvatar id={botId} size={80} />
              <h3>Một chút thời gian với {bot.name}</h3>
              <p>{bot.description}</p>
              <small>
                <LockKeyhole size={11} /> Chỉ bạn xem
              </small>
            </div>
            <div className="day-divider">
              <span>Cuộc trò chuyện của bạn</span>
            </div>
            {thread.messages.map((message) => (
              <Motion
                key={message.id}
                motionKey={message.id}
                className={`message-row ${message.actor === "self" ? "from-self" : "from-bot"}`}
              >
                <div className="message-content">
                  <div className="chat-bubble">
                    <p>{message.text}</p>
                  </div>
                  {message.card && (
                    <Motion
                      kind="mood"
                      motionKey={
                        message.card.kind === "mood"
                          ? message.card.value || 0
                          : message.card.kind === "profile"
                            ? message.card.decision || ""
                            : message.card.kind === "activity"
                              ? Number(message.card.revealed)
                              : 0
                      }
                    >
                      <InlineCardView botId={botId} message={message} />
                    </Motion>
                  )}
                </div>
              </Motion>
            ))}
            {thread.pending && (
              <div className="bot-pending">
                <Typing />
                <button
                  onClick={() => dispatch({ type: "AI_BOT_STOP", botId })}
                >
                  Dừng
                </button>
              </div>
            )}
            {thread.error && (
              <div role="alert" className="reply-error">
                Chưa hiện được phản hồi.
                <Button
                  variant="text"
                  onClick={() => dispatch({ type: "AI_BOT_RETRY", botId })}
                >
                  Thử lại phản hồi
                </Button>
              </div>
            )}
          </div>
          {!atBottom && (
            <button className="new-message" onClick={() => setAtBottom(true)}>
              <ArrowDown size={16} /> Về tin mới nhất
            </button>
          )}
          <div className="chat-bottom">
            <div className="quick-replies" aria-label="Gợi ý trò chuyện">
              {(botId === "guong" && thread.turn % 2 === 1
                ? [
                    "Mình thích khoảng yên tĩnh khi đọc sách",
                    "Mình thích được khám phá",
                    "Mình muốn nghĩ thêm",
                  ]
                : botId === "may" && thread.turn > 0
                  ? ["Kể một chút", "Ghi lại cảm xúc", "Đổi chủ đề"]
                  : bot.starters
              ).map((p) => (
                <button
                  key={p}
                  disabled={!!thread.pending}
                  onClick={() => send(p)}
                >
                  {p}
                </button>
              ))}
            </div>
            <form
              className="bot-composer"
              onSubmit={(e) => {
                e.preventDefault();
                send();
              }}
            >
              <textarea
                id="bot-message"
                aria-label={`Tin nhắn cho ${bot.name}`}
                value={text}
                maxLength={500}
                rows={1}
                onChange={(e) => setText(e.target.value)}
                placeholder={`Nhắn cho ${bot.name}…`}
                onFocus={() =>
                  requestAnimationFrame(() =>
                    log.current?.scrollTo({ top: log.current.scrollHeight }),
                  )
                }
                onKeyDown={(e) => {
                  if (
                    e.key === "Enter" &&
                    !e.shiftKey &&
                    !e.nativeEvent.isComposing
                  ) {
                    e.preventDefault();
                    send();
                  }
                }}
              />
              <button
                type="submit"
                className="send-button"
                disabled={!text.trim() || !!thread.pending}
                aria-label="Gửi tin cho AI"
              >
                <Send size={19} />
              </button>
            </form>
          </div>
        </>
      )}
      {info && (
        <Dialog
          title={`Một chút về ${bot.name}`}
          onClose={() => setInfo(false)}
        >
          <div className="bot-info">
            <BotAvatar id={botId} size={90} />
            <h3>{bot.role}</h3>
            <p>{bot.description}</p>
            <p>
              Đây là trợ lý AI trong bản trải nghiệm với nội dung soạn sẵn, chưa
              kết nối AI thật. Hội thoại chỉ ở trong phiên này.
            </p>
            <p>
              Nội dung không tự chia sẻ sang trợ lý khác hoặc hồ sơ kết nối.
            </p>
          </div>
          <Button onClick={() => setInfo(false)}>Mình đã hiểu</Button>
        </Dialog>
      )}
    </div>
  );
}
