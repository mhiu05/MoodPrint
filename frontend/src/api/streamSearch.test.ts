import { afterEach, expect, it, vi } from "vitest";
import { consumeAISearchReply } from "./stream";

afterEach(() => vi.unstubAllGlobals());
const citation = { sourceId: "s1", title: "Nguồn", url: "https://example.org/article", start: 2, end: 5 };
function serve(citations: unknown[] = [citation]) {
  const body = [{ type: "final", data: { partCount: 1, messages: [{ messageId: "m1", partIndex: 0,
    text: "😀 ơi!", cards: [], citations }], speaker: "hoatdong", steps: [] } },
    { type: "completed", data: {} }].map((e, i) => `data: ${JSON.stringify({ version: "ai-events-v3", seq: `${i+1}`, ...e })}\n\n`).join("");
  const fetch = vi.fn().mockResolvedValue(new Response(body, { headers: { "Content-Type": "text/event-stream" } }));
  vi.stubGlobal("fetch", fetch);
  return fetch;
}
it("negotiates v3 and preserves citations, speaker and steps", async () => {
  const fetch = serve();
  const result = await consumeAISearchReply("/api/v1/ai/runs/run1/events", new AbortController().signal);
  expect(fetch.mock.calls[0][0]).toContain("protocol=3");
  expect(result.messages[0].citations).toEqual([citation]);
  expect(result.speaker).toBe("hoatdong");
});
it.each(["https://localhost/a", "javascript:alert(1)", "https://127.0.0.1/", "https://user:pass@example.org/"])("rejects unsafe source %s", async (url) => {
  serve([{ ...citation, url }]);
  await expect(consumeAISearchReply("/api/v1/ai/runs/r1/events", new AbortController().signal)).rejects.toMatchObject({ code: "INVALID_AI_EVENT" });
});
it("rejects offsets outside codepoint length", async () => {
  serve([{ ...citation, end: 6 }]);
  await expect(consumeAISearchReply("/api/v1/ai/runs/r1/events", new AbortController().signal)).rejects.toMatchObject({ code: "INVALID_AI_EVENT" });
});
