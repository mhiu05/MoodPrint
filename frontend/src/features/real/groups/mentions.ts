/** @mention picker model for group chat: pure functions, no DOM. */
export type MentionTarget = { id: "dieuphoi" | "nhatky" | "hoatdong" | "all"; name: string };

export const EVERYONE: MentionTarget = { id: "all", name: "mọi người" };

export function fold(value: string): string {
  return value
    .toLocaleLowerCase("vi-VN")
    .replace(/đ/g, "d")
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "");
}

/** The "@query" the caret is in (letters and single spaces, at most 12 characters), or null. */
export function activeMention(text: string, caret: number): { start: number; query: string } | null {
  const before = text.slice(0, caret);
  const at = before.lastIndexOf("@");
  if (at < 0) return null;
  // An @ inside a word (an e-mail address) never opens the picker.
  if (at > 0 && /[\p{L}\p{N}._]/u.test(before[at - 1])) return null;
  // Inside quoted text or a "> " quote line it is not a mention (the server ignores it too).
  const head = before.slice(0, at);
  const line = head.slice(head.lastIndexOf("\n") + 1);
  if (/^\s*>/.test(line) || (head.split('"').length - 1) % 2 === 1 || head.lastIndexOf("“") > head.lastIndexOf("”"))
    return null;
  const query = before.slice(at + 1);
  if (query.length > 12 || /\s{2}|[\n@"“”>]/.test(query) || /^\s/.test(query)) return null;
  return { start: at, query };
}

export function mentionOptions(targets: MentionTarget[], query: string): MentionTarget[] {
  const needle = fold(query.trim());
  return targets.filter((target) => {
    const name = fold(target.name);
    return !needle || name.startsWith(needle) || name.split(" ").some((word) => word.startsWith(needle));
  });
}

/** Replace "@query" with "@Name " and return the new text and caret position. */
export function insertMention(text: string, start: number, caret: number, target: MentionTarget) {
  const token = `@${target.name} `;
  return { text: text.slice(0, start) + token + text.slice(caret), caret: start + token.length };
}

/** Picker choices whose "@Name" is still in the text (deleting the token drops the id). */
export function keptMentions(text: string, picked: MentionTarget[]): MentionTarget["id"][] {
  const folded = fold(text);
  const ids: MentionTarget["id"][] = [];
  for (const target of picked) {
    if (folded.includes(`@${fold(target.name)}`) && !ids.includes(target.id)) ids.push(target.id);
  }
  return ids;
}
