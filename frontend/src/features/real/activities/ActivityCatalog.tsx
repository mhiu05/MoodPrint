import { useId, useState } from "react";
import { Sparkles } from "lucide-react";
import { Button, cx, Dialog } from "../../../components/UI";
import { ApiError, errorMessage } from "../../../api/client";
import { canInvite, isOpen, type Definition, type Kind, type Session } from "./activityView";

const HOW_IT_WORKS: Record<Kind, string> = {
  icebreaker: "Ba câu hỏi để làm quen. Mỗi người trả lời riêng; câu trả lời chỉ mở khi cả hai đã gửi. Bạn có thể bỏ qua câu hỏi.",
  coop_quiz: "Năm vòng đố vui cùng một đội. Mỗi người chọn riêng; khi cả hai đã trả lời, đáp án và điểm của đội mới được mở.",
  focus: "Chọn nhịp học hoặc làm việc cùng nhau. Một người tạm dừng sẽ dừng đồng hồ của cả hai; bạn có thể rời phiên và vào lại.",
};

/** "Cùng làm gì đó?" next to the composer; opens the catalog of shared activities. */
export function ActivityEntryButton({
  disabled,
  onOpen,
}: {
  disabled: boolean;
  onOpen: () => void;
}) {
  return (
    <button
      type="button"
      className="activity-entry"
      disabled={disabled}
      onClick={onOpen}
      aria-label="Cùng làm gì đó?"
      title="Cùng làm gì đó?"
    >
      <Sparkles size={18} aria-hidden="true" />
      <span>Cùng làm gì đó?</span>
    </button>
  );
}

/** A server/network failure keeps the choice; a refused request explains itself. */
function inviteFailure(error: unknown) {
  if (error instanceof ApiError && error.status < 500) return errorMessage(error);
  return "Chưa gửi được lời mời. Lựa chọn của bạn vẫn được giữ. Bạn hãy thử lại.";
}

export function ActivityCatalog({
  catalog,
  status,
  onRetryCatalog,
  inviteError,
  current,
  cooldown,
  busy,
  onInvite,
  onClose,
}: {
  catalog: Definition[];
  status: "loading" | "ready" | "empty" | "error";
  onRetryCatalog: () => void;
  inviteError?: { kind: Kind; error: unknown };
  current: Session | null;
  cooldown: Partial<Record<Kind, number>>;
  busy: boolean;
  onInvite: (kind: Kind, options?: Record<string, unknown>) => void;
  onClose: () => void;
}) {
  const [plan, setPlan] = useState("25,5");
  const [cycles, setCycles] = useState(1);
  const id = useId();
  return (
    <Dialog title="Cùng làm gì đó?" onClose={() => !busy && onClose()}>
      <p>Mời người bạn kết nối cùng tham gia. Hoạt động bắt đầu khi cả hai đồng ý.</p>
      {status === "loading" ? <p role="status">Đang tải danh sách hoạt động…</p> : null}
      {status === "error" ? (
        <div className={cx.error} role="alert">
          <p>Chưa tải được danh sách hoạt động. Bạn hãy thử lại.</p>
          <Button variant="secondary" onClick={onRetryCatalog}>Thử lại</Button>
        </div>
      ) : null}
      {status === "empty" ? <p>Hiện chưa có hoạt động chung nào để mời.</p> : null}
      <ul className="activity-catalog">
        {catalog.map((definition) => {
          const allowed = canInvite(current, definition.kind, cooldown);
          return (
            <li key={definition.kind}>
              <h3>{definition.title}</h3>
              <p>{definition.description}</p>
              <p className="activity-how">{HOW_IT_WORKS[definition.kind]}</p>
              <p className={cx.footnote}>Khoảng {definition.estimatedMinutes} phút</p>
              {definition.kind === "focus" && (
                <div className="focus-options">
                  <div>
                    <label htmlFor={`${id}-plan`}>Nhịp</label>
                    <select id={`${id}-plan`} value={plan} onChange={(event) => setPlan(event.target.value)}>
                      {(definition.focusPlans ?? [[25, 5]]).map(([work, rest]) => (
                        <option key={work} value={`${work},${rest}`}>
                          {work} phút tập trung / {rest} phút nghỉ
                        </option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label htmlFor={`${id}-cycles`}>Số lượt</label>
                    <select
                      id={`${id}-cycles`}
                      value={cycles}
                      onChange={(event) => setCycles(Number(event.target.value))}
                    >
                      {Array.from({ length: definition.maxCycles ?? 4 }, (_, i) => i + 1).map(
                        (value) => (
                          <option key={value} value={value}>
                            {value}
                          </option>
                        ),
                      )}
                    </select>
                  </div>
                </div>
              )}
              {inviteError?.kind === definition.kind ? (
                <p className={cx.error} role="alert">{inviteFailure(inviteError.error)}</p>
              ) : null}
              <Button
                disabled={busy || !allowed}
                aria-label={`Mời tham gia ${definition.title}`}
                onClick={() =>
                  onInvite(
                    definition.kind,
                    definition.kind === "focus"
                      ? { plan: plan.split(",").map(Number), cycles }
                      : undefined,
                  )
                }
              >
                {busy ? "Đang gửi lời mời…" : "Mời tham gia"}
              </Button>
              {!allowed && !isOpen(current) && (
                <p className={cx.footnote}>Bạn có thể gửi lại lời mời cho hoạt động này sau ít phút.</p>
              )}
            </li>
          );
        })}
      </ul>
      {isOpen(current) && <p className={cx.note}>Hai bạn đang có một hoạt động. Hoàn thành hoặc kết thúc hoạt động đó để gửi lời mời mới.</p>}
    </Dialog>
  );
}
