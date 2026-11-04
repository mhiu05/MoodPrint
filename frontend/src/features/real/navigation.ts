export const NAV_ITEMS: readonly { to: string; label: string }[] = [
  { to: "/assistants", label: "Trợ lý" },
  { to: "/self", label: "Nhật ký" },
  { to: "/profile", label: "Tài khoản" },
];

export function badgeText(count: number): string {
  return count > 9 ? "9+" : String(count);
}
