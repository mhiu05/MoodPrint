export type AuthCallback =
  | { kind: "recovery"; token: string }
  | { kind: "confirmed" }
  | { kind: "failed"; expired: boolean }
  | null;

/**
 * Supabase email links land on /auth/callback with tokens in the fragment. Read them once,
 * then remove them from the address bar and history before anything else renders.
 *
 * This is called exactly once at module bootstrap (before React mounts, so StrictMode's double
 * render can never re-parse a URL that was already cleaned) and has no React or app imports.
 */
export function readAuthCallback(): AuthCallback {
  if (window.location.pathname !== "/auth/callback") return null;
  const params = new URLSearchParams(
    window.location.hash.replace(/^#/, "") || window.location.search,
  );
  window.history.replaceState(null, "", "/#/");
  if (params.get("error") || params.get("error_code"))
    return { kind: "failed", expired: params.get("error_code") === "otp_expired" };
  const token = params.get("access_token");
  if (params.get("type") === "recovery" && token) return { kind: "recovery", token };
  if (params.get("type") === "signup" || params.get("type") === "email")
    return { kind: "confirmed" };
  return { kind: "failed", expired: false };
}
