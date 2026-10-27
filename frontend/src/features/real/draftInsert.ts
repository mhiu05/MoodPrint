export const DRAFT_LIMIT = 500;

export type DraftInsertion = { ok: true; next: string; caret: number } | { ok: false };

/** Put a suggestion into a draft at the caret or selected range. Unselected text is kept. */
export function insertAtSelection(draft: string, start: number, end: number, text: string, limit = DRAFT_LIMIT): DraftInsertion {
  const before = draft.slice(0, start), after = draft.slice(end);
  const head = before && !/\s$/.test(before) ? `${before} ${text}` : `${before}${text}`;
  const next = head + (after && !/^\s/.test(after) ? ` ${after}` : after);
  if (next.length > limit) return { ok: false };
  return { ok: true, next, caret: head.length };
}
