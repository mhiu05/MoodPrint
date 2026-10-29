import { describe, expect, it } from "vitest";
import {
  calendarDays,
  entryQuery,
  formatJournalDate,
  toggleChoice,
  journalDateWindow,
  isActiveJournalDate,
  activeMonthBounds,
} from "./journalModel";

describe("journal dates and browsing", () => {
  it("places October 2026 on a Monday-first calendar without inventing days", () => {
    const cells = calendarDays("2026-10");
    expect(cells.slice(0, 5)).toEqual([
      null,
      null,
      null,
      "2026-10-01",
      "2026-10-02",
    ]);
    expect(cells.filter(Boolean)).toHaveLength(31);
    expect(cells.at(-1)).toBe(null);
    expect(formatJournalDate("2026-10-28")).toContain("28/10/2026");
  });
  it("keeps leap day and encodes only active server filters", () => {
    expect(calendarDays("2028-02").filter(Boolean)).toHaveLength(29);
    const query = new URLSearchParams(
      entryQuery({
        q: "một ngày & nắng",
        mood: "4",
        media: "image",
        offset: 12,
      }),
    );
    expect(query.get("q")).toBe("một ngày & nắng");
    expect(query.get("mood")).toBe("4");
    expect(query.get("media")).toBe("image");
    expect(query.get("offset")).toBe("12");
    expect(query.get("status")).toBe("saved");
    expect(query.has("from")).toBe(false);
  });
  it("toggles selections without replacing the other emotions", () => {
    expect(toggleChoice(["Lo lắng"], "Mệt mỏi")).toEqual([
      "Lo lắng",
      "Mệt mỏi",
    ]);
    expect(toggleChoice(["Lo lắng", "Mệt mỏi"], "Lo lắng")).toEqual([
      "Mệt mỏi",
    ]);
  });
  it("limits entries and calendar requests to the account's active 90 days", () => {
    expect(journalDateWindow("2026-10-23")).toEqual({
      earliest: "2026-07-26",
      today: "2026-10-23",
    });
    expect(isActiveJournalDate("2026-10-24", "2026-10-23")).toBe(false);
    expect(isActiveJournalDate("2026-07-25", "2026-10-23")).toBe(false);
    expect(isActiveJournalDate("2026-10-23", "2026-10-23")).toBe(true);
    expect(isActiveJournalDate("2026-02-31", "2026-03-10")).toBe(false);
    expect(activeMonthBounds("2026-07", "2026-10-23")).toEqual({
      from: "2026-07-26",
      to: "2026-07-31",
    });
  });
});
