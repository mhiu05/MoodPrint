import type { StreamClient } from "../http/client";
import { createCompanionHttp } from "../http/chat-companion";
import type { CompanionService } from "./companion-types";
export { simulatedChat as createChatPort } from "../mock/simulation";

/**
 * The real workspace talks to the backend Companion when it is switched on with
 * `VITE_PUBLIC_AI_COMPANION=live` (off by default: a deployment without a configured model
 * must not show a chat that can only fail). The demo always keeps the simulated chat.
 */
export function createCompanionService(
  client: StreamClient,
): CompanionService | null {
  return import.meta.env.VITE_PUBLIC_AI_COMPANION === "live"
    ? createCompanionHttp(client)
    : null;
}
