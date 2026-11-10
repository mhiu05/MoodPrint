import type { StreamClient } from "../http/client";
import { createCompanionHttp } from "../http/chat-companion";
import type { CompanionService } from "./companion-types";
export { simulatedChat as createChatPort } from "../mock/simulation";

/**
 * The real workspace talks to the backend Companion only when it is switched on:
 * `VITE_PUBLIC_AI_COMPANION=live` at build time, or the `moodprint:ai-companion=live` browser
 * switch (used by the E2E suite). Off by default so a deployment without a configured model never
 * shows a chat that can only fail. When on, a backend without a model answers 503 `not_ready`,
 * shown as an error, never as sample content. The demo always keeps the simulated chat.
 */
export const COMPANION_SWITCH = "moodprint:ai-companion";
function switchedOn(): boolean {
  if (import.meta.env.VITE_PUBLIC_AI_COMPANION === "live") return true;
  try {
    return globalThis.localStorage?.getItem(COMPANION_SWITCH) === "live";
  } catch {
    return false;
  }
}
export function createCompanionService(
  client: StreamClient,
): CompanionService | null {
  return switchedOn() ? createCompanionHttp(client) : null;
}
