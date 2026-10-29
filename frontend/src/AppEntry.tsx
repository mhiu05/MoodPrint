import { Suspense, lazy, useEffect, useState } from "react";
import { ApiClient } from "./api/client";
import { classifyEntry } from "./appEntryRoute";
import type { AuthCallback } from "./features/auth/callback";
import { LandingPage } from "./features/public/LandingPage";

// The protected app (chat, SDK-heavy views) is fetched only when the visitor goes there.
const RealApp = lazy(() => import("./features/real/RealApp"));

function useLocationKey() {
  const [key, setKey] = useState(() => window.location.pathname + window.location.hash);
  useEffect(() => {
    const update = () => setKey(window.location.pathname + window.location.hash);
    window.addEventListener("hashchange", update);
    window.addEventListener("popstate", update);
    return () => {
      window.removeEventListener("hashchange", update);
      window.removeEventListener("popstate", update);
    };
  }, []);
  return key;
}

/**
 * Public/app boundary. The email callback was already consumed once at bootstrap and arrives here
 * as an immutable value; nothing in the public tree creates an identity.
 */
export function AppEntry({ callback }: { callback: AuthCallback }) {
  const [api] = useState(() => new ApiClient());
  useLocationKey();
  const kind = classifyEntry(window.location.pathname, window.location.hash, callback !== null);
  if (kind === "app")
    return (
      <Suspense
        fallback={
          <main className="real-auth">
            <p role="status">Đang mở MoodPrint…</p>
          </main>
        }
      >
        <RealApp api={api} callback={callback} />
      </Suspense>
    );
  if (kind === "not_found")
    return (
      <main className="real-auth">
        <h1 tabIndex={-1}>Không tìm thấy trang</h1>
        <p>Trang bạn mở không tồn tại.</p>
        <a href="/">Về trang giới thiệu</a>
      </main>
    );
  return <LandingPage api={api} />;
}
