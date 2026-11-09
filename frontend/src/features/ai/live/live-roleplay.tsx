import { useCallback, useEffect, useState } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import { Button, EmptyState, Notice, PageHeader } from "../../../components/ui";
import type {
  LiveCompanion,
  RoleplayRole,
  RoleplayScenario,
  RoleplaySessionView,
} from "../../../services/composition/companion-types";
import { Thread, UrgentBlock } from "./live-chat";
import { describeFailure } from "./use-live-chat";
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

  useEffect(() => {
    service.roleplay
      .scenarios()
      .then(setScenarios)
      .catch((cause) =>
        setError(
          describeFailure(
            (cause as { code?: string }).code ?? "internal_error",
          ),
        ),
      );
  }, [service]);
  const sessionId = query.get("session");
  useEffect(() => {
    if (!sessionId) return;
    service.roleplay
      .get(sessionId)
      .then(setSession)
      .catch(() => setError("Không mở lại được buổi luyện này."));
  }, [service, sessionId]);

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
        useCaseContext: false,
      });
      setSession(created);
      setQuery({ session: created.id });
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
    if (session)
      service.roleplay
        .get(session.id)
        .then(setSession)
        .catch(() => undefined);
  }, [service, session]);
  const finish = async () => {
    if (!session) return;
    setBusy(true);
    setError("");
    try {
      setSession(await service.roleplay.complete(session.id));
    } catch (cause) {
      setError(
        describeFailure((cause as { code?: string }).code ?? "internal_error"),
      );
    } finally {
      setBusy(false);
    }
  };
  const leave = async () => {
    if (!session) return;
    setSession(await service.roleplay.abandon(session.id));
  };

  if (session)
    return (
      <div className="ai-feature stack" data-testid="roleplay-live">
        <PageHeader title={session.scenarioTitle} back="/ai/roleplay" />
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
              <Button variant="ghost" onClick={() => void leave()}>
                Thoát, không cần phản hồi
              </Button>
            </div>
          </>
        ) : session.status === "completed" ? (
          <>
            <Feedback session={session} />
            <Button
              variant="secondary"
              onClick={() => {
                setSession(null);
                setQuery({});
              }}
            >
              Luyện một tình huống khác
            </Button>
          </>
        ) : (
          <EmptyState
            title="Buổi luyện đã kết thúc"
            description="Bạn có thể bắt đầu một buổi mới."
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
        </div>
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
          <Button disabled={busy} onClick={() => void start()}>
            Bắt đầu diễn tập
          </Button>
        </>
      )}
    </div>
  );
}
