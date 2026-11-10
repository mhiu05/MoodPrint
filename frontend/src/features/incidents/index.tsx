import { useState } from "react";
import {
  Link,
  NavLink,
  useLocation,
  useNavigate,
  useParams,
} from "react-router-dom";
import {
  ArrowRight,
  CalendarDays,
  Check,
  Copy,
  Download,
  FileText,
  FolderOpen,
  Pencil,
  Plus,
  Search,
  Trash2,
} from "lucide-react";
import { uid, useDemoStore } from "../../app/store";
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
  SectionHeading,
} from "../../components/ui";
import { copyText, downloadText, formatDate, normalize } from "../../lib/utils";
import { getServices } from "../../services/composition";
import { asLive } from "../../services/composition/companion-types";
import { ApiError } from "../../services/http/client";
import type { Evidence, Incident, TimelineEvent } from "../../types";
import {
  caseSummary,
  eventTime,
  provenanceLabels,
  statusLabels,
  templates,
  mergeCaseEdits,
} from "./model";
import { EvidencePicker } from "./evidence";
import "./incidents.css";
export { CaseWizard } from "./wizard";

export function CaseList() {
  const user = useDemoStore((s) => s.user);
  const real = useDemoStore((s) => s.workspace.kind === "real");
  const allCases = useDemoStore((s) => s.cases);
  const plans = useDemoStore((s) => s.plans);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("all");
  const [order, setOrder] = useState("updated");
  const mine = allCases.filter((c) => c.ownerId === user?.id);
  const filtered = mine
    .filter(
      (c) =>
        (status === "all" || c.status === status) &&
        normalize(
          `${c.title} ${c.summary} ${c.categoryTags.join(" ")}`,
        ).includes(normalize(search)),
    )
    .sort((a, b) =>
      order === "title"
        ? a.title.localeCompare(b.title, "vi")
        : b.updatedAt.localeCompare(a.updatedAt),
    );
  const recoverableDrafts = (() => {
    const prefix = `moodprint-case-draft-v1:${user?.id}:`;
    const drafts: { identity: string; title: string }[] = [];
    try {
      for (let index = 0; index < sessionStorage.length; index++) {
        const key = sessionStorage.key(index);
        if (!key?.startsWith(`${prefix}new`)) continue;
        const draft = JSON.parse(sessionStorage.getItem(key) || "{}") as {
          title?: string;
          summary?: string;
          attachments?: unknown[];
        };
        if (draft.title || draft.summary || draft.attachments?.length)
          drafts.push({
            identity: key.slice(prefix.length),
            title: draft.title || "Phần đang viết",
          });
      }
    } catch {
      /* Keep the list usable if browser storage is unavailable. */
    }
    return drafts;
  })();
  return (
    <div className="case-list-page">
      <PageHeader
        title="Hồ sơ của bạn"
        description="Giữ lại điều bạn muốn nhớ. Bổ sung khi bạn thấy sẵn sàng."
        action={
          <LinkButton to="/cases/new">
            <Plus size={18} />
            Ghi lại sự việc
          </LinkButton>
        }
      />
      {recoverableDrafts.length > 0 && (
        <Notice>
          Bạn còn {recoverableDrafts.length} phần đang viết dở.
          <div className="actions">
            {recoverableDrafts.map((draft) => (
              <Link
                className="chip"
                key={draft.identity}
                to={
                  draft.identity === "new"
                    ? "/cases/new"
                    : `/cases/new?${new URLSearchParams({ draft: draft.identity })}`
                }
              >
                {draft.identity === "new"
                  ? "Tiếp tục bản nháp"
                  : `Tiếp tục: ${draft.title}`}
              </Link>
            ))}
          </div>
        </Notice>
      )}
      <div className="case-intro">
        <FolderOpen size={28} />
        <div>
          <strong>
            {mine.length} hồ sơ cá nhân{real ? "" : " trong demo"}
          </strong>
          <p>
            Nội dung do bạn ghi lại, chưa được kiểm chứng độc lập. Bạn luôn có
            thể sửa hoặc bổ sung.
          </p>
        </div>
      </div>
      <div className="case-toolbar">
        <div className="case-search">
          <Search size={18} />
          <input
            aria-label="Tìm hồ sơ"
            placeholder="Tìm theo tên hoặc nội dung…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <select
          aria-label="Sắp xếp hồ sơ"
          value={order}
          onChange={(e) => setOrder(e.target.value)}
        >
          <option value="updated">Cập nhật mới nhất</option>
          <option value="title">Tên A–Z</option>
        </select>
      </div>
      <div className="chips case-status-filters" aria-label="Lọc trạng thái">
        {[["all", "Tất cả"], ...Object.entries(statusLabels)].map(
          ([value, label]) => (
            <button
              className="chip"
              key={value}
              aria-pressed={value === status}
              onClick={() => setStatus(value)}
            >
              {label}
              <span>
                {value === "all"
                  ? mine.length
                  : mine.filter((c) => c.status === value).length}
              </span>
            </button>
          ),
        )}
      </div>
      <p className="muted" aria-live="polite">
        {filtered.length} hồ sơ{search ? ` khớp với “${search}”` : ""}
      </p>
      {!filtered.length ? (
        <EmptyState
          title={
            mine.length
              ? "Chưa tìm thấy hồ sơ phù hợp"
              : "Mỗi câu chuyện có thể bắt đầu từ một dòng"
          }
          description={
            mine.length
              ? "Thử từ khóa ngắn hơn hoặc bỏ bộ lọc trạng thái."
              : "Bạn có thể viết ngắn, chọn mẫu hoặc kể cùng AI demo."
          }
          action={
            mine.length ? (
              <Button
                variant="secondary"
                onClick={() => {
                  setSearch("");
                  setStatus("all");
                }}
              >
                Bỏ bộ lọc
              </Button>
            ) : (
              <LinkButton to="/cases/new">Tạo hồ sơ đầu tiên</LinkButton>
            )
          }
        />
      ) : (
        <div className="case-cards">
          {filtered.map((item) => {
            const plan = plans.find((p) => p.caseId === item.id);
            return (
              <article className="panel case-card" key={item.id}>
                <div className="heading-row">
                  <Badge
                    tone={
                      item.status === "draft"
                        ? "gray"
                        : item.status === "closed"
                          ? "gray"
                          : "green"
                    }
                  >
                    {statusLabels[item.status]}
                  </Badge>
                  <span className="case-updated">
                    {formatDate(item.updatedAt)}
                  </span>
                </div>
                <h2>
                  <Link to={`/cases/${item.id}`}>{item.title}</Link>
                </h2>
                <p className="case-excerpt">
                  {item.summary || "Bản nháp đang chờ bạn bổ sung."}
                </p>
                <div className="chips">
                  {item.categoryTags.map((tag) => (
                    <span className="chip" key={tag}>
                      {tag}
                    </span>
                  ))}
                </div>
                <div className="case-card-meta">
                  <span>
                    <CalendarDays size={16} />
                    {item.events.length} mốc
                  </span>
                  <span>
                    <FileText size={16} />
                    {item.evidenceIds.length} nguồn
                  </span>
                </div>
                {plan && (
                  <div className="case-plan-preview">
                    <div>
                      <span>Kế hoạch ứng phó</span>
                      <strong>
                        {plan.items.filter((i) => i.status === "done").length}/
                        {plan.items.length}
                      </strong>
                    </div>
                    <Progress
                      value={
                        plan.items.filter((i) => i.status === "done").length
                      }
                      max={plan.items.length}
                    />
                  </div>
                )}
                <Link className="case-open" to={`/cases/${item.id}`}>
                  Mở hồ sơ
                  <ArrowRight size={17} />
                </Link>
              </article>
            );
          })}
        </div>
      )}
      <div className="case-ai-footer">
        <div>
          <strong>Chưa biết bắt đầu kể từ đâu?</strong>
          <p>
            {real
              ? "AI mô phỏng dùng hội thoại mẫu để bạn thử cách sắp xếp câu chuyện."
              : "AI demo có thể gợi câu hỏi để bạn sắp xếp lại câu chuyện."}
          </p>
        </div>
        <LinkButton to="/ai/chat" variant="secondary">
          {real ? "Thử AI mô phỏng" : "Kể cùng AI demo"}
          <ArrowRight size={17} />
        </LinkButton>
      </div>
    </div>
  );
}

