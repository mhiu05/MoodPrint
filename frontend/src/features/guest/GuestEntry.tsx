import "./guest.css";
import { type FormEvent, useEffect, useRef, useState } from "react";
import { ApiError, type ApiClient } from "../../api/client";
import type { SessionView } from "../../api/contracts";
import { validateSession } from "../../api/session";
import { Button, Dialog, cx } from "../../components/UI";
import { ErrorNotice } from "../../components/ErrorNotice";
import { AgeFields } from "../auth/AgeFields";
import { ageDeclaration, bangkokYear } from "../auth/ageDeclaration";
import { beginAttempt, beginOrResumeGuest, clearAttempt } from "./guestAttempt";

declare global {
  interface Window {
    turnstile?: {
      render: (el: HTMLElement, options: Record<string, unknown>) => string;
      reset: (id?: string) => void;
      remove: (id?: string) => void;
    };
  }
}

const TURNSTILE = "https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit";
let challengePromise: Promise<void> | null = null;

function loadChallenge(): Promise<void> {
  if (window.turnstile) return Promise.resolve();
  if (challengePromise) return challengePromise;
  challengePromise = new Promise<void>((resolve, reject) => {
    const script = document.createElement("script");
    script.src = TURNSTILE;
    script.async = true;
    script.onload = () => {
      if (window.turnstile) resolve();
      else { script.remove(); reject(new Error("challenge unavailable")); }
    };
    script.onerror = () => { script.remove(); reject(new Error("challenge unavailable")); };
    document.head.appendChild(script);
  }).catch((reason) => {
    challengePromise = null;
    throw reason;
  });
  return challengePromise;
}

/** Explicit-only trial entry: disclosure, the existing age attestation and one CAPTCHA. */
export function GuestEntry({
  api,
  siteKey,
  onStarted,
  onClose,
}: {
  api: ApiClient;
  siteKey: string;
  onStarted: (session: SessionView) => void;
  onClose: () => void;
}) {
  const [year, setYear] = useState("");
  const [minimum, setMinimum] = useState(false);
  const [token, setToken] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>();
  const [ineligible, setIneligible] = useState(false);
  const [waiting, setWaiting] = useState(false);
  const challenge = useRef<HTMLDivElement>(null);
  const widget = useRef<string | undefined>(undefined);
  const controller = useRef<AbortController | undefined>(undefined);
  const thisYear = bangkokYear();

  useEffect(() => {
    let active = true;
    loadChallenge()
      .then(() => {
        if (!active || !challenge.current || !window.turnstile) return;
        widget.current = window.turnstile.render(challenge.current, {
          sitekey: siteKey,
          callback: (value: string) => setToken(value),
          "expired-callback": () => setToken(""),
          "error-callback": () => setToken(""),
        });
      })
      .catch(() => active && setError(new ApiError(503, "CAPTCHA_UNAVAILABLE", "Chưa tải được bước kiểm tra an toàn. Vui lòng thử lại sau.")));
    return () => {
      active = false;
      controller.current?.abort();
      if (widget.current) window.turnstile?.remove(widget.current);
    };
  }, [siteKey]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    const birthYear = Number(year);
    // Under 18 never reaches the network: no intent, no provider, no identity.
    if (!minimum || !Number.isInteger(birthYear) || birthYear > thisYear - 18 || birthYear < 1900) {
      setIneligible(true);
      return;
    }
    if (!token) {
      setError(new ApiError(422, "CAPTCHA_REQUIRED", "Hãy hoàn tất bước kiểm tra an toàn trước khi bắt đầu."));
      return;
    }
    setIneligible(false);
    setError(undefined);
    setWaiting(false);
    setBusy(true);
    controller.current = new AbortController();
    try {
      const attempt = beginAttempt();
      const session = await beginOrResumeGuest(
        api,
        {
          eligibility: ageDeclaration(year, minimum, thisYear),
          captchaToken: token,
          disclosureVersion: "guest-v1",
        },
        attempt,
        controller.current.signal,
      );
      const valid = validateSession(session);
      api.setCsrf(valid.csrfToken);
      clearAttempt();
      onStarted(valid);
    } catch (reason) {
      if (reason instanceof ApiError && reason.code === "GUEST_ATTEMPT_PENDING") {
        // Unknown outcome: keep the same key and explain; never mint a new identity on a guess.
        setWaiting(true);
      } else {
        setError(reason);
        if (reason instanceof ApiError && reason.status < 500 && reason.code !== "GUEST_ATTEMPT_PENDING") {
          // A definitive rejection (e.g. CAPTCHA) needs a fresh one-shot token and a fresh attempt.
          setToken("");
          if (widget.current) window.turnstile?.reset(widget.current);
          if (reason.code !== "GUEST_CREATION_LIMIT") clearAttempt();
        }
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog title="Dùng thử 2 giờ, không cần email" onClose={() => !busy && onClose()}>
      <form onSubmit={submit} aria-busy={busy} className="guest-entry">
        <p>
          Lượt dùng thử kết thúc sau 2 giờ kể từ khi bắt đầu. Khi hết giờ, bạn không thể mở lại dữ liệu của
          lượt này. MoodPrint sẽ xóa dữ liệu khỏi hệ thống đang hoạt động.
        </p>
        <p className={cx.footnote}>
          Không cần email để dùng thử. MoodPrint dành cho người từ đủ 18 tuổi.
          Tìm bạn và nhắn tin cần tài khoản đã đăng ký.
        </p>
        <AgeFields prefix="guest" year={year} confirmed={minimum} currentYear={thisYear}
          onYear={setYear} onConfirmed={setMinimum} />
        <div ref={challenge} aria-label="Bước kiểm tra an toàn" />
        {ineligible ? (
          <p role="alert" className={cx.error}>
            Bạn cần đủ 18 tuổi để sử dụng MoodPrint.
          </p>
        ) : null}
        {waiting ? (
          <p role="status">
            Đang xử lý lượt dùng thử của bạn. Hãy đợi vài giây rồi bấm “Thử lại”; hệ thống sẽ dùng lại đúng
            yêu cầu này và không tạo thêm lượt mới.
          </p>
        ) : null}
        <ErrorNotice error={error} />
        <div className={cx.actions}>
          <Button type="button" variant="secondary" disabled={busy} onClick={onClose}>
            Để sau
          </Button>
          <Button type="submit" disabled={busy}>
            {busy ? "Đang bắt đầu…" : waiting ? "Thử lại" : "Bắt đầu dùng thử"}
          </Button>
        </div>
      </form>
    </Dialog>
  );
}
