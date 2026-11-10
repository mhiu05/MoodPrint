import { useEffect, useState } from "react";
import { Button, Modal } from "../../../components/ui";
import type { ApprovalView } from "./use-live-chat";

type Preview = Record<string, unknown>;
const text = (value: unknown) =>
  typeof value === "string" || typeof value === "number" ? String(value) : "";

function PreviewBody({ preview }: { preview: Preview }) {
  const kind = text(preview.kind);
  if (kind === "case_event")
    return (
      <dl className="live-preview">
        <dt>Ngày</dt>
        <dd>{text(preview.when) || "Chưa rõ ngày"}</dd>
        <dt>Nơi</dt>
        <dd>{text(preview.place) || "Chưa rõ nơi"}</dd>
        <dt>Mô tả</dt>
        <dd>{text(preview.description)}</dd>
        {Array.isArray(preview.evidence) && preview.evidence.length > 0 && (
          <>
            <dt>Bằng chứng đính kèm</dt>
            <dd>{(preview.evidence as unknown[]).map(text).join(", ")}</dd>
          </>
        )}
        {text(preview.rationale) && (
          <>
            <dt>Lý do AI đề xuất</dt>
            <dd>{text(preview.rationale)}</dd>
          </>
        )}
      </dl>
    );
  if (kind === "action_plan")
    return (
      <div className="live-preview">
        <p>
          <strong>Mục tiêu:</strong> {text(preview.goal)}
        </p>
        <ol>
          {(Array.isArray(preview.steps)
            ? (preview.steps as Preview[])
            : []
          ).map((step, index) => (
            <li key={index}>
              {text(step.label)}
              {text(step.priority) === "high" && (
                <span className="live-priority"> · ưu tiên cao</span>
              )}
              {text(step.reason) && <small> — {text(step.reason)}</small>}
            </li>
          ))}
        </ol>
      </div>
    );
  if (kind === "evidence_analysis")
    return (
      <div className="live-preview">
        <p>
          <strong>Ảnh:</strong> {text(preview.filename) || "ảnh đã chọn"}
        </p>
        <p>{text(preview.consent)}</p>
      </div>
    );
  return <p className="live-preview">{text(preview.summary)}</p>;
}

function useCountdown(expiresAt: string) {
  const [left, setLeft] = useState(() => Date.parse(expiresAt) - Date.now());
  useEffect(() => {
    const timer = setInterval(
      () => setLeft(Date.parse(expiresAt) - Date.now()),
      1000,
    );
    return () => clearInterval(timer);
  }, [expiresAt]);
  return Math.max(0, Math.floor(left / 1000));
}

export function ApprovalDialog({
  approval,
  open,
  busy = false,
  onDecide,
  onDefer,
}: {
  approval: ApprovalView;
  open: boolean;
  busy?: boolean;
  onDecide: (decision: "approve" | "reject") => void;
  onDefer: () => void;
}) {
  const seconds = useCountdown(approval.expiresAt);
  const expired = seconds <= 0;
  const sends = text(approval.preview.kind) === "evidence_analysis";
  return (
    <Modal open={open} onClose={onDefer} title="AI đề xuất — bạn quyết định">
      <div
        className="live-approval"
        role="group"
        aria-label="Đề xuất cần bạn duyệt"
      >
        <p className="live-approval-note">
          AI chỉ đề xuất. Chưa có gì được thay đổi cho đến khi bạn chọn.
        </p>
        <PreviewBody preview={approval.preview} />
        <p className="live-approval-timer" role="timer" aria-live="off">
          {expired
            ? "Đề xuất đã hết hạn. Hãy nhờ AI soạn lại."
            : `Còn ${Math.floor(seconds / 60)} phút ${seconds % 60} giây để quyết định.`}
        </p>
        <div className="live-approval-actions">
          <Button
            variant="secondary"
            disabled={busy || expired}
            onClick={() => onDecide("reject")}
          >
            {sends ? "Không gửi" : "Không lưu"}
          </Button>
          <Button
            disabled={busy || expired}
            onClick={() => onDecide("approve")}
          >
            {sends ? "Đồng ý gửi ảnh cho AI" : "Lưu"}
          </Button>
        </div>
      </div>
    </Modal>
  );
}
