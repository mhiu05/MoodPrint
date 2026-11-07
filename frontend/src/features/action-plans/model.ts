import type { ActionPlan, PlanItem } from "../../types";
export function mergePlanDraft(
  base: ActionPlan | null,
  draft: ActionPlan,
  latest: ActionPlan,
): ActionPlan {
  const merged = { ...latest, ...draft, lastUpdated: latest.lastUpdated };
  for (const key of [
    "goal",
    "chosenOptionId",
    "status",
    "nextReviewDate",
    "outcomeNotes",
  ] as const) {
    if (base && draft[key] === base[key])
      Object.assign(merged, { [key]: latest[key] });
  }
  merged.items = draft.items.flatMap((step) => {
    const current = latest.items.find((i) => i.id === step.id);
    const original = base?.items.find((i) => i.id === step.id);
    if (!current)
      return original && JSON.stringify(step) === JSON.stringify(original)
        ? []
        : [step];
    const item = {
      ...step,
      status:
        original && current.status === original.status
          ? step.status
          : current.status,
    };
    for (const field of ["label", "notes", "priority", "reason"] as const) {
      if (original && step[field] === original[field])
        Object.assign(item, { [field]: current[field] });
    }
    return [item];
  });
  merged.items.push(
    ...latest.items.filter(
      (step) =>
        !draft.items.some((i) => i.id === step.id) &&
        !base?.items.some((i) => i.id === step.id),
    ),
  );
  return merged;
}
export const movePlanItem = (
  items: PlanItem[],
  id: string,
  direction: -1 | 1,
): PlanItem[] => {
  const index = items.findIndex((item) => item.id === id);
  if (index < 0 || index + direction < 0 || index + direction >= items.length)
    return items;
  const next = [...items];
  [next[index], next[index + direction]] = [
    next[index + direction],
    next[index],
  ];
  return next;
};
export const validatePlan = (plan: ActionPlan): string => {
  if (!plan.goal.trim()) return "Bạn hãy đặt một mục tiêu nhỏ cho kế hoạch.";
  if (!plan.items.length || plan.items.some((item) => !item.label.trim()))
    return "Kế hoạch cần ít nhất một bước có nội dung.";
  if (
    plan.status === "completed" &&
    plan.items.some((item) => item.status !== "done")
  )
    return "Vẫn còn bước chưa hoàn tất. Bạn có thể tiếp tục hoặc tạm dừng kế hoạch.";
  return "";
};
