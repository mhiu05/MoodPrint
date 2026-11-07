import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import {
  Link,
  useBlocker,
  useLocation,
  useSearchParams,
} from "react-router-dom";
import {
  ArrowRight,
  BookOpen,
  Check,
  ChevronRight,
  Copy,
  Download,
  ExternalLink,
  FilePenLine,
  Heart,
  LifeBuoy,
  MessageCircle,
  Pencil,
  Phone,
  School,
  Settings,
  ShieldCheck,
  Trash2,
  Users,
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
  SectionHeading,
} from "../../components/ui";
import { knowledgeSources, supportSources } from "../../mocks/data/sources";
import { getServices } from "../../services/composition";
import type { School as ConnectedSchool } from "../../services/ports";
import type { SupportDraft } from "../../types";
import "./support.css";

const statusLabels: Record<SupportDraft["status"], string> = {
  draft: "Bản nháp",
  prepared: "Đã chuẩn bị",
  demo_submitted: "Demo · Đã lưu mô phỏng",
  demo_reviewing: "Demo · Đang xem xét giả lập",
  demo_closed: "Demo · Kết thúc giả lập",
};
const sourceIcons = {
  school: School,
  heart: Heart,
  people: Users,
  phone: Phone,
  shield: ShieldCheck,
};
const errorMessage = (e: unknown) =>
  e instanceof Error
    ? e.message
    : "Chưa thực hiện được thao tác. Nội dung của bạn vẫn được giữ; hãy thử lại.";
const prettyDate = (date: string) => new Date(date).toLocaleDateString("vi-VN");

function UrgentEntry() {
  return (
    <Link className="support-urgent-entry" to="/support/urgent">
      <LifeBuoy size={22} />
      <div>
        <strong>Cần hỗ trợ ngay?</strong>
        <span>Tìm nơi an toàn và người có thể giúp trực tiếp.</span>
      </div>
      <ChevronRight size={20} />
    </Link>
  );
}
export function SupportHome() {
  const demo = useWorkspaceStore((s) => s.workspace.kind === "demo");
  const user = useWorkspaceStore((s) => s.user);
  const drafts = useWorkspaceStore((s) => s.drafts);
  const ownDrafts = drafts.filter((d) => d.ownerId === user?.id);
  const routes = [
    {
      to: "/support/find-help",
      title: "Tìm người có thể giúp",
      copy: "Một giáo viên, người chăm sóc, hay một người lớn bạn tin.",
      icon: Users,
      label: "Tìm một điểm tựa",
      tone: "green",
    },
    {
      to: "/support/prepare",
      title: "Chuẩn bị lời nhắn",
      copy: "Không biết mở lời thế nào? Thử viết ra, rồi sửa theo cách của bạn.",
      icon: FilePenLine,
      label: "Từng câu, từng chút",
      tone: "lavender",
    },
    {
      to: "/support/knowledge",
      title: "Hiểu thêm về tình huống",
      copy: "Bài đọc ngắn và ví dụ để bạn thử một lựa chọn.",
      icon: BookOpen,
      label: "Góc kiến thức",
      tone: "peach",
    },
  ];
  return (
    <div className="support-page stack">
      <PageHeader
        title="Bạn có thể tìm một điểm tựa"
        description="Chọn điều bạn cần lúc này. Bạn quyết định chia sẻ với ai và khi nào."
        action={
          <Link className="button ghost" to="/settings">
            <Settings size={18} />
            Cài đặt
          </Link>
        }
      />
      <UrgentEntry />
      <section className="support-paths">
        {routes.map((route) => (
          <Link
            to={route.to}
            className={`support-path ${route.tone}`}
            key={route.to}
          >
            <div className="support-path-top">
              <route.icon size={26} />
            </div>
            <h2>{route.title}</h2>
            <p>{route.copy}</p>
            <span className="support-path-link">
              Khám phá
              <ArrowRight size={17} />
            </span>
          </Link>
        ))}
      </section>
      <section className="support-recent">
        <SectionHeading
          title="Lời nhắn của bạn"
          to="/support/requests"
          label={demo ? "Xem bản nháp & demo" : "Xem bản nháp"}
        />
        {ownDrafts.length ? (
          ownDrafts
            .slice(-2)
            .reverse()
            .map((d) => (
              <Link
                className="support-draft-row"
                key={d.id}
                to={`/support/prepare?draftId=${d.id}`}
              >
                <FilePenLine size={20} />
                <div>
                  <strong>Gửi {d.recipientType.toLowerCase()}</strong>
                  <span>
                    {statusLabels[d.status]} · {prettyDate(d.createdAt)}
                  </span>
                </div>
                <ChevronRight size={18} />
              </Link>
            ))
        ) : (
          <div className="support-soft-empty">
            <MessageCircle size={27} />
            <div>
              <h3>Bạn có thể bắt đầu bằng một câu.</h3>
              <p>
                {demo
                  ? "Bản nháp được giữ trong trình duyệt demo này."
                  : "Bản nháp đã lưu được giữ trong tài khoản của bạn."}{" "}
                Chưa có gì được gửi cho người khác.
              </p>
            </div>
            <Link to="/support/prepare">
              Soạn lời nhắn
              <ArrowRight size={16} />
            </Link>
          </div>
        )}
      </section>
      <div className="support-footnote">
        <ShieldCheck size={20} />
        <p>
          MoodPrint giúp bạn chuẩn bị. Việc lưu, sao chép và mô phỏng báo cáo
          trong ứng dụng chưa liên hệ với nhà trường hoặc một người hỗ trợ.
        </p>
      </div>
    </div>
  );
}

