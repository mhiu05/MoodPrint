/** Pure helpers for the check-in schedule page; no network, no storage. */

export type Slot = "morning" | "evening";
export type RepeatKind = "daily" | "weekdays" | "weekend" | "custom";

export const BOT_ORDER = ["nhip", "rure", "may", "guong", "caunoi"] as const;
export const WEEKDAY_SHORT = ["T2", "T3", "T4", "T5", "T6", "T7", "CN"];
const WEEKDAY_LONG = ["thứ Hai", "thứ Ba", "thứ Tư", "thứ Năm", "thứ Sáu", "thứ Bảy", "Chủ nhật"];
const PRESETS: Record<Exclude<RepeatKind, "custom">, number[]> = {
  daily: [1, 2, 3, 4, 5, 6, 7],
  weekdays: [1, 2, 3, 4, 5],
  weekend: [6, 7],
};
const ZONE_NAMES: Record<string, string> = {
  "Asia/Ho_Chi_Minh": "Việt Nam",
  "Asia/Saigon": "Việt Nam",
  "Asia/Bangkok": "Bangkok · Hà Nội",
};

export function slotLabel(slot: Slot) {
  return slot === "morning" ? "Buổi sáng" : "Buổi tối";
}

function minutes(value: string) {
  const [hour, minute] = value.split(":").map(Number);
  return hour * 60 + minute;
}

function hhmm(total: number) {
  return `${String(Math.floor(total / 60)).padStart(2, "0")}:${String(total % 60).padStart(2, "0")}`;
}

export function inQuiet(value: string, start: string, end: string) {
  const v = minutes(value), s = minutes(start), e = minutes(end);
  return s <= e ? s <= v && v < e : v >= s || v < e;
}

export function timeOptions(window: [string, string] | string[], step: number, quietStart: string, quietEnd: string, current?: string) {
  const values: string[] = [];
  for (let t = minutes(window[0]); t <= minutes(window[1]); t += step) {
    const value = hhmm(t);
    if (!inQuiet(value, quietStart, quietEnd) || value === current) values.push(value);
  }
  if (current && !values.includes(current)) values.push(current);
  return values.sort();
}

export function quietOptions() {
  return Array.from({ length: 96 }, (_, index) => hhmm(index * 15));
}

export function repeatKind(weekdays: number[]): RepeatKind {
  const key = [...weekdays].sort().join(",");
  for (const [kind, days] of Object.entries(PRESETS)) if (days.join(",") === key) return kind as RepeatKind;
  return "custom";
}

export function weekdaysFor(kind: Exclude<RepeatKind, "custom">) {
  return [...PRESETS[kind]];
}

export function repeatLabel(weekdays: number[]) {
  const kind = repeatKind(weekdays);
  if (kind === "daily") return "mỗi ngày";
  if (kind === "weekdays") return "ngày thường";
  if (kind === "weekend") return "cuối tuần";
  return weekdays.map((day) => WEEKDAY_SHORT[day - 1]).join(", ");
}

/** Calendar parts of an instant in a time zone. */
function parts(date: Date, timeZone: string) {
  const values = Object.fromEntries(
    new Intl.DateTimeFormat("en-CA", {
      timeZone, year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit",
      hourCycle: "h23",
    }).formatToParts(date).map((part) => [part.type, part.value]),
  );
  return { day: `${values.year}-${values.month}-${values.day}`, time: `${values.hour}:${values.minute}` };
}

function dayNumber(day: string) {
  const [y, m, d] = day.split("-").map(Number);
  return Date.UTC(y, m - 1, d) / 86_400_000;
}

export function nextDeliveryText(iso: string | null | undefined, timeZone: string, now = new Date()) {
  if (!iso) return "";
  const at = new Date(iso);
  const target = parts(at, timeZone), today = parts(now, timeZone);
  const offset = dayNumber(target.day) - dayNumber(today.day);
  const evening = minutes(target.time) >= 12 * 60;
  if (offset === 0) return `Lần tới: ${target.time} ${evening ? "tối nay" : "sáng nay"}`;
  if (offset === 1) return `Lần tới: ${target.time} ${evening ? "tối mai" : "sáng mai"}`;
  const [, month, day] = target.day.split("-");
  const weekday = new Date(dayNumber(target.day) * 86_400_000).getUTCDay();
  return `Lần tới: ${target.time} ${WEEKDAY_LONG[(weekday + 6) % 7]}, ${day}/${month}`;
}

/** Last paused day (inclusive) for "pause N days", in the schedule's calendar. */
export function pauseUntil(days: number, timeZone: string, now = new Date()) {
  const today = dayNumber(parts(now, timeZone).day);
  return new Date((today + days - 1) * 86_400_000).toISOString().slice(0, 10);
}

export function shortDate(day: string) {
  const [, month, date] = day.split("-");
  return `${date}/${month}`;
}

export function zoneLabel(timeZone: string, now = new Date()) {
  const name = ZONE_NAMES[timeZone] ?? timeZone.split("/").at(-1)!.replace(/_/g, " ");
  const offset = new Intl.DateTimeFormat("en-US", { timeZone, timeZoneName: "shortOffset" })
    .formatToParts(now).find((part) => part.type === "timeZoneName")?.value ?? "GMT";
  return `${name} (${offset})`;
}

export function deviceZone() {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || "Asia/Ho_Chi_Minh";
  } catch {
    return "Asia/Ho_Chi_Minh";
  }
}

export function checkInError(code: string | undefined, cap = 4, eveningEnd = "22:30") {
  switch (code) {
    case "PROACTIVE_DAILY_CAP":
      return `Bạn đã dùng ${cap} lời hỏi thăm mỗi ngày. Tắt một lời khác để bật lời này.`;
    case "SCHEDULE_WINDOW":
      return `Buổi sáng chọn từ 5:00 đến 11:30, buổi tối từ 17:00 đến ${eveningEnd}.`;
    case "SCHEDULE_IN_QUIET_HOURS":
      return "Giờ này nằm trong giờ yên lặng của bạn. Chọn giờ khác hoặc đổi giờ yên lặng.";
    case "PROACTIVE_INELIGIBLE":
      return "Trợ lý này chưa thể hỏi thăm với tài khoản hiện tại.";
    case "PROACTIVE_UNAVAILABLE":
      return "Lời hỏi thăm đang tạm nghỉ. Bạn thử lại sau nhé.";
    case "STALE_VERSION":
      return "Lịch vừa được thay đổi ở nơi khác. Mình đã tải lại để bạn xem.";
    case "QUIET_HOURS_INVALID":
      return "Giờ yên lặng cần dài từ 4 đến 12 tiếng.";
    case "INVALID_TIMEZONE":
      return "Múi giờ này chưa dùng được. Bạn chọn múi giờ khác nhé.";
    case "SCHEDULE_PAUSE":
      return "Chỉ tạm dừng tối đa 30 ngày.";
    default:
      return "Chưa lưu được thay đổi. Bạn thử lại nhé.";
  }
}