export function CaseDetail() {
  const { caseId } = useParams();
  const location = useLocation();
  const navigate = useNavigate();
  const real = useDemoStore((s) => s.workspace.kind === "real");
  const item = useDemoStore((s) =>
    s.cases.find((c) => c.id === caseId && c.ownerId === s.user?.id),
  );
  const allEvidence = useDemoStore((s) => s.evidence);
  const cases = useDemoStore((s) => s.cases);
  const plan = useDemoStore((s) => s.plans.find((p) => p.caseId === caseId));
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [event, setEvent] = useState<TimelineEvent | null>(null);
  const [attachmentOpen, setAttachmentOpen] = useState(false);
  const [attachments, setAttachments] = useState<Evidence[]>([]);
  const [sourceFilter, setSourceFilter] = useState("all");
  const [dateFilter, setDateFilter] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [retry, setRetry] = useState<(() => Promise<void>) | null>(null);
  const [eventError, setEventError] = useState("");
  const section = location.pathname.endsWith("/timeline")
    ? "timeline"
    : location.pathname.endsWith("/evidence")
      ? "evidence"
      : location.pathname.endsWith("/summary")
        ? "summary"
        : "overview";
  if (!item)
    return (
      <>
        <PageHeader title="Không tìm thấy hồ sơ" back="/cases" />
        <EmptyState
          title={
            real
              ? "Không tìm thấy hồ sơ trong tài khoản của bạn"
              : "Hồ sơ này chưa có ở tài khoản demo của bạn"
          }
          description="Có thể hồ sơ đã được xóa. Bạn có thể mở lại danh sách hoặc tạo một hồ sơ mới."
          action={<LinkButton to="/cases">Về danh sách hồ sơ</LinkButton>}
        />
      </>
    );
  const evidence = allEvidence.filter(
    (e) =>
      item.evidenceIds.includes(e.id) && (!real || e.origin !== "mock_fixture"),
  );
  const persist = async (
    next: Incident,
    after?: () => void | Promise<void>,
  ) => {
    setSaving(true);
    setError("");
    try {
      await getServices().cases.save({
        ...next,
        updatedAt: new Date().toISOString(),
      });
      setRetry(null);
      await after?.();
      useDemoStore
        .getState()
        .notify(real ? "Đã cập nhật hồ sơ." : "Đã cập nhật hồ sơ demo.");
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : "Chưa lưu được. Hãy thử lại.",
      );
      if (cause instanceof ApiError && cause.code === "version_conflict") {
        setRetry(() => async () => {
          try {
            const latest = await getServices().cases.get(next.id);
            await persist(mergeCaseEdits(item, next, latest), after);
          } catch (failure) {
            setError(
              failure instanceof Error
                ? failure.message
                : "Chưa tải được phiên bản mới.",
            );
          }
        });
      } else setRetry(() => () => persist(next, after));
    } finally {
      setSaving(false);
    }
  };
  const saveEvent = () => {
    if (!event) return;
    if (
      !event.description.trim() ||
      (event.timePrecision !== "unknown" && !event.when)
    ) {
      setEventError(
        "Hãy ghi nội dung và thời điểm, hoặc chọn “Không nhớ chính xác”.",
      );
      return;
    }
    const nextEvent = {
      ...event,
      description: event.description.trim(),
      when: event.timePrecision === "unknown" ? "" : event.when,
    };
    const events = item.events.some((e) => e.id === event.id)
      ? item.events.map((e) => (e.id === event.id ? nextEvent : e))
      : [...item.events, nextEvent];
    void persist({ ...item, events }, () => {
      setEvent(null);
      setEventError("");
    });
  };
  const attach = () => {
    if (!attachments.length) return;
    void persist(
      {
        ...item,
        evidenceIds: [...item.evidenceIds, ...attachments.map((e) => e.id)],
      },
      async () => {
        if (!real)
          for (const e of attachments)
            await getServices().evidence.save({ ...e, caseId: item.id });
        setAttachments([]);
        setAttachmentOpen(false);
      },
    );
  };
  const filteredEvents = item.events
    .filter(
      (e) =>
        (sourceFilter === "all" || e.provenance === sourceFilter) &&
        (!dateFilter || e.when.startsWith(dateFilter)),
    )
    .slice()
    .sort((a, b) =>
      !a.when ? 1 : !b.when ? -1 : a.when.localeCompare(b.when),
    );
  const base = `/cases/${item.id}`;
  const summary = caseSummary(item, evidence);
  const related = cases
    .filter((c) => c.ownerId === item.ownerId && c.id !== item.id)
    .slice(0, 3);
  return (
    <div className="case-detail-page">
      <PageHeader
        title={item.title}
        description={`Cập nhật ${formatDate(item.updatedAt)} · ${item.perspective === "witness" ? "Góc nhìn người chứng kiến" : "Điều mình trải qua"}`}
        back="/cases"
        action={
          <div className="actions">
            <LinkButton to={`${base}/edit`} variant="secondary">
              <Pencil size={17} />
              Bổ sung hồ sơ
            </LinkButton>
            <LinkButton to={`/ai/chat?caseId=${item.id}`} variant="secondary">
              Trao đổi về hồ sơ
            </LinkButton>
            <LinkButton
              to={`/ai/roleplay?caseId=${item.id}`}
              variant="secondary"
            >
              Luyện cách trình bày
            </LinkButton>
          </div>
        }
      />
      <div className="case-heading-tools">
        <Badge
          tone={
            item.status === "draft" || item.status === "closed"
              ? "gray"
              : "green"
          }
        >
          {statusLabels[item.status]}
        </Badge>
        <label htmlFor="case-status">Trạng thái do bạn đặt</label>
        <select
          id="case-status"
          value={item.status}
          disabled={saving}
          onChange={(e) =>
            void persist({
              ...item,
              status: e.target.value as Incident["status"],
            })
          }
        >
          {Object.entries(statusLabels).map(([value, label]) => (
            <option value={value} key={value}>
              {label}
            </option>
          ))}
        </select>
      </div>
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
      {error && (
        <Notice tone="error">
          {error}
          <Button
            variant="secondary"
            disabled={saving}
            onClick={() => void retry?.()}
          >
            Thử lại
          </Button>
        </Notice>
      )}
      {section === "overview" && (
        <div className="case-detail-columns">
          <div className="stack">
            <section className="panel case-story">
              <SectionHeading title="Điều bạn đã ghi lại" />
              <p className="preserve-lines">
                {item.summary ||
                  "Bạn chưa viết mô tả. Có thể bổ sung khi thấy sẵn sàng."}
              </p>
              <div className="chips">
                {item.categoryTags.map((tag) => (
                  <span className="chip" key={tag}>
                    {tag}
                  </span>
                ))}
              </div>
              <dl className="case-facts">
                <div>
                  <dt>Thời gian</dt>
                  <dd>
                    {item.events[0]
                      ? eventTime(item.events[0])
                      : "Chưa rõ thời gian"}
                  </dd>
                </div>
                <div>
                  <dt>Địa điểm</dt>
                  <dd>{item.place || "Chưa bổ sung"}</dd>
                </div>
                <div>
                  <dt>Người liên quan</dt>
                  <dd>{item.people || "Chưa bổ sung"}</dd>
                </div>
                <div>
                  <dt>Mẫu đã chọn</dt>
                  <dd>
                    {templates.find((t) => t.id === item.template)?.label ??
                      item.template}
                  </dd>
                </div>
              </dl>
            </section>
            <section className="panel">
              <SectionHeading title="Ảnh hưởng và điều đã thử" />
              <div className="chips">
                {item.impactTags.length ? (
                  item.impactTags.map((tag) => (
                    <span className="chip" key={tag}>
                      {tag}
                    </span>
                  ))
                ) : (
                  <span className="muted">Chưa chia sẻ ảnh hưởng</span>
                )}
              </div>
              <h3>Điều bạn đã thử</h3>
              <p className="preserve-lines">
                {item.tried || "Bạn có thể bổ sung sau."}
              </p>
              <h3>Người có thể hỗ trợ</h3>
              <p>
                {item.trustedPerson ||
                  "Chưa chọn. Bạn có thể bắt đầu bằng một người lớn mình tin tưởng."}
              </p>
            </section>
            <section className="panel">
              <SectionHeading
                title="Diễn biến gần đây"
                to={`${base}/timeline`}
                label="Mở dòng thời gian"
              />
              {item.events.slice(-2).map((e) => (
                <div className="case-event-preview" key={e.id}>
                  <CalendarDays size={19} />
                  <div>
                    <strong>{eventTime(e)}</strong>
                    <p>{e.description}</p>
                    <Badge
                      tone={
                        e.provenance === "mock_extracted" ? "amber" : "gray"
                      }
                    >
                      {provenanceLabels[e.provenance]}
                    </Badge>
                  </div>
                </div>
              ))}
              {!item.events.length && (
                <p>Chưa có mốc. Thêm một điều bạn nhớ khi thấy sẵn sàng.</p>
              )}
              <LinkButton to={`${base}/timeline`} variant="secondary">
                <Plus size={17} />
                Bổ sung diễn biến
              </LinkButton>
            </section>
          </div>
          <aside className="stack">
            <section className="panel case-next-step">
              <h2>Một bước tiếp theo</h2>
              {plan ? (
                <>
                  <p>{plan.goal}</p>
                  <Progress
                    value={plan.items.filter((i) => i.status === "done").length}
                    max={plan.items.length}
                  />
                  <p className="muted">
                    Bạn đã tự ghi hoàn tất{" "}
                    {plan.items.filter((i) => i.status === "done").length}/
                    {plan.items.length} bước.
                  </p>
                </>
              ) : (
                <p>
                  Bạn có thể chọn một bước nhỏ phù hợp với mình, hoặc tạm dừng ở
                  đây.
                </p>
              )}
              <LinkButton to={`${base}/plan`}>
                {plan ? "Tiếp tục kế hoạch" : "Chuẩn bị kế hoạch"}
                <ArrowRight size={17} />
              </LinkButton>
            </section>
            <Notice>
              Hồ sơ là điều bạn ghi lại. Trạng thái “Đã khép lại” do bạn chọn,
              không có nghĩa nhà trường đã xử lý.
            </Notice>
            <LinkButton to={`${base}/summary`} variant="secondary">
              <FileText size={18} />
              Chuẩn bị bản tóm tắt
            </LinkButton>
            <Link to="/support/urgent">Cần người hỗ trợ ngay?</Link>
          </aside>
        </div>
      )}
      {section === "timeline" && (
        <section className="panel">
          <div className="section-heading">
            <div>
              <h2>Dòng thời gian</h2>
              <p className="muted">
                Các mốc có nguồn riêng. Chưa rõ thời gian vẫn có thể ghi lại.
              </p>
            </div>
            <Button
              onClick={() => {
                setEventError("");
                setEvent({
                  id: uid("EVENT"),
                  caseId: item.id,
                  when: "",
                  timePrecision: "unknown",
                  place: "",
                  description: "",
                  provenance: "user_entered",
                  evidenceIds: [],
                  needsReview: false,
                });
              }}
            >
              <Plus size={17} />
              Thêm mốc
            </Button>
          </div>
          <div className="case-timeline-filters">
            <Field label="Lọc nguồn" id="timeline-source">
              <select
                id="timeline-source"
                value={sourceFilter}
                onChange={(e) => setSourceFilter(e.target.value)}
              >
                <option value="all">Tất cả nguồn</option>
                {Object.entries(provenanceLabels).map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </Field>
            <Field
              label="Lọc ngày"
              type="date"
              value={dateFilter}
              onChange={(e) => setDateFilter(e.target.value)}
            />
            {(sourceFilter !== "all" || dateFilter) && (
              <Button
                variant="ghost"
                onClick={() => {
                  setSourceFilter("all");
                  setDateFilter("");
                }}
              >
                Bỏ bộ lọc
              </Button>
            )}
          </div>
          {!filteredEvents.length ? (
            <EmptyState
              title="Chưa có mốc phù hợp"
              description="Thêm một diễn biến mới hoặc bỏ bộ lọc để xem lại."
            />
          ) : (
            <ol className="case-timeline">
              {filteredEvents.map((e) => (
                <li key={e.id}>
                  <span className="timeline-dot" />
                  <div>
                    <div className="heading-row">
                      <strong>{eventTime(e)}</strong>
                      <Button
                        variant="ghost"
                        onClick={() => {
                          setEventError("");
                          setEvent({ ...e });
                        }}
                        aria-label={`Sửa mốc ${e.description.slice(0, 35)}`}
                      >
                        <Pencil size={17} />
                        Sửa
                      </Button>
                    </div>
                    <div className="chips">
                      <Badge
                        tone={
                          e.provenance === "mock_extracted" ? "amber" : "gray"
                        }
                      >
                        {provenanceLabels[e.provenance]}
                      </Badge>
                      {e.needsReview && (
                        <Badge tone="amber">Cần kiểm tra</Badge>
                      )}
                    </div>
                    <p className="preserve-lines">{e.description}</p>
                    <p className="muted">{e.place || "Chưa ghi địa điểm"}</p>
                    {e.evidenceIds.length > 0 && (
                      <div className="chips">
                        {e.evidenceIds.map((id) => (
                          <Link
                            key={id}
                            to={`${base}/evidence#${id}`}
                            className="chip"
                          >
                            <FileText size={15} />
                            Nguồn {id.slice(-8)}
                          </Link>
                        ))}
                      </div>
                    )}
                  </div>
                </li>
              ))}
            </ol>
          )}
        </section>
      )}
      {section === "evidence" && (
        <section className="panel">
          <div className="section-heading">
            <div>
              <h2>Nguồn đính kèm</h2>
              <p className="muted">
                {real
                  ? "Tệp gốc và ghi chú được lưu riêng tư; bạn có thể kiểm tra và sửa phần ghi chú riêng."
                  : "Tệp và ghi chú mẫu để giữ ngữ cảnh, chưa phải thông tin đã xác minh."}
              </p>
            </div>
            <Button onClick={() => setAttachmentOpen(true)}>
              <Plus size={17} />
              {real ? "Thêm nguồn" : "Thêm nguồn mẫu"}
            </Button>
          </div>
          {!evidence.length ? (
            <EmptyState
              title="Hồ sơ vẫn có giá trị khi chưa có tệp"
              description={
                real
                  ? "Bạn có thể tải tệp hoặc lưu ghi chú bất cứ lúc nào."
                  : "Bạn có thể thêm ảnh mẫu, ghi chú hoặc PDF minh họa bất cứ lúc nào."
              }
            />
          ) : (
            <div className="evidence-gallery">
              {evidence.map((e) => (
                <EvidenceCard
                  key={e.id}
                  item={e}
                  busy={saving}
                  onSave={async (next) => {
                    setSaving(true);
                    setError("");
                    try {
                      await getServices().evidence.save(next);
                      useDemoStore
                        .getState()
                        .notify("Đã cập nhật phần kiểm tra nguồn.");
                    } catch (cause) {
                      setError(
                        cause instanceof Error
                          ? cause.message
                          : "Chưa lưu được phần sửa.",
                      );
                      throw cause;
                    } finally {
                      setSaving(false);
                    }
                  }}
                  onDelete={
                    real
                      ? () => {
                          if (
                            window.confirm(
                              "Xóa vĩnh viễn bằng chứng gốc này? Thao tác không thể hoàn tác.",
                            )
                          ) {
                            setSaving(true);
                            setError("");
                            void getServices()
                              .evidence.remove(e.id)
                              .then(() => getServices().cases.get(item.id))
                              .catch((cause: unknown) =>
                                setError(
                                  cause instanceof Error
                                    ? cause.message
                                    : "Chưa xóa được nguồn.",
                                ),
                              )
                              .finally(() => setSaving(false));
                          }
                        }
                      : undefined
                  }
                  onRemove={() => {
                    if (
                      window.confirm(
                        "Bỏ nguồn này khỏi hồ sơ và các mốc liên quan?",
                      )
                    )
                      void persist({
                        ...item,
                        evidenceIds: item.evidenceIds.filter(
                          (id) => id !== e.id,
                        ),
                        events: item.events.map((event) => ({
                          ...event,
                          evidenceIds: event.evidenceIds.filter(
                            (id) => id !== e.id,
                          ),
                        })),
                      });
                  }}
                />
              ))}
            </div>
          )}
        </section>
      )}
      {section === "summary" && (
        <section className="panel">
          <SectionHeading title="Bản tóm tắt để bạn xem lại" />
          <Notice>
            Chưa gửi cho ai. Nội dung chưa rõ được tách riêng; đây không phải
            chứng cứ pháp lý hay kết luận về người khác.
          </Notice>
          <div className="actions summary-actions">
            <Button
              onClick={() =>
                void copyText(summary)
                  .then(() =>
                    useDemoStore.getState().notify("Đã sao chép bản tóm tắt."),
                  )
                  .catch(() =>
                    useDemoStore
                      .getState()
                      .notify(
                        "Chưa sao chép được. Bạn có thể chọn văn bản bên dưới hoặc tải tệp.",
                      ),
                  )
              }
            >
              <Copy size={17} />
              Sao chép
            </Button>
            <Button
              variant="secondary"
              onClick={() =>
                downloadText(
                  summary,
                  `moodprint-${item.id}${real ? "" : "-demo"}.txt`,
                )
              }
            >
              <Download size={17} />
              Tải bản văn bản
            </Button>
            <LinkButton
              variant="secondary"
              to={`/support/prepare?caseId=${item.id}`}
            >
              Chuẩn bị lời nhắn
              <ArrowRight size={17} />
            </LinkButton>
          </div>
          <pre className="case-summary-preview" tabIndex={0}>
            {summary}
          </pre>
        </section>
      )}
      {section === "overview" && related.length > 0 && (
        <section className="case-related">
          <SectionHeading title="Hồ sơ khác của bạn" />
          <div>
            {related.map((c) => (
              <Link to={`/cases/${c.id}`} className="list-row" key={c.id}>
                <span>{c.title}</span>
                <ArrowRight size={17} />
              </Link>
            ))}
          </div>
        </section>
      )}
      <div className="case-danger-zone">
        <Button variant="ghost" onClick={() => setDeleteOpen(true)}>
          <Trash2 size={16} />
          Xóa hồ sơ
        </Button>
      </div>
      <Modal
        open={deleteOpen}
        onClose={() => setDeleteOpen(false)}
        title="Xóa hồ sơ này?"
      >
        <p>
          Hồ sơ “{item.title}”, kế hoạch và nguồn gắn trực tiếp với hồ sơ sẽ bị
          {real ? "xóa khỏi tài khoản của bạn." : "xóa khỏi bản demo."} Thao tác
          này không thể hoàn tác.
        </p>
        <div className="actions">
          <Button variant="secondary" onClick={() => setDeleteOpen(false)}>
            Giữ hồ sơ
          </Button>
          <Button
            variant="danger"
            disabled={saving}
            onClick={() => {
              setSaving(true);
              setError("");
              void getServices()
                .cases.remove(item.id)
                .then(() => {
                  useDemoStore
                    .getState()
                    .notify(real ? "Đã xóa hồ sơ." : "Đã xóa hồ sơ demo.");
                  navigate("/cases", { replace: true });
                })
                .catch((cause: unknown) =>
                  setError(
                    cause instanceof Error
                      ? cause.message
                      : "Chưa xóa được hồ sơ.",
                  ),
                )
                .finally(() => setSaving(false));
            }}
          >
            Xóa hồ sơ
          </Button>
        </div>
      </Modal>
      <Modal
        open={!!event}
        onClose={() => {
          if (!saving) setEvent(null);
        }}
        title={
          event && item.events.some((e) => e.id === event.id)
            ? "Sửa mốc sự việc"
            : "Thêm mốc sự việc"
        }
      >
        {event && (
          <form
            className="stack"
            onSubmit={(e) => {
              e.preventDefault();
              saveEvent();
            }}
          >
            <Field label="Điều đã xảy ra" id="event-description">
              <textarea
                id="event-description"
                rows={4}
                value={event.description}
                onChange={(e) =>
                  setEvent({ ...event, description: e.target.value })
                }
              />
            </Field>
            <Field label="Độ chính xác của thời gian" id="event-precision">
              <select
                id="event-precision"
                value={event.timePrecision}
                onChange={(e) =>
                  setEvent({
                    ...event,
                    timePrecision: e.target
                      .value as TimelineEvent["timePrecision"],
                  })
                }
              >
                <option value="unknown">Không nhớ chính xác</option>
                <option value="day">Nhớ ngày</option>
                <option value="week">Nhớ khoảng tuần</option>
                <option value="exact">Nhớ ngày và giờ</option>
              </select>
            </Field>
            {event.timePrecision !== "unknown" && (
              <Field
                label="Thời điểm"
                type={
                  event.timePrecision === "exact" ? "datetime-local" : "date"
                }
                value={event.when}
                onChange={(e) => setEvent({ ...event, when: e.target.value })}
              />
            )}
            <Field
              label="Địa điểm / nền tảng"
              value={event.place}
              onChange={(e) => setEvent({ ...event, place: e.target.value })}
            />
            <Notice>
              Nguồn hiện tại: {provenanceLabels[event.provenance]}. Phần trích
              từ ảnh mẫu chỉ trở thành “Đã xác nhận lại” khi bạn chủ động kiểm
              tra.
            </Notice>
            <label className="case-checkbox">
              <input
                type="checkbox"
                checked={event.provenance === "user_confirmed"}
                onChange={(e) =>
                  setEvent({
                    ...event,
                    provenance: e.target.checked
                      ? "user_confirmed"
                      : item.events.find((old) => old.id === event.id)
                            ?.provenance === "mock_extracted"
                        ? "mock_extracted"
                        : "user_entered",
                    needsReview:
                      !e.target.checked &&
                      item.events.find((old) => old.id === event.id)
                        ?.provenance === "mock_extracted",
                  })
                }
              />
              Mình đã kiểm tra lại nội dung mốc này
            </label>
            {evidence.length > 0 && (
              <fieldset className="case-fieldset">
                <legend>Gắn nguồn cho mốc</legend>
                {evidence.map((e) => (
                  <label className="case-checkbox" key={e.id}>
                    <input
                      type="checkbox"
                      checked={event.evidenceIds.includes(e.id)}
                      onChange={() =>
                        setEvent({
                          ...event,
                          evidenceIds: event.evidenceIds.includes(e.id)
                            ? event.evidenceIds.filter((id) => id !== e.id)
                            : [...event.evidenceIds, e.id],
                        })
                      }
                    />
                    {e.kind === "screenshot" ? "Ảnh mẫu" : "Ghi chú"} ·{" "}
                    {e.id.slice(-8)}
                  </label>
                ))}
              </fieldset>
            )}
            {eventError && <Notice tone="error">{eventError}</Notice>}
            {error && <Notice tone="error">{error}</Notice>}
            <Button type="submit" disabled={saving}>
              {saving ? "Đang lưu…" : "Lưu mốc"}
            </Button>
          </form>
        )}
      </Modal>
      <Modal
        open={attachmentOpen}
        onClose={() => {
          if (!saving) setAttachmentOpen(false);
        }}
        title={real ? "Thêm nguồn đính kèm" : "Thêm nguồn minh họa"}
      >
        <EvidencePicker items={attachments} onChange={setAttachments} />
        {error && <Notice tone="error">{error}</Notice>}
        <div className="actions">
          <Button onClick={attach} disabled={saving || !attachments.length}>
            {saving
              ? "Đang lưu…"
              : `Thêm ${attachments.length} nguồn vào hồ sơ`}
          </Button>
        </div>
      </Modal>
    </div>
  );
}

