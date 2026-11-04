import { expect, it } from "vitest";
import { normalizePromptOptions, selectionKey, acceptSelection, skillChipLabel, type SelectionState } from "./promptOptions";

it("labels skills from capabilities and preserves unknown ids as a fallback", () => {
  const skills = [{ id: "weekly-review", name: "Nhìn lại tuần", description: "Nhìn lại tuần đã ghi.", available: true }];
  expect(skillChipLabel(skills, "weekly-review")).toBe("Nhìn lại tuần");
  expect(skillChipLabel(skills, "future-skill")).toBe("future-skill");
});

it("normalizes a one-turn skill and deduplicates tools for retry digest", () => {
  expect(normalizePromptOptions({ skillId: "hangout", tools: ["web_search", "maps_search", "web_search"], area: "  Quận 3 " }))
    .toEqual({ skillId: "hangout", tools: ["maps_search", "web_search"], area: "Quận 3" });
  expect(selectionKey({})).toBe(selectionKey({ tools: [] }));
});
it("accepted clears only submitted revision; new prompt selection survives", () => {
  const submitted: SelectionState = { revision: 1, options: { skillId: "hangout" } };
  expect(acceptSelection(submitted, 1).options).toEqual({});
  const next: SelectionState = { revision: 2, options: { skillId: "learn-new-thing" } };
  expect(acceptSelection(next, 1)).toBe(next);
});
it("drops blank area, keeps a reuse id and keys selections independent of order", () => {
  expect(normalizePromptOptions({ tools: [], area: "   " })).toEqual({});
  const id = "00000000-0000-4000-8000-000000000001";
  expect(normalizePromptOptions({ mapsSearchId: id, area: " Quận  3 " })).toEqual({ mapsSearchId: id, area: "Quận 3" });
  expect(selectionKey({ tools: ["web_search", "maps_search"] })).toBe(selectionKey({ tools: ["maps_search", "web_search"] }));
  expect(selectionKey({ skillId: "hangout" })).not.toBe(selectionKey({ skillId: "learn-new-thing" }));
});
it("a rejected or unknown send keeps the frozen selection for an explicit retry", () => {
  const frozen: SelectionState = { revision: 4, options: { tools: ["web_search"] } };
  // Only an accepted send (202) clears; anything else leaves the same object and revision.
  expect(acceptSelection(frozen, 3)).toBe(frozen);
  expect(selectionKey(frozen.options)).toBe(selectionKey({ tools: ["web_search", "web_search"] }));
});
