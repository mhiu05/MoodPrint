import { describe, expect, it } from "vitest";
import { NAV_ITEMS } from "./navigation";

describe("personal navigation", () => {
  it("offers the three remaining destinations", () => {
    expect(NAV_ITEMS.map((item) => item.label)).toEqual(["Trợ lý", "Nhật ký", "Tài khoản"]);
    expect(NAV_ITEMS.some((item) => /connect|messages/.test(item.to))).toBe(false);
  });
});
