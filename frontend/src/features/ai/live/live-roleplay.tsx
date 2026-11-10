import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { Button, EmptyState, Notice, PageHeader } from "../../../components/ui";
import type {
  LiveCompanion,
  RoleplayRole,
  RoleplayScenario,
  RoleplaySessionView,
} from "../../../services/composition/companion-types";
import { Thread, UrgentBlock } from "./live-chat";
import { describeFailure } from "./use-live-chat";
import { useWorkspaceStore } from "../../../app/store";
import "./live.css";

const roleNames: Record<RoleplayRole, string> = {
  teacher: "Giáo viên",
  parent: "Phụ huynh",
  trusted_adult: "Người lớn đáng tin",
};

function Feedback({ session }: { session: RoleplaySessionView }) {
  const f = session.feedback;
  if (!f) return null;
  return (
    <section
      className="live-feedback"
      data-testid="roleplay-feedback"
      aria-label="Phản hồi buổi luyện"
    >
      <h3>Phản hồi sau buổi luyện</h3>
      <p>{f.summary}</p>
      <h4>Điều bạn làm tốt</h4>
      <ul>
        {f.strengths.map((s, i) => (
          <li key={i}>{s}</li>
        ))}
      </ul>
      <h4>Gợi ý cho lần sau</h4>
      <ul>
        {f.suggestions.map((s, i) => (
          <li key={i}>{s}</li>
        ))}
      </ul>
      {f.rephrasings.length > 0 && (
        <>
          <h4>Cách nói khác</h4>
          <ul>
            {f.rephrasings.map((r, i) => (
              <li key={i}>
                “{r.original}” → “{r.better}” <small>({r.why})</small>
              </li>
            ))}
          </ul>
        </>
      )}
      <h4>Bước tiếp theo</h4>
      <ul>
        {f.followUps.map((s, i) => (
          <li key={i}>{s}</li>
        ))}
      </ul>
      {f.safetyNote && <Notice>{f.safetyNote}</Notice>}
    </section>
  );
}

