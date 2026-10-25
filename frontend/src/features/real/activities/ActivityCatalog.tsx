import { useState } from "react";
import { Sparkles } from "lucide-react";
import { Button, cx, Dialog } from "../../../components/UI";
import { canInvite, type Definition, type Kind, type Session } from "./activityView";

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

export function ActivityCatalog({
  catalog,
  current,
  cooldown,
  busy,
  onInvite,
  onClose,
}: {
  catalog: Definition[];
  current: Session | null;
  cooldown: Partial<Record<Kind, number>>;
  busy: boolean;
  onInvite: (kind: Kind, options?: Record<string, unknown>) => void;
  onClose: () => void;
}) {
  const [plan, setPlan] = useState("25,5");
  const [cycles, setCycles] = useState(1);
  return (
    <Dialog title="Cùng làm gì đó?" onClose={() => !busy && onClose()}>
      <p>Mời bạn kia cùng tham gia. Hoạt động chỉ bắt đầu khi cả hai đồng ý.</p>
      <ul className="activity-catalog">
        {catalog.map((definition) => {
          const allowed = canInvite(current, definition.kind, cooldown);
          return (
            <li key={definition.kind}>
              <h3>{definition.title}</h3>
              <p>{definition.description}</p>
              <p className={cx.footnote}>Khoảng {definition.estimatedMinutes} phút</p>
              {definition.kind === "focus" && (
                <div className="focus-options">
                  <label>
                    Nhịp
                    <select value={plan} onChange={(event) => setPlan(event.target.value)}>
                      {(definition.focusPlans ?? [[25, 5]]).map(([work, rest]) => (
                        <option key={work} value={`${work},${rest}`}>
                          {work} phút tập trung / {rest} phút nghỉ
                        </option>
                      ))}
                    </select>
                  </label>
                  <label>
                    Số lượt
                    <select
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
                  </label>
                </div>
              )}
              <Button
                disabled={busy || !allowed}
                aria-label={`Mời cùng chơi ${definition.title}`}
                onClick={() =>
                  onInvite(
                    definition.kind,
                    definition.kind === "focus"
                      ? { plan: plan.split(",").map(Number), cycles }
                      : undefined,
                  )
                }
              >
                Mời cùng chơi
              </Button>
              {!allowed && !current && (
                <p className={cx.footnote}>Hãy thử lại hoạt động này sau ít phút.</p>
              )}
            </li>
          );
        })}
      </ul>
      {current && <p className={cx.note}>Hai bạn đang có một hoạt động khác.</p>}
    </Dialog>
  );
}
