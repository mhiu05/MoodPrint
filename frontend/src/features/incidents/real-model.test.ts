import { describe, expect, it } from "vitest";
import { createCaseDraft, incidentFromDraft, mergeCaseEdits } from "./model";

describe("real case persistence", () => {
  it("keeps UUID event identity and draft version across retries", () => {
    const draft = {
      ...createCaseDraft(),
      summary: "Synthetic",
      firstEventId: crypto.randomUUID(),
      baseVersion: 3,
    };
    const id = crypto.randomUUID();
    const first = incidentFromDraft(draft, id, crypto.randomUUID(), "active");
    const second = incidentFromDraft(draft, id, first.ownerId, "active");
    expect(first.events[0].id).toBe(draft.firstEventId);
    expect(second.events[0].id).toBe(first.events[0].id);
    expect(second.version).toBe(3);
  });
  it("retains another tab's untouched fields when explicitly retrying edits", () => {
    const base = incidentFromDraft(
      { ...createCaseDraft(), summary: "Old" },
      "CASE-X",
      "USER-X",
      "active",
    );
    const edited = { ...base, title: "My edit" };
    const latest = { ...base, summary: "Another tab", version: 4 };
    const merged = mergeCaseEdits(base, edited, latest);
    expect(merged.title).toBe("My edit");
    expect(merged.summary).toBe("Another tab");
    expect(merged.version).toBe(4);
  });
});
