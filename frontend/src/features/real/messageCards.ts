/** Historical social cards have no destination in the current product. */
export function renderableCards<T extends { kind: string }>(cards: readonly T[]): T[] {
  return cards.filter((card) => card.kind !== "discovery");
}
