import { describe, expect, it } from "vitest";
import {
  calendarDays,
  entryQuery,
  formatJournalDate,
  groupEntriesByDay,
  journalDayLabel,
  toggleChoice,
  journalDateWindow,
  isActiveJournalDate,
  activeMonthBounds,
  mergeTimelineEntries,
  groupEntriesByMonth,
} from "./journalModel";

describe("journal dates and browsing", () => {
  it("preserves PostgreSQL microseconds before falling back to IDs", () => {
    const rows = [
      {
        id: "z",
        localDate: "2026-10-23",
        createdAt: "2026-10-23T08:00:00.123001Z",
      },
      {
        id: "a",
        localDate: "2026-10-23",
        createdAt: "2026-10-23T15:00:00.123999+07:00",
      },
      {
        id: "b",
        localDate: "2026-10-23",
        createdAt: "2026-10-23T08:00:00.123999Z",
      },
    ];
    expect(mergeTimelineEntries([], rows).map((row) => row.id)).toEqual([
      "b",
      "a",
      "z",
    ]);
  });
  it("orders actual moment days then creation instants and IDs, never edit times", () => {
    const rows = [
      { id: "a", localDate: "2026-09-30", createdAt: "2026-10-30T12:00:00Z" },
      { id: "b", localDate: "2026-10-01", createdAt: "2026-10-01T12:00:00Z" },
      { id: "c", localDate: "2026-10-01", createdAt: "2026-10-01T12:00:00Z" },
      {
        id: "d",
        localDate: "2026-10-01",
        createdAt: "2026-10-01T14:00:00+07:00",
      },
    ];
    expect(mergeTimelineEntries([], rows).map((row) => row.id)).toEqual([
      "c",
      "b",
      "d",
      "a",
    ]);
    expect(rows[0].id).toBe("a");
  });
  it("deduplicates overlapping pages, keeping the latest fetched version and grouping months once", () => {
    const first = [
      {
        id: "b",
        localDate: "2026-10-23",
        createdAt: "2026-10-23T08:00:00Z",
        text: "old",
      },
      {
        id: "a",
        localDate: "2026-09-30",
        createdAt: "2026-09-30T08:00:00Z",
        text: "September",
      },
    ];
    const merged = mergeTimelineEntries(first, [
      { ...first[0], text: "edited" },
      {
        id: "c",
        localDate: "2025-10-23",
        createdAt: "2025-10-23T08:00:00Z",
        text: "last year",
      },
    ]);
    expect(merged).toHaveLength(3);
    expect(merged[0].text).toBe("edited");
    const groups = groupEntriesByMonth(merged);
    expect(groups.map((group) => group.label)).toEqual([
      "Tháng 10, 2026",
      "Tháng 9, 2026",
      "Tháng 10, 2025",
    ]);
    expect(groupEntriesByMonth([])).toEqual([]);
  });
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
  it("groups a personal timeline by account-local day without inventing missing days", () => {
    expect(journalDayLabel("2026-10-23", "2026-10-23")).toBe("Hôm nay");
    expect(journalDayLabel("2026-10-22", "2026-10-23")).toBe("Hôm qua");
    const groups = groupEntriesByDay(
      [
        { localDate: "2026-10-23", id: "b" },
        { localDate: "2026-10-23", id: "a" },
        { localDate: "2026-09-30", id: "c" },
      ],
      "2026-10-23",
    );
    expect(groups.map((group) => group.label)).toEqual([
      "Hôm nay",
      "30/09/2026",
    ]);
    expect(groups[0].items.map((item) => item.id)).toEqual(["b", "a"]);
    expect(groups[0].monthLabel).toBe("Tháng 10 năm 2026");
    expect(groups[1].monthKey).toBe("2026-09");
  });
});
