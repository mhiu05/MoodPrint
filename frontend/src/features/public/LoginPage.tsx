import { Suspense, lazy, useEffect, useState } from "react";
import { Clock3, UserRoundPlus, ArrowRight } from "lucide-react";
import type { ApiClient } from "../../api/client";
import type { SessionView } from "../../api/contracts";
import type { components } from "../../api/generated/schema";
import { AuthScreen } from "../real/Auth";
import { BrandMark } from "../../companions/Avatar";
import { Button, cx } from "../../components/UI";
import "./landing.css";

type Experience = components["schemas"]["PublicExperience"];
const GuestEntry = lazy(() =>
  import("../guest/GuestEntry").then((module) => ({ default: module.GuestEntry })),
);

function LandingBrand() {
  return (
    <div className="landing-brand">
      <BrandMark />
      <span>MoodPrint</span>
    </div>
  );
}

/** Public entry: the form is the actual authentication flow; trial creation stays a separate action. */
export function LoginPage({ api }: { api: ApiClient }) {
  const [experience, setExperience] = useState<Experience | null | undefined>(undefined);
  const [known, setKnown] = useState<SessionView | null>(null);
  const [entryOpen, setEntryOpen] = useState(false);
  const [offline, setOffline] = useState(() => !navigator.onLine);
  const initialMode = new URLSearchParams(window.location.search).get("mode") === "signup" ? "signup" : "login";

  useEffect(() => {
    const controller = new AbortController();
    api
      .request<Experience>("/public/experience", { signal: controller.signal })
      .then((value) => !controller.signal.aborted && setExperience(value))
      .catch(() => !controller.signal.aborted && setExperience(null));
    if (initialMode !== "signup") {
      api
        .request<SessionView>("/session", { signal: controller.signal })
        .then((value) => !controller.signal.aborted && setKnown(value))
        .catch(() => undefined);
    }
    const toggle = () => setOffline(!navigator.onLine);
    window.addEventListener("online", toggle);
    window.addEventListener("offline", toggle);
    return () => {
      controller.abort();
      window.removeEventListener("online", toggle);
      window.removeEventListener("offline", toggle);
    };
  }, [api, initialMode]);

  const ready = Boolean(experience?.guestAvailable && experience.captchaSiteKey);
  const trialNote = offline
    ? "Bạn đang ngoại tuyến."
    : experience === undefined
      ? "Đang kiểm tra lượt dùng thử…"
      : ready
        ? "Không cần email để dùng thử."
        : "Chưa thể bắt đầu lượt dùng thử. Thử lại sau.";

  function receive(value: SessionView) {
    api.setCsrf(value.csrfToken);
    window.location.assign("/#/assistants");
  }

  return (
    <div className="landing">
      <a className={cx.skipLink} href="#main">Đến nội dung chính</a>
      {known ? (
        <main id="main" className="real-auth landing-auth landing-return">
          <LandingBrand />
          <h1 tabIndex={-1}>Chào bạn trở lại</h1>
          <p className="landing-auth-lede">Phiên MoodPrint của bạn đã sẵn sàng.</p>
          <a className={`${cx.button} ${cx.primary} landing-continue`} href="/#/assistants">
            Tiếp tục sử dụng <ArrowRight size={20} aria-hidden="true" />
          </a>
        </main>
      ) : (
        <AuthScreen
          api={api}
          receive={receive}
          callback={null}
          initialMode={initialMode}
          presentation="landing"
          footerActions={(mode) => (
            <>
              <a className={`${cx.button} ${cx.secondary} landing-signup`} href={mode === "login" ? "/login?mode=signup" : "/login"}>
                {mode === "login" ? <UserRoundPlus size={20} aria-hidden="true" /> : <ArrowRight size={20} aria-hidden="true" />}
                {mode === "login" ? "Tạo tài khoản" : "Đăng nhập"}
              </a>
              <Button
                variant="secondary"
                className="landing-trial"
                disabled={!ready || offline}
                onClick={() => setEntryOpen(true)}
              >
                <Clock3 size={20} aria-hidden="true" />
                Dùng thử 2 giờ
              </Button>
              <p className={`${cx.footnote} landing-status`} role="status">{trialNote}</p>
            </>
          )}
        />
      )}

      {entryOpen && experience?.captchaSiteKey ? (
        <Suspense fallback={<p role="status">Đang mở…</p>}>
          <GuestEntry
            api={api}
            siteKey={experience.captchaSiteKey}
            onClose={() => setEntryOpen(false)}
            onStarted={() => {
              setEntryOpen(false);
              window.location.assign("/#/assistants");
            }}
          />
        </Suspense>
      ) : null}
    </div>
  );
}
