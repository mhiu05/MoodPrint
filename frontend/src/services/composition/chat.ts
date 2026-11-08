import type { StreamClient } from "../http/client";
import type { CompanionService } from "./companion-types";
export { simulatedChat as createChatPort } from "../mock/simulation";

export function createCompanionService(
  client: StreamClient,
): CompanionService | null {
  // Phase 3 will connect its adapter here without editing frozen composition.
  void client;
  return null;
}
