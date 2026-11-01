import { afterEach, describe, expect, it, vi } from "vitest";
import { deriveAIActivity } from "../features/real/aiActivityView";
import { consumeAIReply, type StreamActivity } from "./stream";

type Event = { seq: string; type: string; data: unknown };

function serve(events: Event[]) {
  const body = events.map((event) => `data: ${JSON.stringify({ version: "ai-events-v2", ...event })}\n\n`).join("");
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(body, { headers: { "Content-Type": "text/event-stream" } })));
}

const bubble = { messageId: "00000000-0000-4000-8000-000000000000", partIndex: 0, text: "Gộp lại nhé.", cards: [] };

function turn(progress: unknown[], extra: Record<string, unknown>) {
  serve([
    { seq: "1", type: "progress", data: {} },
    ...progress.map((data, index) => ({ seq: String(index + 2), type: "progress", data })),
    { seq: String(progress.length + 2), type: "final", data: { partCount: 1, messages: [bubble], ...extra } },
    { seq: String(progress.length + 3), type: "completed", data: {} },
  ]);
}

const URL = "/api/v1/ai/runs/run-1/events";
afterEach(() => vi.unstubAllGlobals());

describe("V3 orchestration over ai-events-v2", () => {
  it("reports each real consultation and returns the speaker and receipt-backed steps", async () => {
    turn(
      [{ activity: "consulting", companion: "nhatky" }, { activity: "consulting", companion: "hoatdong" }],
      { speaker: "dieuphoi", steps: [{ kind: "consult", companion: "nhatky" }, { kind: "consult", companion: "hoatdong" }] },
    );
    const seen: StreamActivity[] = [];
    const reply = await consumeAIReply(URL, new AbortController().signal, (activity) => seen.push(activity));
    expect(seen.map((item) => "companion" in item && item.companion)).toEqual(["nhatky", "hoatdong"]);
    expect(reply.speaker).toBe("dieuphoi");
    expect(reply.steps).toHaveLength(2);
  });

  it("accepts a real handoff: the transfer progress and the specialist as speaker", async () => {
    turn([{ activity: "transferring", companion: "nhatky" }], { speaker: "nhatky", steps: [{ kind: "handoff", companion: "nhatky" }] });
    const seen: StreamActivity[] = [];
    const reply = await consumeAIReply(URL, new AbortController().signal, (activity) => seen.push(activity));
    expect(seen).toEqual([{ activity: "transferring", companion: "nhatky" }]);
    expect(reply.speaker).toBe("nhatky");
  });

  it.each([
    [[{ activity: "transferring", companion: "may" }], {}],
    [[{ activity: "transferring" }], {}],
    [[], { speaker: "robot" }],
    [[], { steps: [{ kind: "consult", companion: "dieuphoi" }] }],
    [[], { steps: [{ kind: "teleport", companion: "nhatky" }] }],
    [[], { steps: [{ kind: "consult", companion: "nhatky", note: "x" }] }],
    [[], { steps: [1, 2, 3] }],
  ])("rejects an invented step, speaker or transfer %j %j", async (progress, extra) => {
    turn(progress, extra);
    await expect(consumeAIReply(URL, new AbortController().signal)).rejects.toMatchObject({ code: "INVALID_AI_EVENT" });
  });

  it("names a real consultation and a real transfer in plain words", () => {
    const base = { phase: "accepted" as const, requestKey: "k", runId: "r" };
    expect(deriveAIActivity({ ...base, consulting: { requester: "Điều phối", specialist: "Nhật ký" } }).label)
      .toBe("Điều phối đang hỏi Nhật ký một chút…");
    expect(deriveAIActivity({ ...base, consulting: { requester: "Điều phối", specialist: "Nhật ký", transfer: true } }).label)
      .toBe("Điều phối đang mời Nhật ký trò chuyện cùng bạn…");
  });
});
