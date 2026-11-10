import { useCallback, useEffect, useState } from "react";
import {
  Link,
  useNavigate,
  useParams,
  useSearchParams,
} from "react-router-dom";
import { Button, EmptyState, Notice, PageHeader } from "../../../components/ui";
import { AgentStatusOrb } from "../../../animations/AgentStatusOrb";
import { getServices } from "../../../services/composition";
import {
  ANALYSIS_CONSENT_VERSION,
  type AnalysisReading,
  type AnalysisView,
  type LiveCompanion,
} from "../../../services/composition/companion-types";
import type { Evidence } from "../../../types";
import { describeFailure } from "./use-live-chat";
import "./live.css";

const IMAGE_TYPES = ["image/jpeg", "image/png", "image/webp"];
const confidenceLabels = { high: "cao", medium: "vừa", low: "thấp" };
export const consentText =
  "Ảnh này sẽ được gửi tới mô hình AI để đọc. Hệ thống yêu cầu không lưu phản hồi trên máy chủ AI, " +
  "nhưng điều đó không có nghĩa là dữ liệu bị xóa hoàn toàn. Bản gốc của bạn không bị thay đổi.";

const eligible = (item: Evidence) =>
  item.uploadStatus === "uploaded" &&
  IMAGE_TYPES.includes(item.storedMimeType ?? "");

export function ReadingView({ reading }: { reading: AnalysisReading }) {
  return (
    <div className="live-reading" data-testid="analysis-result">
      <section aria-labelledby="r-text">
        <h3 id="r-text">Chữ đọc được</h3>
        {reading.extractedText.length ? (
          <ul>
            {reading.extractedText.map((item, index) => (
              <li key={index}>
                “{item.text}”{" "}
                <small>
                  (AI tự đánh giá độ rõ: {confidenceLabels[item.confidence]};
                  bạn cần kiểm tra lại)
                </small>
              </li>
            ))}
          </ul>
        ) : (
          <p>Không đọc được chữ nào.</p>
        )}
      </section>
      <section aria-labelledby="r-obs">
        <h3 id="r-obs">Quan sát</h3>
        <ul>
          {reading.observations.map((item, index) => (
            <li key={index}>{item}</li>
          ))}
        </ul>
      </section>
      <section className="live-guess" aria-labelledby="r-guess">
        <h3 id="r-guess">AI suy đoán (chưa xác minh)</h3>
        <ul>
          {reading.inferences.map((item, index) => (
            <li key={index}>
              {item.text} <small>— dựa trên: {item.basis}</small>
            </li>
          ))}
        </ul>
      </section>
      <section aria-labelledby="r-unsure">
        <h3 id="r-unsure">Điều chưa chắc và hạn chế</h3>
        <ul>
          {[...reading.uncertainties, ...reading.limitations].map(
            (item, index) => (
              <li key={index}>{item}</li>
            ),
          )}
        </ul>
      </section>
    </div>
  );
}

