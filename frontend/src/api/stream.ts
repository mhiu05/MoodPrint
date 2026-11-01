import { ApiError } from "./client";
import type { AICard, AiOutput } from "./contracts";

// Never render arbitrary provider error bodies from a stream.
const aiFailureMessages: Record<string, string> = {
  AI_PROVIDER_CONFIGURATION: "Trợ lý đang gặp lỗi kết nối. Bạn có thể thử lại sau.",
  AI_PROVIDER_RATE_LIMIT: "Nhà cung cấp AI đang giới hạn lượt dùng. Bạn hãy thử lại sau ít phút.",
  AI_PROVIDER_UNAVAILABLE: "Chưa kết nối được nhà cung cấp AI. Bạn có thể thử lại sau.",
  AI_TIMEOUT: "Trợ lý chưa phản hồi kịp. Bạn có thể thử lại sau.",
  AI_STORAGE_UNAVAILABLE: "Chưa tải được trạng thái mới nhất. Tải lại cuộc trò chuyện trước khi gửi tiếp.",
};

export type ValidatedFinal = AiOutput & { cards: AICard[] };

export type ValidatedBubble = {
  /** Saved/published id from ai-events-v2; null when an older server answered with v1. */
  messageId: string | null;
  partIndex: number;
  text: string;
  cards: AICard[];
};
/** Backend-rendered collaboration line (Phase 2); present only when the server sent the key. */
export type CollaborationLine = {
  kind: "nhip_energy_for_rure" | "nhip_habit_for_may" | "rure_activity_for_guong";
  companions: [BotName, BotName];
  summary: string;
};
/** V3: a specialist step that actually ran and was used for this reply (server receipt). */
export type ReplyStep = { kind: "consult" | "handoff"; companion: "nhatky" | "hoatdong" };
export type ValidatedReply = {
  messages: ValidatedBubble[];
  collaboration?: CollaborationLine | null;
  /** V3: who actually answered (a handoff changes it) and which specialists helped. */
  speaker?: BotName | null;
  steps?: ReplyStep[];
};
type BotName = "may" | "guong" | "nhip" | "rure" | "caunoi" | "dieuphoi" | "nhatky" | "hoatdong";
/** Real, server-derived progress of a collaborative turn. Never a guessed stage. */
export type StreamActivity =
  | { activity: "consulting"; companion: BotName }
  | { activity: "transferring"; companion: BotName }
  | { activity: "composing" };

const BOTS: readonly string[] = ["may", "guong", "nhip", "rure", "caunoi", "dieuphoi", "nhatky", "hoatdong"];
/** The only allowed edges and their [specialist, requester] pairs (mirrors collaboration/policy.py). */
const EDGE_COMPANIONS: Record<string, [BotName, BotName]> = {
  nhip_energy_for_rure: ["nhip", "rure"],
  nhip_habit_for_may: ["nhip", "may"],
  rure_activity_for_guong: ["rure", "guong"],
};
const SPECIALISTS: readonly string[] = ["nhip", "rure", "nhatky", "hoatdong"];
const V3_SPECIALISTS: readonly string[] = ["nhatky", "hoatdong"];

const RUN_EVENTS = /^\/api\/v1\/ai\/runs\/[a-zA-Z0-9-]+\/events$/;
const MAX_BUBBLES = 4;
const MAX_JOINED = 6000;

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
          BOTS.includes(String(card.botId))
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

function v1Final(data: Record<string, unknown>): ValidatedFinal {
  if (
    typeof data.text !== "string" ||
    !data.text.trim() ||
    Array.from(data.text).length > MAX_JOINED ||
    Object.keys(data).some((key) => !["text", "cards"].includes(key)) ||
    !validCards(data.cards)
  )
    throw invalidStream();
  return { text: data.text, cards: data.cards };
}

export function validCollaboration(value: unknown): value is CollaborationLine | null {
  if (value === null) return true;
  return (
    object(value) &&
    Object.keys(value).every((key) => ["kind", "companions", "summary"].includes(key)) &&
    Object.hasOwn(EDGE_COMPANIONS, String(value.kind)) &&
    Array.isArray(value.companions) &&
    value.companions.length === 2 &&
    value.companions.every((bot, index) => bot === EDGE_COMPANIONS[String(value.kind)][index]) &&
    typeof value.summary === "string" &&
    value.summary.trim().length > 0 &&
    Array.from(value.summary).length <= 200
  );
}

/** progress.data is `{}` or exactly one of the two collaboration shapes. */
function progressActivity(data: Record<string, unknown>): StreamActivity | null {
  const keys = Object.keys(data);
  if (!keys.length) return null;
  if (data.activity === "consulting" && keys.length === 2 && SPECIALISTS.includes(String(data.companion)))
    return { activity: "consulting", companion: data.companion as BotName };
  if (data.activity === "transferring" && keys.length === 2 && V3_SPECIALISTS.includes(String(data.companion)))
    return { activity: "transferring", companion: data.companion as BotName };
  if (data.activity === "composing" && keys.length === 1) return { activity: "composing" };
  throw invalidStream();
}

export function validSteps(value: unknown): value is ReplyStep[] {
  return (
    Array.isArray(value) &&
    value.length <= 2 &&
    value.every(
      (step) =>
        object(step) &&
        Object.keys(step).every((key) => ["kind", "companion"].includes(key)) &&
        ["consult", "handoff"].includes(String(step.kind)) &&
        V3_SPECIALISTS.includes(String(step.companion)),
    )
  );
}