export function FindHelpPage() {
  const people = useWorkspaceStore((s) => s.trustedPeople);
  const demo = useWorkspaceStore((s) => s.workspace.kind === "demo");
  const [editingId, setEditingId] = useState("");
  const [busy, setBusy] = useState(false);
  const [label, setLabel] = useState("");
  const [role, setRole] = useState("Giáo viên");
  const [error, setError] = useState("");
  async function add(e: FormEvent) {
    e.preventDefault();
    if (!label.trim()) {
      setError("Điền một tên gọi để bạn dễ nhớ.");
      return;
    }
    if (
      people.some(
        (p) =>
          p.id !== editingId &&
          p.label.toLocaleLowerCase() === label.trim().toLocaleLowerCase(),
      )
    ) {
      setError("Tên gọi này đã có trong danh sách của bạn.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      await getServices().contacts.save({
        id: editingId || (demo ? uid("TRUST") : crypto.randomUUID()),
        label: label.trim(),
        role,
      });
      setLabel("");
      setEditingId("");
    } catch (cause) {
      setError(errorMessage(cause));
    } finally {
      setBusy(false);
    }
  }
  async function removePerson(id: string) {
    setBusy(true);
    setError("");
    try {
      await getServices().contacts.remove(id);
    } catch (cause) {
      setError(errorMessage(cause));
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="support-page stack">
      <PageHeader
        title="Ai có thể ở bên bạn?"
        description="Bạn được chọn một người mình cảm thấy an toàn. Không bắt buộc phải là người đầu tiên trong danh sách."
        back="/support"
      />
      <UrgentEntry />
      <section className="support-contact-list">
        {supportSources.map((source, i) => {
          const Icon = sourceIcons[source.icon];
          return (
            <article className="support-contact" key={source.id}>
              <div className="support-contact-number">0{i + 1}</div>
              <div className="support-contact-body">
                <div className="support-contact-heading">
                  <Icon size={22} />
                  <h2>{source.title}</h2>
                </div>
                <Badge tone={source.id === "111" ? "peach" : "green"}>
                  {source.tag}
                </Badge>
                <p>{source.description}</p>
                <p className="support-prep-note">{source.preparation}</p>
                {source.id === "111" ? (
                  <div className="actions">
                    <a className="button secondary" href="tel:111">
                      <Phone size={16} />
                      Gọi 111
                    </a>
                    <a
                      href="https://tongdai111.vn/tin/so-dien-thoai-bao-ve-tre-em"
                      target="_blank"
                      rel="noreferrer"
                    >
                      Nguồn chính thức
                      <ExternalLink size={14} />
                    </a>
                  </div>
                ) : source.id === "platform" ? (
                  <LinkButton
                    variant="secondary"
                    to="/knowledge/chan-va-bao-cao-noi-dung"
                  >
                    Xem hướng dẫn
                    <ArrowRight size={16} />
                  </LinkButton>
                ) : (
                  <div className="actions">
                    <LinkButton
                      variant="secondary"
                      to={`/support/prepare?recipient=${source.id}`}
                    >
                      Chuẩn bị lời nhắn
                      <ArrowRight size={16} />
                    </LinkButton>
                    {source.id === "teacher" || source.id === "parent" ? (
                      <Link to={`/ai/roleplay/${source.id}`}>
                        Thử luyện nói
                      </Link>
                    ) : null}
                  </div>
                )}
              </div>
            </article>
          );
        })}
      </section>
      <section className="support-trusted">
        <div>
          <span className="support-eyebrow">Danh sách riêng của bạn</span>
          <h2>Nhớ một người mình có thể tìm đến</h2>
          <p>
            Chỉ cần tên gọi dễ nhớ, không cần số điện thoại hay địa chỉ. Danh
            sách này không tự liên hệ ai.
          </p>
        </div>
        <div>
          {people.length ? (
            <ul className="support-people">
              {people.map((person) => (
                <li key={person.id}>
                  <div>
                    <strong>{person.label}</strong>
                    <small>{person.role}</small>
                  </div>
                  <Button
                    variant="ghost"
                    disabled={busy}
                    aria-label={`Sửa ${person.label}`}
                    onClick={() => {
                      setEditingId(person.id);
                      setLabel(person.label);
                      setRole(person.role);
                      setError("");
                    }}
                  >
                    <Pencil size={16} />
                  </Button>
                  <Button
                    variant="ghost"
                    disabled={busy}
                    aria-label={`Xóa ${person.label}`}
                    onClick={() => removePerson(person.id)}
                  >
                    <Trash2 size={16} />
                  </Button>
                </li>
              ))}
            </ul>
          ) : (
            <p className="muted">
              Bạn chưa thêm người tin cậy. Bạn có thể để sau.
            </p>
          )}
          <form onSubmit={add} className="stack">
            <Field
              label="Tên gọi dễ nhớ"
              value={label}
              maxLength={70}
              onChange={(e) => setLabel(e.target.value)}
              placeholder="Ví dụ: Cô thư viện"
              error={error}
            />
            <div className="field">
              <label htmlFor="trusted-role">Vai trò</label>
              <select
                id="trusted-role"
                value={role}
                onChange={(e) => setRole(e.target.value)}
              >
                <option>Giáo viên</option>
                <option>Người chăm sóc</option>
                <option>Người thân</option>
                <option>Người lớn khác</option>
              </select>
            </div>
            <Button type="submit" variant="secondary" disabled={busy}>
              {busy
                ? "Đang lưu…"
                : editingId
                  ? "Lưu người tin cậy"
                  : "Thêm người tin cậy"}
            </Button>
            {editingId && (
              <Button
                variant="ghost"
                onClick={() => {
                  setEditingId("");
                  setLabel("");
                  setError("");
                }}
              >
                Hủy chỉnh sửa
              </Button>
            )}
          </form>
        </div>
      </section>
      <p className="support-footnote">
        Thông tin Tổng đài 111 được kiểm tra theo nguồn chính thức ngày
        07/11/2026. Các gợi ý người hỗ trợ còn lại là nội dung do MoodPrint biên
        tập, không phải danh bạ dịch vụ đã xác minh.
      </p>
    </div>
  );
}

