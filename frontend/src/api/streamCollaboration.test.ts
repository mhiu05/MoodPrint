import { afterEach, describe, expect, it, vi } from "vitest";
import { consumeAIReply, type StreamActivity } from "./stream";

type Event = { seq: string; type: string; data: unknown };

function serve(events: Event[]) {
  const body = events.map((event) => `data: ${JSON.stringify({ version: "ai-events-v2", ...event })}\n\n`).join("");
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(body, { headers: { "Content-Type": "text/event-stream" } })));
}

const bubble = { messageId: "00000000-0000-4000-8000-000000000000", partIndex: 0, text: "Thử nhé.", cards: [] };
const line = {
  kind: "nhip_energy_for_rure",
  companions: ["nhip", "rure"],
  summary: "Nhịp đã gợi ý mức năng lượng phù hợp với bạn. Rủ Rê đã dựa vào đó để chọn hoạt động này.",
};

function collaborative(progress: unknown[], collaboration: unknown) {
  serve([
    { seq: "1", type: "progress", data: {} },
    ...progress.map((data, index) => ({ seq: String(index + 2), type: "progress", data })),
    {
      seq: String(progress.length + 2),
      type: "final",
      data: collaboration === undefined ? { partCount: 1, messages: [bubble] } : { partCount: 1, messages: [bubble], collaboration },
    },
    { seq: String(progress.length + 3), type: "completed", data: {} },
  ]);
}

afterEach(() => vi.unstubAllGlobals());

describe("collaboration over ai-events-v2", () => {
  it("reports real consulting/composing progress and returns the backend line", async () => {
    collaborative([{ activity: "consulting", companion: "nhip" }, { activity: "composing" }], line);
    const seen: StreamActivity[] = [];
    const reply = await consumeAIReply("/api/v1/ai/runs/run-1/events", new AbortController().signal, (activity) => seen.push(activity));
    expect(seen).toEqual([{ activity: "consulting", companion: "nhip" }, { activity: "composing" }]);
    expect(reply.collaboration).toEqual(line);
  });

  it("accepts a null line and leaves it absent when the server never sends the key", async () => {
    collaborative([], null);
    expect((await consumeAIReply("/api/v1/ai/runs/run-1/events", new AbortController().signal)).collaboration).toBeNull();
    serve([
      { seq: "1", type: "progress", data: {} },
      { seq: "2", type: "final", data: { partCount: 1, messages: [bubble] } },
      { seq: "3", type: "completed", data: {} },
    ]);
    expect("collaboration" in (await consumeAIReply("/api/v1/ai/runs/run-1/events", new AbortController().signal))).toBe(false);
  });

  it.each([
    [{ activity: "consulting", companion: "someone" }],
    [{ activity: "consulting" }],
    [{ activity: "thinking" }],
    [{ activity: "composing", companion: "nhip" }],
    [{ activity: "consulting", companion: "nhip", detail: "x" }],
  ])("rejects an invented or malformed progress event %j", async (data) => {
    collaborative([data], undefined);
    await expect(consumeAIReply("/api/v1/ai/runs/run-1/events", new AbortController().signal)).rejects.toMatchObject({ code: "INVALID_AI_EVENT" });
  });

  it.each([
    [{ ...line, summary: "x".repeat(201) }],
    [{ ...line, companions: ["nhip"] }],
    [{ ...line, companions: ["nhip", "robot"] }],
    [{ ...line, kind: "caunoi_social_for_may" }],
    [{ ...line, extra: true }],
    ["Nhịp đã giúp"],
  ])("rejects a malformed collaboration line %j", async (collaboration) => {
    collaborative([], collaboration);
    await expect(consumeAIReply("/api/v1/ai/runs/run-1/events", new AbortController().signal)).rejects.toMatchObject({ code: "INVALID_AI_EVENT" });
  });
});
