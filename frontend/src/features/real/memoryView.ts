import type { components } from "../../api/generated/schema";

type MemoryDTO = components["schemas"]["MemoryDTO"];
type MemorySource = Pick<MemoryDTO, "origin" | "sourceEntryId" | "sourceLocalDate">;

export function memoryBadge(origin: MemoryDTO["origin"] | undefined): string | null {
  return origin === "journal_auto" ? "Tự động từ nhật ký" : null;
}

export function sourceEntryLink(memory: MemorySource): { to: string; label: string } | null {
  if (memory.origin !== "journal_auto" || !memory.sourceEntryId || !memory.sourceLocalDate) return null;
  const date = memory.sourceLocalDate;
  if (!/^\d{4}-\d{2}-\d{2}$/.test(date) || !/^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$/i.test(memory.sourceEntryId)) return null;
  const parsed = new Date(`${date}T00:00:00Z`);
  if (!Number.isFinite(parsed.getTime()) || parsed.toISOString().slice(0, 10) !== date) return null;
  const [year, month, day] = date.split("-");
  return { to: `/self/entry/${memory.sourceEntryId}`, label: `Xem trang ${day}/${month}/${year}` };
}
