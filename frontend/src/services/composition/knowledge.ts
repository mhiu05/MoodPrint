import { knowledgeArticles } from "../../mocks/data/knowledge";
import type { StreamClient } from "../http/client";
import type { KnowledgeSearchService } from "./knowledge-types";
export const createKnowledgeCatalogPort = { list: () => knowledgeArticles };

export function createKnowledgeSearchPort(
  client: StreamClient,
): KnowledgeSearchService | null {
  // Phase 2 will connect its adapter here without editing frozen composition.
  void client;
  return null;
}
