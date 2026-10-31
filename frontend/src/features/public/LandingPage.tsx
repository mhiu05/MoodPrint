import { Suspense, lazy, useEffect, useState } from "react";
import type { ApiClient } from "../../api/client";
import type { SessionView } from "../../api/contracts";
import type { components } from "../../api/generated/schema";
import { BrandMark } from "../../companions/Avatar";
import { Button, cx } from "../../components/UI";
import "./home.css";

type Experience = components["schemas"]["PublicExperience"];
const GuestEntry = lazy(() =>
  import("../guest/GuestEntry").then((module) => ({ default: module.GuestEntry })),
);

/** Public home: keep the first choice focused on sign-in, registration, or a guest trial. */
export function LandingPage({ api }: { api: ApiClient }) {
  const [experience, setExperience] = useState<Experience | null | undefined>(undefined);
  const [known, setKnown] = useState<SessionView | null>(null);
  const [entryOpen, setEntryOpen] = useState(false);
  const [offline, setOffline] = useState(() => !navigator.onLine);

  useEffect(() => {
    const controller = new AbortController();
    api
      .request<Experience>("/public/experience", { signal: controller.signal })
      .then((value) => !controller.signal.aborted && setExperience(value))
      .catch(() => !controller.signal.aborted && setExperience(null));
    api
      .request<SessionView>("/session", { signal: controller.signal })
      .then((value) => !controller.signal.aborted && setKnown(value))
      .catch(() => undefined);
    const toggle = () => setOffline(!navigator.onLine);
    window.addEventListener("online", toggle);
    window.addEventListener("offline", toggle);
    return () => {
      controller.abort();
      window.removeEventListener("online", toggle);
      window.removeEventListener("offline", toggle);
    };
  }, [api]);

  const ready = Boolean(experience?.guestAvailable && experience.captchaSiteKey);
  const note = offline
    ? "Bạn đang ngoại tuyến."
    : experience === undefined
      ? "Đang kiểm tra lượt dùng thử…"
      : ready
        ? "Dùng thử 2 giờ, không cần email."
        : "Chưa thể bắt đầu lượt dùng thử. Thử lại sau.";

  return (
    <div className="home">
      <a className={cx.skipLink} href="#main">Đến nội dung chính</a>
      <main id="main" className="home-main" tabIndex={-1}>
        <div className="home-brand">
          <BrandMark />
          <span>MoodPrint</span>
        </div>
        <section className="home-entry" aria-labelledby="home-title">
          <h1 id="home-title">Bắt đầu với MoodPrint</h1>
          <p>MoodPrint dành cho người từ đủ 18 tuổi.</p>
          <div className="home-actions">
            {known ? (
              <a className={`${cx.button} ${cx.primary} home-continue`} href="/#/assistants">
                Tiếp tục sử dụng
              </a>
            ) : (
              <Button className="home-trial" disabled={!ready || offline} onClick={() => setEntryOpen(true)}>
                Dùng thử 2 giờ
              </Button>
            )}
            <div className="home-account-actions">
              <a className={`${cx.button} ${cx.secondary}`} href="/login?mode=signup">Tạo tài khoản</a>
              <a className={`${cx.button} ${cx.secondary}`} href="/login">Đăng nhập</a>
            </div>
          </div>
          <p className={`${cx.footnote} home-status`} role="status">
            {known ? "Bạn đã có một phiên đang mở." : note}
          </p>
        </section>
      </main>

      {entryOpen && experience?.captchaSiteKey ? (
        <Suspense fallback={<p role="status">Đang mở…</p>}>
          <GuestEntry
            api={api}
            siteKey={experience.captchaSiteKey}
            onClose={() => setEntryOpen(false)}
            onStarted={() => {
              setEntryOpen(false);
              window.location.hash = "#/assistants";
            }}
          />
        </Suspense>
      ) : null}
    </div>
  );
}