export function LiveRoleplayPage({ service }: { service: LiveCompanion }) {
  const { role } = useParams();
  const [query, setQuery] = useSearchParams();
  const [scenarios, setScenarios] = useState<RoleplayScenario[] | null>(null);
  const [session, setSession] = useState<RoleplaySessionView | null>(null);
  const [key, setKey] = useState("");
  const [goal, setGoal] = useState("");
  const [difficulty, setDifficulty] = useState(1);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [history, setHistory] = useState<RoleplaySessionView[]>([]);
  const [loading, setLoading] = useState(true);
  const [attempt, setAttempt] = useState(0);
  const [useCase, setUseCase] = useState(false);
  const cases = useWorkspaceStore((s) => s.cases);
  const user = useWorkspaceStore((s) => s.user);
  const linkedCase = cases.find(
    (c) => c.id === query.get("caseId") && c.ownerId === user?.id,
  );
  const activeId = session?.id;
  const sessionRevision = useRef(0);
  const activeSession = useRef<string | null>(null);

  useEffect(() => {
    let current = true;
    Promise.all([service.roleplay.scenarios(), service.roleplay.list()])
      .then(([choices, sessions]) => {
        if (!current) return;
        setScenarios(choices);
        setHistory(sessions);
      })
      .catch(
        (cause) =>
          current &&
          setError(
            describeFailure(
              (cause as { code?: string }).code ?? "internal_error",
            ),
          ),
      )
      .finally(() => {
        if (current) setLoading(false);
      });
    return () => {
      current = false;
    };
  }, [service, attempt]);
  const sessionId = query.get("session");
  useEffect(() => {
    if (!sessionId || sessionId === activeId) return;
    let current = true;
    const revision = sessionRevision.current;
    service.roleplay
      .get(sessionId)
      .then((view) => {
        if (current && revision === sessionRevision.current) {
          activeSession.current = view.status === "active" ? view.id : null;
          setSession(view);
        }
      })
      .catch(() => {
        if (current)
          setError(
            "Không mở lại được buổi luyện này. Bạn có thể thử tải lại hoặc chọn tình huống mới.",
          );
      });
    return () => {
      current = false;
    };
  }, [service, sessionId, attempt, activeId]);

  const reset = () => {
    sessionRevision.current++;
    activeSession.current = null;
    setSession(null);
    setUseCase(false);
    setError("");
    setQuery(linkedCase ? { caseId: linkedCase.id } : {});
  };

  const visible = (scenarios ?? []).filter(
    (s) => !role || !(role in roleNames) || s.role === role,
  );
  const picked = visible.find((s) => s.key === key);
  const start = async () => {
    if (!picked || busy) return;
    setBusy(true);
    setError("");
    try {
      const created = await service.roleplay.create({
        id: globalThis.crypto.randomUUID(),
        role: picked.role,
        scenarioKey: picked.key,
        userGoal: goal.trim(),
        difficulty,
        linkedCaseId: linkedCase && useCase ? linkedCase.id : null,
        useCaseContext: !!linkedCase && useCase,
      });
      activeSession.current = created.id;
      setSession(created);
      setQuery({
        session: created.id,
        ...(linkedCase ? { caseId: linkedCase.id } : {}),
      });
    } catch (cause) {
      // Typed goal and choices stay on screen so nothing has to be re-entered.
      setError(
        describeFailure((cause as { code?: string }).code ?? "internal_error"),
      );
    } finally {
      setBusy(false);
    }
  };
  const refresh = useCallback(() => {
    if (activeSession.current !== activeId) return;
    const revision = sessionRevision.current;
    if (activeId)
      service.roleplay
        .get(activeId)
        .then((view) => {
          if (revision === sessionRevision.current) setSession(view);
        })
        .catch(() => undefined);
  }, [service, activeId]);
  const finish = async () => {
    if (!session) return;
    sessionRevision.current++;
    activeSession.current = null;
    setBusy(true);
    setError("");
    try {
      setSession(await service.roleplay.complete(session.id));
    } catch (cause) {
      activeSession.current = session.id;
      setError(
        describeFailure((cause as { code?: string }).code ?? "internal_error"),
      );
    } finally {
      setBusy(false);
    }
  };
  const leave = async () => {
    if (!session || busy) return;
    sessionRevision.current++;
    activeSession.current = null;
    setBusy(true);
    setError("");
    try {
      setSession(await service.roleplay.abandon(session.id));
    } catch {
      activeSession.current = session.id;
      setError(
        "Chưa kết thúc được buổi luyện. Hãy thử lại; nội dung vẫn được giữ.",
      );
    } finally {
      setBusy(false);
    }
  };

  if (session)
    return (
      <div className="ai-feature stack" data-testid="roleplay-live">
        <PageHeader title={session.scenarioTitle} back="/ai" />
        {(session.linkedCaseId || linkedCase) && (
          <Link
            className="button secondary"
            to={`/cases/${session.linkedCaseId ?? linkedCase?.id}`}
          >
            Trở lại hồ sơ
          </Link>
        )}
        <div className="live-roleplay-banner" role="note">
          Diễn tập — đây không phải người thật. Bạn đang luyện nói với{" "}
          {roleNames[session.role].toLowerCase()} do AI đóng vai. Lượt{" "}
          {session.turnCount}/{session.maxTurns}.
        </div>
        {session.safetyLocked && <UrgentBlock />}
        {session.status === "active" ? (
          <>
            <Thread
              service={service}
              conversationId={session.conversationId}
              heading="Phòng luyện nói"
              withMemory={false}
              onSettled={refresh}
            />
            {error && (
              <div className="live-error" role="alert">
                {error}
              </div>
            )}
            <div className="actions">
              <Button
                disabled={busy || session.turnCount < 1}
                onClick={() => void finish()}
              >
                Kết thúc & nhận phản hồi
              </Button>
              <Button
                disabled={busy}
                variant="ghost"
                onClick={() => void leave()}
              >
                Thoát, không cần phản hồi
              </Button>
            </div>
          </>
        ) : session.status === "completed" ? (
          <>
            <Feedback session={session} />
            <Button variant="secondary" onClick={reset}>
              Luyện một tình huống khác
            </Button>
          </>
        ) : (
          <EmptyState
            title="Buổi luyện đã kết thúc"
            description="Bạn có thể bắt đầu một buổi mới."
            action={<Button onClick={reset}>Luyện một tình huống khác</Button>}
          />
        )}
      </div>
    );

  return (
    <div className="ai-feature stack" data-testid="roleplay-live">
      <PageHeader
        title="Luyện cách nói"
        description="Tập nói với giáo viên, phụ huynh hoặc người lớn bạn tin. AI đóng vai; đây không phải người thật."
        back="/ai"
      />
      {error && (
        <div className="live-error" role="alert">
          {error}
          <Button
            variant="secondary"
            onClick={() => {
              setError("");
              setAttempt((n) => n + 1);
            }}
          >
            Thử lại
          </Button>
        </div>
      )}
      {loading && <p role="status">Đang tải tình huống và các buổi luyện…</p>}
      {history.length > 0 && (
        <section aria-label="Buổi luyện đã lưu">
          <h2>Buổi luyện của bạn</h2>
          <div className="stack">
            {history.slice(0, 10).map((item) => (
              <Button
                key={item.id}
                variant="secondary"
                onClick={() =>
                  setQuery({
                    session: item.id,
                    ...(item.linkedCaseId ? { caseId: item.linkedCaseId } : {}),
                  })
                }
              >
                {item.status === "active" ? "Tiếp tục" : "Xem lại"}:{" "}
                {item.scenarioTitle}
              </Button>
            ))}
          </div>
        </section>
      )}
      <fieldset className="live-pick">
        <legend>Chọn tình huống</legend>
        {visible.map((s) => (
          <label key={s.key}>
            <input
              type="radio"
              name="scenario"
              checked={key === s.key}
              onChange={() => {
                setKey(s.key);
                setGoal(s.defaultGoal);
              }}
            />{" "}
            <strong>{roleNames[s.role]}</strong> · {s.title}
            <small> — {s.context}</small>
          </label>
        ))}
      </fieldset>
      {picked && (
        <>
          <label htmlFor="goal">Mục tiêu của bạn</label>
          <textarea
            id="goal"
            rows={2}
            maxLength={300}
            value={goal}
            onChange={(e) => setGoal(e.target.value)}
          />
          <label htmlFor="difficulty">Độ khó</label>
          <select
            id="difficulty"
            value={difficulty}
            onChange={(e) => setDifficulty(Number(e.target.value))}
          >
            <option value={1}>1 — người lớn hỗ trợ ngay</option>
            <option value={2}>2 — hỏi lại, cần thêm thông tin</option>
            <option value={3}>3 — bận nhưng công bằng</option>
          </select>
          <p>Mặc định AI không đọc hồ sơ của bạn khi diễn tập.</p>
          {linkedCase && (
            <label>
              <input
                type="checkbox"
                checked={useCase}
                onChange={(e) => setUseCase(e.target.checked)}
              />{" "}
              Cho AI dùng tóm tắt hồ sơ “{linkedCase.title}” trong buổi luyện
              này
            </label>
          )}
          <Button disabled={busy} onClick={() => void start()}>
            Bắt đầu diễn tập
          </Button>
        </>
      )}
    </div>
  );
}
