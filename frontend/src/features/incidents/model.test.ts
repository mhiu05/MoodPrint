import { describe, expect, it } from "vitest";
import {
  caseSummary,
  createCaseDraft,
  incidentFromDraft,
  validateCaseDraft,
} from "./model";

describe("incident draft validation and honest summaries", () => {
  it("allows an unknown date without inventing a timestamp", () => {
    const draft = {
      ...createCaseDraft(),
      title: "Nhóm chat",
      summary: "Có lời trêu chọc.",
      timePrecision: "unknown" as const,
    };
    expect(validateCaseDraft(draft, false)).toEqual({});
    const saved = incidentFromDraft(draft, "CASE-TEST", "USER-TEST", "active");
    expect(saved.occurredAt).toBe("");
    expect(saved.events[0].timePrecision).toBe("unknown");
    expect(saved.events[0].when).toBe("");
  });
  it("requires a description for a case while allowing a partial draft", () => {
    const draft = { ...createCaseDraft(), title: "Bản nháp" };
    expect(validateCaseDraft(draft, false).summary).toBeTruthy();
    expect(validateCaseDraft(draft, true)).toEqual({});
  });
  it("keeps mock extracted and uncertain events out of the confirmed section", () => {
    const item = incidentFromDraft(
      {
        ...createCaseDraft(),
        title: "Mẫu",
        summary: "Điều mình nhớ.",
        timePrecision: "unknown",
      },
      "CASE-TEST",
      "USER-TEST",
      "active",
    );
    item.events.push({
      id: "MOCK-1",
      caseId: item.id,
      when: "2026-11-01",
      timePrecision: "day",
      place: "",
      description: "Chi tiết ảnh chưa kiểm tra",
      provenance: "mock_extracted",
      evidenceIds: ["E-1"],
      needsReview: true,
    });
    const text = caseSummary(item, []);
    const uncertainStart = text.indexOf("ĐIỀU CHƯA RÕ / CẦN KIỂM TRA");
    expect(uncertainStart).toBeGreaterThan(0);
    expect(text.indexOf("Chi tiết ảnh chưa kiểm tra")).toBeGreaterThan(
      uncertainStart,
    );
    expect(text).toContain("Chưa rõ thời gian");
  });
});
