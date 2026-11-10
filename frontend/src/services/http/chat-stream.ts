// SSE v1 reader over a fetch Response body. Not EventSource: it must carry the bearer token.
import type { StreamEvent } from "./stream-events";

export class StreamProtocolError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "StreamProtocolError";
  }
}

function parseFrame(frame: string): StreamEvent | null {
  const data: string[] = [];
  for (const line of frame.split(/\r?\n/)) {
    if (line.startsWith(":") || line === "") continue;
    const colon = line.indexOf(":");
    const field = colon === -1 ? line : line.slice(0, colon);
    if (field !== "data") continue; // event:/id: are redundant with the JSON envelope
    const value = colon === -1 ? "" : line.slice(colon + 1);
    data.push(value.startsWith(" ") ? value.slice(1) : value);
  }
  if (!data.length) return null;
  let parsed: unknown;
  try {
    parsed = JSON.parse(data.join("\n"));
  } catch {
    throw new StreamProtocolError("Khung dữ liệu không phải JSON hợp lệ.");
  }
  const event = parsed as Partial<StreamEvent> | null;
  if (
    !event ||
    event.v !== 1 ||
    typeof event.seq !== "number" ||
    typeof event.event !== "string"
  )
    throw new StreamProtocolError("Sự kiện không đúng giao thức v1.");
  return event as StreamEvent;
}

/** Yields protocol-checked events; heartbeats are consumed here and never reach the UI. */
export async function* readEvents(
  response: Response,
  signal?: AbortSignal,
): AsyncGenerator<StreamEvent> {
  if (!response.body)
    throw new StreamProtocolError("Phản hồi không có nội dung.");
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let lastSeq = 0;
  const abort = () => void reader.cancel().catch(() => undefined);
  signal?.addEventListener("abort", abort, { once: true });
  try {
    for (;;) {
      signal?.throwIfAborted();
      const { value, done } = await reader.read();
      // A cancelled reader reports `done`; an abort must surface as an abort, not an empty stream.
      signal?.throwIfAborted();
      buffer += decoder.decode(value, { stream: !done });
      let boundary = buffer.search(/\r?\n\r?\n/);
      while (boundary !== -1) {
        const separator = buffer.slice(boundary).match(/^\r?\n\r?\n/)![0];
        const frame = buffer.slice(0, boundary);
        buffer = buffer.slice(boundary + separator.length);
        const event = parseFrame(frame);
        if (event) {
          if (event.seq <= lastSeq)
            throw new StreamProtocolError("Thứ tự sự kiện bị đảo.");
          lastSeq = event.seq;
          if (event.event !== "heartbeat") yield event;
        }
        boundary = buffer.search(/\r?\n\r?\n/);
      }
      if (done) break;
    }
    if (buffer.trim())
      throw new StreamProtocolError("Luồng kết thúc giữa một sự kiện.");
  } finally {
    signal?.removeEventListener("abort", abort);
    await reader.cancel().catch(() => undefined);
  }
}
