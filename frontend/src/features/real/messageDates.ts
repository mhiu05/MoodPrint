/** Calendar labels follow the account's timezone, including across DST changes. */
export function createMessageDateFormatter(timeZone: string, now: Date) {
  const dateFormat = new Intl.DateTimeFormat("vi-VN", {
    timeZone, day: "2-digit", month: "2-digit", year: "numeric",
  });
  const timeFormat = new Intl.DateTimeFormat("vi-VN", {
    timeZone, hour: "2-digit", minute: "2-digit", hourCycle: "h23",
  });
  const today = dateFormat.format(now);
  const parts = Object.fromEntries(dateFormat.formatToParts(now).map(part => [part.type, part.value]));
  const previousDay = new Date(Date.UTC(Number(parts.year), Number(parts.month) - 1, Number(parts.day) - 1));
  const yesterday = new Intl.DateTimeFormat("vi-VN", {
    timeZone: "UTC", day: "2-digit", month: "2-digit", year: "numeric",
  }).format(previousDay);

  return (createdAt?: string | null) => {
    if (!createdAt) return undefined;
    const date = new Date(createdAt);
    if (!Number.isFinite(date.getTime())) return undefined;
    const dayKey = dateFormat.format(date);
    return {
      dayKey,
      dayLabel: dayKey === today ? "Today" : dayKey === yesterday ? "Yesterday" : dayKey,
      time: timeFormat.format(date),
    };
  };
}
