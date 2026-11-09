import { useEffect, useState } from "react";
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
                “{item.text}” <small>(độ tin cậy: {item.confidence})</small>
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
  const [items, setItems] = useState<Evidence[] | null>(null);
  const [loadError, setLoadError] = useState(false);
  const [selected, setSelected] = useState<Evidence | null>(null);
  const [agreed, setAgreed] = useState(false);
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<AnalysisView | null>(null);
  const [message, setMessage] = useState("");
  const [correction, setCorrection] = useState("");
  const [saved, setSaved] = useState(false);
  const load = () => {
    getServices()
      .evidence.list()
      .then((all) => {
        setItems(all.filter(eligible));
        setLoadError(false);
      })
      .catch(() => setLoadError(true));
  };
  useEffect(load, []);

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
      if (view.status === "failed")
        setMessage(describeFailure(view.errorCode ?? "internal_error"));
    } catch (cause) {
      const code = (cause as { code?: string }).code ?? "internal_error";
      // The server may still be working: look the request up before telling the user it failed.
      try {
        const view = await service.analyses.get(id);
        setResult(view);
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
    if (!selected || !correction.trim()) return;
    await getServices().evidence.review(selected.id, {
      userEditedText: correction.trim(),
      reviewStatus: "corrected",
    });
    setSaved(true);
  };

  return (
    <div className="ai-feature stack" data-testid="analysis-live">
      <PageHeader
        title="Phân tích ảnh bằng AI"
        description="Chọn một ảnh bạn đã tải lên. AI chỉ đọc khi bạn đồng ý."
        back="/ai"
      />
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
                onChange={() => setSelected(item)}
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
      {running && (
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
          <Button variant="secondary" onClick={() => setResult(null)}>
            Thử lại
          </Button>
        </div>
      )}
      {result?.status === "succeeded" && result.reading && (
        <>
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
              disabled={!correction.trim()}
              onClick={() => void saveCorrection()}
            >
              Lưu bản chỉnh
            </Button>
            {saved && <p role="status">Đã lưu bản bạn chỉnh.</p>}
          </section>
        </>
      )}
    </div>
  );
}
