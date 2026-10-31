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

type TimelineMoment = { id: string; localDate: string; createdAt: string };

function fractionalSeconds(timestamp: string): string {
  // Pydantic/PostgreSQL retain microseconds that Date.parse rounds down.
  // Date.parse handles the offset; this breaks ties inside the same millisecond.
  return (timestamp.match(/\.(\d+)(?:Z|[+-]\d{2}:\d{2})$/i)?.[1] || "").padEnd(
    6,
    "0",
  );
}

/** Match the API's moment-date order; edits never change creation order. */
export function mergeTimelineEntries<T extends TimelineMoment>(
  previous: T[],
  incoming: T[],
): T[] {
  const unique = new Map(previous.map((entry) => [entry.id, entry]));
  for (const entry of incoming) unique.set(entry.id, entry);
  return [...unique.values()].sort(
    (a, b) =>
      b.localDate.localeCompare(a.localDate) ||
      Date.parse(b.createdAt) - Date.parse(a.createdAt) ||
      fractionalSeconds(b.createdAt).localeCompare(
        fractionalSeconds(a.createdAt),
      ) ||
      b.id.localeCompare(a.id),
  );
}

export function groupEntriesByMonth<T extends TimelineMoment>(items: T[]) {
  const groups: { key: string; label: string; items: T[] }[] = [];
  for (const item of items) {
    const key = item.localDate.slice(0, 7);
    const last = groups.at(-1);
    if (last?.key === key) last.items.push(item);
    else {
      const [year, month] = key.split("-");
      groups.push({
        key,
        label: `Tháng ${Number(month)}, ${year}`,
        items: [item],
      });
    }
  }
  return groups;
}
export function previousJournalDate(day: string): string {
  const date = new Date(`${day}T00:00:00Z`);
  date.setUTCDate(date.getUTCDate() - 1);
  return date.toISOString().slice(0, 10);
}
export function journalDayLabel(day: string, today: string): string {
  if (day === today) return "Hôm nay";
  if (day === previousJournalDate(today)) return "Hôm qua";
  return formatJournalDate(day);
}
export function groupEntriesByDay<T extends { localDate: string }>(
  items: T[],
  today: string,
) {
  const groups: {
    day: string;
    label: string;
    monthKey: string;
    monthLabel: string;
    items: T[];
  }[] = [];
  for (const item of items) {
    const [year, month] = item.localDate.split("-");
    const last = groups.at(-1);
    if (!last || last.day !== item.localDate)
      groups.push({
        day: item.localDate,
        label: journalDayLabel(item.localDate, today),
        monthKey: `${year}-${month}`,
        monthLabel: `Tháng ${Number(month)} năm ${year}`,
        items: [item],
      });
    else last.items.push(item);
  }
  return groups;
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
  "Hôm nay điều gì khiến bạn mỉm cười?",
  "Có điều gì khiến bạn suy nghĩ nhiều nhất?",
  "Bạn muốn cảm ơn bản thân vì điều gì?",
  "Điều gì khiến hôm nay đáng nhớ?",
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
