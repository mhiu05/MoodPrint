import type { SchoolReport } from "../../types";
const categories = [
  ["online", 15],
  ["verbal", 12],
  ["social", 10],
  ["physical", 6],
  ["other", 5],
] as const;
const statuses = [
  ...Array<string>(9).fill("new"),
  ...Array<string>(18).fill("reviewing"),
  ...Array<string>(13).fill("follow_up"),
  ...Array<string>(8).fill("closed"),
];
const summaries: Record<string, string> = {
  online:
    "Một nhóm tài khoản giả lập có lời bình luận khiến bạn học lo lắng. Cần lắng nghe thêm bối cảnh.",
  verbal: "Có ghi nhận lời trêu chọc lặp lại trong giờ ra chơi ở trường mẫu.",
  social:
    "Một học sinh giả lập cho biết nhiều lần không được tham gia hoạt động nhóm.",
  physical:
    "Bản ghi mẫu về xô đẩy trong khu vực chung. Cần ưu tiên người lớn hỗ trợ an toàn.",
  other:
    "Người chứng kiến giả lập muốn trao đổi với người hỗ trợ về tình huống chưa rõ.",
};
export const schoolSeed: SchoolReport[] = categories
  .flatMap(([category, count]) =>
    Array.from({ length: count }, (_, i) => ({ category, local: i })),
  )
  .map((r, i) => ({
    id: `SCHOOL-DEMO-${String(i + 1).padStart(3, "0")}`,
    category: r.category,
    date: `2026-${String(9 + (i % 3)).padStart(2, "0")}-${String(1 + ((i * 7) % 27)).padStart(2, "0")}`,
    group: ["Khối mẫu 6–7", "Khối mẫu 8–9", "Khối mẫu 10–12"][i % 3],
    status: statuses[i] as SchoolReport["status"],
    summary: summaries[r.category],
    handledByRole: i % 2 ? "Tổ hỗ trợ mẫu" : "Giáo viên phụ trách mẫu",
    notes: "",
    demo: true,
  }));
export function filterReports(
  reports: SchoolReport[],
  filter: { month: string; category: string; status: string },
) {
  return reports.filter(
    (r) =>
      (!filter.month || r.date.startsWith(filter.month)) &&
      (!filter.category || r.category === filter.category) &&
      (!filter.status || r.status === filter.status),
  );
}
export function aggregateReports(reports: SchoolReport[]) {
  const categories: Record<string, number> = {
    online: 0,
    verbal: 0,
    social: 0,
    physical: 0,
    other: 0,
  };
  const statuses: Record<string, number> = {
    new: 0,
    reviewing: 0,
    follow_up: 0,
    closed: 0,
  };
  const months: Record<string, number> = {
    "2026-09": 0,
    "2026-10": 0,
    "2026-11": 0,
  };
  for (const r of reports) {
    categories[r.category]++;
    statuses[r.status]++;
    months[r.date.slice(0, 7)]++;
  }
  return { total: reports.length, categories, statuses, months };
}
