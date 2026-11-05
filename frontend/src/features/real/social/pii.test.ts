import { describe, expect, it } from "vitest";
import { looksLikeContact } from "./pii";

describe("contact-detail advisory", () => {
  it.each([
    "số mình 0912345678 nè",
    "gọi 0912 345 678 nhé",
    "zalo 0912.345.678",
    "+84912345678",
    "mail mình là an.nguyen@gmail.com",
    "xem https://example.org/profile",
    "www.facebook.com/an",
    "vào trang an-portfolio.vn",
  ])("flags %s", (text) => {
    expect(looksLikeContact(text)).toBe(true);
  });

  it.each([
    "hẹn 25/10/2026 nhé",
    "ngày 2026-10-25",
    "giá 150.000đ thôi",
    "khoảng 1.500.000 VND",
    "mình 23 tuổi, học năm 3",
    "3.14 là số pi",
    "chạy 10 km mỗi sáng",
    "hôm nay vui ghê",
  ])("does not flag %s", (text) => {
    expect(looksLikeContact(text)).toBe(false);
  });
});
