import { afterEach, describe, expect, it, vi } from "vitest";
import { consumeGroupTurn, type GroupEvent } from "./groupEvents";

const URL = "/api/v1/ai/groups/g-1/turns/t-1/events";
const bubble = { messageId: "00000000-0000-4000-8000-000000000001", partIndex: 0, text: "Mình nghe đây.", cards: [] };

function serve(events: { seq: string; type: string; data: unknown }[]) {
  const body = events.map((event) => `id: ${event.seq}\ndata: ${JSON.stringify({ version: "ai-group-events-v1", ...event })}\n\n`).join("");
  const fetchMock = vi.fn().mockResolvedValue(new Response(body, { headers: { "Content-Type": "text/event-stream" } }));
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

afterEach(() => vi.unstubAllGlobals());

const turn = [
  { seq: "1", type: "turn_started", data: { turnId: "t-1" } },
  { seq: "2", type: "agent_selected", data: { agent: "nhatky", ordinal: 0 } },
  { seq: "3", type: "agent_started", data: { agent: "nhatky", ordinal: 0 } },
  { seq: "4", type: "agent_message", data: { agent: "nhatky", ordinal: 0, messages: [bubble] } },
  { seq: "5", type: "turn_completed", data: {} },
];

describe("ai-group-events-v1", () => {
  it("delivers real speaker events in order and ends at the terminal event", async () => {
    serve(turn);
    const seen: GroupEvent[] = [];
    const result = await consumeGroupTurn(URL, new AbortController().signal, (event) => seen.push(event));
    expect(result).toEqual({ outcome: "completed", lastSeq: 5 });
    expect(seen.map((event) => event.type)).toEqual(["turn_started", "agent_selected", "agent_started", "agent_message", "turn_completed"]);
  });

  it("resumes after a cursor without repeating events", async () => {
    const fetchMock = serve(turn);
    const seen: GroupEvent[] = [];
    await consumeGroupTurn(URL, new AbortController().signal, (event) => seen.push(event), 3);
    expect(fetchMock.mock.calls[0][0]).toBe(`${URL}?afterSeq=3`);
    expect(seen.map((event) => event.type)).toEqual(["agent_message", "turn_completed"]);
  });

  it.each([
    [{ seq: "2", type: "agent_selected", data: { agent: "may", ordinal: 0 } }],
    [{ seq: "2", type: "agent_message", data: { agent: "nhatky", ordinal: 0, messages: [] } }],
    [{ seq: "2", type: "agent_started", data: { agent: "nhatky", ordinal: 7 } }],
    [{ seq: "3", type: "turn_completed", data: {} }],
    [{ seq: "2", type: "token", data: { text: "x" } }],
  ])("rejects invented speakers, empty or out-of-order events %j", async (event) => {
    serve([turn[0], event]);
    await expect(consumeGroupTurn(URL, new AbortController().signal, () => undefined)).rejects.toMatchObject({ code: "INVALID_AI_EVENT" });
  });
});