type ComposerValues = {
  recipient: string;
  purpose: string;
  detail: string;
  identity: "alias" | "disclose";
  alias: string;
};
const displayName = (values: ComposerValues, nickname: string) =>
  values.identity === "alias"
    ? values.alias.trim() || "Một học sinh"
    : `${nickname} (tên hiển thị${useWorkspaceStore.getState().workspace.kind === "demo" ? " demo" : ""})`;
function compose(values: ComposerValues, nickname: string) {
  const name = displayName(values, nickname);
  return `Chào ${values.recipient.toLowerCase()},\n\nMình là ${name}. ${values.purpose}.\n\n${values.detail.trim() || "Mình muốn có một lúc nói chuyện riêng về việc đang khiến mình lo lắng."}\n\nMình mong được nghe trước, rồi cùng bàn một bước an toàn tiếp theo. Mình muốn trao đổi riêng về những thông tin nào sẽ được chia sẻ thêm.\n\nCảm ơn vì đã dành thời gian lắng nghe.`;
}

function updateEnvelope(
  content: string,
  previous: ComposerValues,
  next: ComposerValues,
  nickname: string,
) {
  if (content === compose(previous, nickname)) return compose(next, nickname);
  const oldGreeting = `Chào ${previous.recipient.toLowerCase()},\n\n`;
  let result = content.startsWith(oldGreeting)
    ? `Chào ${next.recipient.toLowerCase()},\n\n${content.slice(oldGreeting.length)}`
    : content;
  const oldIdentity = `\n\nMình là ${displayName(previous, nickname)}. `;
  if (result.includes(oldIdentity))
    result = result.replace(
      oldIdentity,
      `\n\nMình là ${displayName(next, nickname)}. `,
    );
  return result;
}
type RecoveryDraft = {
  values: ComposerValues;
  content: string;
  caseId: string;
  draftId: string;
  createdAt: string;
};
function recoveryId(text: string) {
  let hash = 0;
  for (const character of text)
    hash = (Math.imul(hash, 31) + character.charCodeAt(0)) | 0;
  return `${text.length}-${hash >>> 0}`;
}
function readRecovery(key: string, fallback: RecoveryDraft) {
  try {
    const raw = sessionStorage.getItem(key);
    if (raw) {
      const candidate = JSON.parse(raw) as RecoveryDraft;
      if (
        candidate.values &&
        ["recipient", "purpose", "detail", "alias"].every(
          (name) =>
            typeof candidate.values[name as keyof ComposerValues] === "string",
        ) &&
        ["alias", "disclose"].includes(candidate.values.identity) &&
        typeof candidate.content === "string" &&
        typeof candidate.caseId === "string" &&
        typeof candidate.draftId === "string" &&
        typeof candidate.createdAt === "string"
      )
        return { draft: candidate, recovered: true };
    }
  } catch {
    /* The form remains usable when local recovery is unavailable. */
  }
  return { draft: fallback, recovered: false };
}

