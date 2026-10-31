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
  /** Set only from a server `consulting` progress event of this run (Phase 2). */
  consulting?: { requester: string; specialist: string; transfer?: boolean } | null;
};

export type AIActivityView = {
  label: string | null;
  busy: boolean;
  orbState: "working" | null;
  consulting?: { requester: string; specialist: string };
};

const CHECKING = "Đang kiểm tra trạng thái cuộc trò chuyện…";

export function deriveAIActivity({ phase, requestKey, runId, consulting }: AIActivityInput): AIActivityView {
  switch (phase) {
    case "submitting":
      return { label: "Đang gửi tin nhắn…", busy: true, orbState: null };
    case "accepted":
      // Without both identities the run cannot be tied to this view: no loop.
      if (!requestKey || !runId) return { label: CHECKING, busy: true, orbState: null };
      // A consultation is named only while the server says it is running; never a guessed stage.
      return consulting
        ? {
          label: consulting.transfer
            ? `${consulting.requester} đang mời ${consulting.specialist} trò chuyện cùng bạn…`
            : `${consulting.requester} đang hỏi ${consulting.specialist} một chút…`,
          busy: true, orbState: "working", consulting,
        }
        : { label: "Đang trả lời…", busy: true, orbState: "working" };
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
