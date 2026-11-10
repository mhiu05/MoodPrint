import { ThinkingOrb } from "thinking-orbs";
import type { OrbState } from "thinking-orbs";
import { useDemoStore } from "../app/store";
import { useReducedMotion } from "../hooks/useReducedMotion";
import { CircleAlert } from "lucide-react";
type State =
  | "idle"
  | "listening"
  | "processing"
  | "searching"
  | "analyzing"
  | "responding"
  | "error";
const labels: Record<State, string> = {
  idle: "Sẵn sàng trò chuyện",
  listening: "Mô phỏng lượt lắng nghe",
  processing: "Đang phát lại kịch bản mẫu",
  searching: "Đang hiển thị dữ liệu trích xuất mẫu",
  analyzing: "Đang phát lại phân tích mẫu",
  responding: "Đang tạo phản hồi mô phỏng",
  error: "Đã dừng mô phỏng",
};
const modes: Record<State, OrbState> = {
  idle: "breathing",
  listening: "listening",
  processing: "working",
  searching: "searching",
  analyzing: "solving",
  responding: "composing",
  error: "breathing",
};
export function AgentStatusOrb({
  state = "idle",
  size = 64,
  showLabel = true,
}: {
  state?: State;
  size?: 20 | 32 | 64;
  showLabel?: boolean;
}) {
  const reduced = useReducedMotion();
  const preference = useDemoStore((s) => s.preferences.reducedMotion);
  return (
    <span className={`orb-wrap orb-${state}`} role="status">
      {state === "idle" || state === "error" || reduced || preference ? (
        <span
          className="orb-static"
          style={{ width: size, height: size }}
          aria-hidden="true"
        >
          {state === "error" ? (
            <CircleAlert size={size / 2} />
          ) : (
            <svg
              width={size * 0.6}
              height={size * 0.6}
              viewBox="0 0 40 40"
              fill="none"
              aria-hidden="true"
            >
              <path
                d="M12 16h.1M28 16h.1M13 24c3 5 11 5 14 0"
                stroke="currentColor"
                strokeWidth="2.6"
                strokeLinecap="round"
              />
            </svg>
          )}
        </span>
      ) : (
        <ThinkingOrb
          state={modes[state]}
          size={size}
          color="#126A61"
          theme="light"
          aria-hidden="true"
        />
      )}
      {showLabel && <span className="orb-label">{labels[state]}</span>}
    </span>
  );
}
export default AgentStatusOrb;
