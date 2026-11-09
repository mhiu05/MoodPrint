import { describe, expect, it } from "vitest";
import { readEvents, StreamProtocolError } from "./chat-stream";

const frame = (seq: number, event: string, data: unknown, v = 1) =>
  `event: ${event}\nid: ${seq}\ndata: ${JSON.stringify({ v, seq, runId: "r", event, data })}\n\n`;

function responseOf(chunks: string[]): Response {
  const encoder = new TextEncoder();
  return new Response(
    new ReadableStream({
      start(controller) {
        for (const chunk of chunks) controller.enqueue(encoder.encode(chunk));
        controller.close();
      },
    }),
  );
}
async function collect(response: Response, signal?: AbortSignal) {
  const out = [];
  for await (const event of readEvents(response, signal)) out.push(event);
  return out;
}

describe("SSE v1 reader", () => {
  const full =
    frame(1, "run.started", { runId: "r" }) +
    frame(2, "heartbeat", {}) +
    frame(3, "message.delta", { messageId: "m", text: "Xin chào" }) +
    frame(4, "run.completed", { status: "completed" });

  it("reassembles frames split at every possible byte boundary", async () => {
    const bytes = new TextEncoder().encode(full);
    for (let cut = 1; cut < bytes.length; cut += 7) {
      const decoder = new TextDecoder();
      const left = decoder.decode(bytes.slice(0, cut), { stream: true });
      const events = await collect(responseOf([left, full.slice(left.length)]));
      expect(events.map((e) => e.event)).toEqual([
        "run.started",
        "message.delta",
        "run.completed",
      ]);
    }
  });

  it("keeps multi-byte Vietnamese text intact when a character is split", async () => {
    const bytes = new TextEncoder().encode(
      frame(1, "message.delta", { text: "ề" }),
    );
    const middle = bytes.indexOf(0xe1) + 1;
    const encoder = new TextEncoder();
    const response = new Response(
      new ReadableStream({
        start(controller) {
          controller.enqueue(bytes.slice(0, middle));
          controller.enqueue(bytes.slice(middle));
          controller.close();
        },
      }),
    );
    void encoder;
    const [event] = await collect(response);
    expect((event.data as { text: string }).text).toBe("ề");
  });

  it("drops heartbeats and tolerates CRLF framing and comments", async () => {
    const crlf = full.replace(/\n/g, "\r\n");
    const events = await collect(responseOf([": ping\r\n\r\n", crlf]));
    expect(events.map((e) => e.event)).not.toContain("heartbeat");
    expect(events).toHaveLength(3);
  });

  it("rejects a wrong protocol version, a non-increasing seq and broken JSON", async () => {
    await expect(
      collect(responseOf([frame(1, "run.started", {}, 2)])),
    ).rejects.toBeInstanceOf(StreamProtocolError);
    await expect(
      collect(
        responseOf([
          frame(2, "run.started", {}),
          frame(2, "message.delta", {}),
        ]),
      ),
    ).rejects.toThrow(/Thứ tự/);
    await expect(collect(responseOf(["data: {not json\n\n"]))).rejects.toThrow(
      /JSON/,
    );
  });

  it("fails loudly when the stream ends in the middle of an event", async () => {
    await expect(
      collect(
        responseOf([frame(1, "run.started", {}), 'data: {"v":1,"seq":2']),
      ),
    ).rejects.toThrow(/giữa một sự kiện/);
  });

  it("stops reading when the caller aborts", async () => {
    const controller = new AbortController();
    const pending = new Response(new ReadableStream({ start() {} }));
    const run = collect(pending, controller.signal);
    controller.abort(new DOMException("stop", "AbortError"));
    await expect(run).rejects.toMatchObject({ name: "AbortError" });
  });
});
