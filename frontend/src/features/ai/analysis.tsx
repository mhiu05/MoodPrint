import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ArrowRight, Check, CircleHelp, RotateCcw, Trash2 } from "lucide-react";
import { uid, useWorkspaceStore } from "../../app/store";
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
import { getServices } from "../../services/composition";
import { asLive } from "../../services/composition/companion-types";
import { LiveAnalysisPage } from "./live/live-analysis";
import type { Analysis, Evidence, Incident } from "../../types";
import {
  analysisVariants,
  buildConfirmedTimeline,
  correctEvidence,
} from "./analysis-model";
import { startFixtureAnalysis } from "./analysis-workflow";
const labelTime = (value: string) =>
  value.includes("T")
    ? new Date(value).toLocaleString("vi-VN", {
        timeZone: "Asia/Bangkok",
        day: "2-digit",
        month: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
        hour12: false,
      })
    : "16/10 · không rõ giờ";

export function AnalysisPage() {
  const real = useWorkspaceStore((state) => state.workspace.kind === "real");
  const companion = real ? asLive(getServices().companion) : null;
  return companion ? (
    <LiveAnalysisPage service={companion} />
  ) : (
    <SimulatedAnalysisPage />
  );
}

function SimulatedAnalysisPage() {
  const { analysisId } = useParams();
  const navigate = useNavigate();
  const store = useWorkspaceStore();
  const demo = store.workspace.kind === "demo";
  const analysis = store.analyses.find(
    (item) => item.id === analysisId && item.ownerId === store.user?.id,
  );
  const [filter, setFilter] = useState("all");
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState("");
  if (!analysis)
    return (
      <div className="ai-feature stack">
        <PageHeader title="Phân tích ảnh mẫu" back="/ai" />
        <EmptyState
          title="Chưa có bộ ảnh này"
          description="Bạn có thể mở một bộ ảnh hư cấu để thử luồng rà soát."
        />
        {analysisVariants.map((variant) => (
          <Button
            variant="secondary"
            key={variant.id}
            onClick={() =>
              navigate(`/ai/analysis/${startFixtureAnalysis(variant.id).id}`)
            }
          >
            {variant.label}
            <ArrowRight size={18} />
          </Button>
        ))}
      </div>
    );
  const evidence = analysis.evidenceIds
    .map((id) => store.evidence.find((item) => item.id === id))
    .filter((item): item is Evidence => !!item);
  const active = evidence.filter((item) => item.reviewStatus !== "rejected");
  const confirmed = active.filter(
    (item) =>
      item.reviewStatus === "confirmed" &&
      analysis.confirmedIds.includes(item.id),
  );
  const timeline = buildConfirmedTimeline(
    "preview",
    active,
    analysis.confirmedIds,
  );
  const editable = !analysis.caseId;
  const ready = analysis.status === "review" || analysis.status === "confirmed";
  const processing = analysis.status === "processing";
  const shown = evidence.filter(
    (item) =>
      filter === "all" ||
      (filter === "confirmed"
        ? item.reviewStatus === "confirmed"
        : item.reviewStatus !== "confirmed" &&
          item.reviewStatus !== "rejected"),
  );
  function patchAnalysis(patch: Partial<Analysis>) {
    void getServices()
      .analysis.save({ ...analysis!, ...patch })
      .catch((cause: unknown) =>
        setError(
          cause instanceof Error
            ? cause.message
            : "Chưa giữ được thay đổi mô phỏng.",
        ),
      );
  }
  function review(item: Evidence, status: Evidence["reviewStatus"]) {
    void getServices().analysis.saveEvidence({ ...item, reviewStatus: status });
    patchAnalysis({
      confirmedIds:
        status === "confirmed"
          ? [...new Set([...analysis!.confirmedIds, item.id])]
          : analysis!.confirmedIds.filter((id) => id !== item.id),
    });
  }
  function edit(item: Evidence, text: string) {
    void getServices().analysis.saveEvidence(correctEvidence(item, text));
    patchAnalysis({
      confirmedIds: analysis!.confirmedIds.filter((id) => id !== item.id),
    });
  }
  async function run() {
    if (running) return;
    setRunning(true);
    setError("");
    patchAnalysis({ status: "processing" });
    try {
      await getServices().run(
        () => undefined,
        store.preferences.reducedMotion ? 0 : 800,
      );
      patchAnalysis({ status: "review" });
    } catch (cause) {
      patchAnalysis({ status: "error" });
      setError(
        cause instanceof Error
          ? cause.message
          : "Chưa mở được kết quả mẫu. Hãy thử lại.",
      );
    } finally {
      setRunning(false);
    }
  }
  async function createCase() {
    if (!demo || !confirmed.length || busy) return;
    setBusy(true);
    setError("");
    const id = uid("CASE");
    const events = buildConfirmedTimeline(id, active, analysis!.confirmedIds);
    const linkedChats = store.chats.filter(
      (chat) =>
        chat.ownerId === store.user?.id &&
        chat.messages.some((message) =>
          message.sourceIds?.includes(analysis!.id),
        ),
    );
    const now = new Date().toISOString();
    const item: Incident = {
      id,
      ownerId: store.user?.id ?? "USER-AN",
      title: "Nhóm chat lớp — ảnh mẫu",
      template: "TPL-FREE",
      perspective: "self",
      summary: [
        analysis!.description,
        ...events.map((event) => event.description),
      ]
        .filter(Boolean)
        .join("\n"),
      categoryTags: ["online"],
      status: "active",
      impactTags: [],
      events,
      evidenceIds: active.map((source) => source.id),
      linkedChatIds: linkedChats.map((chat) => chat.id),
      people: "Các vai trong tình huống hư cấu; chưa xác minh danh tính",
      place: "Nhóm chat lớp (mẫu)",
      occurredAt: "",
      tried: "",
      trustedPerson: "",
      createdAt: now,
      updatedAt: now,
      demo: true,
    };
    try {
      await getServices().cases.save(item);
      await Promise.all(
        active.map((source) =>
          getServices().analysis.saveEvidence({ ...source, caseId: id }),
        ),
      );
      await Promise.all(
        linkedChats.map((chat) =>
          getServices().chat.save({ ...chat, linkedCaseId: id }),
        ),
      );
      await getServices().analysis.save({
        ...analysis!,
        caseId: id,
        status: "confirmed",
      });
      store.notify(`Đã tạo hồ sơ từ ${confirmed.length} nguồn bạn xác nhận.`);
      navigate(`/cases/${id}`);
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : "Chưa lưu được hồ sơ. Nội dung đã kiểm tra vẫn được giữ.",
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="ai-feature stack">
      <PageHeader
        title="Cùng kiểm tra từng nguồn"
        description={
          analysisVariants.find((item) => item.id === analysis.fixture)
            ?.description
        }
        back="/ai"
        action={<Badge tone="lavender">Phân tích mô phỏng</Badge>}
      />
      <Notice>
        8 ảnh hoàn toàn hư cấu. Văn bản được dựng sẵn; không có OCR hoặc AI
        thật. Xác nhận nghĩa là bạn đã kiểm tra nội dung mẫu, không xác thực sự
        việc ngoài đời.
      </Notice>
      {!demo && (
        <Notice>
          AI mô phỏng · Nội dung phân tích chỉ lưu trên thiết bị này. Bộ ảnh mẫu
          không thể lưu vào hồ sơ thật.
        </Notice>
      )}
      <section className="ai-analysis-context panel">
        <h2>Đặt ảnh cạnh lời kể của bạn</h2>
        <div className="grid-2">
          <div className="field">
            <label htmlFor="analysis-description">Bối cảnh muốn giữ lại</label>
            <textarea
              id="analysis-description"
              rows={3}
              placeholder="Ví dụ: đây là nhóm lớp trong tình huống mẫu…"
              value={analysis.description}
              disabled={!editable || processing}
              onChange={(event) =>
                patchAnalysis({ description: event.target.value })
              }
            />
          </div>
          <div className="field">
            <label htmlFor="analysis-question">
              Bạn có thấy an toàn hôm nay không?
            </label>
            <textarea
              id="analysis-question"
              rows={3}
              value={analysis.questionAnswer}
              disabled={!editable || processing}
              placeholder="Có thể ghi chưa rõ, hoặc để sau."
              onChange={(event) =>
                patchAnalysis({ questionAnswer: event.target.value })
              }
            />
          </div>
        </div>
        <Link to="/support/urgent">
          Nếu đang không an toàn, tìm hỗ trợ trực tiếp <ArrowRight size={15} />
        </Link>
      </section>
      {!ready && (
        <div className="ai-processing panel">
          <AgentStatusOrb
            state={
              running
                ? "analyzing"
                : analysis.status === "error"
                  ? "error"
                  : "idle"
            }
            size={64}
          />
          <div>
            <h2>
              {running
                ? "Đang mở kết quả mẫu…"
                : processing
                  ? "Lượt mở trước đã dừng."
                  : "Bạn sẵn sàng xem nội dung mẫu?"}
            </h2>
            <p>
              {active.length} ảnh đã chọn.{" "}
              {processing && !running
                ? "Bạn có thể mở lại kết quả mẫu; phần đã nhập vẫn được giữ."
                : "Bạn có thể bỏ ảnh khỏi bộ mẫu trước khi tiếp tục."}
            </p>
            {!running && (
              <Button onClick={run} disabled={!active.length}>
                {analysis.status === "error" || processing
                  ? "Thử mở lại kết quả"
                  : "Xem phân tích mô phỏng"}
                <ArrowRight size={18} />
              </Button>
            )}
          </div>
        </div>
      )}
      {error && <Notice tone="error">{error}</Notice>}
      {ready && (
        <Notice>
          Phần diễn giải bên dưới minh họa bộ ảnh gốc. Ảnh bị bỏ và lời bạn sửa
          không được AI phân tích lại trong demo; dòng thời gian chỉ dùng đúng
          phần bạn xác nhận ở từng nguồn.
        </Notice>
      )}
      {ready && (
        <section
          className="ai-summary-grid"
          aria-label="Kết quả mẫu có giới hạn"
        >
          <div className="ai-summary-block">
            <span className="ai-summary-label">
              <Check size={17} />
              Điều nhìn thấy
            </span>
            <p>
              Có lời gọi biệt danh ở ảnh 01/05, lời hẹn ở ảnh 03 và câu phản đối
              ở ảnh 06.
            </p>
            <div className="chips">
              {["01", "03", "05", "06"].map((number) => (
                <a
                  className="ai-source"
                  key={number}
                  href={`#source-${number}`}
                >
                  Ảnh {number}
                </a>
              ))}
            </div>
          </div>
          <div className="ai-summary-block">
            <span className="ai-summary-label">
              <CircleHelp size={17} />
              Dấu hiệu cần xem xét
            </span>
            <p>
              Lời gọi biệt danh xuất hiện ở các ngày khác nhau. Lời hẹn có thể
              gây lo tùy bối cảnh; chưa kết luận là đe dọa.
            </p>
            <a className="ai-source" href="#source-03">
              Xem ảnh 03
            </a>
          </div>
          <div className="ai-summary-block">
            <span className="ai-summary-label">
              <CircleHelp size={17} />
              Điều chưa rõ
            </span>
            <p>
              Phần bị cắt, danh tính bị che, ý định người gửi và sự việc tương
              ứng ở lớp. Ảnh 08 có thể trùng ảnh 07.
            </p>
            {analysis.fixture === "conflict" && (
              <p className="ai-discrepancy">
                Lời kể: khoảng 18:00. Ảnh 03: 20:10. Hai thông tin được giữ
                riêng; chưa biết giờ chụp.
              </p>
            )}
          </div>
          <div className="ai-summary-block">
            <span className="ai-summary-label">
              <ArrowRight size={17} />
              Bước bạn có thể chọn
            </span>
            <p>
              Kiểm tra từng ảnh, lưu phần bạn xác nhận và chuẩn bị nói với người
              lớn tin cậy. Bạn có thể để phần chưa rõ lại sau.
            </p>
            <Link to="/knowledge/luu-anh-chup-co-ngu-canh">
              Cách giữ ảnh có ngữ cảnh
            </Link>
          </div>
        </section>
      )}
      <section>
        <div className="heading-row">
          <div>
            <h2>Ảnh và nội dung trích mẫu</h2>
            <p className="muted">
              {confirmed.length}/{active.length} nguồn đã xác nhận · bản gốc
              luôn được giữ.
            </p>
          </div>
          <Badge tone="neutral">8 ảnh hư cấu</Badge>
        </div>
        <Progress value={confirmed.length} max={active.length} />
        <div className="segmented ai-review-filters" aria-label="Lọc nguồn">
          {[
            ["all", "Tất cả"],
            ["review", "Cần kiểm tra"],
            ["confirmed", "Đã xác nhận"],
          ].map(([value, label]) => (
            <button
              key={value}
              aria-pressed={filter === value}
              onClick={() => setFilter(value)}
            >
              {label}
            </button>
          ))}
        </div>
        <div className="ai-evidence-list">
          {shown.map((item) => {
            const number = item.id.slice(-2);
            const rejected = item.reviewStatus === "rejected";
            return (
              <article
                className={`ai-evidence-row ${rejected ? "is-rejected" : ""}`}
                id={`source-${number}`}
                key={item.id}
              >
                <a
                  className="ai-evidence-image"
                  href={item.assetPath}
                  target="_blank"
                  rel="noreferrer"
                >
                  <img
                    src={item.assetPath}
                    alt={`Ảnh chat hư cấu ${number}, ${labelTime(item.shownTimestamp)}; mở để xem nguồn mẫu`}
                    loading="lazy"
                  />
                </a>
                <div className="ai-evidence-content">
                  <div className="heading-row">
                    <h3>Ảnh {number}</h3>
                    <Badge
                      tone={
                        item.reviewStatus === "confirmed" ? "green" : "neutral"
                      }
                    >
                      {item.reviewStatus === "confirmed"
                        ? "Bạn đã xác nhận"
                        : item.reviewStatus === "corrected"
                          ? "Đã sửa · cần xác nhận"
                          : rejected
                            ? "Đã bỏ khỏi bộ ảnh"
                            : "Chưa xác nhận"}
                    </Badge>
                  </div>
                  <small>
                    {labelTime(item.shownTimestamp)} · giờ hiển thị, không phải
                    giờ chụp
                  </small>
                  <div className="field">
                    <label htmlFor={`text-${item.id}`}>
                      Nội dung nhận diện mẫu
                    </label>
                    <textarea
                      id={`text-${item.id}`}
                      rows={3}
                      value={item.userEditedText ?? item.extractedText}
                      disabled={!ready || rejected || !editable}
                      onChange={(event) => edit(item, event.target.value)}
                    />
                  </div>
                  <details>
                    <summary>Xem văn bản nguồn ban đầu</summary>
                    <p className="ai-original">{item.originalText}</p>
                  </details>
                  {item.limitations.map((limit) => (
                    <p className="ai-limitation" key={limit}>
                      <CircleHelp size={15} />
                      {limit}
                    </p>
                  ))}
                  <div className="actions">
                    {rejected ? (
                      <Button
                        variant="secondary"
                        disabled={!editable || processing}
                        onClick={() => review(item, "unreviewed")}
                      >
                        <RotateCcw size={16} />
                        Đưa ảnh trở lại
                      </Button>
                    ) : (
                      <>
                        <Button
                          variant={
                            item.reviewStatus === "confirmed"
                              ? "secondary"
                              : "primary"
                          }
                          disabled={
                            !ready ||
                            !editable ||
                            !(item.userEditedText ?? item.extractedText).trim()
                          }
                          onClick={() =>
                            review(
                              item,
                              item.reviewStatus === "confirmed"
                                ? "unreviewed"
                                : "confirmed",
                            )
                          }
                        >
                          <Check size={16} />
                          {item.reviewStatus === "confirmed"
                            ? "Bỏ xác nhận"
                            : "Xác nhận nội dung"}
                        </Button>
                        <Button
                          variant="ghost"
                          disabled={!editable || processing}
                          onClick={() => review(item, "rejected")}
                        >
                          <Trash2 size={16} />
                          Bỏ ảnh
                        </Button>
                      </>
                    )}
                  </div>
                </div>
              </article>
            );
          })}
          {!shown.length && (
            <EmptyState
              title="Không có nguồn trong bộ lọc này"
              description="Chọn Tất cả để tiếp tục rà soát."
            />
          )}
        </div>
      </section>
      {ready && (
        <section className="panel">
          <h2>Dòng thời gian bạn đã xác nhận</h2>
          <p className="muted">
            Chỉ các nguồn được xác nhận mới xuất hiện. Ảnh 07/08 có nội dung
            giống nhau được gộp thành một mốc; phần bạn sửa khác nhau được giữ
            để đối chiếu.
          </p>
          {timeline.length ? (
            <ol className="ai-timeline">
              {timeline.map((event) => (
                <li key={event.id}>
                  <time>{labelTime(event.when)}</time>
                  <p>{event.description}</p>
                  <small>
                    Nguồn{" "}
                    {event.evidenceIds.map((id) => id.slice(-2)).join(", ")} ·
                    Người dùng xác nhận
                    {event.needsReview ? " · Còn giới hạn ngữ cảnh" : ""}
                  </small>
                </li>
              ))}
            </ol>
          ) : (
            <p>
              Chưa có mốc nào. Chọn một ảnh và xác nhận phần bạn đã kiểm tra.
            </p>
          )}
          <div className="actions">
            {!demo ? (
              <p>
                Bộ ảnh mẫu không thể lưu vào hồ sơ thật. Bạn vẫn có thể luyện rà
                soát nội dung tại đây.
              </p>
            ) : analysis.caseId ? (
              <>
                <Link
                  className="button primary"
                  to={`/cases/${analysis.caseId}`}
                >
                  Mở hồ sơ đã lưu
                  <ArrowRight size={18} />
                </Link>
                <Link
                  className="button secondary"
                  to={`/cases/${analysis.caseId}/plan`}
                >
                  Chọn bước tiếp theo
                </Link>
              </>
            ) : (
              <Button
                disabled={!confirmed.length}
                onClick={() => setConfirmOpen(true)}
              >
                Tạo hồ sơ từ nội dung đã xác nhận
                <ArrowRight size={18} />
              </Button>
            )}
          </div>
        </section>
      )}
      <Modal
        open={confirmOpen}
        onClose={() => !busy && setConfirmOpen(false)}
        title="Lưu phần bạn đã kiểm tra?"
      >
        <div className="stack">
          <p>
            {confirmed.length} nguồn đã xác nhận sẽ tạo {timeline.length} mốc.{" "}
            {active.length - confirmed.length} nguồn chưa xác nhận chỉ được giữ
            trong bằng chứng, không trở thành sự kiện.
          </p>
          <Notice>
            Nhận định về động cơ và danh tính chưa rõ sẽ không được ghi thành sự
            thật. Hồ sơ chỉ nằm trong bản demo, chưa gửi cho ai.
          </Notice>
          {error && <Notice tone="error">{error}</Notice>}
          <div className="actions">
            <Button disabled={busy} onClick={createCase}>
              {busy ? "Đang lưu mẫu…" : "Xác nhận và tạo hồ sơ"}
            </Button>
            <Button
              variant="secondary"
              disabled={busy}
              onClick={() => setConfirmOpen(false)}
            >
              Kiểm tra tiếp
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
