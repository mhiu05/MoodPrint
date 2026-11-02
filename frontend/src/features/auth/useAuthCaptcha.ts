import { useEffect, useState } from "react";
import { ApiError, type ApiClient } from "../../api/client";
import type { components } from "../../api/generated/schema";
import { useCaptcha } from "./CaptchaChallenge";

type Experience = components["schemas"]["PublicExperience"];

/** Each auth surface can stand alone, including step-up auth inside the protected app. */
export function useAuthCaptcha(api: ApiClient, enabled = true) {
  const [experience, setExperience] = useState<Experience>();
  const [error, setError] = useState<unknown>();
  const [generation, setGeneration] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    setError(undefined);
    api.request<Experience>("/public/experience", { signal: controller.signal })
      .then(value => { if (!controller.signal.aborted) setExperience(value); })
      .catch(reason => { if (!controller.signal.aborted) setError(reason); });
    return () => controller.abort();
  }, [api, generation]);
  const required = enabled && experience?.authCaptchaRequired === true;
  const challenge = useCaptcha(experience?.captchaSiteKey, required);
  function fields(): { captchaToken?: string } {
    if (!enabled) return {};
    if (!experience || error) throw new ApiError(503, "CAPTCHA_UNAVAILABLE", "Chưa kiểm tra được bước an toàn. Hãy thử lại.");
    return required ? { captchaToken: challenge.take() } : {};
  }
  return {
    challenge, required, fields,
    loading: enabled && !experience && !error,
    error: enabled ? error : undefined,
    retry: () => setGeneration(value => value + 1),
  };
}
