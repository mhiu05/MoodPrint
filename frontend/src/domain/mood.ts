import type { Mood } from "./types";
export const demoDate = (clock: number) =>
  new Date(clock + 7 * 3600000).toISOString().slice(0, 10);
export function moodSummary(entries: Mood[], clock: number) {
  const end = demoDate(clock);
  const buckets = Array.from({ length: 7 }, (_, i) => {
    const date = new Date(Date.parse(end + "T00:00:00Z") - (6 - i) * 86400000)
      .toISOString()
      .slice(0, 10);
    const items = entries
      .filter((x) => x.date === date)
      .sort((a, b) => b.time - a.time || (a.id < b.id ? 1 : -1));
    return { date, entry: items[0] ?? null };
  });
  const points = buckets.flatMap((x) => (x.entry ? [x.entry.value] : []));
  return {
    buckets,
    count: points.length,
    mean: points.length
      ? points.reduce((a, b) => a + b, 0) / points.length
      : null,
    min: points.length ? Math.min(...points) : null,
    max: points.length ? Math.max(...points) : null,
  };
}
