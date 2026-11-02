import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError } from "../../api/client";
import { ErrorNotice } from "../../components/ErrorNotice";
import "./captcha.css";

declare global {
  interface Window {
    turnstile?: {
      render: (el: HTMLElement, options: Record<string, unknown>) => string;
      reset: (id?: string) => void;
      remove: (id?: string) => void;
    };
  }
}

const SCRIPT = "https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit";
let challengePromise: Promise<void> | null = null;

function loadChallenge(): Promise<void> {
  if (window.turnstile) return Promise.resolve();
  if (challengePromise) return challengePromise;
  challengePromise = new Promise<void>((resolve, reject) => {
    const script = document.createElement("script");
    script.src = SCRIPT;
    script.async = true;
    script.onload = () => {
      if (window.turnstile) resolve();
      else { script.remove(); reject(new Error("challenge unavailable")); }
    };
    script.onerror = () => { script.remove(); reject(new Error("challenge unavailable")); };
    document.head.appendChild(script);
  }).catch(reason => { challengePromise = null; throw reason; });
  return challengePromise;
}

const unavailable = () => new ApiError(503, "CAPTCHA_UNAVAILABLE", "Chưa tải được bước kiểm tra an toàn. Hãy thử lại.");
const required = () => new ApiError(422, "CAPTCHA_REQUIRED", "Hãy hoàn tất bước kiểm tra an toàn rồi thử lại.");

/** Token lives only in this widget instance and is removed synchronously before an attempt. */
export function useCaptcha(siteKey: string | null | undefined, enabled = true) {
  const container = useRef<HTMLDivElement>(null);
  const widget = useRef<string | undefined>(undefined);
  const token = useRef("");
  const [loading, setLoading] = useState(enabled);
  const [error, setError] = useState<unknown>();
  const [generation, setGeneration] = useState(0);
  const reset = useCallback(() => {
    token.current = "";
    if (widget.current !== undefined) window.turnstile?.reset(widget.current);
  }, []);
  const take = useCallback(() => {
    if (!token.current) {
      // A primary submit may dismiss the duplicate expiry notice, but a loader
      // failure must keep its retry control available until the user recovers.
      setError((previous: unknown) => previous instanceof ApiError && previous.code === "CAPTCHA_REQUIRED" ? undefined : previous);
      throw required();
    }
    setError(undefined);
    const response = token.current;
    reset();
    return response;
  }, [reset]);
  const retry = useCallback(() => setGeneration(value => value + 1), []);

  useEffect(() => {
    token.current = "";
    if (!enabled) { setLoading(false); setError(undefined); return; }
    setLoading(true);
    setError(undefined);
    if (!siteKey) { setLoading(false); setError(unavailable()); return; }
    let active = true;
    loadChallenge().then(() => {
      if (!active || !container.current || !window.turnstile) return;
      widget.current = window.turnstile.render(container.current, {
        sitekey: siteKey,
        // Flexible widgets have a 300px minimum; compact fits narrow mobile forms.
        size: container.current.clientWidth < 300 ? "compact" : "flexible",
        callback: (value: string) => { if (active) { token.current = value; setError(undefined); } },
        "expired-callback": () => { if (active) { reset(); setError(required()); } },
        "error-callback": () => { if (active) { token.current = ""; setError(unavailable()); } },
        "timeout-callback": () => { if (active) { reset(); setError(required()); } },
      });
      setLoading(false);
    }).catch(() => { if (active) { setLoading(false); setError(unavailable()); } });
    return () => {
      active = false;
      token.current = "";
      if (widget.current !== undefined) window.turnstile?.remove(widget.current);
      widget.current = undefined;
    };
  }, [siteKey, enabled, generation, reset]);

  return { container, loading, error, reset, take, retry };
}

export function CaptchaChallenge({ challenge }: { challenge: ReturnType<typeof useCaptcha> }) {
  return <div className="auth-captcha">
    <div ref={challenge.container} role="group" aria-label="Bước kiểm tra an toàn" />
    {challenge.loading ? <p role="status">Đang tải bước kiểm tra an toàn…</p> : null}
    <ErrorNotice error={challenge.error} retry={challenge.retry} />
  </div>;
}
