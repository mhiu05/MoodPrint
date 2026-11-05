import { describe, expect, it } from "vitest";
import {
  checkInError,
  inQuiet,
  nextDeliveryText,
  pauseUntil,
  quietOptions,
  repeatKind,
  slotLabel,
  timeOptions,
  weekdaysFor,
  zoneLabel,
} from "./checkinsModel";

describe("check-in schedule model", () => {
  it("treats quiet hours as [start, end) across midnight", () => {
    expect(inQuiet("22:00", "22:00", "07:00")).toBe(true);
    expect(inQuiet("06:45", "22:00", "07:00")).toBe(true);
    expect(inQuiet("07:00", "22:00", "07:00")).toBe(false);
    expect(inQuiet("21:45", "22:00", "07:00")).toBe(false);
    expect(inQuiet("13:00", "12:00", "16:00")).toBe(true);
  });

  it("offers only in-window 15-minute times outside quiet hours", () => {
    const evening = timeOptions(["17:00", "22:30"], 15, "22:00", "07:00");
    expect(evening[0]).toBe("17:00");
    expect(evening.at(-1)).toBe("21:45");
    expect(evening).toHaveLength(20);
    const morning = timeOptions(["05:00", "11:30"], 15, "22:00", "07:00");
    expect(morning[0]).toBe("07:00");
    expect(morning.at(-1)).toBe("11:30");
  });

  it("keeps a saved value visible even when it is no longer offered", () => {
    expect(timeOptions(["17:00", "22:30"], 15, "22:00", "07:00", "22:15")).toContain("22:15");
  });

  it("lists quiet-hour boundaries every 15 minutes", () => {
    const options = quietOptions();
    expect(options).toHaveLength(96);
    expect(options[0]).toBe("00:00");
    expect(options.at(-1)).toBe("23:45");
  });

  it("maps weekday sets to repeat presets", () => {
    expect(repeatKind([1, 2, 3, 4, 5, 6, 7])).toBe("daily");
    expect(repeatKind([1, 2, 3, 4, 5])).toBe("weekdays");
    expect(repeatKind([6, 7])).toBe("weekend");
    expect(repeatKind([1, 3])).toBe("custom");
    expect(weekdaysFor("weekend")).toEqual([6, 7]);
  });

  it("describes the next delivery in the schedule's time zone", () => {
    const now = new Date("2026-10-31T01:00:00Z"); // 08:00 in Ho Chi Minh City
    expect(nextDeliveryText("2026-11-01T00:30:00Z", "Asia/Ho_Chi_Minh", now)).toBe("Lần tới: 07:30 sáng mai");
    expect(nextDeliveryText("2026-10-31T13:00:00Z", "Asia/Ho_Chi_Minh", now)).toBe("Lần tới: 20:00 tối nay");
    expect(nextDeliveryText("2026-11-03T00:30:00Z", "Asia/Ho_Chi_Minh", now)).toBe("Lần tới: 07:30 thứ Ba, 03/11");
    expect(nextDeliveryText(null, "Asia/Ho_Chi_Minh", now)).toBe("");
  });

  it("computes the last paused day inclusively in the schedule zone", () => {
    const now = new Date("2026-10-31T18:00:00Z"); // already 1 Nov in Ho Chi Minh City
    expect(pauseUntil(1, "Asia/Ho_Chi_Minh", now)).toBe("2026-11-01");
    expect(pauseUntil(3, "Asia/Ho_Chi_Minh", now)).toBe("2026-11-03");
  });

  it("names time zones in plain Vietnamese with their offset", () => {
    const now = new Date("2026-10-31T00:00:00Z");
    expect(zoneLabel("Asia/Ho_Chi_Minh", now)).toBe("Việt Nam (GMT+7)");
    expect(zoneLabel("Asia/Tokyo", now)).toBe("Tokyo (GMT+9)");
  });

  it("uses natural Vietnamese for every documented error", () => {
    expect(checkInError("PROACTIVE_DAILY_CAP", 4)).toBe("Bạn đã dùng 4 lời hỏi thăm mỗi ngày. Tắt một lời khác để bật lời này.");
    expect(checkInError("SCHEDULE_IN_QUIET_HOURS")).toMatch(/giờ yên lặng/);
    expect(checkInError("STALE_VERSION")).toBe("Lịch vừa được thay đổi ở nơi khác. Mình đã tải lại để bạn xem.");
    expect(checkInError("SOMETHING_ELSE")).toBe("Chưa lưu được thay đổi. Bạn thử lại nhé.");
    expect(slotLabel("evening")).toBe("Buổi tối");
  });
});
