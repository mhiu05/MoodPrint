import { describe, expect, it } from "vitest";
import { badgeText } from "./useSocialSummary";
import { previewLine, relativeTime } from "./format";

const NOW = Date.parse("2026-10-25T12:00:00Z");
const ago = (ms: number) => new Date(NOW - ms).toISOString();

describe("message list formatting", () => {
  it("describes recent times relatively and old ones by date", () => {
    expect(relativeTime(ago(20_000), NOW)).toBe("vừa xong");
    expect(relativeTime(ago(5 * 60_000), NOW)).toBe("5 phút trước");
    expect(relativeTime(ago(3 * 3_600_000), NOW)).toBe("3 giờ trước");
    expect(relativeTime(ago(26 * 3_600_000), NOW)).toBe("hôm qua");
    expect(relativeTime(ago(4 * 86_400_000), NOW)).toBe("4 ngày trước");
    expect(relativeTime(ago(30 * 86_400_000), NOW)).toMatch(/^\d{2}\/\d{2}$/);
    expect(relativeTime(new Date(NOW + 60_000).toISOString(), NOW)).toBe("vừa xong");
  });

  it("prefixes own previews and explains an empty conversation", () => {
    expect(previewLine("chào", "self")).toBe("Bạn: chào");
    expect(previewLine("chào", "peer")).toBe("chào");
    expect(previewLine(null)).toMatch(/Chưa có tin nhắn/);
  });

  it("caps badge numbers at 9+", () => {
    expect(badgeText(3)).toBe("3");
    expect(badgeText(12)).toBe("9+");
  });
});
