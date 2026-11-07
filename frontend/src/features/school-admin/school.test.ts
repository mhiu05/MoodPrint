import { describe, expect, it } from "vitest";
import { schoolSeed, aggregateReports, filterReports } from "./school-data";
describe("independent synthetic school reports", () => {
  it("has 48 reports with matching category and status aggregates", () => {
    expect(schoolSeed).toHaveLength(48);
    const stats = aggregateReports(schoolSeed);
    expect(stats.categories).toEqual({
      online: 15,
      verbal: 12,
      social: 10,
      physical: 6,
      other: 5,
    });
    expect(stats.statuses).toEqual({
      new: 9,
      reviewing: 18,
      follow_up: 13,
      closed: 8,
    });
    expect(schoolSeed.some((r) => "ownerId" in r || "studentCaseId" in r)).toBe(
      false,
    );
  });
  it("filters the same collection used by charts and lists", () => {
    const filtered = filterReports(schoolSeed, {
      month: "2026-10",
      category: "online",
      status: "",
    });
    expect(
      filtered.every(
        (r) => r.date.startsWith("2026-10") && r.category === "online",
      ),
    ).toBe(true);
    expect(aggregateReports(filtered).total).toBe(filtered.length);
  });
});
