/**
 * Maps the real AI request/run lifecycle to one status presentation.
 * The public contract (ai-events-v1) only says "accepted" and later a terminal
 * event; it never reports searching, reading or reasoning stages, so neither
 * does this adapter. No timers: every phase comes from an actual request outcome.
 */
export type AIActivityPhase =
  | "idle" | "submitting" | "accepted"
  | "cancelling" | "reconciling"
  | "completed" | "cancelled" | "failed" | "unavailable";

export type AIActivityInput = {
  phase: AIActivityPhase;
  /** Local ownership token for the current send intent or resumed run. */
  requestKey?: string;
  runId?: string;
};

export type AIActivityView = {
  label: string | null;
  busy: boolean;
  orbState: "working" | null;
};

const CHECKING = "Đang kiểm tra trạng thái cuộc trò chuyện…";

export function deriveAIActivity({ phase, requestKey, runId }: AIActivityInput): AIActivityView {
  switch (phase) {
    case "submitting":
      return { label: "Đang gửi tin nhắn…", busy: true, orbState: null };
    case "accepted":
      // Without both identities the run cannot be tied to this view: no loop.
      return requestKey && runId
        ? { label: "Đang trả lời…", busy: true, orbState: "working" }
        : { label: CHECKING, busy: true, orbState: null };
    case "cancelling":
      return { label: "Đang yêu cầu dừng…", busy: true, orbState: null };
    case "reconciling":
      return { label: CHECKING, busy: true, orbState: null };
    case "cancelled":
      return { label: "Đã dừng phản hồi.", busy: false, orbState: null };
    default:
      return { label: null, busy: false, orbState: null };
  }
}
