type Groupable = { id: string; actor: "self" | "bot"; runId?: string | null };

export type MessageGroup<T> = { key: string; items: T[] };

/** Adjacent bot bubbles of one run read as one turn; every other message stays alone. */
export function groupMessages<T>(
  rows: T[],
  select: (row: T) => Groupable = (row) => row as Groupable,
): MessageGroup<T>[] {
  const groups: MessageGroup<T>[] = [];
  let previous: Groupable | undefined;
  for (const row of rows) {
    const message = select(row);
    const last = groups[groups.length - 1];
    if (
      last &&
      previous &&
      message.actor === "bot" &&
      previous.actor === "bot" &&
      message.runId &&
      message.runId === previous.runId
    ) {
      last.items.push(row);
    } else {
      groups.push({ key: message.id, items: [row] });
    }
    previous = message;
  }
  return groups;
}
