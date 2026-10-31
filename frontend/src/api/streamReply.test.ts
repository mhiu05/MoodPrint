import { afterEach, describe, expect, it, vi } from "vitest";
import { consumeAIReply } from "./stream";

type Event = { version?: string; seq: string; type: string; data: unknown };

function serve(events: Event[]) {
  const body = events
    .map((event) => `data: ${JSON.stringify({ version: "ai-events-v2", ...event })}\n\n`)
    .join("");
  const fetch = vi.fn().mockResolvedValue(
    new Response(body, { headers: { "Content-Type": "text/event-stream" } }),
  );
  vi.stubGlobal("fetch", fetch);
  return fetch;
}

const bubble = (index: number, text: string, cards: unknown[] = []) => ({
  messageId: `00000000-0000-4000-8000-00000000000${index}`,
  partIndex: index,
  text,
  cards,
});

function reply(final: unknown, version = "ai-events-v2") {
  serve([
    { version, seq: "1", type: "progress", data: {} },
    { version, seq: "2", type: "final", data: final },
    { version, seq: "3", type: "completed", data: {} },
  ]);
  return consumeAIReply("/api/v1/ai/runs/run-1/events", new AbortController().signal);
}

afterEach(() => vi.unstubAllGlobals());

describe("validated multi-bubble AI stream (ai-events-v2)", () => {
  it("requests protocol 2 and returns ordered bubbles with their saved ids", async () => {
    const fetch = serve([
      { seq: "1", type: "progress", data: {} },
      {
        seq: "2",
        type: "final",
        data: { partCount: 2, messages: [bubble(0, "Nghe mệt thật."), bubble(1, "Thử nghỉ nhé?", [{ kind: "mood_form" }])] },
      },
      { seq: "3", type: "completed", data: {} },
    ]);
    const result = await consumeAIReply("/api/v1/ai/runs/run-1/events", new AbortController().signal);
    expect(fetch.mock.calls[0][0]).toBe("/api/v1/ai/runs/run-1/events?protocol=2");
    expect(result.messages.map((message) => [message.messageId, message.partIndex, message.text])).toEqual([
      ["00000000-0000-4000-8000-000000000000", 0, "Nghe mệt thật."],
      ["00000000-0000-4000-8000-000000000001", 1, "Thử nghỉ nhé?"],
    ]);
    expect(result.messages[1].cards).toEqual([{ kind: "mood_form" }]);
  });

  it("accepts a v1 stream from an older server as one bubble without an id", async () => {
    await expect(reply({ text: "Xin chào", cards: [] }, "ai-events-v1")).resolves.toEqual({
      messages: [{ messageId: null, partIndex: 0, text: "Xin chào", cards: [] }],
    });
  });

  it.each([
    ["unknown bubble key", { partCount: 1, messages: [{ ...bubble(0, "A"), extra: 1 }] }],
    ["unknown final key", { partCount: 1, messages: [bubble(0, "A")], receipt: {} }],
    ["count mismatch", { partCount: 2, messages: [bubble(0, "A")] }],
    ["gap in part order", { partCount: 2, messages: [bubble(0, "A"), bubble(2, "B")] }],
    ["empty bubble", { partCount: 1, messages: [bubble(0, "   ")] }],
    ["five bubbles", { partCount: 5, messages: [0, 1, 2, 3, 4].map((index) => bubble(index, `Ý ${index}`)) }],
    ["too many cards", { partCount: 2, messages: [bubble(0, "A", [{ kind: "mood_form" }, { kind: "discovery" }]), bubble(1, "B", [{ kind: "mood_form" }, { kind: "discovery" }])] }],
    ["forged card", { partCount: 1, messages: [bubble(0, "A", [{ kind: "save_memory" }])] }],
    ["joined text too long", { partCount: 2, messages: [bubble(0, "x".repeat(3000)), bubble(1, "y".repeat(3000))] }],
    ["missing id", { partCount: 1, messages: [{ ...bubble(0, "A"), messageId: "" }] }],
  ])("rejects an unsafe v2 final: %s", async (_name, final) => {
    await expect(reply(final)).rejects.toMatchObject({ code: "INVALID_AI_EVENT" });
  });

  it("rejects a stream that mixes protocol versions", async () => {
    serve([
      { version: "ai-events-v2", seq: "1", type: "progress", data: {} },
      { version: "ai-events-v1", seq: "2", type: "final", data: { text: "A", cards: [] } },
      { version: "ai-events-v2", seq: "3", type: "completed", data: {} },
    ]);
    await expect(
      consumeAIReply("/api/v1/ai/runs/run-1/events", new AbortController().signal),
    ).rejects.toMatchObject({ code: "INVALID_AI_EVENT" });
  });

  it("never returns bubbles before the completed event", async () => {
    serve([
      { seq: "1", type: "progress", data: {} },
      { seq: "2", type: "final", data: { partCount: 1, messages: [bubble(0, "A")] } },
    ]);
    await expect(
      consumeAIReply("/api/v1/ai/runs/run-1/events", new AbortController().signal),
    ).rejects.toMatchObject({ code: "INVALID_AI_EVENT" });
  });

  it("rejects an events URL that is not a run stream", async () => {
    await expect(
      consumeAIReply("/api/v1/ai/runs/run-1/events?protocol=2", new AbortController().signal),
    ).rejects.toMatchObject({ code: "INVALID_AI_EVENT" });
  });
});