function v2Final(data: Record<string, unknown>): ValidatedReply {
  const messages = data.messages;
  if (
    Object.keys(data).some((key) => !["partCount", "messages", "collaboration", "speaker", "steps"].includes(key)) ||
    ("collaboration" in data && !validCollaboration(data.collaboration)) ||
    ("speaker" in data && data.speaker !== null && !BOTS.includes(String(data.speaker))) ||
    ("steps" in data && !validSteps(data.steps)) ||
    !Array.isArray(messages) ||
    messages.length < 1 ||
    messages.length > MAX_BUBBLES ||
    data.partCount !== messages.length
  )
    throw invalidStream();
  const bubbles = messages.map((message: unknown, index): ValidatedBubble => {
    if (
      !object(message) ||
      Object.keys(message).some((key) => !["messageId", "partIndex", "text", "cards"].includes(key)) ||
      typeof message.messageId !== "string" ||
      !/^[a-zA-Z0-9-]{1,64}$/.test(message.messageId) ||
      message.partIndex !== index ||
      typeof message.text !== "string" ||
      !message.text.trim() ||
      !validCards(message.cards)
    )
      throw invalidStream();
    return { messageId: message.messageId, partIndex: index, text: message.text, cards: message.cards };
  });
  // The same bounds an old client enforces on the joined v1 text and its cards.
  const joined = bubbles.map((bubble) => bubble.text).join("\n\n");
  if (Array.from(joined).length > MAX_JOINED || bubbles.flatMap((bubble) => bubble.cards).length > 3)
    throw invalidStream();
  const reply: ValidatedReply = { messages: bubbles };
  if ("collaboration" in data) reply.collaboration = data.collaboration as CollaborationLine | null;
  if ("speaker" in data) reply.speaker = data.speaker as BotName | null;
  if ("steps" in data) reply.steps = data.steps as ReplyStep[];
  return reply;
}

/** Buffer until a validated final and terminal receipt. Provider deltas never enter UI state. */
async function consume<T>(
  url: string,
  signal: AbortSignal,
  accept: (version: unknown) => boolean,
  final: (version: string, data: Record<string, unknown>) => T,
  onProgress?: (activity: StreamActivity) => void,
): Promise<T> {
  const response = await fetch(url, {
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
    sequence = 0n,
    version: string | undefined;
  let result: T | undefined;
  try {
    while (true) {
      const chunk = await reader.read();
      buffer += decoder.decode(chunk.value, { stream: !chunk.done });
      if (buffer.length > 1_000_000) throw invalidStream();
      let separator: RegExpExecArray | null;
      while ((separator = /\r?\n\r?\n/.exec(buffer))) {
        const block = buffer.slice(0, separator.index);
        buffer = buffer.slice(separator.index + separator[0].length);
        // The server ends a stream with `event: revoked` when the turn lost its permission,
        // session or data version mid-run: the run is already stopped server-side.
        if (block.split(/\r?\n/).some((line) => line.trim() === "event: revoked"))
          throw new ApiError(409, "RUN_CANCELLED", "Phản hồi đã dừng vì quyền hoặc dữ liệu vừa thay đổi.");
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
          !accept(event.version) ||
          (version !== undefined && event.version !== version) ||
          typeof event.seq !== "string" ||
          !/^[1-9]\d*$/.test(event.seq) ||
          !object(event.data)
        )
          throw invalidStream();
        // One stream never mixes protocol versions.
        version = event.version as string;
        const next = BigInt(event.seq);
        if (next <= sequence) continue;
        if (next !== sequence + 1n) throw invalidStream();
        sequence = next;
        if (event.type === "progress") {
          // v1 progress is always `{}`; v2 may carry the two collaboration activities.
          // v1 progress data is never read (raw provider deltas must not reach the UI, nor fail it).
          const activity = version === "ai-events-v2" ? progressActivity(event.data) : null;
          if (activity) onProgress?.(activity);
          continue;
        }
        if (event.type === "final") {
          result = final(version, event.data);
        } else if (event.type === "completed") {
          if (result === undefined) throw invalidStream();
          return result;
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
              "Phản hồi bị gián đoạn và không tự tiếp tục. Tải lại cuộc trò chuyện để kiểm tra trước khi gửi tin mới.",
            );
          const code = typeof event.data.code === "string" ? event.data.code : "";
          if (Object.hasOwn(aiFailureMessages, code))
            throw new ApiError(503, "RUN_FAILED", aiFailureMessages[code]);
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

/** ai-events-v1: one joined final message (the legacy contract). */
export async function consumeAIEvents(
  eventsUrl: string,
  signal: AbortSignal,
): Promise<ValidatedFinal> {
  if (!RUN_EVENTS.test(eventsUrl)) throw invalidStream();
  return consume(eventsUrl, signal, (version) => version === "ai-events-v1", (_version, data) => v1Final(data));
}

/**
 * ai-events-v2: the validated bubbles of one reply, all at once after `completed`.
 * The server's eventsUrl never carries a query; this client adds `?protocol=2`. A server
 * that predates v2 ignores the query and answers v1, which becomes one bubble without an id.
 */
export async function consumeAIReply(
  eventsUrl: string,
  signal: AbortSignal,
  onProgress?: (activity: StreamActivity) => void,
): Promise<ValidatedReply> {
  if (!RUN_EVENTS.test(eventsUrl)) throw invalidStream();
  return consume(
    `${eventsUrl}?protocol=2`,
    signal,
    (version) => version === "ai-events-v1" || version === "ai-events-v2",
    (version, data) => {
      if (version === "ai-events-v2") return v2Final(data);
      const single = v1Final(data);
      return { messages: [{ messageId: null, partIndex: 0, text: single.text, cards: single.cards }] };
    },
    onProgress,
  );
}
