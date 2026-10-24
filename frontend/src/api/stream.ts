import { ApiError } from "./client";
import type { AICard, AiOutput } from "./contracts";

export type ValidatedFinal = AiOutput & { cards: AICard[] };

function object(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

export function validCards(value: unknown): value is AICard[] {
  return (
    Array.isArray(value) &&
    value.length <= 3 &&
    value.every((card) => {
      if (!object(card)) return false;
      if (card.kind === "navigate_bot")
        return (
          Object.keys(card).every((key) => ["kind", "botId"].includes(key)) &&
          ["may", "guong", "nhip", "rure", "caunoi"].includes(
            String(card.botId),
          )
        );
      return (
        ["mood_form", "discovery"].includes(String(card.kind)) &&
        Object.keys(card).length === 1
      );
    })
  );
}

const invalidStream = () =>
  new ApiError(
    502,
    "INVALID_AI_EVENT",
    "Chưa nhận được phản hồi hợp lệ. Vui lòng tải lại cuộc trò chuyện.",
  );

/** Buffer until a validated final and terminal receipt. Provider deltas never enter UI state. */
export async function consumeAIEvents(
  eventsUrl: string,
  signal: AbortSignal,
): Promise<ValidatedFinal> {
  if (!/^\/api\/v1\/ai\/runs\/[a-zA-Z0-9-]+\/events$/.test(eventsUrl))
    throw invalidStream();
  const response = await fetch(eventsUrl, {
    credentials: "same-origin",
    cache: "no-store",
    headers: { Accept: "text/event-stream" },
    signal,
  });
  if (
    !response.ok ||
    !response.body ||
    !response.headers.get("Content-Type")?.includes("text/event-stream")
  ) {
    throw new ApiError(
      response.status || 502,
      "STREAM_UNAVAILABLE",
      "Chưa thể nhận phản hồi. Vui lòng tải lại cuộc trò chuyện để kiểm tra trạng thái.",
    );
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "",
    sequence = 0n;
  let final: ValidatedFinal | undefined;
  try {
    while (true) {
      const chunk = await reader.read();
      buffer += decoder.decode(chunk.value, { stream: !chunk.done });
      if (buffer.length > 1_000_000) throw invalidStream();
      let separator: RegExpExecArray | null;
      while ((separator = /\r?\n\r?\n/.exec(buffer))) {
        const block = buffer.slice(0, separator.index);
        buffer = buffer.slice(separator.index + separator[0].length);
        const data = block
          .split(/\r?\n/)
          .filter((line) => line.startsWith("data:"))
          .map((line) => line.slice(5).trimStart())
          .join("\n");
        if (!data) continue;
        let event: unknown;
        try {
          event = JSON.parse(data);
        } catch {
          throw invalidStream();
        }
        if (
          !object(event) ||
          event.version !== "ai-events-v1" ||
          typeof event.seq !== "string" ||
          !/^[1-9]\d*$/.test(event.seq) ||
          !object(event.data)
        )
          throw invalidStream();
        const next = BigInt(event.seq);
        if (next <= sequence) continue;
        if (next !== sequence + 1n) throw invalidStream();
        sequence = next;
        if (event.type === "progress") continue;
        if (event.type === "final") {
          if (
            typeof event.data.text !== "string" ||
            !event.data.text.trim() ||
            Array.from(event.data.text).length > 6000 ||
            Object.keys(event.data).some(
              (key) => !["text", "cards"].includes(key),
            ) ||
            !validCards(event.data.cards)
          )
            throw invalidStream();
          final = { text: event.data.text, cards: event.data.cards };
        } else if (event.type === "completed") {
          if (!final) throw invalidStream();
          return final;
        } else if (event.type === "cancelled") {
          throw new ApiError(
            409,
            "RUN_CANCELLED",
            "Phản hồi đã dừng. Bạn có thể gửi một tin nhắn mới.",
          );
        } else if (event.type === "failed") {
          if (event.data.code === "AI_INTERRUPTED")
            throw new ApiError(
              409,
              "RUN_INTERRUPTED",
              "Phản hồi đã bị gián đoạn. Lượt này không tự chạy lại; tải lại hội thoại rồi chủ động gửi tin mới.",
            );
          throw new ApiError(
            503,
            "RUN_FAILED",
            "Chưa hoàn tất phản hồi. Vui lòng tải lại cuộc trò chuyện để kiểm tra trước khi gửi lại.",
          );
        } else throw invalidStream();
      }
      if (chunk.done) throw invalidStream();
    }
  } finally {
    await reader.cancel().catch(() => {});
    reader.releaseLock();
  }
}
