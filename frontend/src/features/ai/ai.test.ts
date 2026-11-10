import { describe, expect, it } from "vitest";
import {
  buildConfirmedTimeline,
  correctEvidence,
  createFixtureEvidence,
} from "./analysis-model";
import {
  chatFixtures,
  scenarios,
  roleplayScripts,
  getRoleplayPrompt,
} from "../../mocks/scenarios";

describe("analysis review contract", () => {
  it("excludes every unconfirmed or rejected source from the case timeline", () => {
    const evidence = createFixtureEvidence("analysis-1", "multi");
    expect(buildConfirmedTimeline("case-1", evidence, [])).toEqual([]);
    const confirmed = evidence.map((item, index) => ({
      ...item,
      reviewStatus:
        index === 0 ? ("confirmed" as const) : ("unreviewed" as const),
    }));
    expect(
      buildConfirmedTimeline("case-1", confirmed, [confirmed[0].id]),
    ).toHaveLength(1);
    expect(
      buildConfirmedTimeline("case-1", confirmed, [confirmed[1].id]),
    ).toHaveLength(0);
  });
  it("keeps the original source immutable after a correction", () => {
    const source = createFixtureEvidence("analysis-1", "multi")[0];
    const corrected = correctEvidence(source, "Nội dung mình đã kiểm tra");
    expect(corrected.originalText).toBe(
      "Một bạn gọi Minh bằng biệt danh Minh không thích.",
    );
    expect(source.userEditedText).toBeUndefined();
    expect(corrected.userEditedText).toBe("Nội dung mình đã kiểm tra");
    expect(corrected.reviewStatus).toBe("corrected");
  });
  it("does not count the duplicate screenshot as another event", () => {
    const evidence = createFixtureEvidence("analysis-1", "duplicate").map(
      (item) => ({ ...item, reviewStatus: "confirmed" as const }),
    );
    const events = buildConfirmedTimeline(
      "case-1",
      evidence,
      evidence.map((item) => item.id),
    );
    expect(events).toHaveLength(7);
    expect(events.flatMap((event) => event.evidenceIds)).toContain(
      "analysis-1-MEDIA-08",
    );
    expect(events[6].evidenceIds).toEqual([
      "analysis-1-MEDIA-07",
      "analysis-1-MEDIA-08",
    ]);
  });
  it("preserves a distinct user correction on the near-duplicate source", () => {
    const evidence = createFixtureEvidence("analysis-1", "duplicate")
      .slice(6)
      .map((item) => ({ ...item, reviewStatus: "confirmed" as const }));
    evidence[1] = {
      ...evidence[1],
      userEditedText: "Tin nhắn khác mà mình đã kiểm tra lại.",
    };
    const events = buildConfirmedTimeline(
      "case-1",
      evidence,
      evidence.map((item) => item.id),
    );
    expect(events).toHaveLength(2);
    expect(events[1].description).toBe(
      "Tin nhắn khác mà mình đã kiểm tra lại.",
    );
    expect(events[1].needsReview).toBe(true);
  });
});

describe("scripted conversation coverage", () => {
  it("offers 30 selectable scenarios and 12 finite, multi-turn chat fixtures", () => {
    expect(scenarios).toHaveLength(30);
    expect(new Set(scenarios.map((item) => item.id)).size).toBe(30);
    expect(chatFixtures).toHaveLength(12);
    for (const fixture of chatFixtures) {
      expect(fixture.messages.length).toBeGreaterThanOrEqual(4);
      expect(fixture.messages.length).toBeLessThanOrEqual(8);
      expect(
        fixture.messages.some(
          (message) => message.speaker === "ai" && message.body.includes("?"),
        ),
      ).toBe(true);
      expect(fixture.unknowns.length).toBeGreaterThan(0);
    }
  });
  it("offers six roleplay scripts with at least three user practice turns", () => {
    expect(roleplayScripts).toHaveLength(6);
    for (const script of roleplayScripts)
      expect(script.replies.length).toBeGreaterThanOrEqual(3);
  });
  it("changes the practice prompt to reflect the chosen tone while keeping the same question", () => {
    const script = roleplayScripts[0];
    expect(getRoleplayPrompt(script, 0, "neutral")).toBe(script.prompts[0]);
    expect(getRoleplayPrompt(script, 0, "gentle")).toContain(
      "cô đang lắng nghe",
    );
    expect(getRoleplayPrompt(script, 0, "respectfully_challenging")).toContain(
      "kiểm tra rõ",
    );
    expect(getRoleplayPrompt(script, 0, "respectfully_challenging")).toContain(
      script.prompts[0],
    );
  });
});
