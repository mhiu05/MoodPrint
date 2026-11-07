import type { ActionPlan, DemoUser, Incident } from "../../types";
export const personas: DemoUser[] = [
  { id: "USER-AN", nickname: "An", ageBand: "11–13", demo: true },
  { id: "USER-MINH", nickname: "Minh", ageBand: "14–17", demo: true },
  { id: "USER-HA", nickname: "Hà", ageBand: "14–17", demo: true },
  { id: "USER-LINH", nickname: "Linh", ageBand: "14–17", demo: true },
];
const date = "2026-11-07T09:00:00+07:00";
const makeCase = (
  ownerId: string,
  title: string,
  summary: string,
  index = 1,
): Incident => {
  const id = `CASE-${ownerId.replace("USER-", "")}-${String(index).padStart(3, "0")}`;
  return {
    id,
    ownerId,
    title,
    summary,
    template: "TPL-VERBAL",
    perspective: ownerId === "USER-LINH" ? "witness" : "self",
    categoryTags: ["Ở trường"],
    status: ownerId === "USER-HA" ? "monitoring" : "active",
    impactTags: ["Khó tập trung"],
    events: [
      {
        id: `EV-${id}-1`,
        caseId: id,
        when: "2026-11-04",
        timePrecision: "day",
        place: "Trong lớp",
        description: summary,
        provenance: "user_entered",
        evidenceIds: [],
        needsReview: false,
      },
    ],
    evidenceIds: [],
    linkedChatIds: [],
    linkedPlanId: index === 1 ? `PLAN-${ownerId}` : undefined,
    people: "Bạn cùng lớp (bí danh)",
    place: "Trong lớp",
    occurredAt: "2026-11-04",
    tried: "Đã đề nghị dừng lại",
    trustedPerson: "Một giáo viên mình tin tưởng",
    createdAt: date,
    updatedAt: date,
    demo: true,
  };
};
export const seedCases = [
  makeCase(
    "USER-AN",
    "Chuyện trong giờ ra chơi",
    "Một vài bạn gọi mình bằng biệt danh mình không thích. Chuyện đã lặp lại trong hai tuần.",
  ),
  makeCase(
    "USER-MINH",
    "Nhóm chat lớp",
    "Có lời trêu chọc trong nhóm chat. Mình muốn ghi lại để chuẩn bị nói với người lớn.",
  ),
  makeCase(
    "USER-MINH",
    "Chuyện ở hành lang",
    "Mình nghe một lời hẹn gặp sau giờ học và chưa rõ ý nghĩa.",
    2,
  ),
  makeCase(
    "USER-HA",
    "Nhóm làm bài tập",
    "Mình nhiều lần không được tham gia nhóm. Mình chưa biết lý do.",
  ),
  makeCase(
    "USER-LINH",
    "Điều mình chứng kiến",
    "Mình thấy một bạn ngồi riêng và muốn tìm cách hỗ trợ an toàn.",
  ),
];
export const seedPlans: ActionPlan[] = seedCases
  .filter((c) => c.linkedPlanId)
  .map((c) => ({
    id: c.linkedPlanId!,
    caseId: c.id,
    goal: "Chuẩn bị nói với một người mình tin tưởng",
    chosenOptionId: "trusted-adult",
    status: "active",
    items: [
      {
        id: `${c.id}-P1`,
        label: "Ghi lại điều mình nhớ rõ",
        status: "done",
        notes: "Đã ghi lại lần gần nhất.",
        priority: "normal",
        reason: "Giúp kể lại theo điều mình thực sự nhớ.",
      },
      {
        id: `${c.id}-P2`,
        label: "Chọn một người lớn mình tin tưởng",
        status: "not_started",
        notes: "",
        priority: "high",
        reason: "Bạn không cần xử lý chuyện này một mình.",
      },
      {
        id: `${c.id}-P3`,
        label: "Luyện một câu mở đầu",
        status: "not_started",
        notes: "",
        priority: "normal",
        reason: "Một lời mở đầu ngắn có thể giúp bạn dễ bắt đầu hơn.",
      },
    ],
    nextReviewDate: "2026-11-14",
    lastUpdated: date,
    demo: true,
  }));
