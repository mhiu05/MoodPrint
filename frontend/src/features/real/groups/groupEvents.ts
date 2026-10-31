import { ApiError } from "../../../api/client";
import { validCards } from "../../../api/stream";
import type { AICard } from "../../../api/contracts";

export type AgentId = "dieuphoi" | "nhatky" | "hoatdong";
export type GroupBubble = { messageId: string; partIndex: number; text: string; cards: AICard[] };
/** Server-derived group turn events (ai-group-events-v1). Nothing here is guessed client-side. */
export type GroupEvent =
  | { type: "turn_started" }
  | { type: "agent_selected" | "agent_started"; agent: AgentId; ordinal: number }
  | { type: "agent_message"; agent: AgentId; ordinal: number; messages: GroupBubble[] }
  | { type: "agent_failed"; agent: AgentId; ordinal: number; code: string }
  | { type: "turn_completed" | "turn_cancelled" }
  | { type: "turn_failed"; code: string };
export type GroupOutcome = "completed" | "cancelled" | "failed";

const AGENTS = ["dieuphoi", "nhatky", "hoatdong"];
const URL_PATTERN = /^\/api\/v1\/ai\/groups\/[a-zA-Z0-9-]+\/turns\/[a-zA-Z0-9-]+\/events$/;
const invalid = () => new ApiError(502, "INVALID_AI_EVENT", "Chưa nhận được phản hồi hợp lệ. Vui lòng tải lại nhóm.");
const object = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value);

function agentOf(data: Record<string, unknown>): { agent: AgentId; ordinal: number } {
  if (!AGENTS.includes(String(data.agent)) || !Number.isInteger(data.ordinal) || (data.ordinal as number) < 0 || (data.ordinal as number) > 2)
    throw invalid();
  return { agent: data.agent as AgentId, ordinal: data.ordinal as number };
}

export function parseGroupEvent(type: unknown, data: Record<string, unknown>): GroupEvent {
  switch (type) {
    case "turn_started":
      return { type };
    case "agent_selected":
    case "agent_started":
      return { type, ...agentOf(data) };
    case "agent_message": {
      const messages = data.messages;
      if (!Array.isArray(messages) || messages.length < 1 || messages.length > 4) throw invalid();
      return {
        type, ...agentOf(data),
        messages: messages.map((message: unknown, index) => {
          if (!object(message) || typeof message.messageId !== "string" || !/^[a-zA-Z0-9-]{1,64}$/.test(message.messageId) ||
            message.partIndex !== index || typeof message.text !== "string" || !message.text.trim() || !validCards(message.cards))
            throw invalid();
          return { messageId: message.messageId, partIndex: index, text: message.text, cards: message.cards as AICard[] };
        }),
      };
    }
    case "agent_failed":
      return { type, ...agentOf(data), code: typeof data.code === "string" ? data.code : "failed" };
    case "turn_completed":
    case "turn_cancelled":
      return { type };
    case "turn_failed":
      return { type, code: typeof data.code === "string" ? data.code : "AI_RUN_FAILED" };
    default:
      throw invalid();
  }
}

/** Read one group turn until its terminal event. Reconnects resume from the last seq seen. */
export async function consumeGroupTurn(
  eventsUrl: string,
  signal: AbortSignal,
  onEvent: (event: GroupEvent) => void,
  afterSeq = 0,
): Promise<{ outcome: GroupOutcome; lastSeq: number }> {
  if (!URL_PATTERN.test(eventsUrl)) throw invalid();
  const response = await fetch(`${eventsUrl}?afterSeq=${afterSeq}`, {
    credentials: "same-origin", cache: "no-store", headers: { Accept: "text/event-stream" }, signal,
  });
  if (!response.ok || !response.body || !response.headers.get("Content-Type")?.includes("text/event-stream"))
    throw new ApiError(response.status || 502, "STREAM_UNAVAILABLE", "Chưa thể nhận phản hồi. Vui lòng tải lại nhóm.");
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "", sequence = afterSeq;
  try {
    while (true) {
      const chunk = await reader.read();
      buffer += decoder.decode(chunk.value, { stream: !chunk.done });
      if (buffer.length > 1_000_000) throw invalid();
      let separator: RegExpExecArray | null;
      while ((separator = /\r?\n\r?\n/.exec(buffer))) {
        const block = buffer.slice(0, separator.index);
        buffer = buffer.slice(separator.index + separator[0].length);
        if (block.split(/\r?\n/).some((line) => line.trim() === "event: revoked"))
          throw new ApiError(409, "RUN_CANCELLED", "Lượt trả lời đã dừng vì quyền hoặc dữ liệu vừa thay đổi.");
        const raw = block.split(/\r?\n/).filter((line) => line.startsWith("data:")).map((line) => line.slice(5).trimStart()).join("\n");
        if (!raw) continue;
        let event: unknown;
        try {
          event = JSON.parse(raw);
        } catch {
          throw invalid();
        }
        if (!object(event) || event.version !== "ai-group-events-v1" || typeof event.seq !== "string" ||
          !/^[1-9]\d{0,2}$/.test(event.seq) || !object(event.data))
          throw invalid();
        const next = Number(event.seq);
        if (next <= sequence) continue;
        if (next !== sequence + 1) throw invalid();
        sequence = next;
        const parsed = parseGroupEvent(event.type, event.data);
        onEvent(parsed);
        if (parsed.type === "turn_completed") return { outcome: "completed", lastSeq: sequence };
        if (parsed.type === "turn_cancelled") return { outcome: "cancelled", lastSeq: sequence };
        if (parsed.type === "turn_failed") return { outcome: "failed", lastSeq: sequence };
      }
      if (chunk.done) throw invalid();
    }
  } finally {
    await reader.cancel().catch(() => {});
    reader.releaseLock();
  }
}
