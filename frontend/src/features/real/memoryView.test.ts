import { expect, it } from "vitest";
import { memoryBadge, sourceEntryLink } from "./memoryView";

it("labels automatic memories and links the exact local source day", () => {
  const sourceEntryId = "22222222-2222-4222-8222-222222222222";
  expect(memoryBadge("journal_auto")).toBe("Tự động từ nhật ký");
  expect(memoryBadge("approved")).toBeNull();
  expect(memoryBadge(undefined)).toBeNull();
  expect(sourceEntryLink({ origin: "journal_auto", sourceEntryId, sourceLocalDate: "2026-11-04" }))
    .toEqual({ to: `/self/entry/${sourceEntryId}`, label: "Xem trang 04/11/2026" });
  expect(sourceEntryLink({ origin: "approved", sourceEntryId, sourceLocalDate: "2026-11-04" })).toBeNull();
  expect(sourceEntryLink({ origin: "journal_auto", sourceEntryId, sourceLocalDate: null })).toBeNull();
});
