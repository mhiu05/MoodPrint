import { useEffect, useRef, useState } from "react";
import {
  Link,
  useLocation,
  useNavigate,
  useParams,
  useSearchParams,
} from "react-router-dom";
import {
  ArrowRight,
  BookOpen,
  Check,
  CircleHelp,
  FileImage,
  FolderOpen,
  MessageCircle,
  Plus,
  Sparkles,
} from "lucide-react";
import { uid, useWorkspaceStore } from "../../app/store";
import {
  Badge,
  Button,
  EmptyState,
  Modal,
  Notice,
  PageHeader,
} from "../../components/ui";
import { AgentStatusOrb } from "../../animations/AgentStatusOrb";
import { chatFixtures, scenarios } from "../../mocks/scenarios";
import type { ChatFixture } from "../../mocks/scenarios";
import type { ChatMessage, ChatSession } from "../../types";
import { getServices } from "../../services/composition";
import { asLive } from "../../services/composition/companion-types";
import { LiveChatPage } from "./live/live-chat";
import { analysisVariants } from "./analysis-model";
import { startFixtureAnalysis } from "./analysis-workflow";
import {
  ChatTopBar,
  ChatComposer,
  MessageList,
  MessageBubble,
  TypingIndicator,
  AttachmentPreview,
} from "./chat-presentation";

const fallback =
  "Trong bản demo này mình chỉ có một số tình huống mẫu. Bạn có thể chọn câu gợi ý để tiếp tục tình huống gần nhất, hoặc lưu nội dung bạn vừa nhập vào hồ sơ nháp. Mình không tự hiểu hoặc phân tích câu tự do này.";
const articleFor = (fixture: ChatFixture) =>
  fixture.scenarioId === "SC-11"
    ? "nguoi-chung-kien"
    : fixture.scenarioId === "SC-13"
      ? "noi-chuyen-voi-nguoi-cham-soc"
      : ["SC-08", "SC-22"].includes(fixture.scenarioId)
        ? "luu-anh-chup-co-ngu-canh"
        : fixture.articleTopic === "Trực tuyến"
          ? "bat-nat-online"
          : fixture.articleTopic === "Giao tiếp"
            ? "noi-chuyen-voi-giao-vien"
            : "bat-nat-la-gi";

function Findings({
  fixture,
  caseId,
  onCreate,
  onAnalysis,
  contextualSlug,
}: {
  fixture: ChatFixture;
  caseId?: string;
  onCreate: () => void;
  onAnalysis: () => void;
  contextualSlug?: string;
}) {
  return (
    <div className="ai-findings">
      <div className="ai-findings-heading">
        <Sparkles size={19} />
        <strong>Cùng sắp xếp lại</strong>
        <Badge tone="neutral">Từ kịch bản mẫu</Badge>
      </div>
      <dl>
        <div>
          <dt>
            <Check size={16} />
            Điều bạn đã kể
          </dt>
          <dd>{fixture.observation}</dd>
        </div>
        <div>
          <dt>
            <CircleHelp size={16} />
            Dấu hiệu cần xem xét
          </dt>
          <dd>{fixture.indication}</dd>
        </div>
        <div>
          <dt>
            <CircleHelp size={16} />
            Điều chưa rõ
          </dt>
          <dd>
            {fixture.unknowns.map((unknown) => (
              <p key={unknown}>{unknown}</p>
            ))}
          </dd>
        </div>
        <div>
          <dt>
            <ArrowRight size={16} />
            Bước bạn có thể chọn
          </dt>
          <dd>{fixture.nextStep}</dd>
        </div>
      </dl>
      <details>
        <summary>Xem chi tiết lý do và nguồn</summary>
        <p>
          Phản hồi dựa vào tình huống hư cấu {fixture.scenarioId}, không xác
          minh danh tính hay sự việc. Hướng dẫn nền tảng có thể xem trong thư
          viện.
        </p>
        <Link to={`/knowledge/${contextualSlug || articleFor(fixture)}`}>
          <BookOpen size={16} />
          Mở bài hướng dẫn và nguồn tham khảo
        </Link>
      </details>
      <div className="actions">
        {fixture.urgent ? (
          <Link className="button primary" to="/support/urgent">
            Tìm hỗ trợ ngay
          </Link>
        ) : ["SC-08", "SC-22"].includes(fixture.scenarioId) ? (
          <Button onClick={onAnalysis}>
            <FileImage size={17} />
            Kiểm tra ảnh mẫu
          </Button>
        ) : caseId ? (
          <Link className="button primary" to={`/cases/${caseId}`}>
            Mở hồ sơ liên quan
          </Link>
        ) : (
          <Button onClick={onCreate}>
            <FolderOpen size={17} />
            Tạo hồ sơ từ lời kể
          </Button>
        )}
        <Link
          className="button secondary"
          to={`/ai/roleplay${caseId ? `?caseId=${caseId}` : ""}`}
        >
          Luyện cách nói
        </Link>
        {caseId && (
          <Link className="button secondary" to={`/cases/${caseId}/plan`}>
            Thêm vào kế hoạch ứng phó
          </Link>
        )}
      </div>
    </div>
  );
}