export function LiveAnalysisPage({ service }: { service: LiveCompanion }) {
  const { analysisId } = useParams();
  const [query] = useSearchParams();
  const navigate = useNavigate();
  const [items, setItems] = useState<Evidence[] | null>(null);
  const [loadError, setLoadError] = useState(false);
  const [selected, setSelected] = useState<Evidence | null>(null);
  const [agreed, setAgreed] = useState(false);
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<AnalysisView | null>(null);
  const [message, setMessage] = useState("");
  const [correction, setCorrection] = useState("");
  const [saved, setSaved] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState("");
  const [attempt, setAttempt] = useState(0);
  const requestedEvidence = query.get("evidenceId");
  const requestedCase = query.get("caseId");
  const load = useCallback(() => {
    getServices()
      .evidence.list()
      .then((all) => {
        setItems(all.filter(eligible));
        const chosen = all.find(
          (item) => item.id === requestedEvidence && eligible(item),
        );
        if (chosen) setSelected(chosen);
        setLoadError(false);
      })
      .catch(() => setLoadError(true));
  }, [requestedEvidence]);
  useEffect(load, [load]);

  useEffect(() => {
    if (!analysisId || analysisId === "new") return;
    let current = true;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const startedAt = Date.now();
    const read = async () => {
      try {
        const view = await service.analyses.get(analysisId);
        if (!current) return;
        setResult(view);
        setMessage(
          view.status === "failed"
            ? describeFailure(view.errorCode ?? "internal_error")
            : "",
        );
        if (view.status === "running") {
          if (Date.now() - startedAt > 180000)
            setMessage(
              "Kết quả chưa sẵn sàng sau thời gian chờ. Bạn có thể thử tải lại sau; không cần gửi ảnh lần nữa.",
            );
          else timer = setTimeout(() => void read(), 1500);
        }
      } catch {
        if (current)
          setMessage(
            "Chưa mở lại được kết quả này. Hãy thử tải lại; bạn không cần gửi ảnh lần nữa.",
          );
      }
    };
    void read();
    return () => {
      current = false;
      clearTimeout(timer);
    };
  }, [service, analysisId, attempt]);

  const selectedImage = result
    ? (items?.find((item) => item.id === result.evidenceId) ?? null)
    : selected;

  const start = async () => {
    if (!selected || !agreed) return; // no consent, no request
    setRunning(true);
    setMessage("");
    const id = globalThis.crypto.randomUUID();
    try {
      const view = await service.analyses.create({
        id,
        evidenceId: selected.id,
        consentVersion: ANALYSIS_CONSENT_VERSION,
      });
      setResult(view);
      navigate(
        `/ai/analysis/${id}${requestedCase ? `?caseId=${encodeURIComponent(requestedCase)}` : ""}`,
        { replace: true },
      );
      if (view.status === "failed")
        setMessage(describeFailure(view.errorCode ?? "internal_error"));
    } catch (cause) {
      const code = (cause as { code?: string }).code ?? "internal_error";
      // The server may still be working: look the request up before telling the user it failed.
      try {
        const view = await service.analyses.get(id);
        setResult(view);
        navigate(`/ai/analysis/${id}`, { replace: true });
        if (view.status === "failed")
          setMessage(describeFailure(view.errorCode ?? code));
      } catch {
        setMessage(describeFailure(code));
      }
    } finally {
      setRunning(false);
    }
  };

  const saveCorrection = async () => {
    if (!selectedImage || !correction.trim() || saving) return;
    setSaving(true);
    setSaveError("");
    try {
      await getServices().evidence.review(selectedImage.id, {
        userEditedText: correction.trim(),
        reviewStatus: "corrected",
      });
      setSaved(true);
    } catch {
      setSaveError(
        "Chưa lưu được bản chỉnh. Nội dung vẫn ở đây; hãy thử lưu lại.",
      );
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="ai-feature stack" data-testid="analysis-live">
      <PageHeader
        title="Phân tích ảnh bằng AI"
        description="Chọn một ảnh bạn đã tải lên. AI chỉ đọc khi bạn đồng ý."
        back={requestedCase ? `/cases/${requestedCase}/evidence` : "/ai"}
      />
      {!items && !loadError && <p role="status">Đang tải danh sách ảnh…</p>}
      {loadError && (
        <Notice>
          Chưa tải được danh sách ảnh.{" "}
          <button className="link-button" onClick={load}>
            Thử lại
          </button>
        </Notice>
      )}
      {items?.length === 0 && (
        <EmptyState
          title="Chưa có ảnh phù hợp"
          description="Hãy tải một ảnh JPEG, PNG hoặc WebP lên phần bằng chứng trước."
          action={
            <Link
              className="button secondary"
              to={requestedCase ? `/cases/${requestedCase}/evidence` : "/cases"}
            >
              Mở bằng chứng trong hồ sơ
            </Link>
          }
        />
      )}
      {items && items.length > 0 && !result && (
        <fieldset className="live-pick">
          <legend>Ảnh để phân tích</legend>
          {items.map((item) => (
            <label key={item.id}>
              <input
                type="radio"
                name="evidence"
                checked={selected?.id === item.id}
                onChange={() => {
                  setSelected(item);
                  setAgreed(false);
                }}
              />{" "}
              {item.originalFilename ?? "Ảnh"}
            </label>
          ))}
        </fieldset>
      )}
      {selected && !result && (
        <div className="live-consent">
          <label>
            <input
              type="checkbox"
              checked={agreed}
              onChange={(event) => setAgreed(event.target.checked)}
            />{" "}
            Tôi đồng ý gửi ảnh này cho AI đọc
          </label>
          <p>{consentText}</p>
          <Button disabled={!agreed || running} onClick={() => void start()}>
            Phân tích ảnh
          </Button>
        </div>
      )}
      {(running || (result?.status === "running" && !message)) && (
        <div className="live-working" role="status">
          <AgentStatusOrb state="analyzing" size={32} showLabel={false} />
          <span>
            AI đang đọc ảnh. Bạn có thể rời trang; kết quả sẽ còn khi bạn quay
            lại.
          </span>
        </div>
      )}
      {message && (
        <div className="live-error" role="alert">
          <span>{message}</span>
          <Button
            variant="secondary"
            onClick={() => {
              if (
                result?.status === "failed" ||
                result?.status === "cancelled"
              ) {
                setResult(null);
                setMessage("");
                setAgreed(false);
                navigate(
                  `/ai/analysis/new${requestedCase ? `?caseId=${encodeURIComponent(requestedCase)}` : ""}`,
                  { replace: true },
                );
              } else if (analysisId && analysisId !== "new")
                setAttempt((n) => n + 1);
              else {
                setResult(null);
                setMessage("");
              }
            }}
          >
            Thử lại
          </Button>
        </div>
      )}
      {result?.status === "succeeded" && result.reading && (
        <>
          {selectedImage && (
            <p>Ảnh gốc: {selectedImage.originalFilename ?? "Ảnh đã tải lên"}</p>
          )}
          <ReadingView reading={result.reading} />
          <section className="live-correction">
            <h3>Bạn chỉnh lại</h3>
            <p>
              Bản của AI được giữ nguyên bên trên; bản bạn sửa được lưu riêng
              cho bằng chứng này.
            </p>
            <label className="sr-only" htmlFor="live-correction">
              Nội dung bạn sửa
            </label>
            <textarea
              id="live-correction"
              rows={3}
              value={correction}
              onChange={(event) => {
                setCorrection(event.target.value);
                setSaved(false);
              }}
            />
            <Button
              disabled={!correction.trim() || saving || !selectedImage}
              onClick={() => void saveCorrection()}
            >
              Lưu bản chỉnh
            </Button>
            {saved && <p role="status">Đã lưu bản bạn chỉnh.</p>}
            {saveError && <p role="alert">{saveError}</p>}
          </section>
        </>
      )}
      {result && result.status !== "running" && (
        <Link
          className="button secondary"
          to="/ai/analysis/new"
          onClick={() => {
            setResult(null);
            setSelected(null);
            setAgreed(false);
            setMessage("");
            setCorrection("");
            setSaved(false);
          }}
        >
          Chọn ảnh khác
        </Link>
      )}
    </div>
  );
}
