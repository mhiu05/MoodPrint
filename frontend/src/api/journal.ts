import { uploadJournalBytes } from "./journalUpload";
import type { components } from "./generated/schema";

export type JournalMedia = components["schemas"]["JournalMediaDTO"];
export type JournalMediaType = JournalMedia["type"];
// The server emits default list fields; Required reflects that response invariant.
export type JournalEntry = Required<components["schemas"]["JournalEntryDTO"]>;
export type JournalInput = components["schemas"]["JournalEntryInput"];
export type JournalCollection = Omit<
  components["schemas"]["JournalEntryPage"],
  "items"
> & { items: JournalEntry[] };
export type JournalUpload = components["schemas"]["MediaReservation"];

/** Upload capabilities remain transient; never persist these URLs or tokens. */
export function uploadJournalFile(
  descriptor: JournalUpload,
  file: Blob,
  signal?: AbortSignal,
  onProgress?: (percent: number) => void,
) {
  return uploadJournalBytes(descriptor, file, signal, onProgress);
}
