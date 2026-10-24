import { afterEach, describe, expect, it, vi } from "vitest";
import { consumeAIEvents } from "./stream";

function stream(final: unknown, sequence = "1") {
  const body = `data: ${JSON.stringify({ version: "ai-events-v1", seq: sequence, type: "final", data: final })}\n\ndata: ${JSON.stringify({ version: "ai-events-v1", seq: String(BigInt(sequence) + 1n), type: "completed", data: {} })}\n\n`;
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(
      new Response(body, {
        headers: { "Content-Type": "text/event-stream" },
      }),
    ),
  );
  return consumeAIEvents(
    "/api/v1/ai/runs/123/events",
    new AbortController().signal,
  );
}

afterEach(() => vi.unstubAllGlobals());
describe("validated AI stream", () => {
  it("accepts only typed navigation cards after completion", async () => {
    await expect(
      stream({
        text: "Hello",
        cards: [
          { kind: "mood_form" },
          { kind: "navigate_bot", botId: "guong" },
        ],
      }),
    ).resolves.toEqual({
      text: "Hello",
      cards: [{ kind: "mood_form" }, { kind: "navigate_bot", botId: "guong" }],
    });
  });
  it.each([
    { text: "Hello", cards: [{ kind: "save_memory", text: "forged" }] },
    { text: "Hello", cards: [{ kind: "navigate_bot", botId: "unknown" }] },
    { text: "Saved", cards: [], receipt: { status: "succeeded" } },
    { text: "x".repeat(6001), cards: [] },
  ])("rejects untrusted final output %#", async (value) => {
    await expect(stream(value)).rejects.toMatchObject({
      code: "INVALID_AI_EVENT",
    });
  });
  it("rejects a missing event instead of displaying an incomplete result", async () => {
    await expect(
      stream({ text: "Hello", cards: [] }, "2"),
    ).rejects.toMatchObject({ code: "INVALID_AI_EVENT" });
  });
  it("distinguishes an interrupted durable turn from a retryable provider failure", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          new Response(
            `data: ${JSON.stringify({ version: "ai-events-v1", seq: "1", type: "failed", data: { code: "AI_INTERRUPTED" } })}\n\n`,
            { headers: { "Content-Type": "text/event-stream" } },
          ),
        ),
    );
    await expect(
      consumeAIEvents(
        "/api/v1/ai/runs/123/events",
        new AbortController().signal,
      ),
    ).rejects.toMatchObject({ code: "RUN_INTERRUPTED" });
  });
});
