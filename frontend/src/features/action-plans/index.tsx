import { useEffect, useState } from "react";
import { Link, NavLink, useParams } from "react-router-dom";
import {
  ArrowDown,
  ArrowRight,
  ArrowUp,
  Check,
  CheckCircle2,
  Flag,
  Pause,
  Pencil,
  Play,
  Plus,
  Save,
  Trash2,
} from "lucide-react";
import { uid, useWorkspaceStore } from "../../app/store";
import {
  Badge,
  Button,
  EmptyState,
  Field,
  LinkButton,
  Modal,
  Notice,
  PageHeader,
  Progress,
  Skeleton,
} from "../../components/ui";
import { getServices } from "../../services/composition";
import { ApiError } from "../../services/http/client";
import type { ActionPlan, Incident, PlanItem } from "../../types";
import { mergePlanDraft, movePlanItem, validatePlan } from "./model";
import "./plans.css";

interface PlanOption {
  id: string;
  title: string;
  reason: string;
  conditions: string;
  considerations: string;
  labels: string[];
}
interface PlanRecovery {
  plan: ActionPlan | null;
  base: ActionPlan | null;
  recovered: boolean;
}
function readPlanRecovery(key: string, stored?: ActionPlan): PlanRecovery {
  try {
    const raw = sessionStorage.getItem(key);
    if (raw) {
      const parsed = JSON.parse(raw) as ActionPlan & {
        version?: number;
        plan?: ActionPlan;
        base?: ActionPlan | null;
      };
      const draft = parsed.plan ?? parsed;
      if (
        typeof draft.caseId === "string" &&
        key.endsWith(`:${draft.caseId}`) &&
        Array.isArray(draft.items)
      ) {
        const base =
          parsed.version === 2
            ? (parsed.base ?? null)
            : draft.lastUpdated === stored?.lastUpdated
              ? (stored ?? null)
              : null;
        return { plan: draft, base, recovered: true };
      }
    }
  } catch {
    /* Explicit save remains available if recovery storage cannot be read. */
  }
  return { plan: stored ?? null, base: stored ?? null, recovered: false };
}
const planStatusLabels: Record<ActionPlan["status"], string> = {
  draft: "Bản nháp",
  active: "Đang thực hiện",
  paused: "Đã tạm dừng",
  completed: "Bạn đã hoàn tất các bước",
};
const itemStatusLabels: Record<PlanItem["status"], string> = {
  not_started: "Chưa bắt đầu",
  doing: "Đang làm",
  done: "Đã làm",
};
function optionsFor(item: Incident): PlanOption[] {
  const online =
    /chat|trực tuyến|online/i.test(
      `${item.title} ${item.categoryTags.join(" ")}`,
    ) ||
    ["TPL-THREAT", "TPL-IMAGE", "TPL-IMPERSONATION"].includes(item.template);
  return [
    {
      id: "trusted-adult",
      title:
        item.perspective === "witness"
          ? "Nhờ người lớn hỗ trợ bạn ấy"
          : "Chuẩn bị nói với người mình tin",
      reason: item.trustedPerson
        ? `Bạn đã nhắc đến ${item.trustedPerson}. Chuẩn bị trước có thể giúp buổi nói chuyện dễ bắt đầu hơn.`
        : "Một người lớn đáng tin có thể cùng bạn suy nghĩ cách hỗ trợ.",
      conditions:
        "Chọn người khiến bạn thấy được lắng nghe, vào lúc bạn có thể nói chuyện riêng.",
      considerations:
        "Bạn không phải kể mọi chi tiết ngay. Nếu người đầu tiên chưa hiểu, có thể tìm người khác.",
      labels: [
        "Chọn một người lớn mình tin tưởng",
        "Viết ba điều mình muốn người đó hiểu",
        "Luyện một câu mở đầu và lời đề nghị hỗ trợ",
      ],
    },
    {
      id: "document",
      title: "Làm rõ điều mình còn nhớ",
      reason: !item.occurredAt
        ? "Bạn chưa nhớ rõ thời gian. Ghi riêng phần chắc và chưa chắc sẽ giúp giữ đúng câu chuyện."
        : "Các mốc có ngữ cảnh giúp bạn nhìn lại điều mình đã trải qua.",
      conditions:
        "Chỉ ghi lại điều bạn nhớ hoặc có sẵn. Không cần đi thu thập thêm nếu điều đó khiến bạn bất an.",
      considerations:
        "Không đoán danh tính hay ý định; không tự đối đầu để tìm bằng chứng.",
      labels: [
        "Ghi lại một điều mình nhớ rõ",
        "Đánh dấu phần chưa chắc và nguồn đang có",
        "Xem lại bản tóm tắt cùng người mình tin",
      ],
    },
    {
      id: online ? "platform" : "safe-support",
      title: online
        ? "Chuẩn bị dùng công cụ của nền tảng"
        : "Sắp xếp một điểm tựa an toàn",
      reason: online
        ? "Với tình huống trực tuyến, bạn có thể tìm hiểu công cụ chặn hoặc báo nội dung."
        : "Một người hoặc nơi có thể tìm đến sẽ giúp bạn bớt phải xử lý một mình.",
      conditions: online
        ? "Kiểm tra đúng nền tảng và cân nhắc cùng người lớn bạn tin. Giữ nội dung có sẵn trước nếu phù hợp."
        : "Chọn người hoặc địa điểm bạn tiếp cận được trong sinh hoạt hằng ngày.",
      considerations: online
        ? "Đây là bước chuẩn bị. MoodPrint không tự chặn, báo cáo hoặc gửi nội dung; không bảo đảm nền tảng sẽ xử lý."
        : "Không hẹn gặp hay đối đầu người đang khiến bạn lo sợ. Nếu nguy hiểm trước mắt, tìm hỗ trợ trực tiếp.",
      labels: online
        ? [
            "Chọn người lớn có thể cùng xem nội dung",
            "Tìm hướng dẫn chặn hoặc báo nội dung của nền tảng",
            "Tự cân nhắc bước phù hợp và ghi lại kết quả",
          ]
        : [
            "Chọn người hoặc nơi có thể tìm đến",
            "Chuẩn bị một câu nhờ giúp ngắn gọn",
            "Ghi lại cách tìm hỗ trợ nếu tình hình thay đổi",
          ],
    },
  ];
}
function makePlan(item: Incident, option?: PlanOption): ActionPlan {
  const demo = useWorkspaceStore.getState().workspace.kind === "demo";
  return {
    id: demo ? uid("PLAN") : crypto.randomUUID(),
    caseId: item.id,
    goal: option?.title ?? "Chuẩn bị một bước nhỏ phù hợp với mình",
    chosenOptionId: option?.id ?? "manual",
    status: "draft",
    nextReviewDate: "",
    lastUpdated: new Date().toISOString(),
    demo,
    items: (
      option?.labels ?? [
        "Ghi lại điều mình muốn thay đổi",
        "Chọn người có thể hỗ trợ",
        "Chuẩn bị bước nhỏ tiếp theo",
      ]
    ).map((label, index) => ({
      id: demo ? uid("STEP") : crypto.randomUUID(),
      label,
      status: "not_started",
      notes: "",
      priority: index === 0 ? "high" : "normal",
      reason:
        index === 0
          ? "Bắt đầu bằng một việc mình có thể lựa chọn."
          : "Có thể điều chỉnh theo mức sẵn sàng của bạn.",
    })),
  };
}
export function PlanPage() {
  const { caseId } = useParams();
  const workspace = useWorkspaceStore((s) => s.workspace);
  return (
    <PlanWorkspace
      key={`${workspace.kind}:${workspace.userId}:${caseId}`}
      caseId={caseId}
    />
  );
}
function PlanWorkspace({ caseId }: { caseId?: string }) {
  const kind = useWorkspaceStore((s) => s.workspace.kind);
  const [loading, setLoading] = useState(kind === "real");
  const [loadError, setLoadError] = useState("");
  const [attempt, setAttempt] = useState(0);
  const item = useWorkspaceStore((s) =>
    s.cases.find((c) => c.id === caseId && c.ownerId === s.user?.id),
  );
  const stored = useWorkspaceStore((s) =>
    s.plans.find((p) => p.caseId === caseId),
  );
  useEffect(() => {
    if (kind !== "real" || !caseId) return;
    let active = true;
    void getServices()
      .plans.getForCase(caseId)
      .then(() => {
        if (active) {
          setLoading(false);
          setLoadError("");
        }
      })
      .catch((cause: unknown) => {
        if (active) {
          setLoading(false);
          setLoadError(
            cause instanceof Error ? cause.message : "Chưa tải được kế hoạch.",
          );
        }
      });
    return () => {
      active = false;
    };
  }, [caseId, kind, attempt]);
  if (loading) return <Skeleton />;
  if (loadError)
    return (
      <Notice tone="error">
        {loadError}
        <Button
          onClick={() => {
            setLoading(true);
            setAttempt((value) => value + 1);
          }}
        >
          Thử tải lại
        </Button>
      </Notice>
    );
  if (!item)
    return (
      <>
        <PageHeader title="Chưa tìm thấy hồ sơ" back="/cases" />
        <EmptyState
          title="Kế hoạch cần gắn với một hồ sơ của bạn"
          description="Mở hồ sơ trong tài khoản của bạn để tiếp tục."
          action={<LinkButton to="/cases">Về danh sách hồ sơ</LinkButton>}
        />
      </>
    );
  return <PlanEditor key={item.id} item={item} stored={stored} />;
}
function PlanEditor({ item, stored }: { item: Incident; stored?: ActionPlan }) {
  const demo = useWorkspaceStore((s) => s.workspace.kind === "demo");
  const key = `moodprint-plan-draft-v1:${item.ownerId}:${item.id}`;
  const [initial] = useState(() => readPlanRecovery(key, stored));
  const [plan, setPlan] = useState<ActionPlan | null>(initial.plan);
  const [baseRevision, setBaseRevision] = useState<ActionPlan | null>(
    initial.base,
  );
  const [notReady, setNotReady] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [conflictRevision, setConflictRevision] = useState<ActionPlan | null>(
    null,
  );
  const [savedLabel, setSavedLabel] = useState("");
  const [editing, setEditing] = useState<PlanItem | null>(null);
  const [deleteStep, setDeleteStep] = useState<PlanItem | null>(null);
  const [completion, setCompletion] = useState<PlanItem | null>(null);
  const [completionNotes, setCompletionNotes] = useState("");
  const [editError, setEditError] = useState("");
  const [changeOptions, setChangeOptions] = useState(false);
  const [replaceOption, setReplaceOption] = useState<PlanOption | null>(null);
  const base = `/cases/${item.id}`;
  const options = optionsFor(item);
  const dirty = !!plan && JSON.stringify(plan) !== JSON.stringify(stored);
  const latest = conflictRevision ?? stored ?? null;
  const sameRevision = (left: ActionPlan | null, right: ActionPlan | null) =>
    left?.version !== undefined || right?.version !== undefined
      ? left?.id === right?.id && left?.version === right?.version
      : JSON.stringify(left) === JSON.stringify(right);
  const conflict = !!plan && !sameRevision(baseRevision, latest);
  useEffect(() => {
    if (!plan || !dirty) return;
    try {
      sessionStorage.setItem(
        key,
        JSON.stringify({
          version: 2,
          plan,
          base: baseRevision,
          baseRevision: baseRevision?.lastUpdated ?? null,
        }),
      );
    } catch {
      /* Explicit save remains available. */
    }
  }, [plan, baseRevision, dirty, key]);
  const updatePlan = (patch: Partial<ActionPlan>) => {
    setPlan((p) => (p ? { ...p, ...patch } : p));
    setSavedLabel("");
    setError("");
  };
  const choose = (option?: PlanOption) => {
    const next = makePlan(item, option);
    setPlan({
      ...next,
      id: plan?.id ?? stored?.id ?? next.id,
      version: plan?.version ?? stored?.version,
    });
    setNotReady(false);
    setChangeOptions(false);
    setError("");
    setSavedLabel("");
  };
  const save = async (target?: ActionPlan) => {
    const next = target ?? plan;
    if (!next) return;
    const current =
      conflictRevision ??
      useWorkspaceStore.getState().plans.find((p) => p.caseId === item.id) ??
      null;
    if (!sameRevision(baseRevision, current)) {
      setError(
        "Kế hoạch đã có cập nhật mới. Hãy đối chiếu tiến độ trước khi lưu; phần đang viết vẫn được giữ.",
      );
      return;
    }
    const issue = validatePlan(next);
    if (issue) {
      setError(issue);
      return;
    }
    setSaving(true);
    setError("");
    const record = { ...next, lastUpdated: new Date().toISOString() };
    try {
      const saved = await getServices().plans.save(record);
      setPlan((current) =>
        current && JSON.stringify(current) !== JSON.stringify(next)
          ? {
              ...current,
              version: saved.version,
              lastUpdated: saved.lastUpdated,
            }
          : saved,
      );
      setBaseRevision(saved);
      setConflictRevision(null);
      try {
        sessionStorage.removeItem(key);
      } catch {
        /* State is saved. */
      }
      setSavedLabel(
        demo
          ? "Đã lưu trong demo. Home đã được cập nhật."
          : "Đã lưu kế hoạch. Home đã được cập nhật.",
      );
      useWorkspaceStore
        .getState()
        .notify(
          demo ? "Đã lưu kế hoạch ứng phó demo." : "Đã lưu kế hoạch ứng phó.",
        );
    } catch (cause) {
      if (
        cause instanceof ApiError &&
        cause.code === "version_conflict" &&
        cause.details.latest
      )
        setConflictRevision(cause.details.latest as ActionPlan);
      setError(
        cause instanceof Error
          ? cause.message
          : "Chưa lưu được. Nội dung vẫn ở đây; bạn hãy thử lại.",
      );
    } finally {
      setSaving(false);
    }
  };
  const updateItem = (next: PlanItem) => {
    if (!plan) return;
    updatePlan({
      items: plan.items.some((i) => i.id === next.id)
        ? plan.items.map((i) => (i.id === next.id ? next : i))
        : [...plan.items, next],
      status:
        plan.status === "completed" && next.status !== "done"
          ? "active"
          : plan.status,
    });
  };
  const done = plan?.items.filter((i) => i.status === "done").length ?? 0;
  return (
    <div className="plan-page">
      <PageHeader
        title="Kế hoạch ứng phó"
        description={`Một bước nhỏ cho “${item.title}”. Bạn quyết định nhịp độ của mình.`}
        back={base}
      />
      <nav className="case-tabs" aria-label="Các phần trong hồ sơ">
        {[
          ["", "Tổng quan"],
          ["/timeline", "Dòng thời gian"],
          ["/evidence", "Nguồn đính kèm"],
          ["/plan", "Kế hoạch ứng phó"],
          ["/summary", "Bản tóm tắt"],
        ].map(([suffix, label]) => (
          <NavLink key={suffix} to={`${base}${suffix}`} end={suffix === ""}>
            {label}
          </NavLink>
        ))}
      </nav>
      {initial.recovered && (
        <Notice>
          Đã khôi phục phần kế hoạch đang chỉnh sửa trong phiên này.
        </Notice>
      )}
      {conflict && (
        <Notice tone="warning">
          <strong>Kế hoạch đã có tiến độ mới được lưu.</strong>
          <p>
            Phần mục tiêu, ghi chú và thứ tự đang chỉnh của bạn vẫn được giữ. Để
            tránh ghi đè cập nhật từ Home, hãy lấy trạng thái mới nhất cho những
            bước trùng nhau trước khi lưu.
          </p>
          <Button
            variant="secondary"
            onClick={() => {
              if (plan)
                setPlan(
                  latest ? mergePlanDraft(baseRevision, plan, latest) : plan,
                );
              setBaseRevision(latest);
              setError("");
            }}
          >
            Giữ chỉnh sửa và cập nhật tiến độ mới
          </Button>
        </Notice>
      )}
      {(!plan || changeOptions) && (
        <section className="plan-start">
          <div className="section-heading">
            <div>
              <h2>Bạn muốn bắt đầu theo cách nào?</h2>
              <p className="muted">
                Ba phương án gợi ý để bạn cân nhắc. Không có lựa chọn nào bắt
                buộc.
              </p>
            </div>
            {changeOptions && (
              <Button variant="ghost" onClick={() => setChangeOptions(false)}>
                Giữ kế hoạch hiện tại
              </Button>
            )}
          </div>
          <div className="plan-options">
            {options.map((option) => (
              <article key={option.id} className="plan-option">
                <h3>{option.title}</h3>
                <dl>
                  <div>
                    <dt>Vì sao gợi ý?</dt>
                    <dd>{option.reason}</dd>
                  </div>
                  <div>
                    <dt>Khi nào phù hợp?</dt>
                    <dd>{option.conditions}</dd>
                  </div>
                  <div>
                    <dt>Điều cần cân nhắc</dt>
                    <dd>{option.considerations}</dd>
                  </div>
                </dl>
                <Button
                  variant="secondary"
                  onClick={() =>
                    plan ? setReplaceOption(option) : choose(option)
                  }
                >
                  Chọn phương án này
                  <ArrowRight size={17} />
                </Button>
              </article>
            ))}
          </div>
          <div className="plan-start-actions">
            <Button
              variant="secondary"
              onClick={() =>
                plan
                  ? setReplaceOption({
                      id: "manual",
                      title: "Kế hoạch của mình",
                      reason: "",
                      conditions: "",
                      considerations: "",
                      labels: [
                        "Ghi lại điều mình muốn thay đổi",
                        "Chọn người có thể hỗ trợ",
                        "Chuẩn bị bước nhỏ tiếp theo",
                      ],
                    })
                  : choose()
              }
            >
              <Pencil size={17} />
              Tự tạo kế hoạch
            </Button>
            <Button variant="ghost" onClick={() => setNotReady(true)}>
              Mình chưa sẵn sàng
            </Button>
          </div>
          {notReady && (
            <Notice>
              Bạn có thể dừng ở đây. Hồ sơ vẫn được giữ, và bạn có thể quay lại
              khi sẵn sàng. <Link to={base}>Quay về hồ sơ</Link> hoặc{" "}
              <Link to="/support">xem nguồn hỗ trợ</Link>.
            </Notice>
          )}
        </section>
      )}
      {plan && !changeOptions && (
        <div className="plan-layout">
          <div className="stack">
            <section className="panel plan-goal">
              <div className="heading-row">
                <Badge
                  tone={
                    plan.status === "paused" || plan.status === "draft"
                      ? "gray"
                      : "green"
                  }
                >
                  {planStatusLabels[plan.status]}
                </Badge>
                <Button
                  variant="ghost"
                  disabled={saving}
                  onClick={() => setChangeOptions(true)}
                >
                  Xem phương án khác
                </Button>
              </div>
              <Field
                label="Mục tiêu của bạn"
                value={plan.goal}
                onChange={(e) => updatePlan({ goal: e.target.value })}
                placeholder="Một điều nhỏ bạn muốn chuẩn bị…"
              />
              <div className="plan-progress-label">
                <strong>
                  {done}/{plan.items.length} bước bạn đã làm
                </strong>
                <span>
                  {plan.items.length
                    ? Math.round((done / plan.items.length) * 100)
                    : 0}
                  %
                </span>
              </div>
              <Progress value={done} max={plan.items.length} />
              <p className="muted">
                Đánh dấu hoàn tất là ghi nhận của bạn. Không có tin nhắn hay báo
                cáo nào được tự gửi.
              </p>
              {plan.status === "paused" && (
                <Notice>
                  Kế hoạch đang tạm dừng. Bạn vẫn có thể sửa và trở lại lúc thấy
                  phù hợp.
                </Notice>
              )}
              {plan.status === "completed" && (
                <Notice>
                  Chúc bạn giữ được nhịp độ phù hợp với mình. Hoàn tất checklist
                  không có nghĩa tình huống đã được giải quyết hoặc an toàn.
                </Notice>
              )}
            </section>
            <section className="panel plan-checklist">
              <div className="section-heading">
                <h2>Những bước nhỏ</h2>
                <Button
                  variant="secondary"
                  disabled={saving}
                  onClick={() => {
                    setEditError("");
                    setEditing({
                      id: demo ? uid("STEP") : crypto.randomUUID(),
                      label: "",
                      status: "not_started",
                      notes: "",
                      priority: "normal",
                      reason: "",
                    });
                  }}
                >
                  <Plus size={17} />
                  Thêm bước
                </Button>
              </div>
              {!plan.items.length && (
                <EmptyState
                  title="Bạn có thể thêm bước đầu tiên"
                  description="Một câu ngắn mô tả việc bạn muốn chuẩn bị là đủ."
                />
              )}
              <ol className="plan-items">
                {plan.items.map((step, index) => (
                  <li
                    key={step.id}
                    className={`plan-item ${step.status === "done" ? "done" : ""}`}
                  >
                    <div className="plan-step-main">
                      <button
                        className="plan-check"
                        aria-label={
                          step.status === "done"
                            ? `Bỏ hoàn tất: ${step.label}`
                            : `Hoàn tất: ${step.label}`
                        }
                        aria-pressed={step.status === "done"}
                        disabled={saving}
                        onClick={() => {
                          if (step.status === "done")
                            updateItem({ ...step, status: "not_started" });
                          else {
                            setCompletion(step);
                            setCompletionNotes(step.notes);
                          }
                        }}
                      >
                        {step.status === "done" ? (
                          <Check size={20} />
                        ) : (
                          <span />
                        )}
                      </button>
                      <div className="plan-step-content">
                        <div className="chips">
                          {step.priority === "high" && (
                            <Badge tone="amber">
                              <Flag size={13} />
                              Ưu tiên trước
                            </Badge>
                          )}
                          <span className="plan-step-status">
                            {itemStatusLabels[step.status]}
                          </span>
                        </div>
                        <h3>{step.label}</h3>
                        {step.reason && (
                          <p className="plan-step-reason">{step.reason}</p>
                        )}
                        {step.notes && (
                          <p className="plan-step-note">
                            <strong>Ghi chú của bạn:</strong> {step.notes}
                          </p>
                        )}
                        <div className="plan-step-controls">
                          <select
                            aria-label={`Trạng thái bước ${index + 1}`}
                            value={step.status}
                            disabled={saving}
                            onChange={(e) => {
                              if (
                                e.target.value === "done" &&
                                step.status !== "done"
                              ) {
                                setCompletion(step);
                                setCompletionNotes(step.notes);
                              } else
                                updateItem({
                                  ...step,
                                  status: e.target.value as PlanItem["status"],
                                });
                            }}
                          >
                            {Object.entries(itemStatusLabels).map(
                              ([value, label]) => (
                                <option key={value} value={value}>
                                  {label}
                                </option>
                              ),
                            )}
                          </select>
                          <Button
                            variant="ghost"
                            disabled={saving}
                            onClick={() => {
                              setEditError("");
                              setEditing({ ...step });
                            }}
                            aria-label={`Sửa bước ${index + 1}`}
                          >
                            <Pencil size={16} />
                            Sửa
                          </Button>
                          <Button
                            variant="ghost"
                            disabled={saving}
                            onClick={() => setDeleteStep(step)}
                            aria-label={`Xóa bước ${index + 1}`}
                          >
                            <Trash2 size={16} />
                          </Button>
                        </div>
                      </div>
                    </div>
                    <div className="plan-reorder">
                      <Button
                        variant="ghost"
                        disabled={saving || index === 0}
                        aria-label={`Đưa bước ${index + 1} lên`}
                        onClick={() =>
                          updatePlan({
                            items: movePlanItem(plan.items, step.id, -1),
                          })
                        }
                      >
                        <ArrowUp size={17} />
                      </Button>
                      <span aria-hidden="true">{index + 1}</span>
                      <Button
                        variant="ghost"
                        disabled={saving || index === plan.items.length - 1}
                        aria-label={`Đưa bước ${index + 1} xuống`}
                        onClick={() =>
                          updatePlan({
                            items: movePlanItem(plan.items, step.id, 1),
                          })
                        }
                      >
                        <ArrowDown size={17} />
                      </Button>
                    </div>
                  </li>
                ))}
              </ol>
            </section>
            <section className="panel">
              <h2>Xem lại khi bạn thấy phù hợp</h2>
              <Field
                label="Ngày muốn xem lại (không phải lời nhắc tự động)"
                type="date"
                value={plan.nextReviewDate}
                onChange={(e) => updatePlan({ nextReviewDate: e.target.value })}
              />
              <Field
                label="Ghi chú kết quả / điều muốn điều chỉnh"
                id="plan-outcome"
              >
                <textarea
                  id="plan-outcome"
                  rows={4}
                  value={plan.outcomeNotes ?? ""}
                  onChange={(e) => updatePlan({ outcomeNotes: e.target.value })}
                  placeholder="Điều gì đã diễn ra? Bạn có muốn đổi cách tiếp cận không?"
                />
              </Field>
            </section>
          </div>
          <aside className="stack plan-sidebar">
            <section className="panel">
              <h2>Nhịp độ của bạn</h2>
              <Field label="Trạng thái kế hoạch" id="plan-status">
                <select
                  id="plan-status"
                  value={plan.status}
                  onChange={(e) =>
                    updatePlan({
                      status: e.target.value as ActionPlan["status"],
                    })
                  }
                >
                  {Object.entries(planStatusLabels).map(([value, label]) => (
                    <option key={value} value={value}>
                      {label}
                    </option>
                  ))}
                </select>
              </Field>
              <div className="plan-state-actions">
                {plan.status === "paused" ? (
                  <Button
                    variant="secondary"
                    onClick={() => updatePlan({ status: "active" })}
                  >
                    <Play size={16} />
                    Tiếp tục
                  </Button>
                ) : plan.status !== "completed" ? (
                  <Button
                    variant="secondary"
                    onClick={() => updatePlan({ status: "paused" })}
                  >
                    <Pause size={16} />
                    Tạm dừng
                  </Button>
                ) : (
                  <Button
                    variant="secondary"
                    onClick={() => updatePlan({ status: "active" })}
                  >
                    Mở lại kế hoạch
                  </Button>
                )}
                {plan.status !== "completed" && (
                  <Button
                    variant="ghost"
                    onClick={() => {
                      if (
                        plan.items.length &&
                        plan.items.every((i) => i.status === "done")
                      )
                        updatePlan({ status: "completed" });
                      else
                        setError(
                          "Vẫn còn bước chưa hoàn tất. Bạn có thể sửa, xóa bước không phù hợp hoặc tạm dừng.",
                        );
                    }}
                  >
                    <CheckCircle2 size={16} />
                    Đánh dấu hoàn tất
                  </Button>
                )}
              </div>
              <div className="plan-save">
                <Button
                  disabled={saving || !dirty || conflict}
                  onClick={() => void save()}
                >
                  <Save size={17} />
                  {saving
                    ? "Đang lưu…"
                    : stored
                      ? "Lưu thay đổi"
                      : "Lưu kế hoạch"}
                </Button>
                <small role="status">
                  {dirty
                    ? "Có thay đổi chưa lưu vào hồ sơ."
                    : savedLabel || "Các thay đổi đã được lưu."}
                </small>
              </div>
            </section>
            <Notice>
              Đây là gợi ý để bạn cân nhắc. Không cần tự đối đầu hay thu thập
              thêm thông tin nếu bạn thấy không an toàn.
            </Notice>
            <div className="plan-related-links">
              <Link to={`/support/prepare?caseId=${item.id}`}>
                Chuẩn bị lời nhắn nhờ giúp
                <ArrowRight size={16} />
              </Link>
              <Link to={`/ai/roleplay?caseId=${item.id}`}>
                Luyện nói trước
                <ArrowRight size={16} />
              </Link>
              <Link to={`${base}/timeline`}>
                Bổ sung diễn biến
                <ArrowRight size={16} />
              </Link>
              <Link to="/support/urgent">
                Tìm hỗ trợ ngay
                <ArrowRight size={16} />
              </Link>
            </div>
          </aside>
        </div>
      )}
      {error && (
        <Notice tone="error">
          {error}
          <div className="actions">
            <Button
              variant="secondary"
              disabled={saving || !plan || conflict}
              onClick={() => void save()}
            >
              Thử lưu lại
            </Button>
            <span>Nội dung chỉnh sửa vẫn được giữ.</span>
          </div>
        </Notice>
      )}
      {savedLabel && (
        <p className="plan-save-success" role="status">
          <CheckCircle2 size={18} />
          {savedLabel}
        </p>
      )}
      {plan && !changeOptions && (
        <div className="plan-mobile-save">
          <span>
            {dirty
              ? "Thay đổi chưa lưu"
              : demo
                ? "Đã lưu trong demo"
                : "Đã lưu kế hoạch"}
          </span>
          <Button
            disabled={saving || !dirty || conflict}
            onClick={() => void save()}
          >
            <Save size={17} />
            {saving ? "Đang lưu…" : "Lưu kế hoạch"}
          </Button>
        </div>
      )}
      <Modal
        open={!!editing}
        onClose={() => setEditing(null)}
        title={
          editing && plan?.items.some((i) => i.id === editing.id)
            ? "Sửa bước nhỏ"
            : "Thêm bước nhỏ"
        }
      >
        {editing && (
          <form
            className="stack"
            onSubmit={(e) => {
              e.preventDefault();
              if (!editing.label.trim()) {
                setEditError("Hãy viết một việc nhỏ bạn muốn làm.");
                return;
              }
              updateItem({ ...editing, label: editing.label.trim() });
              setEditing(null);
            }}
          >
            <Field
              label="Bạn muốn làm gì?"
              value={editing.label}
              onChange={(e) =>
                setEditing({ ...editing, label: e.target.value })
              }
              error={editError}
            />
            <Field label="Độ ưu tiên" id="step-priority">
              <select
                id="step-priority"
                value={editing.priority}
                onChange={(e) =>
                  setEditing({
                    ...editing,
                    priority: e.target.value as PlanItem["priority"],
                  })
                }
              >
                <option value="normal">Theo nhịp của bạn</option>
                <option value="high">Ưu tiên trước</option>
              </select>
            </Field>
            <Field label="Lý do của bước này" id="step-reason">
              <textarea
                id="step-reason"
                rows={2}
                value={editing.reason}
                onChange={(e) =>
                  setEditing({ ...editing, reason: e.target.value })
                }
              />
            </Field>
            <Field label="Ghi chú (không bắt buộc)" id="step-notes">
              <textarea
                id="step-notes"
                rows={3}
                value={editing.notes}
                onChange={(e) =>
                  setEditing({ ...editing, notes: e.target.value })
                }
              />
            </Field>
            <Button type="submit">Giữ thay đổi bước</Button>
            <small className="muted">
              Sau đó chọn “Lưu kế hoạch” để cập nhật hồ sơ và Home.
            </small>
          </form>
        )}
      </Modal>
      <Modal
        open={!!completion}
        onClose={() => setCompletion(null)}
        title="Bạn vừa làm một bước nhỏ"
      >
        <p>{completion?.label}</p>
        <Field
          label="Điều gì đã diễn ra? (không bắt buộc)"
          id="completion-notes"
        >
          <textarea
            id="completion-notes"
            rows={4}
            value={completionNotes}
            onChange={(e) => setCompletionNotes(e.target.value)}
            placeholder="Bạn có thể ghi vài dòng hoặc bỏ qua."
          />
        </Field>
        <div className="actions">
          <Button
            onClick={() => {
              if (completion)
                updateItem({
                  ...completion,
                  status: "done",
                  notes: completionNotes,
                });
              setCompletion(null);
            }}
          >
            Ghi nhận và giữ ghi chú
          </Button>
          <Button
            variant="ghost"
            onClick={() => {
              if (completion) updateItem({ ...completion, status: "done" });
              setCompletion(null);
            }}
          >
            Bỏ qua ghi chú
          </Button>
        </div>
        <p className="muted">
          Chọn “Lưu kế hoạch” để cập nhật tiến độ ở Home. Không có hành động
          liên hệ nào được thực hiện.
        </p>
      </Modal>
      <Modal
        open={!!deleteStep}
        onClose={() => setDeleteStep(null)}
        title="Bỏ bước này khỏi kế hoạch?"
      >
        <p>{deleteStep?.label}</p>
        <p>Bạn có thể thêm lại một bước khác sau.</p>
        <div className="actions">
          <Button variant="secondary" onClick={() => setDeleteStep(null)}>
            Giữ bước
          </Button>
          <Button
            variant="danger"
            onClick={() => {
              if (plan && deleteStep)
                updatePlan({
                  items: plan.items.filter((i) => i.id !== deleteStep.id),
                  status: plan.status === "completed" ? "active" : plan.status,
                });
              setDeleteStep(null);
            }}
          >
            Bỏ bước
          </Button>
        </div>
      </Modal>
      <Modal
        open={!!replaceOption}
        onClose={() => setReplaceOption(null)}
        title="Bắt đầu với phương án khác?"
      >
        <p>
          Checklist hiện tại sẽ được thay bằng ba bước gợi ý. Hồ sơ sự việc và
          dòng thời gian vẫn được giữ.
        </p>
        <div className="actions">
          <Button variant="secondary" onClick={() => setReplaceOption(null)}>
            Giữ kế hoạch hiện tại
          </Button>
          <Button
            onClick={() => {
              if (replaceOption)
                choose(
                  replaceOption.id === "manual" ? undefined : replaceOption,
                );
              setReplaceOption(null);
            }}
          >
            Dùng phương án mới
          </Button>
        </div>
      </Modal>
    </div>
  );
}