function EvidenceCard({
  item,
  busy,
  onSave,
  onRemove,
  onDelete,
}: {
  item: Evidence;
  busy: boolean;
  onSave: (item: Evidence) => void | Promise<void>;
  onRemove: () => void;
  onDelete?: () => void;
}) {
  const [edit, setEdit] = useState(false);
  const [text, setText] = useState(
    item.userEditedText ?? (item.extractedText || item.originalText),
  );
  const [failure, setFailure] = useState("");
  const [downloading, setDownloading] = useState(false);
  const save = async (next: Evidence) => {
    setFailure("");
    try {
      await onSave(next);
      setEdit(false);
    } catch (cause) {
      setFailure(
        cause instanceof Error
          ? cause.message
          : "Chưa lưu được. Nội dung sửa vẫn được giữ.",
      );
    }
  };
  const download = async () => {
    setDownloading(true);
    setFailure("");
    try {
      const signed = await getServices().evidence.getDownloadUrl(item.id);
      const link = document.createElement("a");
      link.href = signed.url;
      link.download = item.originalFilename ?? "evidence";
      link.rel = "noopener";
      document.body.append(link);
      link.click();
      link.remove();
    } catch (cause) {
      setFailure(
        cause instanceof Error
          ? cause.message
          : "Chưa tải được tệp. Vui lòng thử lại.",
      );
    } finally {
      setDownloading(false);
    }
  };
  return (
    <article className="evidence-card" id={item.id}>
      <div className="heading-row">
        <Badge tone={item.origin === "mock_fixture" ? "amber" : "gray"}>
          {item.origin === "mock_fixture"
            ? "Nguồn mẫu giả lập"
            : item.origin === "user_upload"
              ? "Tệp riêng tư"
              : "Mình nhập"}
        </Badge>
        <Button
          variant="ghost"
          aria-label={`Bỏ nguồn ${item.id}`}
          disabled={busy}
          onClick={onRemove}
        >
          <Trash2 size={17} />
        </Button>
      </div>
      {item.kind === "screenshot" &&
        (item.assetPath ? (
          <img
            className="evidence-image"
            src={item.assetPath}
            alt="Ảnh tin nhắn giả lập, không phải hội thoại thật"
          />
        ) : (
          <div className="mock-chat-screenshot">
            <span>ĐOẠN CHAT MẪU · DEMO</span>
            <p>Đừng cho bạn ấy vào nhóm.</p>
            <small>Tài khoản giả · Chưa rõ ngữ cảnh</small>
          </div>
        ))}
      <h3>
        {item.origin === "user_upload"
          ? (item.originalFilename ?? "Tệp đính kèm")
          : item.kind === "screenshot"
            ? "Ảnh chụp mẫu"
            : item.kind === "pdf_placeholder"
              ? "PDF minh họa (placeholder)"
              : "Ghi chú"}
      </h3>
      <p className="muted">
        {item.id} · Mốc hiển thị: {item.shownTimestamp || "Chưa rõ"}
      </p>
      {item.origin === "user_upload" && (
        <>
          <p className="muted">
            {item.byteSize?.toLocaleString("vi-VN")} bytes ·{" "}
            {item.storedMimeType ?? "Chưa rõ định dạng"}
          </p>
          <Notice>
            Tệp gốc được lưu riêng tư. Kết quả AI và phần bạn chỉnh không thay
            thế bản gốc.
          </Notice>
          <Button
            variant="secondary"
            disabled={downloading}
            onClick={() => void download()}
          >
            <Download size={16} />
            {downloading ? "Đang chuẩn bị…" : "Tải tệp gốc"}
          </Button>
          {asLive(getServices().companion) &&
            ["image/png", "image/jpeg", "image/webp"].includes(
              item.storedMimeType ?? "",
            ) && (
              <Link
                className="button secondary"
                to={`/ai/analysis/new?${new URLSearchParams({ evidenceId: item.id, ...(item.caseId ? { caseId: item.caseId } : {}) })}`}
              >
                Xem và phân tích ảnh bằng AI
              </Link>
            )}
        </>
      )}
      {failure && <Notice tone="error">{failure}</Notice>}
      {edit ? (
        <Field label="Sửa phần nội dung bạn đọc được" id={`edit-${item.id}`}>
          <textarea
            id={`edit-${item.id}`}
            rows={4}
            value={text}
            onChange={(e) => setText(e.target.value)}
          />
        </Field>
      ) : (
        <p className="preserve-lines">
          {item.userEditedText ?? (item.extractedText || item.originalText)}
        </p>
      )}
      <details>
        <summary>Xem nội dung gốc và giới hạn</summary>
        <p className="preserve-lines">{item.originalText}</p>
        <ul>
          {item.limitations.map((limit) => (
            <li key={limit}>{limit}</li>
          ))}
        </ul>
      </details>
      <div className="chips">
        <Badge tone={item.reviewStatus === "confirmed" ? "green" : "amber"}>
          {
            {
              unreviewed: "Chưa kiểm tra",
              corrected: "Đã sửa, cần xác nhận",
              confirmed: "Bạn đã xác nhận",
              rejected: "Đã loại khỏi xác nhận",
            }[item.reviewStatus]
          }
        </Badge>
      </div>
      <div className="actions">
        {edit ? (
          <>
            <Button
              onClick={() => {
                void save({
                  ...item,
                  userEditedText: text,
                  reviewStatus: "corrected",
                });
              }}
              disabled={!text.trim()}
            >
              Lưu phần sửa
            </Button>
            <Button
              variant="ghost"
              onClick={() => {
                setText(
                  item.userEditedText ??
                    (item.extractedText || item.originalText),
                );
                setEdit(false);
              }}
            >
              Hủy sửa
            </Button>
          </>
        ) : (
          <Button variant="secondary" onClick={() => setEdit(true)}>
            <Pencil size={16} />
            Sửa nội dung đọc được
          </Button>
        )}
        {!edit && item.reviewStatus !== "confirmed" && (
          <Button
            variant="secondary"
            onClick={() => void save({ ...item, reviewStatus: "confirmed" })}
          >
            <Check size={16} />
            Mình đã kiểm tra
          </Button>
        )}
        {!edit && item.reviewStatus !== "rejected" && (
          <Button
            variant="ghost"
            onClick={() => void save({ ...item, reviewStatus: "rejected" })}
          >
            Đánh dấu chưa dùng
          </Button>
        )}
      </div>
      {onDelete && (
        <Button variant="ghost" disabled={busy} onClick={onDelete}>
          Xóa vĩnh viễn bằng chứng
        </Button>
      )}
    </article>
  );
}
