export type EntryKind = "public" | "app" | "not_found";

/**
 * Decides which tree the page shows without creating any identity.
 *
 * - a consumed email callback, any `#/…` hash (including the legacy `#/`) → the existing app
 * - the bare root → the public landing
 * - any other real path → a public not-found page (the server still serves index.html)
 */
export function classifyEntry(
  pathname: string,
  hash: string,
  hasCallback: boolean,
): EntryKind {
  if (hasCallback) return "app";
  if (pathname !== "/" && pathname !== "/index.html") return "not_found";
  return hash.startsWith("#/") ? "app" : "public";
}
