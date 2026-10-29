import { describe, expect, it } from "vitest";
import { deriveAIActivity } from "./aiActivityView";

describe("deriveAIActivity", () => {
  it("shows sending text before acceptance, without an orb", () => {
    expect(deriveAIActivity({ phase: "submitting", requestKey: "intent-1" })).toEqual({
      label: "Đang gửi tin nhắn…", busy: true, orbState: null,
    });
  });

  it("runs the working orb only for an accepted run with current identity", () => {
    expect(deriveAIActivity({ phase: "accepted", requestKey: "intent-1", runId: "run-1" })).toEqual({
      label: "Đang trả lời…", busy: true, orbState: "working",
    });
  });

  it("never animates an accepted phase that is missing its request or run identity", () => {
    for (const input of [
      { phase: "accepted" as const, requestKey: "intent-1" },
      { phase: "accepted" as const, runId: "run-1" },
      { phase: "accepted" as const },
    ]) {
      const view = deriveAIActivity(input);
      expect(view.orbState).toBeNull();
      expect(view.busy).toBe(true);
      expect(view.label).toBe("Đang kiểm tra trạng thái cuộc trò chuyện…");
    }
  });

  it("uses static text while a stop is requested or the conversation is reconciled", () => {
    expect(deriveAIActivity({ phase: "cancelling", requestKey: "k", runId: "r" })).toEqual({
      label: "Đang yêu cầu dừng…", busy: true, orbState: null,
    });
    expect(deriveAIActivity({ phase: "reconciling", requestKey: "k", runId: "r" })).toEqual({
      label: "Đang kiểm tra trạng thái cuộc trò chuyện…", busy: true, orbState: null,
    });
  });

  it("stops every visual and busy state at terminal phases", () => {
    expect(deriveAIActivity({ phase: "idle" })).toEqual({ label: null, busy: false, orbState: null });
    expect(deriveAIActivity({ phase: "completed", runId: "r" })).toEqual({ label: null, busy: false, orbState: null });
    expect(deriveAIActivity({ phase: "cancelled", runId: "r" })).toEqual({ label: "Đã dừng phản hồi.", busy: false, orbState: null });
    expect(deriveAIActivity({ phase: "failed", runId: "r" })).toEqual({ label: null, busy: false, orbState: null });
    expect(deriveAIActivity({ phase: "unavailable" })).toEqual({ label: null, busy: false, orbState: null });
  });

  it("never names an invented stage such as searching or thinking", () => {
    const labels = (["idle", "submitting", "accepted", "cancelling", "reconciling", "completed", "cancelled", "failed", "unavailable"] as const)
      .map((phase) => deriveAIActivity({ phase, requestKey: "k", runId: "r" }).label ?? "");
    expect(labels.join(" ")).not.toMatch(/tìm|suy nghĩ|phân tích|đang đọc|%/i);
  });
});
