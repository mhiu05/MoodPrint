export type JournalFilters = {
  from?: string;
  to?: string;
  q?: string;
  mood?: string;
  media?: string;
  status?: string;
  offset?: number;
  limit?: number;
};
export function calendarDays(month: string): (string | null)[] {
  const [year, number] = month.split("-").map(Number);
  const start = new Date(Date.UTC(year, number - 1, 1));
  const count = new Date(Date.UTC(year, number, 0)).getUTCDate();
  const padding = (start.getUTCDay() + 6) % 7;
  const cells: (string | null)[] = Array(padding).fill(null);
  for (let day = 1; day <= count; day++)
    cells.push(`${month}-${String(day).padStart(2, "0")}`);
  while (cells.length % 7) cells.push(null);
  return cells;
}
export function entryQuery(filters: JournalFilters = {}): string {
  const query = new URLSearchParams({
    status: filters.status || "saved",
    offset: String(filters.offset || 0),
    limit: String(filters.limit || 12),
  });
  for (const field of ["from", "to", "q", "mood", "media"] as const) {
    const value = filters[field]?.trim();
    if (value) query.set(field, value);
  }
  return query.toString();
}
export function formatJournalDate(day: string): string {
  const [year, month, date] = day.split("-");
  return `${date}/${month}/${year}`;
}
export function toggleChoice(choices: string[], choice: string): string[] {
  return choices.includes(choice)
    ? choices.filter((value) => value !== choice)
    : choices.length < 12
      ? [...choices, choice]
      : choices;
}

export const journalMoodLabels = [
  "Rất tệ",
  "Hơi buồn",
  "Bình thường",
  "Khá vui",
  "Rất vui",
];
export const emotionChoices = [
  "Lo lắng",
  "Mệt mỏi",
  "Hào hứng",
  "Bình yên",
  "Biết ơn",
  "Cô đơn",
  "Tự hào",
  "Khác",
];
export const factorChoices = [
  "Học tập",
  "Công việc",
  "Bạn bè",
  "Gia đình",
  "Giấc ngủ",
  "Tình cảm",
  "Sức khỏe",
  "Khác",
];
export const writingPrompts = [
  "Hôm nay có điều gì khiến bạn mỉm cười?",
  "Có điều gì khiến bạn cảm thấy áp lực?",
  "Bạn đã học được điều gì hôm nay?",
  "Điều gì khiến bạn biết ơn?",
];

export function monthBounds(month: string) {
  const [year, number] = month.split("-").map(Number);
  return {
    from: `${month}-01`,
    to: `${month}-${new Date(Date.UTC(year, number, 0)).getUTCDate()}`,
  };
}

export function journalDateWindow(today: string) {
  const earliest = new Date(`${today}T00:00:00Z`);
  earliest.setUTCDate(earliest.getUTCDate() - 89);
  return { earliest: earliest.toISOString().slice(0, 10), today };
}
export function isActiveJournalDate(day: string, today: string): boolean {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(day)) return false;
  const parsed = new Date(`${day}T00:00:00Z`);
  return (
    !Number.isNaN(parsed.getTime()) &&
    parsed.toISOString().slice(0, 10) === day &&
    day >= journalDateWindow(today).earliest &&
    day <= today
  );
}
export function activeMonthBounds(month: string, today: string) {
  const bounds = monthBounds(month),
    { earliest } = journalDateWindow(today);
  return {
    from: bounds.from < earliest ? earliest : bounds.from,
    to: bounds.to > today ? today : bounds.to,
  };
}
