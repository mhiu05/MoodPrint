import { useEffect, useRef, useState } from "react";
import {
  Link,
  useBlocker,
  useLocation,
  useNavigate,
  useParams,
} from "react-router-dom";
import { ArrowLeft, ArrowRight, Check, Save, Sparkles } from "lucide-react";
import { uid, useDemoStore } from "../../app/store";
import {
  Badge,
  Button,
  Field,
  Modal,
  Notice,
  PageHeader,
  Progress,
} from "../../components/ui";
import { demoService } from "../../mocks/services/demo";
import type { Incident } from "../../types";
import {
  caseDraftIdentity,
  createCaseDraft,
  incidentFromDraft,
  templates,
  validateCaseDraft,
} from "./model";
import type { CaseDraft } from "./model";
import { EvidencePicker } from "./evidence";

const steps = [
  "Tên và mục đích",
  "Chuyện xảy ra",
  "Người liên quan",
  "Ảnh hưởng",
  "Nguồn đính kèm",
  "Xem lại và lưu",
];
const impacts = [
  "Cảm thấy không an toàn",
  "Khó tập trung",
  "Khó ngủ",
  "Ngại đến lớp",
  "Ảnh hưởng tình bạn",
  "Chưa muốn chia sẻ",
];
function readDraft(
  key: string,
  initial: CaseDraft,
): { draft: CaseDraft; recovered: boolean } {
  try {
    const raw = sessionStorage.getItem(key);
    if (!raw) return { draft: initial, recovered: false };
    const draft = JSON.parse(raw) as CaseDraft;
    if (
      typeof draft.summary === "string" &&
      typeof draft.title === "string" &&
      Array.isArray(draft.attachments)
    )
      return {
        draft: {
          ...initial,
          ...draft,
          step: Math.max(0, Math.min(5, draft.step || 0)),
        },
        recovered: true,
      };
  } catch {
    /* Keep the empty form available if browser storage is blocked. */
  }
  return { draft: initial, recovered: false };
}
export function CaseWizard() {
  const { caseId } = useParams();
  const user = useDemoStore((s) => s.user);
  const location = useLocation();
  const navigate = useNavigate();
  const prefill = (location.state as { prefill?: Partial<Incident> } | null)
    ?.prefill;
  const queryIdentity = new URLSearchParams(location.search).get("draft");
  const draftIdentity =
    caseId ??
    (prefill
      ? caseDraftIdentity(prefill)
      : queryIdentity?.startsWith("new:import:")
        ? queryIdentity
        : "new");
  useEffect(() => {
    if (caseId || !prefill || queryIdentity === draftIdentity) return;
    const query = new URLSearchParams(location.search);
    query.set("draft", draftIdentity);
    void navigate(
      { pathname: location.pathname, search: query.toString() },
      { replace: true, state: location.state },
    );
  }, [
    caseId,
    prefill,
    queryIdentity,
    draftIdentity,
    location.pathname,
    location.search,
    location.state,
    navigate,
  ]);
  return (
    <CaseWizardForm
      key={`${user?.id}:${draftIdentity}`}
      draftIdentity={draftIdentity}
    />
  );
}
function CaseWizardForm({ draftIdentity }: { draftIdentity: string }) {
  const { caseId } = useParams();
  const user = useDemoStore((s) => s.user);
  const existing = useDemoStore((s) =>
    s.cases.find((c) => c.id === caseId && c.ownerId === s.user?.id),
  );
  const evidence = useDemoStore((s) => s.evidence);
  const location = useLocation();
  const navigate = useNavigate();
  const key = `moodprint-case-draft-v1:${user?.id ?? "signed-out"}:${draftIdentity}`;
  const prefill = (location.state as { prefill?: Partial<Incident> } | null)
    ?.prefill;
  const [initial] = useState(() => {
    const draft = createCaseDraft(existing ?? prefill);
    return readDraft(key, draft);
  });
  const [draft, setDraft] = useState(initial.draft);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState("");
  const [leave, setLeave] = useState(false);
  const [storageBlocked, setStorageBlocked] = useState(false);
  const saved = useRef(false);
  const dirty = !!(
    draft.title ||
    draft.summary ||
    draft.people ||
    draft.place ||
    draft.tried ||
    draft.trustedPerson ||
    draft.attachments.length ||
    draft.impactTags.length
  );
  const blocker = useBlocker(
    ({ currentLocation, nextLocation }) =>
      dirty &&
      !saved.current &&
      currentLocation.pathname !== nextLocation.pathname,
  );
  const update = <K extends keyof CaseDraft>(name: K, value: CaseDraft[K]) => {
    setDraft((d) => ({ ...d, [name]: value }));
    setErrors((e) => ({ ...e, [name]: "" }));
  };
  useEffect(() => {
    if (saved.current) return;
    try {
      sessionStorage.setItem(key, JSON.stringify(draft));
    } catch {
      queueMicrotask(() => setStorageBlocked(true));
    }
  }, [draft, key]);
  useEffect(() => {
    if (!dirty) return;
    const unload = (event: BeforeUnloadEvent) => {
      if (saved.current) return;
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", unload);
    return () => window.removeEventListener("beforeunload", unload);
  }, [dirty]);
  const save = async (partial: boolean) => {
    const issues = validateCaseDraft(draft, partial);
    setErrors(issues);
    if (Object.keys(issues).length) {
      update("step", 1);
      return;
    }
    if (!user) return;
    setSaving(true);
    setSaveError("");
    const item = incidentFromDraft(
      draft,
      existing?.id ?? uid("CASE"),
      user.id,
      partial
        ? "draft"
        : existing?.status === "draft"
          ? "active"
          : (existing?.status ?? "active"),
      existing,
    );
    try {
      await demoService.saveCase(item);
      draft.attachments.forEach((attachment) =>
        useDemoStore.getState().putEvidence({ ...attachment, caseId: item.id }),
      );
      useDemoStore
        .getState()
        .chats.filter(
          (chat) =>
            chat.ownerId === user.id && item.linkedChatIds.includes(chat.id),
        )
        .forEach((chat) =>
          useDemoStore.getState().putChat({ ...chat, linkedCaseId: item.id }),
        );
      saved.current = true;
      if (blocker.state === "blocked") blocker.reset();
      try {
        sessionStorage.removeItem(key);
      } catch {
        /* Saved item remains in store. */
      }
      useDemoStore
        .getState()
        .notify(
          partial ? "Đã lưu bản nháp trong demo." : "Đã lưu hồ sơ trong demo.",
        );
      navigate(`/cases/${item.id}`, { replace: true });
    } catch (error) {
      setSaveError(
        error instanceof Error
          ? error.message
          : "Chưa lưu được. Nội dung vẫn ở đây, bạn hãy thử lại.",
      );
    } finally {
      setSaving(false);
    }
  };
  if (caseId && !existing)
    return (
      <>
        <PageHeader title="Không tìm thấy hồ sơ" back="/cases" />
        <Notice>
          Hồ sơ không còn tồn tại hoặc không thuộc tài khoản demo này.
        </Notice>
      </>
    );
  const template =
    templates.find((t) => t.id === draft.template) ?? templates[7];
  return (
    <div className="case-wizard">
      <PageHeader
        title={existing ? "Bổ sung hồ sơ" : "Ghi lại một chuyện"}
        description="Bạn có thể kể từng chút một, theo cách mình thấy thoải mái."
      />
      {initial.recovered && (
        <Notice>
          Đã khôi phục phần bạn đang viết. Bạn có thể tiếp tục từ bước{" "}
          {draft.step + 1}.
        </Notice>
      )}
      {draft.linkedChatIds.length > 0 && (
        <Notice>
          Nội dung được chuẩn bị từ hội thoại demo. Nguồn được giữ cùng bản
          nháp:{" "}
          {draft.linkedChatIds.map((id) => (
            <Link key={id} to={`/ai/chat/${id}`}>
              Mở hội thoại gốc
            </Link>
          ))}
          .
        </Notice>
      )}
      {storageBlocked && (
        <Notice tone="warning">
          Trình duyệt đang chặn lưu nháp tự động. Hãy chọn “Lưu nháp” trước khi
          rời trang.
        </Notice>
      )}
      <div className="wizard-layout">
        <aside className="wizard-steps" aria-label="Các bước tạo hồ sơ">
          {steps.map((label, index) => (
            <button
              key={label}
              className={draft.step === index ? "current" : ""}
              aria-current={draft.step === index ? "step" : undefined}
              onClick={() => update("step", index)}
            >
              <span>
                {index < draft.step ? <Check size={16} /> : index + 1}
              </span>
              {label}
            </button>
          ))}
          <p className="muted">
            Chỉ dùng nội dung giả. Không cần tên thật hay thông tin nhận diện.
          </p>
          <Link to="/ai/chat" className="ai-entry">
            <Sparkles size={18} />
            Muốn kể cùng AI demo?
          </Link>
        </aside>
        <section className="panel wizard-form">
          <div className="wizard-progress">
            <span>Bước {draft.step + 1}/6</span>
            <Badge tone="gray">Tự giữ nháp trong phiên</Badge>
          </div>
          <Progress value={draft.step + 1} max={6} />
          <h2>{steps[draft.step]}</h2>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              if (draft.step < 5) update("step", draft.step + 1);
              else void save(false);
            }}
            className="stack"
          >
            {draft.step === 0 && (
              <>
                <Field
                  label="Đặt tên hồ sơ"
                  hint="Có thể dùng tên trung tính, ví dụ “Chuyện trong nhóm chat”."
                  value={draft.title}
                  onChange={(e) => update("title", e.target.value)}
                  placeholder="Điều mình muốn ghi lại"
                  maxLength={120}
                />
                <fieldset className="case-fieldset">
                  <legend>Góc nhìn của bạn</legend>
                  <div className="segmented">
                    {(["self", "witness"] as const).map((p) => (
                      <button
                        key={p}
                        type="button"
                        aria-pressed={draft.perspective === p}
                        onClick={() => update("perspective", p)}
                      >
                        {p === "self" ? "Mình trải qua" : "Mình chứng kiến"}
                      </button>
                    ))}
                  </div>
                </fieldset>
                <fieldset className="case-fieldset">
                  <legend>Chọn mẫu gần với câu chuyện</legend>
                  <div className="template-grid">
                    {templates.map((t) => (
                      <button
                        type="button"
                        key={t.id}
                        className={`template-choice ${t.id === draft.template ? "selected" : ""}`}
                        aria-pressed={t.id === draft.template}
                        onClick={() => {
                          update("template", t.id);
                          if (t.id === "TPL-WITNESS")
                            update("perspective", "witness");
                        }}
                      >
                        {t.label}
                        {t.id === draft.template && <Check size={16} />}
                      </button>
                    ))}
                  </div>
                  <small className="muted">
                    Đổi mẫu vẫn giữ nội dung bạn đã viết.
                  </small>
                </fieldset>
              </>
            )}
            {draft.step === 1 && (
              <>
                <Notice>{template.hint}</Notice>
                {(draft.template === "TPL-THREAT" ||
                  draft.template === "TPL-PHYSICAL") && (
                  <p>
                    Nếu bạn đang không an toàn, hãy tìm người lớn ở gần.{" "}
                    <Link to="/support/urgent">Mở nguồn trợ giúp ngay</Link>.
                  </p>
                )}
                <Field
                  label="Chuyện gì đã xảy ra?"
                  id="case-story"
                  error={errors.summary}
                  hint="Điều bạn thấy hoặc nghe; phần chưa chắc có thể ghi rõ là chưa chắc."
                >
                  <textarea
                    id="case-story"
                    rows={6}
                    value={draft.summary}
                    onChange={(e) => update("summary", e.target.value)}
                    aria-invalid={!!errors.summary}
                    placeholder="Bạn có thể bắt đầu bằng một điều mình nhớ…"
                  />
                </Field>
                <div className="grid-2">
                  <Field label="Độ chính xác của thời gian" id="case-precision">
                    <select
                      id="case-precision"
                      value={draft.timePrecision}
                      onChange={(e) =>
                        update(
                          "timePrecision",
                          e.target.value as CaseDraft["timePrecision"],
                        )
                      }
                    >
                      <option value="unknown">Không nhớ chính xác</option>
                      <option value="day">Nhớ ngày</option>
                      <option value="week">Nhớ khoảng tuần</option>
                      <option value="exact">Nhớ ngày và giờ</option>
                    </select>
                  </Field>
                  {draft.timePrecision !== "unknown" && (
                    <Field
                      label={
                        draft.timePrecision === "week"
                          ? "Một ngày trong khoảng tuần đó"
                          : "Thời điểm"
                      }
                      type={
                        draft.timePrecision === "exact"
                          ? "datetime-local"
                          : "date"
                      }
                      value={draft.occurredAt}
                      onChange={(e) => update("occurredAt", e.target.value)}
                      error={errors.occurredAt}
                    />
                  )}
                </div>
                <Field
                  label="Ở đâu? (không bắt buộc)"
                  value={draft.place}
                  onChange={(e) => update("place", e.target.value)}
                  placeholder="Trong lớp, nhóm chat, hành lang…"
                />
                <fieldset className="case-fieldset">
                  <legend>Bối cảnh (có thể chọn nhiều)</legend>
                  <div className="chips">
                    {[
                      "Ở trường",
                      "Trực tuyến",
                      "Lặp lại nhiều lần",
                      "Một lần",
                      "Chưa chắc",
                    ].map((tag) => (
                      <button
                        className="chip"
                        type="button"
                        key={tag}
                        aria-pressed={draft.categoryTags.includes(tag)}
                        onClick={() =>
                          update(
                            "categoryTags",
                            draft.categoryTags.includes(tag)
                              ? draft.categoryTags.filter((t) => t !== tag)
                              : [...draft.categoryTags, tag],
                          )
                        }
                      >
                        {tag}
                      </button>
                    ))}
                  </div>
                </fieldset>
              </>
            )}
            {draft.step === 2 && (
              <>
                <Notice>
                  Bạn có thể dùng vai trò hoặc bí danh: bạn cùng lớp, người gửi
                  tin, người chứng kiến, người có thể giúp.
                </Notice>
                <Field label="Những người liên quan" id="case-people">
                  <textarea
                    id="case-people"
                    rows={5}
                    value={draft.people}
                    onChange={(e) => update("people", e.target.value)}
                    placeholder="Ví dụ: Một bạn gửi tin; hai bạn có mặt; cô giáo có thể hỗ trợ."
                  />
                </Field>
                <Field
                  label="Người bạn có thể tin tưởng"
                  value={draft.trustedPerson}
                  onChange={(e) => update("trustedPerson", e.target.value)}
                  placeholder="Giáo viên, người thân, người chăm sóc…"
                  list="case-trusted-people"
                />
                <TrustedPeopleList />
              </>
            )}
            {draft.step === 3 && (
              <>
                <fieldset className="case-fieldset">
                  <legend>Chuyện này ảnh hưởng đến bạn thế nào?</legend>
                  <div className="impact-options">
                    {impacts.map((impact) => (
                      <label key={impact}>
                        <input
                          type="checkbox"
                          checked={draft.impactTags.includes(impact)}
                          onChange={() =>
                            update(
                              "impactTags",
                              draft.impactTags.includes(impact)
                                ? draft.impactTags.filter((t) => t !== impact)
                                : [...draft.impactTags, impact],
                            )
                          }
                        />
                        {impact}
                      </label>
                    ))}
                  </div>
                </fieldset>
                <Field
                  label="Bạn đã thử làm gì? (không bắt buộc)"
                  id="case-tried"
                >
                  <textarea
                    id="case-tried"
                    rows={4}
                    value={draft.tried}
                    onChange={(e) => update("tried", e.target.value)}
                    placeholder="Bạn cũng có thể ghi “mình chưa thử gì”."
                  />
                </Field>
                <p className="muted">
                  Bạn không cần tự giải quyết mọi chuyện. Có thể để trống và bổ
                  sung sau.
                </p>
              </>
            )}
            {draft.step === 4 && (
              <>
                <p>Không có tệp vẫn lưu được hồ sơ.</p>
                <EvidencePicker
                  items={draft.attachments}
                  onChange={(items) => update("attachments", items)}
                />
                {existing && existing.evidenceIds.length > 0 && (
                  <p className="muted">
                    {
                      evidence.filter((e) =>
                        existing.evidenceIds.includes(e.id),
                      ).length
                    }{" "}
                    nguồn trước đó vẫn được giữ trong hồ sơ.
                  </p>
                )}
              </>
            )}
            {draft.step === 5 && (
              <>
                <Notice>
                  Bạn quyết định nội dung nào được lưu. Hồ sơ này chỉ nằm trong
                  bản demo.
                </Notice>
                <div className="review-list">
                  {[
                    {
                      label: "Tên và góc nhìn",
                      content: `${draft.title || "Điều mình muốn ghi lại"} · ${draft.perspective === "self" ? "Mình trải qua" : "Mình chứng kiến"}`,
                      step: 0,
                    },
                    {
                      label: "Chuyện xảy ra",
                      content:
                        draft.summary || "Chưa có mô tả — bạn có thể lưu nháp.",
                      step: 1,
                    },
                    {
                      label: "Thời gian và nơi chốn",
                      content: `${draft.timePrecision === "unknown" ? "Chưa rõ thời gian" : draft.occurredAt || "Chưa chọn thời gian"} · ${draft.place || "Chưa ghi địa điểm"}`,
                      step: 1,
                    },
                    {
                      label: "Người liên quan / hỗ trợ",
                      content: `${draft.people || "Chưa bổ sung"} · ${draft.trustedPerson || "Chưa chọn người hỗ trợ"}`,
                      step: 2,
                    },
                    {
                      label: "Ảnh hưởng và điều đã thử",
                      content: `${draft.impactTags.join(", ") || "Chưa chia sẻ"} · ${draft.tried || "Chưa bổ sung"}`,
                      step: 3,
                    },
                    {
                      label: "Nguồn đính kèm",
                      content: `${draft.attachments.length} nguồn mới`,
                      step: 4,
                    },
                  ].map((row) => (
                    <div key={row.label}>
                      <div>
                        <strong>{row.label}</strong>
                        <p>{row.content}</p>
                      </div>
                      <Button
                        variant="ghost"
                        type="button"
                        onClick={() => update("step", row.step)}
                      >
                        Sửa
                      </Button>
                    </div>
                  ))}
                </div>
              </>
            )}
            {saveError && (
              <Notice tone="error">
                {saveError}
                <Button
                  type="button"
                  variant="secondary"
                  disabled={saving}
                  onClick={() => void save(draft.step !== 5)}
                >
                  Thử lưu lại
                </Button>
              </Notice>
            )}
            <div className="wizard-footer">
              <Button
                type="button"
                variant="ghost"
                disabled={saving || draft.step === 0}
                onClick={() => update("step", draft.step - 1)}
              >
                <ArrowLeft size={17} />
                Trước
              </Button>
              <Button type="submit" disabled={saving}>
                {saving ? (
                  "Đang lưu…"
                ) : draft.step === 5 ? (
                  <>
                    <Check size={18} />
                    Lưu hồ sơ
                  </>
                ) : (
                  <>
                    Tiếp tục
                    <ArrowRight size={17} />
                  </>
                )}
              </Button>
            </div>
            <div className="wizard-secondary">
              <Button
                variant="secondary"
                type="button"
                disabled={saving}
                onClick={() => void save(true)}
              >
                <Save size={17} />
                Lưu nháp
              </Button>
              <Button
                variant="ghost"
                type="button"
                disabled={saving}
                onClick={() => setLeave(true)}
              >
                Rời phần đang viết
              </Button>
            </div>
          </form>
        </section>
      </div>
      <Modal
        open={leave || blocker.state === "blocked"}
        onClose={() => {
          setLeave(false);
          if (blocker.state === "blocked") blocker.reset();
        }}
        title="Bạn muốn dừng ở đây?"
      >
        <p>
          Phần đang viết được giữ trong phiên trình duyệt này. Bạn có thể lưu
          vào danh sách hồ sơ để quay lại ở lần mở sau.
        </p>
        <div className="stack">
          <Button
            onClick={() => {
              setLeave(false);
              void save(true);
            }}
            disabled={saving}
          >
            Lưu nháp và quay lại
          </Button>
          <Button
            variant="secondary"
            onClick={() => {
              saved.current = true;
              if (blocker.state === "blocked") blocker.proceed();
              else navigate(existing ? `/cases/${existing.id}` : "/cases");
            }}
          >
            Rời trang, giữ phần đang viết
          </Button>
          <Button
            variant="ghost"
            onClick={() => {
              setLeave(false);
              if (blocker.state === "blocked") blocker.reset();
            }}
          >
            Tiếp tục viết
          </Button>
        </div>
      </Modal>
    </div>
  );
}
function TrustedPeopleList() {
  const people = useDemoStore((s) => s.trustedPeople);
  return (
    <datalist id="case-trusted-people">
      {people.map((person) => (
        <option key={person.id} value={person.label} />
      ))}
    </datalist>
  );
}
