import { describe, expect, it } from "vitest";
import type { ActionPlan } from "../../types";
import { mergePlanDraft, movePlanItem, validatePlan } from "./model";

const plan: ActionPlan = {
  id: "P-1",
  caseId: "C-1",
  goal: "Chuẩn bị lời nhắn",
  chosenOptionId: "manual",
  status: "active",
  nextReviewDate: "",
  lastUpdated: "",
  demo: true,
  items: [
    {
      id: "A",
      label: "Chọn người hỗ trợ",
      status: "done",
      notes: "Mình chọn cô giáo.",
      priority: "high",
      reason: "Để không tự xử lý.",
    },
    {
      id: "B",
      label: "Ghi lại điều muốn nói",
      status: "not_started",
      notes: "",
      priority: "normal",
      reason: "",
    },
    {
      id: "C",
      label: "Luyện nói",
      status: "doing",
      notes: "",
      priority: "normal",
      reason: "",
    },
  ],
};
describe("plan state invariants", () => {
  it("merges independent local step progress with a different step changed in Home", () => {
    const draft = {
      ...plan,
      goal: "Mục tiêu mới",
      items: plan.items.map((item) =>
        item.id === "B"
          ? { ...item, status: "doing" as const, notes: "Đang chuẩn bị." }
          : item,
      ),
    };
    const latest = {
      ...plan,
      items: plan.items.map((item) =>
        item.id === "C" ? { ...item, status: "done" as const } : item,
      ),
    };
    const merged = mergePlanDraft(plan, draft, latest);
    expect(merged.goal).toBe("Mục tiêu mới");
    expect(merged.items[1].status).toBe("doing");
    expect(merged.items[1].notes).toBe("Đang chuẩn bị.");
    expect(merged.items[2].status).toBe("done");
    expect(plan.items[1].status).toBe("not_started");
  });
  it("reorders steps without losing completion, notes, or priority", () => {
    const reordered = movePlanItem(plan.items, "A", 1);
    expect(reordered.map((item) => item.id)).toEqual(["B", "A", "C"]);
    expect(reordered[1]).toEqual(plan.items[0]);
    expect(plan.items.map((item) => item.id)).toEqual(["A", "B", "C"]);
  });
  it("prevents completion with unfinished steps", () => {
    expect(validatePlan({ ...plan, status: "completed" })).toBeTruthy();
    expect(
      validatePlan({
        ...plan,
        status: "completed",
        items: plan.items.map((item) => ({ ...item, status: "done" })),
      }),
    ).toBe("");
  });
  it("rejects an empty goal or empty checklist", () => {
    expect(validatePlan({ ...plan, goal: " " })).toBeTruthy();
    expect(validatePlan({ ...plan, items: [] })).toBeTruthy();
  });
});