/** Real workspace with a live Companion → the real chat; otherwise the labelled simulation. */
export function ChatPage() {
  const real = useWorkspaceStore((state) => state.workspace.kind === "real");
  const companion = real ? asLive(getServices().companion) : null;
  return companion ? (
    <LiveChatPage service={companion} />
  ) : (
    <SimulatedChatPage />
  );
}

function SimulatedChatPage() {
  const { sessionId } = useParams();
  const [search] = useSearchParams();
  const location = useLocation();
  const navigate = useNavigate();
  const store = useWorkspaceStore();
  const demo = store.workspace.kind === "demo";
  const [draftId, setDraftId] = useState(() => uid("CHAT"));
  const [scenarioId, setScenarioId] = useState(
    search.get("scenario") ?? "SC-01",
  );
  const [attachments, setAttachments] = useState(false);
  const [optionsOpen, setOptionsOpen] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const [verified, setVerified] = useState(false);
  const [reviewText, setReviewText] = useState("");
  const [phase, setPhase] = useState<
    "idle" | "processing" | "responding" | "error"
  >("idle");
  const [partial, setPartial] = useState("");
  const [error, setError] = useState("");
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);
  const mounted = useRef(true);
  const completeRef = useRef<(() => void) | null>(null);
  const retryRef = useRef<(() => void) | null>(null);
  const session = store.chats.find(
    (item) =>
      item.id === (sessionId ?? draftId) && item.ownerId === store.user?.id,
  );
  const text = session?.draft ?? "";
  const currentScenario = session?.scenarioId ?? scenarioId;
  const fixture = chatFixtures.find(
    (item) => item.scenarioId === currentScenario,
  );
  const suggested = fixture?.messages[session?.cursor ?? 0];
  const busy = phase === "processing" || phase === "responding";
  const mine = store.cases.filter((item) => item.ownerId === store.user?.id);
  const externalContext =
    session?.sourceArticleId || search.get("articleId") || search.get("topic");
  const contextualSlug =
    session?.sourceArticleSlug || search.get("articleSlug") || undefined;
  const unfinished = session?.messages.at(-1)?.speaker === "user";
  const providedCase =
    search.get("caseId") ||
    (location.state as { caseId?: string } | null)?.caseId;
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      if (timer.current) clearInterval(timer.current);
    };
  }, []);
  function ensureSession(): ChatSession {
    if (session) return session;
    const linkedCaseId = mine.find((item) => item.id === providedCase)?.id;
    return {
      id: draftId,
      ownerId: store.user?.id ?? "USER-AN",
      ...(linkedCaseId ? { linkedCaseId } : {}),
      ...(search.get("articleId")
        ? {
            sourceArticleId: search.get("articleId")!,
            sourceArticleSlug: search.get("articleSlug") ?? undefined,
            sourceIds: (search.get("sourceIds") ?? "")
              .split(",")
              .filter(Boolean),
          }
        : {}),
      scenarioId: currentScenario,
      title:
        scenarios.find((item) => item.id === currentScenario)?.title ??
        "Trò chuyện mẫu",
      cursor: 0,
      messages: [],
    };
  }
  async function runReply(chatId: string, response: ChatMessage) {
    setError("");
    setPartial("");
    setPhase("processing");
    retryRef.current = () => {
      void runReply(chatId, response);
    };
    try {
      await getServices().run(
        () => undefined,
        store.preferences.reducedMotion ? 0 : 500,
      );
      if (!mounted.current) return;
      const finish = () => {
        if (timer.current) clearInterval(timer.current);
        timer.current = null;
        const current = useWorkspaceStore
          .getState()
          .chats.find((item) => item.id === chatId);
        if (
          current &&
          !current.messages.some((item) => item.id === response.id)
        )
          void getServices()
            .chat.save({
              ...current,
              messages: [
                ...current.messages,
                { ...response, createdAt: new Date().toISOString() },
              ],
            })
            .catch((cause: unknown) =>
              setError(
                cause instanceof Error
                  ? cause.message
                  : "Chưa giữ được phản hồi mẫu.",
              ),
            );
        setPartial("");
        setPhase("idle");
        completeRef.current = null;
        retryRef.current = null;
      };
      completeRef.current = finish;
      if (
        store.preferences.reducedMotion ||
        window.matchMedia("(prefers-reduced-motion: reduce)").matches
      ) {
        finish();
        return;
      }
      setPhase("responding");
      let length = 0;
      timer.current = setInterval(() => {
        length += 12;
        setPartial(response.body.slice(0, length));
        if (length >= response.body.length) finish();
      }, 28);
    } catch (cause) {
      if (mounted.current) {
        setPhase("error");
        setError(
          cause instanceof Error
            ? cause.message
            : "Phản hồi mẫu chưa mở được. Hãy thử lại.",
        );
      }
    }
  }
  function send(body: string, scenarioOverride?: string) {
    if (!body.trim() || busy || unfinished || phase === "error") return;
    const current = scenarioOverride
      ? {
          ...ensureSession(),
          id: uid("CHAT"),
          scenarioId: scenarioOverride,
          title:
            scenarios.find((item) => item.id === scenarioOverride)?.title ??
            "Trò chuyện mẫu",
          cursor: 0,
          messages: [],
          draft: "",
        }
      : ensureSession();
    const selectedFixture = scenarioOverride
      ? chatFixtures.find((item) => item.scenarioId === scenarioOverride)
      : fixture;
    const expected = selectedFixture?.messages[current.cursor];
    const accepted =
      expected?.speaker === "user" &&
      expected.body.trim().toLocaleLowerCase("vi") ===
        body.trim().toLocaleLowerCase("vi");
    const response: ChatMessage = accepted
      ? {
          ...selectedFixture!.messages[current.cursor + 1],
          id: uid("message"),
          sourceIds: [
            ...(selectedFixture!.messages[current.cursor + 1].sourceIds ?? []),
            ...(current.sourceArticleId ? [current.sourceArticleId] : []),
            ...(current.sourceIds ?? []),
          ],
        }
      : {
          id: uid("message"),
          speaker: "ai",
          body: fallback,
          sourceIds: current.sourceIds,
        };
    const next: ChatSession = {
      ...current,
      cursor: current.cursor + (accepted ? 2 : 0),
      draft: "",
      messages: [
        ...current.messages,
        {
          id: uid("message"),
          speaker: "user",
          body: body.trim(),
          createdAt: new Date().toISOString(),
        },
      ],
    };
    void getServices()
      .chat.save(next)
      .catch((cause: unknown) =>
        setError(
          cause instanceof Error ? cause.message : "Chưa giữ được lời kể.",
        ),
      );
    if (!sessionId || scenarioOverride)
      navigate(`/ai/chat/${next.id}`, { replace: true });
    void runReply(next.id, response);
  }
  function updateDraft(value: string) {
    const current = ensureSession();
    void getServices()
      .chat.save({ ...current, draft: value })
      .catch((cause: unknown) =>
        setError(
          cause instanceof Error ? cause.message : "Chưa giữ được bản nháp.",
        ),
      );
    if (!sessionId) navigate(`/ai/chat/${current.id}`, { replace: true });
  }
  function chooseScenario(id: string) {
    setScenarioId(id);
    setDraftId(uid("CHAT"));
    setError("");
    setPhase("idle");
    setOptionsOpen(false);
    navigate(`/ai/chat?scenario=${id}`);
  }
  function openCreate() {
    setOptionsOpen(false);
    const current = ensureSession();
    setReviewText(
      current.messages
        .filter((message) => message.speaker === "user")
        .map((message) => message.body)
        .join("\n"),
    );
    setVerified(false);
    setCreateOpen(true);
  }
  function goToWizard() {
    if (!verified || !reviewText.trim()) return;
    const current = ensureSession();
    void getServices().chat.save(current);
    navigate("/cases/new", {
      state: {
        prefill: {
          title: current.title,
          summary: reviewText,
          ...(demo ? { linkedChatIds: [current.id] } : {}),
          occurredAt: "",
          template: currentScenario === "SC-11" ? "TPL-WITNESS" : "TPL-FREE",
          perspective: currentScenario === "SC-11" ? "witness" : "self",
        },
      },
    });
  }
  if (sessionId && !session)
    return (
      <div className="ai-feature chat-unavailable">
        <PageHeader title="Cuộc trò chuyện mẫu" back="/ai" />
        <EmptyState
          title="Không tìm thấy cuộc trò chuyện này"
          description="Bạn có thể bắt đầu một cuộc trò chuyện mới trong tài khoản demo hiện tại."
          action={
            <Link className="button primary" to="/ai/chat">
              Bắt đầu cuộc trò chuyện
            </Link>
          }
        />
      </div>
    );
  return (
    <div className="ai-feature chat-layout">
      <ChatTopBar
        phase={phase}
        onHistory={() => setHistoryOpen(true)}
        onMenu={() => setOptionsOpen(true)}
      />
      {!demo && (
        <Notice>
          AI mô phỏng · Cuộc trò chuyện chỉ lưu trên thiết bị này. Lời kể chuyển
          sang hồ sơ cần bạn kiểm tra và lưu riêng.
        </Notice>
      )}
      <MessageList
        sessionKey={session?.id ?? draftId}
        revision={`${session?.messages.length ?? 0}:${partial}:${phase}`}
        lastSpeaker={session?.messages.at(-1)?.speaker}
      >
        {externalContext && (
          <div className="chat-context">
            Từ thư viện {externalContext}
            {contextualSlug && (
              <Link
                className="ai-context-source"
                to={`/knowledge/${contextualSlug}`}
              >
                Mở bài đã tham khảo <ArrowRight size={15} />
              </Link>
            )}
            <span>Giữ nguồn tham khảo · Phản hồi theo kịch bản mẫu.</span>
          </div>
        )}
        {!session?.messages.length && (
          <div className="chat-empty">
            <AgentStatusOrb state="idle" size={64} showLabel={false} />
            <h2>Mình nghe bạn kể.</h2>
            <p>Bạn muốn bắt đầu từ chuyện gì?</p>
            <div className="chat-starters">
              {suggested?.speaker === "user" && (
                <div className="ai-quick-reply">
                  <button onClick={() => send(suggested.body)}>
                    {suggested.body}
                    <ArrowRight size={16} />
                  </button>
                </div>
              )}
              <button
                onClick={() =>
                  send(
                    chatFixtures.find((item) => item.scenarioId === "SC-11")!
                      .messages[0].body,
                    "SC-11",
                  )
                }
              >
                Mình muốn giúp một người bạn <ArrowRight size={16} />
              </button>
              <button
                onClick={() =>
                  send(
                    chatFixtures.find((item) => item.scenarioId === "SC-13")!
                      .messages[0].body,
                    "SC-13",
                  )
                }
              >
                Mình chưa biết nói với ai <ArrowRight size={16} />
              </button>
            </div>
            {!fixture && (
              <p className="ai-demo-footnote">
                Tình huống này chưa có hội thoại dựng sẵn. Lời bạn kể vẫn có thể
                lưu vào hồ sơ nháp.
              </p>
            )}
          </div>
        )}
        {session?.messages.map((message, index) => (
          <MessageBubble
            key={message.id}
            message={message}
            grouped={
              index > 0 &&
              session.messages[index - 1].speaker === message.speaker
            }
          >
            {message.rich &&
              fixture &&
              !message.sourceIds?.some((id) => id.startsWith("ANALYSIS")) && (
                <Findings
                  fixture={fixture}
                  contextualSlug={contextualSlug}
                  caseId={session.linkedCaseId}
                  onCreate={openCreate}
                  onAnalysis={() =>
                    navigate(
                      `/ai/analysis/${startFixtureAnalysis(currentScenario === "SC-22" ? "conflict" : "multi", session.id).id}`,
                    )
                  }
                />
              )}
            {message.sourceIds
              ?.filter((id) => id.startsWith("ANALYSIS"))
              .map((id) => (
                <AttachmentPreview key={id} analysisId={id} />
              ))}
          </MessageBubble>
        ))}
        {busy && (
          <TypingIndicator
            phase={phase}
            partial={partial}
            onComplete={() => completeRef.current?.()}
          />
        )}
        {error && (
          <Notice tone="error">
            {error}
            <Button variant="secondary" onClick={() => retryRef.current?.()}>
              Thử lại phản hồi mẫu
            </Button>
          </Notice>
        )}
        {unfinished && !busy && !error && session && (
          <Notice>
            Lượt phản hồi trước đã dừng. Lời bạn nhập vẫn được giữ.
            <Button
              variant="secondary"
              onClick={() => {
                const lastUser = session.messages.at(-1);
                const previous = fixture?.messages[session.cursor - 2];
                const response: Omit<ChatMessage, "id"> =
                  previous?.body.trim().toLocaleLowerCase("vi") ===
                  lastUser?.body.trim().toLocaleLowerCase("vi")
                    ? fixture!.messages[session.cursor - 1]
                    : { speaker: "ai" as const, body: fallback };
                void runReply(session.id, {
                  ...response,
                  id: uid("message"),
                  sourceIds: [
                    ...(response.sourceIds ?? []),
                    ...(session.sourceIds ?? []),
                    ...(session.sourceArticleId
                      ? [session.sourceArticleId]
                      : []),
                  ],
                });
              }}
            >
              Tiếp tục phản hồi mẫu
            </Button>
          </Notice>
        )}
      </MessageList>
      <ChatComposer
        value={text}
        onChange={updateDraft}
        onSend={() => send(text)}
        onAttach={() => setAttachments(true)}
        blocked={busy || unfinished || phase === "error"}
        busy={busy}
        suggestions={
          session &&
          session.messages.length > 0 &&
          suggested?.speaker === "user" &&
          !busy &&
          !unfinished &&
          phase !== "error" ? (
            <div className="ai-quick-reply">
              <button className="chip" onClick={() => send(suggested.body)}>
                {suggested.body}
                <ArrowRight size={16} />
              </button>
            </div>
          ) : undefined
        }
      />
      <Modal
        open={optionsOpen}
        onClose={() => setOptionsOpen(false)}
        title="Tùy chọn cuộc trò chuyện"
      >
        <div className="stack">
          <div className="chat-menu-actions">
            <Button
              variant="ghost"
              disabled={busy}
              onClick={() => chooseScenario(currentScenario)}
            >
              <Plus size={18} />
              Cuộc trò chuyện mới
            </Button>
            <Button
              variant="ghost"
              disabled={
                !session?.messages.some(
                  (message) => message.speaker === "user",
                ) || busy
              }
              onClick={openCreate}
            >
              <FolderOpen size={18} />
              Lưu lời kể vào hồ sơ
            </Button>
            <Link
              className="button ghost"
              to={`/ai/roleplay${session?.linkedCaseId ? `?caseId=${session.linkedCaseId}` : ""}`}
            >
              <MessageCircle size={18} />
              Luyện cách nói
            </Link>
            <Link className="button ghost" to="/support/urgent">
              Tìm hỗ trợ ngay <ArrowRight size={16} />
            </Link>
          </div>
          <div className="chat-menu-context">
            <label htmlFor="chat-scenario">Chọn tình huống mẫu</label>
            <select
              id="chat-scenario"
              value={currentScenario}
              disabled={busy}
              onChange={(event) => chooseScenario(event.target.value)}
            >
              {scenarios.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.id} · {item.title}
                </option>
              ))}
            </select>
            <p className="ai-demo-footnote">
              30 tình huống hư cấu · 12 hội thoại nhiều lượt. Đổi tình huống mở
              cuộc trò chuyện mới; lịch sử và bản nháp cũ được giữ.
            </p>
          </div>
          <div className="chat-menu-context">
            <label htmlFor="chat-linked-case">Hồ sơ liên quan</label>
            <select
              id="chat-linked-case"
              disabled={busy}
              value={
                session?.linkedCaseId ??
                mine.find((item) => item.id === providedCase)?.id ??
                ""
              }
              onChange={(event) =>
                void getServices().chat.save({
                  ...ensureSession(),
                  linkedCaseId: event.target.value || undefined,
                })
              }
            >
              <option value="">Chưa chọn hồ sơ</option>
              {mine.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.title}
                </option>
              ))}
            </select>
            {session?.linkedCaseId && (
              <Link
                className="button ghost"
                to={`/cases/${session.linkedCaseId}`}
              >
                Xem hồ sơ <ArrowRight size={16} />
              </Link>
            )}
          </div>
          <p className="ai-demo-footnote">
            Câu tự do được lưu nguyên văn. AI chỉ phản hồi theo kịch bản có sẵn,
            không tự phân tích thông tin ngoài mẫu.
          </p>
        </div>
      </Modal>
      <Modal
        open={historyOpen}
        onClose={() => setHistoryOpen(false)}
        title="Lịch sử trò chuyện"
      >
        <div className="chat-history">
          {store.chats
            .filter((chat) => chat.ownerId === store.user?.id)
            .reverse()
            .map((chat) => (
              <button
                className="ai-recent-row"
                key={chat.id}
                disabled={busy}
                aria-current={chat.id === session?.id ? "page" : undefined}
                onClick={() => {
                  setHistoryOpen(false);
                  setPhase("idle");
                  setError("");
                  navigate(`/ai/chat/${chat.id}`);
                }}
              >
                <MessageCircle size={20} />
                <div>
                  <strong>{chat.title}</strong>
                  <small>
                    {chat.draft ? "Có bản nháp · " : ""}
                    {chat.messages.length} tin nhắn
                  </small>
                </div>
                <ArrowRight size={18} />
              </button>
            ))}
          {!store.chats.some((chat) => chat.ownerId === store.user?.id) && (
            <p>Cuộc trò chuyện và bản nháp sẽ ở đây để bạn quay lại.</p>
          )}
          <Button
            variant="secondary"
            disabled={busy}
            onClick={() => {
              setHistoryOpen(false);
              chooseScenario(currentScenario);
            }}
          >
            <Plus size={18} />
            Cuộc trò chuyện mới
          </Button>
        </div>
      </Modal>
      <Modal
        open={attachments}
        onClose={() => setAttachments(false)}
        title="Đính kèm bộ dữ liệu mẫu"
      >
        <div className="stack">
          <Notice>
            Chỉ sử dụng ảnh hư cấu có sẵn. Không tải, đọc hoặc gửi file cá nhân.
          </Notice>
          {analysisVariants.map((variant) => (
            <button
              className="ai-attachment-option"
              key={variant.id}
              onClick={() => {
                const current = ensureSession();
                void getServices().chat.save(current);
                const analysis = startFixtureAnalysis(variant.id, current.id);
                setAttachments(false);
                navigate(`/ai/analysis/${analysis.id}`);
              }}
            >
              <FileImage size={23} />
              <span>
                <strong>{variant.label}</strong>
                <small>{variant.description}</small>
              </span>
              <ArrowRight size={18} />
            </button>
          ))}
        </div>
      </Modal>
      <Modal
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        title="Kiểm tra lời kể trước khi tạo hồ sơ"
      >
        <div className="stack">
          <p>
            Chỉ lời bạn đã nhập được chuyển sang biểu mẫu. Bạn có thể sửa và bổ
            sung ở bước tiếp theo; nhận định mẫu của AI không được chuyển thành
            sự thật.
          </p>
          <div className="field">
            <label htmlFor="chat-review">Lời kể muốn giữ</label>
            <textarea
              id="chat-review"
              rows={6}
              value={reviewText}
              onChange={(event) => {
                setReviewText(event.target.value);
                setVerified(false);
              }}
            />
          </div>
          <label className="ai-check-label">
            <input
              type="checkbox"
              checked={verified}
              onChange={(event) => setVerified(event.target.checked)}
            />
            Mình đã kiểm tra và muốn dùng nội dung này để tạo hồ sơ.
          </label>
          <div className="actions">
            <Button
              disabled={!verified || !reviewText.trim()}
              onClick={goToWizard}
            >
              Xác nhận và tiếp tục
              <ArrowRight size={18} />
            </Button>
            <Button variant="secondary" onClick={() => setCreateOpen(false)}>
              Kể tiếp
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
