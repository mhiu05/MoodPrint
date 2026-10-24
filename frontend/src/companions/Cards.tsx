import { useState } from "react";
import { Link } from "react-router-dom";
import {
  ArrowUpRight,
  Check,
  LockKeyhole,
  Frown,
  Meh,
  Smile,
  SmilePlus,
  BookOpen,
  Sparkles,
} from "lucide-react";
import { useDemo } from "../state/Provider";
import { Button, Dialog, cx } from "../components/UI";
import { moodSummary } from "../domain/mood";
import { moodLabels } from "../mocks/fixtures";
import { botById, type BotId, type BotMessage } from "./registry";
export function MiniMoodChart() {
  const { state } = useDemo();
  const summary = moodSummary(state.moods, state.clock);
  return (
    <div className="mini-insight">
      <div className="inline-title">
        <span>Nhịp cảm xúc của bạn</span>
        <strong>
          <span>
            {summary.mean === null
              ? "—"
              : summary.mean.toLocaleString("vi-VN", {
                  minimumFractionDigits: 1,
                  maximumFractionDigits: 1,
                })}
          </span>
          <small> / 5</small>
        </strong>
      </div>
      <div
        className="mini-bars"
        role="img"
        aria-label={`Tâm trạng bảy ngày: ${summary.buckets.map((b) => `${b.date}: ${b.entry?.value ?? "chưa ghi"}`).join(", ")}`}
      >
        {summary.buckets.map((b) => (
          <div key={b.date}>
            <span className="bar-track">
              <i
                style={{
                  height: b.entry ? `${b.entry.value * 20}%` : "3px",
                  background: b.entry ? "#8bb5a1" : "#dadfd9",
                }}
              />
            </span>
            <small>{b.date.slice(8)}</small>
          </div>
        ))}
      </div>
      <p>
        {summary.count < 3
          ? "Ghi thêm vài ngày để cùng nhìn lại nhé."
          : `${summary.count} ngày bạn đã dành thời gian lắng nghe mình.`}
      </p>
      <Link to="/self?tab=week">
        Xem chi tiết <ArrowUpRight size={15} />
      </Link>
    </div>
  );
}
export function InlineCardView({
  botId,
  message,
}: {
  botId: BotId;
  message: BotMessage;
}) {
  const { dispatch } = useDemo();
  const card = message.card!;
  const [edit, setEdit] = useState(false),
    [text, setText] = useState(card.kind === "profile" ? card.text : "");
  const resolve = (outcome: string, value?: number) =>
    dispatch({
      type: "AI_BOT_CARD",
      botId,
      id: message.id,
      outcome,
      value,
      text,
    });
  switch (card.kind) {
    case "mood":
      return (
        <div className="inline-card mood-card">
          <span className="card-eyebrow">MỘT CHÚT LẮNG NGHE MÌNH</span>
          <h3>
            {card.value
              ? "Đã giữ lại nhịp hôm nay"
              : "Lúc này, bạn thấy thế nào?"}
          </h3>
          {card.value ? (
            <>
              <p className="saved-mood">
                <Check size={18} /> {moodLabels[card.value - 1]}
              </p>
              <button
                className="inline-link"
                onClick={() =>
                  dispatch({
                    type: "AI_BOT_SEND",
                    botId,
                    text: "Nhìn lại tuần",
                  })
                }
              >
                Xem xu hướng <ArrowUpRight size={15} />
              </button>
            </>
          ) : (
            <div className="inline-moods" aria-label="Chọn cảm xúc">
              {[Frown, Meh, Meh, Smile, SmilePlus].map((Icon, i) => (
                <button
                  key={i}
                  aria-label={`${i + 1} ${moodLabels[i]}`}
                  onClick={() => resolve("mood", i + 1)}
                >
                  <Icon size={29} strokeWidth={1.5} />
                  <span>{moodLabels[i]}</span>
                </button>
              ))}
            </div>
          )}
          <small className="private-hint">
            <LockKeyhole size={12} /> Chỉ mình bạn xem
          </small>
        </div>
      );
    case "insight":
      return (
        <div className="inline-card">
          <MiniMoodChart />
        </div>
      );
    case "profile":
      return (
        <div className="inline-card profile-card">
          <span className="card-eyebrow">
            <Sparkles size={13} /> MỘT ĐIỀU VỀ BẠN
          </span>
          <h3>{card.text}</h3>
          <p>Đúng với bạn chứ? Chỉ lưu vào hồ sơ riêng.</p>
          {card.decision ? (
            <p role="status">
              <Check size={16} />{" "}
              {card.decision === "saved"
                ? "Đã lưu vào hồ sơ riêng"
                : "Đã bỏ qua nhận xét này"}
            </p>
          ) : (
            <>
              <div className="inline-actions">
                <Button onClick={() => resolve("save")}>Lưu vào hồ sơ</Button>
                <Button variant="text" onClick={() => setEdit(true)}>
                  Chưa đúng lắm
                </Button>
                <Button variant="text" onClick={() => resolve("skip")}>
                  Bỏ qua
                </Button>
              </div>
              {edit && (
                <Dialog
                  title="Viết theo cách của bạn"
                  onClose={() => setEdit(false)}
                >
                  <label htmlFor="suggestion-edit">Điều muốn giữ lại</label>
                  <textarea
                    id="suggestion-edit"
                    value={text}
                    onChange={(e) => setText(e.target.value)}
                    maxLength={120}
                  />
                  <Button
                    disabled={!text.trim()}
                    onClick={() => {
                      resolve("save");
                      setEdit(false);
                    }}
                  >
                    Lưu điều đã sửa
                  </Button>
                </Dialog>
              )}
            </>
          )}
        </div>
      );
    case "activity":
      return (
        <div className="inline-card activity-inline">
          <span className="activity-stamp">
            <BookOpen size={21} />
          </span>
          <span className="card-eyebrow">BA PHÚT THỬ ĐIỀU MỚI</span>
          <h3>
            {card.mode === "puzzle"
              ? "Càng lấy đi, càng lớn?"
              : "Một chút tình cờ, một điều hay"}
          </h3>
          <p>
            {card.mode === "puzzle"
              ? card.revealed
                ? "Đáp án là… cái hố! Bạn đã đoán ra chưa?"
                : "Đoán thử trước khi xem đáp án nhé."
              : card.revealed
                ? "I found this book by serendipity. Giờ đến câu của bạn nhé!"
                : "Serendipity /ˌser.ənˈdɪp.ə.ti/"}
          </p>
          <Button
            variant="secondary"
            onClick={() => resolve("reveal")}
            disabled={card.revealed}
          >
            {card.revealed
              ? "Đã khám phá"
              : card.mode === "puzzle"
                ? "Xem đáp án"
                : "Xem câu ví dụ"}
          </Button>
        </div>
      );
    case "match":
      return (
        <div className="inline-card match-inline">
          <div className="match-art" aria-hidden="true">
            <span>m</span>
            <span>w</span>
          </div>
          <h3>Một điểm chung. Một khởi đầu.</h3>
          <p>Khám phá từ sở thích bạn chọn chia sẻ.</p>
          <Link className={`${cx.button} ${cx.primary}`} to="/connect">
            Xem người phù hợp <ArrowUpRight size={16} />
          </Link>
          <Link className="inline-link" to="/profile?tab=sharing">
            Sửa hồ sơ kết nối
          </Link>
        </div>
      );
    case "handoff":
      return (
        <div className="inline-card">
          <p>Không chuyển nội dung cuộc trò chuyện này.</p>
          <Link className="inline-link" to={`/assistants/${card.botId}`}>
            Mở trò chuyện với {botById(card.botId)!.name}{" "}
            <ArrowUpRight size={16} />
          </Link>
        </div>
      );
  }
}
