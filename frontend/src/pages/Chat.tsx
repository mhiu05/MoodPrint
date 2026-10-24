import { useEffect, useRef, useState } from "react";
import { Link, Navigate, useParams, useSearchParams } from "react-router-dom";
import {
  ArrowLeft,
  Send,
  ShieldCheck,
  Shapes,
  LockKeyhole,
  MoreHorizontal,
} from "lucide-react";
import { useDemo } from "../state/Provider";
import { visibleChat, visibleReveal } from "../state/reducer";
import {
  Avatar,
  Badge,
  Button,
  cx,
  Dialog,
  Go,
  Intro,
  Motion,
  Typing,
} from "../components/UI";
import { humanPrompts, questions } from "../mocks/fixtures";
import { Concepts } from "./Connect";
export function ChatPage() {
  const { state, dispatch } = useDemo();
  const { connectionId = "" } = useParams();
  const room = visibleChat(state, connectionId);
  const [params, setParams] = useSearchParams();
  const [text, setText] = useState(""),
    [warning, setWarning] = useState<string>(),
    [reveal, setReveal] = useState<string>(),
    [end, setEnd] = useState(false),
    [menu, setMenu] = useState(false);
  const log = useRef<HTMLDivElement>(null);
  const [newMessage, setNewMessage] = useState(false);
  const [autoScroll, setAutoScroll] = useState(true);
  const panel = params.get("panel");
  useEffect(() => {
    if (
      room &&
      ((panel && !["activities", "activity"].includes(panel)) ||
        (panel === "activity" && params.get("activityId") !== "ACT01"))
    )
      setParams({ panel: "activities" }, { replace: true });
  }, [panel, params, room?.id]);
  useEffect(() => {
    if (autoScroll && log.current)
      log.current.scrollTop = log.current.scrollHeight;
    else setNewMessage(true);
  }, [room?.messages.length, autoScroll]);
  const activityStatus = state.activities
    .filter((a) => a.connectionId === connectionId)
    .at(-1)?.status;
  useEffect(() => {
    if (
      activityStatus === "completed" ||
      (panel &&
        ["stopped", "cancelled", "declined"].includes(activityStatus || ""))
    ) {
      const heading = document.querySelector<HTMLElement>(
        activityStatus === "completed"
          ? "[data-completed-heading]"
          : "[data-activity-heading]",
      );
      heading?.focus({ preventScroll: true });
      heading?.scrollIntoView({ block: "start", behavior: "instant" });
    }
  }, [activityStatus, panel]);
  if (!room)
    return <Navigate replace to="/connect?tab=requests&reason=closed" />;
  const peer = state.candidates.find((x) => x.id === room.candidateId)!;
  const act = state.activities.filter((x) => x.connectionId === room.id).at(-1);
  const send = (value = text, confirmed = false) => {
    if (!value.trim() || value.length > 500) return;
    if (
      !confirmed &&
      (/\b[^\s@]+@[^\s@]+\.[^\s@]+\b/.test(value) ||
        /[0-9][0-9\s.-]{7,}[0-9]/.test(value))
    ) {
      setWarning(value);
      return;
    }
    if (
      state.connections
        .flatMap((c) => c.messages)
        .filter(
          (m) =>
            m.actor === "self" && !m.scripted && m.at > state.clock - 60000,
        ).length >= 20
    ) {
      dispatch({
        type: "NOTICE",
        text: "Bạn đã gửi 20 tin trong một phút demo. Hãy nghỉ một chút nhé.",
      });
      return;
    }
    dispatch({ type: "HUMAN_SEND", connectionId: room.id, text: value });
    setText("");
  };
  const reveals = state.reveals.filter((r) => r.connectionId === room.id);
  const selected = reveals.find((r) => r.id === reveal);
  return (
    <div className={`${cx.chatPage} ${panel ? cx.withActivity : ""}`}>
      <header className="human-chat-header">
        <Link className="icon-button" to="/messages" aria-label="Về tin nhắn">
          <ArrowLeft size={21} />
        </Link>
        <Avatar name={peer.alias} color={peer.color} />
        <div>
          <h1 tabIndex={-1}>{peer.alias}</h1>
          <p>Bạn kết nối · Nhân vật mẫu</p>
        </div>
        <button
          className="icon-button"
          aria-label="Tùy chọn cuộc trò chuyện"
          onClick={() => setMenu(true)}
        >
          <MoreHorizontal size={22} />
        </button>
      </header>
      {menu && (
        <Dialog title="Cuộc trò chuyện của bạn" onClose={() => setMenu(false)}>
          <p>Bạn có thể dừng hoặc chặn bất cứ lúc nào.</p>
          <div className={cx.actions}>
            <Button
              variant="secondary"
              onClick={() => {
                setEnd(true);
                setMenu(false);
              }}
            >
              Kết thúc
            </Button>
            <Button
              variant="danger"
              onClick={() => dispatch({ type: "BLOCK", candidateId: peer.id })}
            >
              Chặn ngay
            </Button>
          </div>
          <Go secondary to="/settings?tab=safety">
            An toàn & báo cáo
          </Go>
        </Dialog>
      )}
      <details className={cx.revealStrip}>
        <summary>Chia sẻ từng thông tin</summary>
        <section aria-label="Chia sẻ từng thông tin">
          <LockKeyhole size={18} />
          <strong>Chia sẻ theo lựa chọn</strong>
          <div className={cx.actions}>
            <Button
              variant="text"
              onClick={() =>
                dispatch({
                  type: "REVEAL_REQUEST",
                  connectionId: room.id,
                  field: "displayName",
                  owner: "peer",
                })
              }
            >
              Xin xem tên đối phương
            </Button>
            <Button
              variant="text"
              onClick={() =>
                dispatch({
                  type: "REVEAL_REQUEST",
                  connectionId: room.id,
                  field: "displayName",
                  owner: "self",
                })
              }
            >
              Mô phỏng yêu cầu xem tên mình
            </Button>
            {state.identities.gender === "Nữ" && (
              <>
                <Button
                  variant="text"
                  onClick={() =>
                    dispatch({
                      type: "REVEAL_REQUEST",
                      connectionId: room.id,
                      field: "gender",
                      owner: "peer",
                    })
                  }
                >
                  Xin xem giới tính mẫu
                </Button>
                <Button
                  variant="text"
                  onClick={() =>
                    dispatch({
                      type: "REVEAL_REQUEST",
                      connectionId: room.id,
                      field: "gender",
                      owner: "self",
                    })
                  }
                >
                  Mô phỏng yêu cầu giới tính mình
                </Button>
              </>
            )}
          </div>
          {reveals.map((r) => (
            <div className={cx.revealRow} key={r.id}>
              <span>
                {r.field === "displayName" ? "Tên hiển thị" : "Giới tính"} ·{" "}
                {r.owner === "self"
                  ? `An → ${peer.alias}`
                  : `${peer.alias} → An`}{" "}
                ·{" "}
                {
                  {
                    pending: "Đang chờ",
                    granted: "Đã cho phép",
                    declined: "Đã từ chối",
                    revoked: "Đã thu hồi",
                    expired: "Đã hết hạn",
                  }[r.status]
                }
              </span>
              {r.status === "pending" && (
                <Button variant="secondary" onClick={() => setReveal(r.id)}>
                  {r.owner === "self"
                    ? "Xem trước & quyết định"
                    : "Mô phỏng phản hồi"}
                </Button>
              )}
              {r.status === "granted" && (
                <>
                  <strong>
                    {visibleReveal(
                      state,
                      room.id,
                      r.field,
                      r.owner,
                      r.recipient,
                    )}
                  </strong>
                  <Button
                    variant="text"
                    onClick={() =>
                      dispatch({ type: "REVEAL_REVOKE", id: r.id })
                    }
                  >
                    {r.owner === "self" ? "Thu hồi" : "Mô phỏng thu hồi"}
                  </Button>
                </>
              )}
            </div>
          ))}
        </section>
      </details>
      <div
        ref={log}
        className={cx.messageLog}
        role="log"
        aria-label="Hội thoại với nhân vật giả lập"
        aria-live="polite"
        onScroll={() => {
          const el = log.current!;
          setAutoScroll(el.scrollHeight - el.scrollTop - el.clientHeight < 80);
        }}
      >
        {room.messages.map((m) => (
          <Motion key={m.id} motionKey={m.id}>
            <div
              className={`${cx.bubble} ${m.actor === "self" ? cx.mine : ""}`}
            >
              <p>{m.text}</p>
            </div>
          </Motion>
        ))}
      </div>
      {newMessage && (
        <Button
          variant="text"
          onClick={() => {
            setAutoScroll(true);
            setNewMessage(false);
          }}
        >
          Xem tin mới
        </Button>
      )}
      {room.pending && <Typing />}
      <button
        className="shared-activity-entry"
        onClick={() => setParams({ panel: "activities" })}
      >
        <Shapes size={17} /> Cùng làm gì đó? <span>↗</span>
      </button>
      <div className={cx.chips} aria-label="Gợi ý mở đầu">
        {humanPrompts.map((p) => (
          <Button key={p} variant="secondary" onClick={() => send(p)}>
            {p}
          </Button>
        ))}
      </div>
      <form
        className={cx.composer}
        onSubmit={(e) => {
          e.preventDefault();
          send();
        }}
      >
        <label htmlFor="human-message">
          <span className={cx.srOnly}>Tin nhắn demo</span>{" "}
          <small>{text.length}/500</small>
        </label>
        <div>
          <textarea
            id="human-message"
            rows={1}
            value={text}
            onChange={(e) => setText(e.target.value)}
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
            placeholder="Bắt đầu bằng một điều bạn cùng thích…"
          />
          <Button
            type="submit"
            disabled={!text.trim() || text.length > 500}
            aria-label="Gửi tin nhắn demo"
          >
            <Send size={19} />
          </Button>
        </div>
        {text.length > 500 && (
          <p className={cx.error}>
            Tối đa 500 ký tự. Nội dung nháp vẫn được giữ.
          </p>
        )}
      </form>
      {panel && (
        <section className={cx.activitySheet} aria-label="Hoạt động chung">
          <div className={cx.sectionHeading}>
            <h2 tabIndex={-1} data-activity-heading>
              Làm gì cùng nhau?
            </h2>
            <Button variant="secondary" onClick={() => setParams({})}>
              Về trò chuyện
            </Button>
          </div>
          <p className="activity-subtitle">
            Một chút cùng chơi, thêm chút hiểu nhau.
          </p>
          {panel === "activity" && act && act.status === "active" ? (
            <ActivityPanel activityId={act.id} />
          ) : act?.status === "completed" ? (
            <div className={cx.completion}>
              <h3 tabIndex={-1} data-completed-heading>
                Thêm một chút hiểu nhau!
              </h3>
              <p>Vậy là hai bạn đã biết thêm một chút về nhau rồi!</p>
              <Button onClick={() => setParams({})}>Tiếp tục trò chuyện</Button>
            </div>
          ) : act?.status === "active" ? (
            <Button
              onClick={() =>
                setParams({ panel: "activity", activityId: "ACT01" })
              }
            >
              Tiếp tục thẻ câu hỏi đang chơi
            </Button>
          ) : (
            <>
              <article className={cx.activityHero}>
                <span className={cx.chapter}>✳ / Cùng bắt đầu</span>
                <h3>Câu hỏi làm quen</h3>
                <p>
                  3 câu hỏi nhỏ, đủ để câu chuyện bắt đầu. Không có đáp án đúng
                  hay sai.
                </p>
                {act?.status === "pending" ? (
                  <>
                    <p>Chưa thể chơi — cần người kia đồng ý riêng.</p>
                    <div className={cx.simulation}>
                      <small>Mô phỏng đối phương</small>
                      <div className={cx.actions}>
                        <Button
                          onClick={() => {
                            dispatch({
                              type: "ACTIVITY_DECIDE",
                              id: act.id,
                              outcome: "accept",
                            });
                            setParams({
                              panel: "activity",
                              activityId: "ACT01",
                            });
                          }}
                        >
                          Đồng ý hoạt động
                        </Button>
                        <Button
                          variant="secondary"
                          onClick={() =>
                            dispatch({
                              type: "ACTIVITY_DECIDE",
                              id: act.id,
                              outcome: "decline",
                            })
                          }
                        >
                          Từ chối hoạt động
                        </Button>
                        <Button
                          variant="text"
                          onClick={() =>
                            dispatch({
                              type: "ACTIVITY_DECIDE",
                              id: act.id,
                              outcome: "cancel",
                            })
                          }
                        >
                          Hủy lời mời hoạt động
                        </Button>
                      </div>
                    </div>
                  </>
                ) : (
                  <>
                    <p>
                      {act &&
                      ["stopped", "cancelled", "declined"].includes(act.status)
                        ? "Lượt trước đã dừng hoặc chưa được chấp nhận. Phòng chat vẫn mở."
                        : ""}
                    </p>
                    <Button
                      onClick={() =>
                        dispatch({
                          type: "ACTIVITY_INVITE",
                          connectionId: room.id,
                          activityId: "ACT01",
                        })
                      }
                    >
                      Mời cùng tham gia
                    </Button>
                  </>
                )}
              </article>
              <Concepts />
            </>
          )}
        </section>
      )}
      {warning && (
        <Dialog
          title="Bạn muốn xem lại tin nhắn này không?"
          onClose={() => setWarning(undefined)}
        >
          <p>
            Mẫu cảnh báo tìm thấy chuỗi giống email hoặc số liên hệ. Quy tắc này
            không nhận ra mọi thông tin riêng tư. Đừng dùng thông tin thật trong
            demo.
          </p>
          <div className={cx.actions}>
            <Button
              variant="secondary"
              onClick={() => {
                setText(warning);
                setWarning(undefined);
                document.getElementById("human-message")?.focus();
              }}
            >
              Sửa tin nhắn
            </Button>
            <Button variant="secondary" onClick={() => setWarning(undefined)}>
              Hủy gửi
            </Button>
            <Button
              onClick={() => {
                send(warning, true);
                setWarning(undefined);
              }}
            >
              Vẫn gửi trong demo
            </Button>
          </div>
        </Dialog>
      )}
      {selected && (
        <Dialog
          title={
            selected.owner === "self"
              ? "Bạn muốn chia sẻ mục này chứ?"
              : "Mô phỏng quyết định của đối phương"
          }
          onClose={() => setReveal(undefined)}
        >
          <p>
            {selected.field === "displayName" ? "Tên hiển thị" : "Giới tính"}{" "}
            demo:{" "}
            <strong>
              {selected.owner === "self"
                ? state.identities[selected.field]
                : peer.identity[selected.field]}
            </strong>
          </p>
          <p>
            Người nhận: {selected.owner === "self" ? peer.alias : "An"}. Chỉ
            trường này, theo chiều này và trong phòng này được cho xem.
          </p>
          <p className={cx.note}>
            Thu hồi chỉ ẩn truy cập còn lại, không xóa thông tin mà người kia đã
            nhìn thấy hoặc tự lưu. Không bắt buộc chia sẻ lại.
          </p>
          <div className={cx.actions}>
            <Button
              onClick={() => {
                dispatch({
                  type: "REVEAL_DECIDE",
                  id: selected.id,
                  outcome: "accept",
                });
                setReveal(undefined);
              }}
            >
              Đồng ý chia sẻ trường này
            </Button>
            <Button
              variant="secondary"
              onClick={() => {
                dispatch({
                  type: "REVEAL_DECIDE",
                  id: selected.id,
                  outcome: "decline",
                });
                setReveal(undefined);
              }}
            >
              Từ chối chia sẻ
            </Button>
          </div>
        </Dialog>
      )}
      {end && (
        <Dialog
          destructive
          title="Kết thúc cuộc trò chuyện này?"
          onClose={() => setEnd(false)}
        >
          <p>
            Phòng sẽ đóng, thông tin đã cho xem bị thu hồi và hoạt động chung
            dừng. Lần kết nối khác cần lời mời mới sau thời gian chờ.
          </p>
          <div className={cx.actions}>
            <Button
              data-cancel
              variant="secondary"
              onClick={() => setEnd(false)}
            >
              Hủy
            </Button>
            <Button
              variant="danger"
              onClick={() => dispatch({ type: "END", connectionId: room.id })}
            >
              Kết thúc kết nối
            </Button>
          </div>
        </Dialog>
      )}
    </div>
  );
}
function ActivityPanel({ activityId }: { activityId: string }) {
  const { state, dispatch } = useDemo();
  const act = state.activities.find((x) => x.id === activityId)!;
  const q = questions[act.step];
  const [stop, setStop] = useState(false);
  useEffect(() => {
    const heading = document.querySelector<HTMLElement>(
      "[data-question-heading]",
    );
    heading?.focus({ preventScroll: true });
    heading?.scrollIntoView({ block: "start", behavior: "instant" });
  }, [act.id, act.step]);
  return (
    <>
      <Motion kind="activity" motionKey={`${act.id}-${act.step}`}>
        <div className={cx.question}>
          <p className={cx.eyebrow}>Câu {act.step + 1} trong 3</p>
          <div className={cx.progress} aria-hidden="true">
            {questions.map((_, i) => (
              <span key={i} data-filled={i <= act.step} />
            ))}
          </div>
          <h3 tabIndex={-1} data-question-heading>
            {q.text}
          </h3>
          <p>Bạn có thể bỏ qua bất kỳ câu nào.</p>
          <fieldset disabled={act.answers[act.step] !== undefined}>
            <legend>Bạn chọn điều gì?</legend>
            {q.options.map((x) => (
              <label className={cx.radioRow} key={x}>
                <input
                  type="radio"
                  name={`q-${act.step}`}
                  checked={act.answers[act.step] === x}
                  onChange={() =>
                    dispatch({
                      type: "ACTIVITY_ANSWER",
                      id: act.id,
                      step: act.step,
                      text: x,
                    })
                  }
                />
                {x}
              </label>
            ))}
          </fieldset>
          {act.pending && <Typing />}
          {act.reply && <p className={cx.note}>Bạn cùng chơi: {act.reply}</p>}
          <div className={cx.actions}>
            <Button
              disabled={!act.reply || !!act.pending}
              onClick={() =>
                dispatch({ type: "ACTIVITY_NEXT", id: act.id, step: act.step })
              }
            >
              {act.step === 2 ? "Hoàn tất hoạt động" : "Câu tiếp theo"}
            </Button>
            <Button
              variant="secondary"
              disabled={act.answers[act.step] !== undefined}
              onClick={() =>
                dispatch({
                  type: "ACTIVITY_ANSWER",
                  id: act.id,
                  step: act.step,
                  outcome: "skip",
                })
              }
            >
              Bỏ qua câu này
            </Button>
          </div>
        </div>
      </Motion>
      <Button variant="text" onClick={() => setStop(true)}>
        Dừng ở đây
      </Button>
      {stop && (
        <Dialog
          destructive
          title="Dừng hoạt động ở đây?"
          onClose={() => setStop(false)}
        >
          <p>
            Các câu trả lời đã chọn chỉ ở trong phiên demo. Bạn vẫn có thể trò
            chuyện.
          </p>
          <div className={cx.actions}>
            <Button
              data-cancel
              variant="secondary"
              onClick={() => setStop(false)}
            >
              Chơi tiếp
            </Button>
            <Button
              variant="danger"
              onClick={() => {
                dispatch({ type: "ACTIVITY_STOP", id: act.id });
                setStop(false);
              }}
            >
              Dừng hoạt động
            </Button>
          </div>
        </Dialog>
      )}
    </>
  );
}
