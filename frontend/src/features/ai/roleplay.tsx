import { useRef, useState } from "react";
import {
  Link,
  useLocation,
  useNavigate,
  useParams,
  useSearchParams,
} from "react-router-dom";
import {
  ArrowRight,
  Check,
  CircleHelp,
  MessageCircle,
  Mic,
  Pause,
  Play,
  RotateCcw,
  Send,
  Square,
  UserRound,
} from "lucide-react";
import { uid, useDemoStore } from "../../app/store";
import {
  Badge,
  Button,
  EmptyState,
  Modal,
  Notice,
  PageHeader,
  Progress,
} from "../../components/ui";
import { AgentStatusOrb } from "../../animations/AgentStatusOrb";
import { demoService } from "../../mocks/services/demo";
import {
  getRoleplayPrompt,
  roleLabels,
  roleplayScripts,
} from "../../mocks/scenarios";
import type { Role } from "../../mocks/scenarios";
import type { ChatMessage, RoleplaySession } from "../../types";

export function RoleplayPage() {
  const { role } = useParams();
  const [query] = useSearchParams();
  const location = useLocation();
  const navigate = useNavigate();
  const store = useDemoStore();
  const knownRole =
    role && Object.keys(roleLabels).includes(role) ? (role as Role) : undefined;
  const scripts = roleplayScripts.filter(
    (script) => !knownRole || script.role === knownRole,
  );
  const [selectedId, setSelectedId] = useState(
    query.get("script") ?? scripts[0]?.id ?? roleplayScripts[0].id,
  );
  const selected =
    scripts.find((script) => script.id === selectedId) ?? scripts[0];
  const [goal, setGoal] = useState("");
  const [tone, setTone] = useState("gentle");
  const [mode, setMode] = useState<"text" | "voice_demo">("text");
  const [text, setText] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [endOpen, setEndOpen] = useState(false);
  const [voicePlaying, setVoicePlaying] = useState(false);
  const [chosenLines, setChosenLines] = useState<string[]>([]);
  const lastTurn = useRef<{ id: string; body: string } | null>(null);
  const feedback = location.pathname.endsWith("/feedback");
  const requestedSession = query.get("session");
  const sessions = store.roleplays.filter(
    (item) =>
      item.ownerId === store.user?.id &&
      (!knownRole || item.role === knownRole),
  );
  const session = requestedSession
    ? sessions.find((item) => item.id === requestedSession)
    : feedback
      ? sessions.at(-1)
      : undefined;
  const script =
    roleplayScripts.find((item) => item.id === session?.scenarioId) ?? selected;
  const caseId = store.cases.find(
    (item) =>
      item.ownerId === store.user?.id && item.id === query.get("caseId"),
  )?.id;
  const context = caseId ? `&caseId=${caseId}` : "";
  const userTurns =
    session?.turns.filter((turn) => turn.speaker === "user") ?? [];
  const returnUrl = session
    ? `/ai/roleplay/${session.role}?session=${session.id}${context}`
    : "/ai/roleplay";
  function begin() {
    if (!selected) return;
    const id = uid("RP");
    const item: RoleplaySession = {
      id,
      ownerId: store.user?.id ?? "USER-AN",
      role: selected.role,
      scenarioId: selected.id,
      tone,
      mode,
      cursor: 0,
      status: "active",
      turns: [
        {
          id: uid("turn"),
          speaker: "system",
          body: `Mục tiêu buổi tập: ${goal.trim() || selected.goal}. Đây là người nghe mô phỏng, không phải người thật.`,
        },
        {
          id: uid("turn"),
          speaker: "ai",
          body: getRoleplayPrompt(selected, 0, tone),
        },
      ],
    };
    store.putRoleplay(item);
    setText("");
    setError("");
    setChosenLines([]);
    navigate(`/ai/roleplay/${selected.role}?session=${id}${context}`);
  }
  async function reply(body: string, retry = false) {
    if (
      !session ||
      !script ||
      pending ||
      session.status !== "active" ||
      !body.trim()
    )
      return;
    setPending(true);
    setError("");
    const currentId = session.id;
    const currentCursor = session.cursor;
    if (!retry) {
      lastTurn.current = { id: uid("turn"), body: body.trim() };
      store.putRoleplay({
        ...session,
        turns: [
          ...session.turns,
          { id: lastTurn.current.id, speaker: "user", body: body.trim() },
        ],
      });
      setText("");
    }
    try {
      await demoService.run(
        () => {
          const current = useDemoStore
            .getState()
            .roleplays.find((item) => item.id === currentId);
          if (!current) return;
          const cursor = Math.min(currentCursor + 1, script.replies.length);
          const next: ChatMessage = {
            id: uid("turn"),
            speaker: "ai",
            body: getRoleplayPrompt(script, cursor, current.tone),
          };
          useDemoStore.getState().putRoleplay({
            ...current,
            cursor,
            turns: [...current.turns, next],
            status: cursor >= script.replies.length ? "completed" : "active",
          });
        },
        store.preferences.reducedMotion ? 0 : 500,
      );
      setVoicePlaying(false);
      lastTurn.current = null;
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : "Chưa mở được lượt mẫu. Nội dung bạn nói vẫn được giữ.",
      );
    } finally {
      setPending(false);
    }
  }
  function finish() {
    if (!session) return;
    store.putRoleplay({ ...session, status: "completed" });
    setEndOpen(false);
    setVoicePlaying(false);
    navigate(
      `/ai/roleplay/${session.role}/feedback?session=${session.id}${context}`,
    );
  }
  function sendToSupport() {
    const selectedLines = userTurns.filter((turn) =>
      chosenLines.includes(turn.id),
    );
    if (!selectedLines.length) return;
    navigate(`/support/prepare${caseId ? `?caseId=${caseId}` : ""}`, {
      state: { content: selectedLines.map((turn) => turn.body).join("\n\n") },
    });
  }
  if (role && !knownRole)
    return (
      <div className="ai-feature">
        <PageHeader title="Phòng luyện nói" back="/ai" />
        <EmptyState
          title="Chưa có vai luyện tập này"
          action={
            <Link className="button primary" to="/ai/roleplay">
              Chọn người nghe mẫu
            </Link>
          }
        />
      </div>
    );
  if ((requestedSession || feedback) && !session)
    return (
      <div className="ai-feature">
        <PageHeader title="Buổi luyện nói" back="/ai/roleplay" />
        <EmptyState
          title="Không tìm thấy buổi luyện này"
          description="Chọn một người nghe và bắt đầu một buổi tập mới."
          action={
            <Link className="button primary" to="/ai/roleplay">
              Về phòng luyện nói
            </Link>
          }
        />
      </div>
    );
  if (feedback && session && script)
    return (
      <div className="ai-feature ai-roleplay-page stack">
        <PageHeader
          title="Mang theo một câu bạn muốn nói."
          description="Bạn có thể thử lại, sửa lời của mình hoặc dừng ở đây."
          back={returnUrl}
          action={<Badge tone="lavender">Phản hồi mẫu</Badge>}
        />
        <div className="ai-feedback-intro">
          <AgentStatusOrb state="idle" size={64} showLabel={false} />
          <div>
            <h2>Mỗi lần tập là một lần chuẩn bị.</h2>
            <p>
              Bạn đã có {userTurns.length} lượt nói với vai{" "}
              {roleLabels[session.role as Role].toLocaleLowerCase("vi")}. Không
              có điểm số hoặc đánh giá con người.
            </p>
          </div>
        </div>
        <Notice>
          Đây là gợi ý cố định cho kịch bản “{script.title}”, không phải AI đã
          phân tích lời nhập tự do của bạn. Buổi tập chưa gửi hoặc liên hệ ai.
        </Notice>
        <div className="ai-feedback-sections">
          <section>
            <h2>
              <Check size={20} />
              Điều đã luyện rõ
            </h2>
            <p>
              {userTurns.length
                ? script.strength
                : "Bạn chưa có lượt nói nào. Bạn có thể quay lại và thử một câu mở đầu khi sẵn sàng."}
            </p>
          </section>
          <section>
            <h2>
              <CircleHelp size={20} />
              Có thể bổ sung
            </h2>
            <p>{script.improve}</p>
            <p className="muted">
              Thử kiểm tra: sự việc cụ thể, thời gian/bối cảnh, lời nhờ giúp,
              điều chưa chắc và cách diễn đạt tôn trọng.
            </p>
          </section>
          <section>
            <h2>
              <MessageCircle size={20} />
              Một câu để thử
            </h2>
            <blockquote>{script.example}</blockquote>
          </section>
        </div>
        <section className="panel">
          <h2>Chọn lời của bạn để chuẩn bị tin nhắn</h2>
          <p>
            Chỉ những đoạn bạn chọn bên dưới mới được đưa sang bản nháp hỗ trợ.
          </p>
          {userTurns.length ? (
            <div className="stack">
              {userTurns.map((turn) => (
                <label className="ai-transcript-choice" key={turn.id}>
                  <input
                    type="checkbox"
                    checked={chosenLines.includes(turn.id)}
                    onChange={(event) =>
                      setChosenLines((lines) =>
                        event.target.checked
                          ? [...lines, turn.id]
                          : lines.filter((id) => id !== turn.id),
                      )
                    }
                  />
                  <span>{turn.body}</span>
                </label>
              ))}
              <Button disabled={!chosenLines.length} onClick={sendToSupport}>
                Chuẩn bị lời nhắn từ {chosenLines.length} đoạn đã chọn
                <ArrowRight size={18} />
              </Button>
            </div>
          ) : (
            <p className="muted">Chưa có lời của bạn để đưa sang bản nháp.</p>
          )}
        </section>
        <details className="panel">
          <summary>Xem lại toàn bộ transcript mẫu</summary>
          <div className="ai-roleplay-transcript">
            {session.turns.map((turn) => (
              <div className={`ai-message ${turn.speaker}`} key={turn.id}>
                <small>
                  {turn.speaker === "user"
                    ? "Bạn"
                    : turn.speaker === "system"
                      ? "Bối cảnh buổi tập"
                      : `${roleLabels[session.role as Role]} · mô phỏng`}
                </small>
                <p>{turn.body}</p>
              </div>
            ))}
          </div>
        </details>
        <div className="actions">
          <Button
            onClick={() => {
              setSelectedId(script.id);
              setMode(session.mode);
              setTone(session.tone);
              navigate(
                `/ai/roleplay/${session.role}${caseId ? `?caseId=${caseId}` : ""}`,
              );
            }}
          >
            <RotateCcw size={17} />
            Luyện lại tình huống này
          </Button>
          <Link className="button secondary" to="/ai/roleplay">
            Chọn người lớn khác
          </Link>
          {caseId && (
            <Link className="button secondary" to={`/cases/${caseId}`}>
              Về hồ sơ liên quan
            </Link>
          )}
        </div>
      </div>
    );
  if (!session)
    return (
      <div className="ai-feature ai-roleplay-page stack">
        <PageHeader
          title="Thử nói trước, theo cách của bạn."
          description="Chọn một người nghe mẫu. Bạn có thể tạm dừng và làm lại bất cứ lúc nào."
          back="/ai"
          action={<Badge tone="lavender">Phòng luyện nói</Badge>}
        />
        <div className="ai-roleplay-setup">
          <section>
            <h2>Bạn muốn luyện với ai?</h2>
            <div className="ai-role-tabs">
              {(Object.entries(roleLabels) as [Role, string][]).map(
                ([value, label]) => (
                  <Link
                    key={value}
                    className={knownRole === value ? "active" : ""}
                    to={`/ai/roleplay/${value}${caseId ? `?caseId=${caseId}` : ""}`}
                  >
                    <UserRound size={22} />
                    {label}
                  </Link>
                ),
              )}
            </div>
            <h2>Chọn cuộc trò chuyện muốn thử</h2>
            <div className="ai-script-list">
              {scripts.map((item) => (
                <label
                  className={`ai-script-choice ${selected?.id === item.id ? "selected" : ""}`}
                  key={item.id}
                >
                  <input
                    type="radio"
                    name="script"
                    checked={selected?.id === item.id}
                    onChange={() => {
                      setSelectedId(item.id);
                      setGoal("");
                    }}
                  />
                  <span>
                    <strong>{item.title}</strong>
                    <small>
                      {item.goal} · {roleLabels[item.role]}
                    </small>
                  </span>
                </label>
              ))}
            </div>
          </section>
          <section className="ai-setup-details panel">
            <AgentStatusOrb state="idle" size={64} showLabel={false} />
            <h2>Bạn chọn nhịp của buổi tập.</h2>
            <div className="field">
              <label htmlFor="roleplay-goal">Mục tiêu của mình</label>
              <textarea
                id="roleplay-goal"
                rows={3}
                value={goal}
                placeholder={selected?.goal}
                onChange={(event) => setGoal(event.target.value)}
              />
            </div>
            <div className="field">
              <label htmlFor="roleplay-tone">Cách người nghe phản hồi</label>
              <select
                id="roleplay-tone"
                value={tone}
                onChange={(event) => setTone(event.target.value)}
              >
                <option value="gentle">Nhẹ nhàng, từng bước</option>
                <option value="neutral">Trung tính, hỏi rõ sự việc</option>
                <option value="respectfully_challenging">
                  Hỏi kỹ nhưng tôn trọng
                </option>
              </select>
              <small>
                Cách xưng hô là mẫu. Độ khó không tạo phản hồi xúc phạm.
              </small>
            </div>
            <fieldset className="ai-mode-fieldset">
              <legend>Cách luyện</legend>
              <label>
                <input
                  type="radio"
                  checked={mode === "text"}
                  onChange={() => setMode("text")}
                />
                <MessageCircle size={17} />
                Bằng chữ
              </label>
              <label>
                <input
                  type="radio"
                  checked={mode === "voice_demo"}
                  onChange={() => setMode("voice_demo")}
                />
                <Mic size={17} />
                Voice demo
              </label>
            </fieldset>
            {mode === "voice_demo" && (
              <Notice>
                Voice demo chỉ hiển thị nhịp và transcript. Không thu âm, không
                phát âm thanh, không xin quyền microphone.
              </Notice>
            )}
            {caseId && (
              <Link className="ai-source" to={`/cases/${caseId}`}>
                Đang chuẩn bị từ hồ sơ liên quan
              </Link>
            )}
            <Button onClick={begin}>
              Bắt đầu buổi luyện
              <ArrowRight size={18} />
            </Button>
            <small className="muted">
              Kịch bản có 3 lượt của bạn. Lời tự nhập không được AI phân tích.
            </small>
          </section>
        </div>
        {sessions.filter((item) => item.status !== "completed").length > 0 && (
          <section>
            <h2>Buổi tập đang làm dở</h2>
            {sessions
              .filter((item) => item.status !== "completed")
              .slice(-3)
              .reverse()
              .map((item) => (
                <Link
                  className="ai-recent-row"
                  key={item.id}
                  to={`/ai/roleplay/${item.role}?session=${item.id}${context}`}
                >
                  <MessageCircle size={20} />
                  <div>
                    <strong>
                      {
                        roleplayScripts.find(
                          (candidate) => candidate.id === item.scenarioId,
                        )?.title
                      }
                    </strong>
                    <small>
                      {item.cursor}/3 lượt ·{" "}
                      {item.status === "paused"
                        ? "Đang tạm dừng"
                        : "Đang luyện"}
                    </small>
                  </div>
                  <ArrowRight size={18} />
                </Link>
              ))}
          </section>
        )}
      </div>
    );
  if (!script) return null;
  return (
    <div className="ai-feature ai-roleplay-page stack">
      <PageHeader
        title={script.title}
        description={`Người nghe: ${roleLabels[session.role as Role]} · ${session.mode === "text" ? "Bằng chữ" : "Voice demo"}`}
        back="/ai/roleplay"
        action={<Badge tone="lavender">Người nghe mô phỏng</Badge>}
      />
      <section className="ai-roleplay-stage">
        <div className="ai-roleplay-stage-top">
          <AgentStatusOrb
            state={
              pending
                ? "responding"
                : voicePlaying && session.status === "active"
                  ? "listening"
                  : "idle"
            }
            size={64}
          />
          <div>
            <h2>
              {session.status === "paused"
                ? "Mình tạm dừng ở đây."
                : session.status === "completed"
                  ? "Bạn đã đi hết kịch bản mẫu."
                  : "Bạn có thể nói từng câu một."}
            </h2>
            <p>
              {session.cursor}/3 lượt đã luyện ·{" "}
              {session.tone === "gentle"
                ? "Nhẹ nhàng"
                : session.tone === "neutral"
                  ? "Trung tính"
                  : "Hỏi kỹ, tôn trọng"}
            </p>
          </div>
        </div>
        <Progress value={session.cursor} max={3} />
        {session.mode === "voice_demo" && (
          <div className="ai-voice-demo">
            <div
              className={`ai-wave ${voicePlaying ? "playing" : ""}`}
              aria-hidden="true"
            >
              {Array.from({ length: 18 }, (_, index) => (
                <span
                  key={index}
                  style={{
                    height: `${14 + ((index * 13) % 35)}px`,
                    animationDelay: `${index * 40}ms`,
                  }}
                />
              ))}
            </div>
            <div>
              <strong>Voice demo · không có âm thanh hoặc ghi âm</strong>
              <p>Phát nhịp mô phỏng và dùng cùng transcript với chế độ chữ.</p>
            </div>
            <Button
              variant="secondary"
              disabled={session.status !== "active" || pending}
              onClick={() => setVoicePlaying((value) => !value)}
            >
              {voicePlaying ? <Pause size={18} /> : <Play size={18} />}
              {voicePlaying ? "Dừng nhịp mô phỏng" : "Phát nhịp mô phỏng"}
            </Button>
          </div>
        )}
        <div
          className="ai-roleplay-transcript"
          role="log"
          aria-label="Transcript buổi tập"
        >
          {session.turns.map((turn) => (
            <div key={turn.id} className={`ai-message ${turn.speaker}`}>
              <small>
                {turn.speaker === "user"
                  ? "Bạn"
                  : turn.speaker === "system"
                    ? "Bối cảnh"
                    : `${roleLabels[session.role as Role]} · mô phỏng`}
              </small>
              <p>{turn.body}</p>
            </div>
          ))}
          {pending && (
            <p className="ai-turn-status" role="status">
              Đang mở lượt tiếp theo trong kịch bản…
            </p>
          )}
        </div>
        {error && (
          <Notice tone="error">
            {error}
            <Button
              variant="secondary"
              disabled={pending}
              onClick={() =>
                lastTurn.current && reply(lastTurn.current.body, true)
              }
            >
              Thử lại lượt mẫu
            </Button>
          </Notice>
        )}
        {session.status === "active" && (
          <div className="ai-roleplay-composer">
            <small>
              Câu gợi ý cho lượt {session.cursor + 1} · bạn có thể viết lại theo
              cách của mình
            </small>
            <Button
              variant="secondary"
              disabled={pending || !!error}
              onClick={() => setText(script.replies[session.cursor])}
            >
              Dùng câu gợi ý
            </Button>
            <form
              onSubmit={(event) => {
                event.preventDefault();
                void reply(text);
              }}
            >
              <div className="field">
                <label htmlFor="roleplay-response">Lời bạn muốn thử</label>
                <textarea
                  id="roleplay-response"
                  rows={3}
                  value={text}
                  disabled={pending || !!error}
                  onChange={(event) => setText(event.target.value)}
                  placeholder={script.replies[session.cursor]}
                />
              </div>
              <Button
                disabled={!text.trim() || pending || !!error}
                type="submit"
              >
                <Send size={17} />
                {session.mode === "voice_demo"
                  ? "Dùng câu này trong voice demo"
                  : "Nói câu này"}
              </Button>
            </form>
            <p className="ai-demo-footnote">
              Câu trả lời tiếp theo dựng sẵn; nội dung tự nhập chỉ lưu vào
              transcript.
            </p>
          </div>
        )}
        <div className="actions ai-roleplay-controls">
          {session.status === "completed" ? (
            <Link
              className="button primary"
              to={`/ai/roleplay/${session.role}/feedback?session=${session.id}${context}`}
            >
              Xem gợi ý sau buổi tập
              <ArrowRight size={18} />
            </Link>
          ) : (
            <>
              <Button
                variant="secondary"
                disabled={pending}
                onClick={() => {
                  store.putRoleplay({
                    ...session,
                    status: session.status === "paused" ? "active" : "paused",
                  });
                  setVoicePlaying(false);
                }}
              >
                {session.status === "paused" ? (
                  <Play size={17} />
                ) : (
                  <Pause size={17} />
                )}
                {session.status === "paused" ? "Tiếp tục buổi tập" : "Tạm dừng"}
              </Button>
              <Button
                variant="ghost"
                disabled={pending}
                onClick={() => setEndOpen(true)}
              >
                <Square size={16} />
                Kết thúc buổi tập
              </Button>
            </>
          )}
        </div>
      </section>
      <Modal
        open={endOpen}
        onClose={() => setEndOpen(false)}
        title="Kết thúc buổi luyện này?"
      >
        <div className="stack">
          <p>
            Transcript {userTurns.length} lượt của bạn sẽ được giữ trong bản
            demo. Bạn có thể xem gợi ý và bắt đầu lại khi muốn.
          </p>
          <div className="actions">
            <Button onClick={finish}>Kết thúc và xem gợi ý</Button>
            <Button variant="secondary" onClick={() => setEndOpen(false)}>
              Luyện tiếp
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