export function SupportPreparePage() {
  const location = useLocation();
  const ownerId = useWorkspaceStore((s) => s.user?.id);
  const imported = (location.state as { content?: unknown } | null)?.content;
  return (
    <SupportComposer
      key={`${ownerId}:${location.search}:${typeof imported === "string" ? recoveryId(imported) : ""}`}
    />
  );
}
function ConnectedSchools() {
  const [schools, setSchools] = useState<ConnectedSchool[] | null>(null);
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let active = true;
    void getServices()
      .support.listSchools()
      .then((items) => {
        if (active) {
          setSchools(items);
          setError("");
        }
      })
      .catch((cause: unknown) => {
        if (active) setError(errorMessage(cause));
      });
    return () => {
      active = false;
    };
  }, [attempt]);
  return (
    <div className="support-demo-intake">
      <h3>
        {schools === null
          ? "Kết nối với trường"
          : schools.length
            ? "Trường đã kết nối"
            : "Chưa có trường kết nối"}
      </h3>
      {error ? (
        <Notice tone="error">
          {error}
          <Button
            variant="secondary"
            onClick={() => setAttempt((value) => value + 1)}
          >
            Thử tải lại
          </Button>
        </Notice>
      ) : schools === null ? (
        <p role="status">Đang tải danh sách trường…</p>
      ) : (
        <>
          {schools.length > 0 && (
            <ul>
              {schools.map((school) => (
                <li key={school.id}>{school.name}</li>
              ))}
            </ul>
          )}
          <p>
            Bản nháp chưa được chia sẻ. Bạn có thể sao chép hoặc tải lời nhắn để
            tự chọn người nhận khi sẵn sàng.
          </p>
        </>
      )}
    </div>
  );
}
function SupportComposer() {
  const demo = useWorkspaceStore((s) => s.workspace.kind === "demo");
  const [params] = useSearchParams();
  const location = useLocation();
  const user = useWorkspaceStore((s) => s.user);
  const cases = useWorkspaceStore((s) => s.cases);
  const drafts = useWorkspaceStore((s) => s.drafts);
  const people = useWorkspaceStore((s) => s.trustedPeople);
  const notify = useWorkspaceStore((s) => s.notify);
  const ownCases = cases.filter((c) => c.ownerId === user?.id);
  const existing = drafts.find(
    (d) => d.id === params.get("draftId") && d.ownerId === user?.id,
  );
  const importedContent = (location.state as { content?: unknown } | null)
    ?.content;
  const fromRoleplay =
    typeof importedContent === "string" ? importedContent : "";
  const initialCaseId = existing?.caseId || params.get("caseId") || "";
  const initialCase = ownCases.find((c) => c.id === initialCaseId);
  const source = supportSources.find((s) => s.id === params.get("recipient"));
  const contextId = existing?.id
    ? `saved:${existing.id}`
    : fromRoleplay
      ? `roleplay:${initialCase?.id || "none"}:${recoveryId(fromRoleplay)}`
      : initialCase
        ? `case:${initialCase.id}`
        : `new:${source?.id || "default"}`;
  const [recoveryContext, setRecoveryContext] = useState(contextId);
  const recoveryKey = `moodprint-support-draft-v1:${user?.id || "signed-out"}:${recoveryContext}`;
  const [initial] = useState(() => {
    const values: ComposerValues = {
      recipient: existing?.recipientType || source?.recipient || "Giáo viên",
      purpose:
        existing?.compose?.purpose || "Mình muốn nhờ giúp về một sự việc",
      detail:
        fromRoleplay ||
        existing?.compose?.detail ||
        existing?.content ||
        initialCase?.summary ||
        "",
      identity: existing?.identityMode || "alias",
      alias: existing?.compose?.alias || user?.nickname || "Một học sinh",
    };
    return readRecovery(recoveryKey, {
      values,
      content:
        existing?.content ||
        fromRoleplay ||
        compose(values, user?.nickname || "Bạn"),
      caseId: initialCase?.id || "",
      draftId: existing?.id || (demo ? uid("SUPPORT") : crypto.randomUUID()),
      createdAt: existing?.createdAt || new Date().toISOString(),
    });
  });
  const [caseId, setCaseId] = useState(initial.draft.caseId);
  const [values, setValues] = useState(initial.draft.values);
  const [content, setContent] = useState(initial.draft.content);
  const [draftId] = useState(initial.draft.draftId);
  const [createdAt] = useState(initial.draft.createdAt);
  const [version, setVersion] = useState(existing?.version);
  const snapshot = JSON.stringify({ values, content, caseId });
  const recoveryData = JSON.stringify({
    values,
    content,
    caseId,
    draftId,
    createdAt,
  });
  const [cleanSnapshot, setCleanSnapshot] = useState(() =>
    initial.recovered || (!existing && (fromRoleplay || initialCase))
      ? ""
      : snapshot,
  );
  const dirty = snapshot !== cleanSnapshot;
  const blocker = useBlocker(
    ({ currentLocation, nextLocation }) =>
      dirty &&
      nextLocation.pathname !== "/support/urgent" &&
      (currentLocation.pathname !== nextLocation.pathname ||
        currentLocation.search !== nextLocation.search),
  );
  const [status, setStatus] = useState<SupportDraft["status"]>(
    existing?.status || "draft",
  );
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [confirmDemo, setConfirmDemo] = useState(false);
  const [acknowledged, setAcknowledged] = useState(false);
  const [confirmRegenerate, setConfirmRegenerate] = useState(false);
  const [storageBlocked, setStorageBlocked] = useState(false);
  const selectedCase = ownCases.find((c) => c.id === caseId);
  useEffect(() => {
    try {
      if (dirty) sessionStorage.setItem(recoveryKey, recoveryData);
      else sessionStorage.removeItem(recoveryKey);
    } catch {
      queueMicrotask(() => setStorageBlocked(true));
    }
  }, [recoveryKey, recoveryData, dirty]);
  useEffect(() => {
    if (!dirty) return;
    const unload = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", unload);
    return () => window.removeEventListener("beforeunload", unload);
  }, [dirty]);
  function update(patch: Partial<ComposerValues>) {
    const next = { ...values, ...patch };
    setValues(next);
    if (
      patch.recipient !== undefined ||
      patch.identity !== undefined ||
      patch.alias !== undefined ||
      patch.purpose !== undefined
    )
      setContent((current) =>
        updateEnvelope(current, values, next, user?.nickname || "Bạn"),
      );
    setSuccess("");
  }
  function selectCase(id: string) {
    setCaseId(id);
    setSuccess(
      "Đã đổi hồ sơ liên quan. Nội dung bạn chọn được giữ nguyên; liên kết hồ sơ không tự thêm toàn bộ tóm tắt.",
    );
  }
  function regenerate() {
    setContent(compose(values, user?.nickname || "Bạn"));
    setConfirmRegenerate(false);
    setSuccess(
      "Đã tạo lại bản xem trước từ phần chuẩn bị. Bạn có thể sửa trực tiếp.",
    );
  }
  async function save(nextStatus: SupportDraft["status"]) {
    if (!demo && nextStatus.startsWith("demo_")) return;
    if (!user) {
      setError("Bạn cần đăng nhập để lưu bản nháp.");
      return;
    }
    if (!values.recipient.trim() || !content.trim()) {
      setError(
        "Chọn người nhận và viết ít nhất một câu trong nội dung xem trước.",
      );
      return;
    }
    setBusy(true);
    setError("");
    setSuccess("");
    try {
      const saved = await getServices().support.save({
        id: draftId,
        ownerId: user.id,
        ...(caseId ? { caseId } : {}),
        recipientType: values.recipient,
        identityMode: values.identity,
        compose: {
          purpose: values.purpose,
          detail: values.detail,
          alias: values.alias,
        },
        content: content.trim(),
        status: nextStatus,
        createdAt,
        demo,
        version,
      });
      setVersion(saved.version);
      try {
        sessionStorage.removeItem(recoveryKey);
      } catch {
        /* The saved draft remains available in the store. */
      }
      setCleanSnapshot(snapshot);
      setRecoveryContext(`saved:${draftId}`);
      setStatus(saved.status);
      setConfirmDemo(false);
      setAcknowledged(false);
      const message =
        nextStatus === "demo_submitted"
          ? "Đã lưu mô phỏng, chưa gửi. Nhà trường và người hỗ trợ chưa nhận được nội dung này."
          : demo
            ? "Đã lưu bản nháp trong trình duyệt demo. Chưa gửi cho ai."
            : "Đã lưu bản nháp trong tài khoản. Chưa gửi cho ai.";
      setSuccess(message);
      notify(message);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }
  async function copy() {
    setError("");
    setSuccess("");
    try {
      if (!content.trim()) throw new Error("Bạn chưa có nội dung để sao chép.");
      if (!navigator.clipboard?.writeText)
        throw new Error(
          "Trình duyệt chưa cho phép sao chép. Bạn có thể chọn nội dung xem trước và sao chép thủ công.",
        );
      await navigator.clipboard.writeText(content);
      setSuccess(
        "Đã sao chép. Bạn tự chọn nơi dán và người nhận ngoài MoodPrint.",
      );
    } catch (e) {
      setError(errorMessage(e));
    }
  }
  function download() {
    setError("");
    setSuccess("");
    let url = "";
    try {
      if (!content.trim())
        throw new Error("Bạn chưa có nội dung để tải xuống.");
      const text = `BẢN CHUẨN BỊ MOODPRINT — CHƯA GỬI\nNgười nhận dự kiến: ${values.recipient}\nChế độ: ${values.identity === "alias" ? "Bí danh (không bảo đảm ẩn danh tuyệt đối)" : demo ? "Tên hiển thị demo" : "Tên hiển thị"}\n\n${content}`;
      url = URL.createObjectURL(
        new Blob([text], { type: "text/plain;charset=utf-8" }),
      );
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `moodprint-loi-nhan-${draftId}.txt`;
      document.body.append(anchor);
      anchor.click();
      anchor.remove();
      setSuccess(
        "Đã tạo tệp văn bản để tải xuống. Kiểm tra thư mục tải của thiết bị; chưa gửi cho ai.",
      );
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      if (url) setTimeout(() => URL.revokeObjectURL(url), 1000);
    }
  }
  return (
    <div className="support-compose-page stack">
      <PageHeader
        title="Một lời nhắn, theo cách của bạn"
        description="Thử viết ra trước. Bạn có thể sửa, để dành hoặc tự chia sẻ khi thấy sẵn sàng."
        back="/support"
      />
      <Notice>
        {demo
          ? "Đây là bản chuẩn bị cục bộ."
          : "Bản nháp đã lưu được giữ trong tài khoản của bạn."}{" "}
        MoodPrint không gửi email, tin nhắn hay báo cáo thật.
      </Notice>
      {initial.recovered && dirty && (
        <Notice>
          Đã khôi phục bản tạm chưa lưu của bạn trong phiên trình duyệt này.
        </Notice>
      )}
      {storageBlocked && (
        <Notice tone="warning">
          Trình duyệt không cho giữ bản tạm. Hãy lưu bản nháp hoặc sao chép
          trước khi rời trang.
        </Notice>
      )}
      {fromRoleplay && (
        <Notice tone="success">
          Đã mang lời bạn chọn từ buổi luyện nói vào bản xem trước. Bạn có thể
          sửa tiếp.
        </Notice>
      )}
      {initialCaseId && !initialCase && (
        <Notice tone="warning">
          Hồ sơ trong đường dẫn không có trong phiên của bạn. Bạn có thể viết
          mới hoặc chọn một hồ sơ khác.
        </Notice>
      )}
      {params.get("draftId") && !existing && (
        <Notice tone="warning">
          Không tìm thấy bản nháp trong phiên của bạn. Nội dung mới bên dưới
          chưa được lưu.
        </Notice>
      )}
      <div className="support-compose-layout">
        <section className="support-compose-fields">
          <div className="support-step-label">
            <span>1</span>
            <h2>Chọn điều muốn nói</h2>
          </div>
          <div className="field">
            <label htmlFor="support-case">
              Hồ sơ liên quan (không bắt buộc)
            </label>
            <select
              id="support-case"
              value={caseId}
              onChange={(e) => selectCase(e.target.value)}
            >
              <option value="">Viết lời nhắn mới</option>
              {ownCases.map((c) => (
                <option value={c.id} key={c.id}>
                  {c.title}
                </option>
              ))}
            </select>
          </div>
          {!ownCases.length && (
            <p className="muted">
              Không cần tạo hồ sơ trước. Bạn vẫn có thể viết bên dưới.
            </p>
          )}
          <div className="field">
            <label htmlFor="support-recipient">Người bạn muốn nhờ</label>
            <select
              id="support-recipient"
              value={values.recipient}
              onChange={(e) => update({ recipient: e.target.value })}
            >
              {[
                "Giáo viên",
                "Người chăm sóc",
                "Người lớn tin cậy khác",
                "Tổng đài 111",
                ...(demo ? ["Trường Mẫu A (demo)"] : []),
                ...people.map((p) => p.label),
                ...(![
                  "Giáo viên",
                  "Người chăm sóc",
                  "Người lớn tin cậy khác",
                  "Tổng đài 111",
                  ...(demo ? ["Trường Mẫu A (demo)"] : []),
                  ...people.map((p) => p.label),
                ].includes(values.recipient)
                  ? [values.recipient]
                  : []),
              ].map((r) => (
                <option key={r}>{r}</option>
              ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor="support-purpose">Điều bạn cần</label>
            <select
              id="support-purpose"
              value={values.purpose}
              onChange={(e) => update({ purpose: e.target.value })}
            >
              <option>Mình muốn nhờ giúp về một sự việc</option>
              <option>Mình muốn được lắng nghe trước</option>
              <option>Mình muốn trình bày để cùng tìm cách xử lý</option>
            </select>
          </div>
          <div className="field">
            <label htmlFor="support-detail">
              Điều đã xảy ra và điều muốn nhờ
            </label>
            <textarea
              id="support-detail"
              rows={5}
              maxLength={6000}
              value={values.detail}
              placeholder="Chỉ kể phần bạn thấy sẵn sàng chia sẻ…"
              onChange={(e) => update({ detail: e.target.value })}
            />
            <small>
              Thông tin chưa rõ có thể ghi “mình chưa chắc”. Không tự thêm tên
              hay thời gian.
            </small>
          </div>
          <fieldset className="support-identity">
            <legend>Cách giới thiệu trong bản xem trước</legend>
            <label>
              <input
                type="radio"
                name="identity"
                checked={values.identity === "alias"}
                onChange={() => update({ identity: "alias" })}
              />
              <span>
                Dùng bí danh<small>Bạn chọn tên gọi để giới thiệu.</small>
              </span>
            </label>
            <label>
              <input
                type="radio"
                name="identity"
                checked={values.identity === "disclose"}
                onChange={() => update({ identity: "disclose" })}
              />
              <span>
                {demo ? "Dùng tên hiển thị demo" : "Dùng tên hiển thị"}
                <small>
                  {user?.nickname || "Bạn"} — không phải xác minh danh tính.
                </small>
              </span>
            </label>
          </fieldset>
          {values.identity === "alias" && (
            <Field
              label="Bí danh trong lời nhắn"
              maxLength={50}
              value={values.alias}
              onChange={(e) => update({ alias: e.target.value })}
            />
          )}
          <p className="support-privacy-note">
            <ShieldCheck size={16} />
            Bí danh không bảo đảm ẩn danh tuyệt đối. Nội dung, ảnh hoặc tệp bạn
            tự chia sẻ có thể vẫn cho biết danh tính.
          </p>
          <Button
            variant="secondary"
            onClick={() => {
              if (
                content.trim() &&
                content !== compose(values, user?.nickname || "Bạn")
              )
                setConfirmRegenerate(true);
              else regenerate();
            }}
          >
            Cập nhật bản xem trước
            <ArrowRight size={16} />
          </Button>
        </section>
        <section className="support-preview">
          <div className="support-step-label">
            <span>2</span>
            <h2>Đọc lại & sửa lời của bạn</h2>
          </div>
          <div className="support-preview-paper">
            <div className="support-paper-heading">
              <FilePenLine size={18} />
              <span>Bản nhắn riêng</span>
              <Badge tone="peach">Chưa gửi</Badge>
            </div>
            <dl className="support-preview-metadata">
              <div>
                <dt>Người nhận dự kiến</dt>
                <dd>{values.recipient}</dd>
              </div>
              <div>
                <dt>Cách giới thiệu</dt>
                <dd>{displayName(values, user?.nickname || "Bạn")}</dd>
              </div>
            </dl>
            <div className="field">
              <label htmlFor="support-preview">Nội dung xem trước</label>
              <textarea
                id="support-preview"
                value={content}
                maxLength={10000}
                onChange={(e) => {
                  setContent(e.target.value);
                  setSuccess("");
                }}
                rows={17}
              />
            </div>
            <p className="muted">
              Lời bạn viết được giữ khi đổi lựa chọn. Hãy kiểm tra tên và xưng
              hô trong lời tự viết trước khi chia sẻ. Tạo lại theo mẫu cần bạn
              xác nhận.
            </p>
          </div>
          <div className="actions">
            <Button disabled={busy} onClick={() => save("draft")}>
              {busy ? "Đang lưu…" : "Lưu bản nháp"}
            </Button>
            {!demo && (
              <Button
                variant="secondary"
                disabled={busy}
                onClick={() => save("prepared")}
              >
                Đánh dấu đã chuẩn bị
              </Button>
            )}
            <Button variant="secondary" disabled={busy} onClick={copy}>
              <Copy size={16} />
              Sao chép
            </Button>
            <Button variant="ghost" disabled={busy} onClick={download}>
              <Download size={16} />
              Tải bản .txt
            </Button>
          </div>
          <p className="support-save-state">
            {statusLabels[status]} · Không tự gửi cho ai
          </p>
          {error && <Notice tone="error">{error}</Notice>}
          {success && (
            <Notice tone="success">
              <div role="status">{success}</div>
            </Notice>
          )}
          {demo ? (
            <div className="support-demo-intake">
              <h3>Muốn thử quy trình báo cáo?</h3>
              <p>
                Chỉ mô phỏng lưu một báo cáo mẫu. Không có trường thật hoặc
                người trực tiếp nhận.
              </p>
              <Button
                variant="secondary"
                disabled={busy}
                onClick={() => {
                  setAcknowledged(false);
                  setConfirmDemo(true);
                }}
              >
                Lưu báo cáo demo
              </Button>
              <Link to="/support/requests">
                Xem bản nháp & theo dõi demo
                <ArrowRight size={15} />
              </Link>
            </div>
          ) : (
            <ConnectedSchools />
          )}
        </section>
      </div>
      {selectedCase && (
        <Link
          className="support-return-plan"
          to={`/cases/${selectedCase.id}/plan`}
        >
          Quay lại kế hoạch của “{selectedCase.title}”<ArrowRight size={16} />
        </Link>
      )}
      <Modal
        open={confirmDemo}
        title="Lưu mô phỏng, chưa gửi tới nhà trường"
        onClose={() => {
          if (!busy) setConfirmDemo(false);
        }}
      >
        <div className="stack">
          <Notice>
            Thao tác này chỉ đổi trạng thái trong trình duyệt demo. Trường học,
            Tổng đài 111 và người bạn chọn không nhận được nội dung.
          </Notice>
          <p>
            Người nhận dự kiến: <strong>{values.recipient}</strong>. Bạn vẫn
            phải tự liên hệ nếu muốn được hỗ trợ thật.
          </p>
          <label className="support-confirm">
            <input
              type="checkbox"
              checked={acknowledged}
              onChange={(e) => setAcknowledged(e.target.checked)}
            />
            Tôi hiểu đây chỉ là mô phỏng, chưa gửi cho ai.
          </label>
          {error && <Notice tone="error">{error}</Notice>}
          <div className="actions">
            <Button
              disabled={!acknowledged || busy}
              onClick={() => save("demo_submitted")}
            >
              {busy ? "Đang lưu…" : "Xác nhận lưu mô phỏng"}
            </Button>
            <Button
              variant="ghost"
              disabled={busy}
              onClick={() => setConfirmDemo(false)}
            >
              Quay lại chỉnh sửa
            </Button>
          </div>
        </div>
      </Modal>
      <Modal
        open={confirmRegenerate}
        title="Thay lời đang viết bằng mẫu mới?"
        onClose={() => setConfirmRegenerate(false)}
      >
        <div className="stack">
          <p>
            Lời tự viết hoặc đoạn bạn chọn từ buổi luyện nói sẽ được thay bằng
            mẫu từ phần chuẩn bị bên trái. Bạn có thể ở lại để sao chép lời hiện
            tại trước.
          </p>
          <div className="actions">
            <Button
              variant="secondary"
              onClick={() => setConfirmRegenerate(false)}
            >
              Giữ lời hiện tại
            </Button>
            <Button onClick={regenerate}>Xác nhận tạo lại theo mẫu</Button>
          </div>
        </div>
      </Modal>
      <Modal
        open={blocker.state === "blocked"}
        title="Bạn còn lời nhắn chưa lưu"
        onClose={() => {
          if (blocker.state === "blocked") blocker.reset();
        }}
      >
        <div className="stack">
          <p>
            Bạn có thể ở lại chỉnh sửa và lưu bản nháp. Nếu rời trang, bản tạm
            được giữ cho phiên của bạn trong trình duyệt này khi bộ nhớ khả
            dụng.
          </p>
          <div className="actions">
            <Button
              onClick={() => {
                if (blocker.state === "blocked") blocker.reset();
              }}
            >
              Ở lại chỉnh sửa
            </Button>
            <Button
              variant="secondary"
              onClick={() => {
                if (blocker.state === "blocked") blocker.proceed();
              }}
            >
              Rời trang & giữ bản tạm
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}

export function SupportRequestsPage() {
  const demo = useWorkspaceStore((s) => s.workspace.kind === "demo");
  const user = useWorkspaceStore((s) => s.user);
  const drafts = useWorkspaceStore((s) => s.drafts);
  const [filter, setFilter] = useState("all");
  const [error, setError] = useState("");
  const [busyId, setBusyId] = useState("");
  const ownDrafts = drafts.filter((d) => d.ownerId === user?.id);
  const results = ownDrafts
    .filter(
      (d) =>
        filter === "all" ||
        (filter === "draft"
          ? d.status === "draft" || d.status === "prepared"
          : d.status.startsWith("demo_")),
    )
    .slice()
    .reverse();
  async function advance(draft: SupportDraft) {
    setBusyId(draft.id);
    setError("");
    try {
      if (!demo) return;
      await getServices().support.save({
        ...draft,
        status:
          draft.status === "demo_submitted" ? "demo_reviewing" : "demo_closed",
      });
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusyId("");
    }
  }
  return (
    <div className="support-page stack">
      <PageHeader
        title="Những lời bạn đang chuẩn bị"
        description={
          demo
            ? "Bản nháp và các bước mô phỏng được giữ trong trình duyệt demo này."
            : "Các bản nháp đã lưu được giữ trong tài khoản của bạn."
        }
        back="/support"
        action={<LinkButton to="/support/prepare">Soạn lời mới</LinkButton>}
      />
      <Notice>
        {demo
          ? "Chưa gửi thật. Các mốc “đang xem xét” và “kết thúc” bên dưới chỉ do bạn bấm thử; không phản ánh phản hồi từ trường hay người hỗ trợ."
          : "Lưu và chuẩn bị lời nhắn chưa gửi nội dung tới trường hay người hỗ trợ. Bạn vẫn có thể mở lại, sao chép và tải bản nháp."}
      </Notice>
      <div className="segmented" aria-label="Lọc lời nhắn">
        {[
          ["all", "Tất cả"],
          ["draft", "Bản nháp"],
          ...(demo ? [["demo", "Báo cáo demo"]] : []),
        ].map(([key, label]) => (
          <button
            key={key}
            aria-pressed={filter === key}
            onClick={() => setFilter(key)}
          >
            {label}
          </button>
        ))}
      </div>
      {error && (
        <Notice tone="error">
          {error} Bạn có thể bấm lại bước mô phỏng để thử lại.
        </Notice>
      )}
      {results.length ? (
        results.map((draft) => {
          const steps = [
            "Đã lưu mô phỏng · chưa gửi",
            "Đang xem xét · giả lập",
            "Kết thúc · giả lập",
          ];
          const progress =
            draft.status === "demo_closed"
              ? 2
              : draft.status === "demo_reviewing"
                ? 1
                : 0;
          return (
            <article className="support-request" key={draft.id}>
              <div className="support-request-heading">
                <div>
                  <Badge tone={draft.status === "draft" ? "green" : "peach"}>
                    {statusLabels[draft.status]}
                  </Badge>
                  <h2>Lời nhắn tới {draft.recipientType.toLowerCase()}</h2>
                  <p>
                    {prettyDate(draft.createdAt)} ·{" "}
                    {draft.identityMode === "alias"
                      ? "Dùng bí danh"
                      : demo
                        ? "Tên hiển thị demo"
                        : "Tên hiển thị"}
                  </p>
                </div>
                <LinkButton
                  variant="secondary"
                  to={`/support/prepare?draftId=${draft.id}`}
                >
                  Mở & chỉnh sửa
                </LinkButton>
              </div>
              <p className="support-request-excerpt">
                {draft.content.slice(0, 180)}
                {draft.content.length > 180 ? "…" : ""}
              </p>
              {demo && draft.status.startsWith("demo_") && (
                <>
                  <ol
                    className="support-status-timeline"
                    aria-label="Tiến trình mô phỏng"
                  >
                    {steps.map((step, i) => (
                      <li
                        key={step}
                        className={i <= progress ? "complete" : ""}
                      >
                        <span>
                          {i <= progress ? <Check size={14} /> : i + 1}
                        </span>
                        <div>
                          <strong>{step}</strong>
                          <small>
                            {i <= progress
                              ? "Đã bấm thử trong demo"
                              : "Chưa mô phỏng"}
                          </small>
                        </div>
                      </li>
                    ))}
                  </ol>
                  {draft.status !== "demo_closed" && (
                    <Button
                      variant="secondary"
                      disabled={!!busyId}
                      onClick={() => advance(draft)}
                    >
                      {busyId === draft.id
                        ? "Đang cập nhật…"
                        : draft.status === "demo_submitted"
                          ? "Mô phỏng bước xem xét"
                          : "Mô phỏng bước kết thúc"}
                    </Button>
                  )}
                  <p className="support-footnote">
                    Không có thời hạn xử lý hoặc thông báo thật. Dữ liệu này
                    không được đưa vào School Admin Demo.
                  </p>
                </>
              )}
            </article>
          );
        })
      ) : (
        <EmptyState
          title={
            filter === "demo"
              ? "Chưa có báo cáo mô phỏng"
              : "Bạn chưa lưu lời nhắn nào ở đây"
          }
          description="Bạn có thể chuẩn bị một câu mở lời rồi lưu lại. Không cần gửi ngay."
          action={
            <LinkButton to="/support/prepare">
              Viết lời nhắn đầu tiên
            </LinkButton>
          }
        />
      )}
    </div>
  );
}

export function UrgentPage() {
  const source = knowledgeSources.find((s) => s.id === "VN-111")!;
  return (
    <main className="support-urgent-page stack">
      <Link className="support-urgent-brand" to="/support">
        <span>
          <LifeBuoy size={22} />
        </span>
        MoodPrint
      </Link>
      <header>
        <Badge tone="peach">Hỗ trợ ngay</Badge>
        <h1>
          Điều cần nhất lúc này
          <br />
          là bạn được an toàn.
        </h1>
        <p>
          Nếu nguy cơ đang diễn ra, bạn không cần tiếp tục kể chuyện trong ứng
          dụng.
        </p>
      </header>
      <ol className="support-urgent-steps">
        <li>
          <span>1</span>
          <div>
            <h2>Tìm nơi an toàn</h2>
            <p>
              Nếu có thể rời đi an toàn, đến nơi có người lớn hoặc người có thể
              giúp. Đừng đi gặp riêng người đang đe dọa.
            </p>
          </div>
        </li>
        <li>
          <span>2</span>
          <div>
            <h2>Nhờ một người ở gần</h2>
            <p>
              Giáo viên, người chăm sóc hoặc người lớn bạn tin. Có thể chỉ nói:
              “Em đang không an toàn. Em cần người ở cùng.”
            </p>
          </div>
        </li>
        <li>
          <span>3</span>
          <div>
            <h2>Liên hệ hỗ trợ trực tiếp</h2>
            <p>
              Tại Việt Nam, Tổng đài bảo vệ trẻ em <strong>111</strong> hoạt
              động <strong>24/24, miễn phí</strong>. Nếu có nguy hiểm tức thời
              hoặc cần cấp cứu, nhờ người lớn liên hệ dịch vụ khẩn cấp phù hợp
              tại nơi bạn đang ở.
            </p>
          </div>
        </li>
      </ol>
      <a href="tel:111" className="button primary support-call">
        <Phone size={22} />
        Gọi 111<span>Mở chức năng gọi của thiết bị</span>
      </a>
      <a
        className="support-official-link"
        href={source.url}
        target="_blank"
        rel="noreferrer"
      >
        Xem thông tin chính thức của Tổng đài 111
        <ExternalLink size={16} />
      </a>
      <div className="support-urgent-note">
        <ShieldCheck size={19} />
        <p>
          Bạn tự quyết định bấm gọi. MoodPrint không tự gọi, định vị, điều phối
          hay thông báo cho ai. Không cần đăng nhập hoặc hoàn thành hồ sơ để xem
          trang này.
        </p>
      </div>
      <small className="muted">
        Nguồn: Tổng đài Quốc gia bảo vệ trẻ em · kiểm tra 07/11/2026.
      </small>
      <div className="actions">
        <LinkButton to="/support" variant="secondary">
          Về Support
        </LinkButton>
        <LinkButton to="/ai/chat" variant="ghost">
          Quay lại trò chuyện
        </LinkButton>
      </div>
    </main>
  );
}
