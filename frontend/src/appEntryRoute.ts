export type EntryKind = "public" | "app" | "not_found";

/**
 * Decides which tree the page shows without creating any identity.
 *
 * - a consumed email callback, or a hash route on a known path → the existing app
 * - `/login` → the public login page; the bare root → the public landing
 * - any other real path → a public not-found page (the server still serves index.html)
 */
export function classifyEntry(
  pathname: string,
  hash: string,
  hasCallback: boolean,
): EntryKind {
  if (hasCallback) return "app";
  if (pathname !== "/" && pathname !== "/index.html" && pathname !== "/login") return "not_found";
  if (hash.startsWith("#/")) return "app";
  return "public";
}
