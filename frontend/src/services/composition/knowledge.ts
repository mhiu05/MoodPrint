import { knowledgeArticles } from "../../mocks/data/knowledge";
import type { StreamClient } from "../http/client";
import { createKnowledgeHttp } from "../http/knowledge";
import type { KnowledgeSearchService } from "./knowledge-types";
export const createKnowledgeCatalogPort = { list: () => knowledgeArticles };

export function createKnowledgeSearchPort(
  client: StreamClient,
): KnowledgeSearchService | null {
  // Vitest still asserts this seam is null. The Vite app, including Playwright
  // `--mode test`, does not set VITEST, so the live adapter is on there.
  if (import.meta.env.VITEST) return null;
  return createKnowledgeHttp(client);
}
