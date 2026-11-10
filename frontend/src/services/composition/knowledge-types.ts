export type Citation = {
  sourceId: string;
  documentId: string;
  title: string;
  publisher: string;
  url: string | null;
  section: string | null;
  publishedAt: string | null;
  lastReviewed: string | null;
  applicability: string;
  countryScope: string[];
};

export type RetrievedChunk = {
  chunkId: string;
  text: string;
  score: number;
  matchKind: string;
  citation: Citation;
};

export type KnowledgeSearchResponse = {
  status: "ok" | "no_results";
  corpusVersion: string;
  mode: "hybrid" | "lexical" | "vector";
  degraded: boolean;
  latencyMs: number;
  chunks: RetrievedChunk[];
};

export type KnowledgeDocument = {
  documentId: string;
  title: string;
  sections: { heading: string; text: string }[];
  citation: Citation;
  derivedFrom: { sourceId: string; locator: string }[];
};

export type KnowledgeSourceInfo = {
  sourceId: string;
  publisher: string;
  title: string;
  url: string | null;
  verifiedOn: string;
  countryScope: string[];
  licenceClass: string;
};

export type CorpusInfo = {
  version: string;
  documents: number;
  chunks: number;
  publishedAt: string | null;
};

export type RealKnowledgeSearch = {
  search(
    q: string,
    filters: { topic?: string; age?: string },
    signal?: AbortSignal,
  ): Promise<KnowledgeSearchResponse>;
  document(id: string, signal?: AbortSignal): Promise<KnowledgeDocument>;
  sources(signal?: AbortSignal): Promise<KnowledgeSourceInfo[]>;
  corpus(signal?: AbortSignal): Promise<CorpusInfo>;
};

// The pre-branch composition test still supplies `{ live: true }`.
export type KnowledgeSearchService =
  { readonly live: true } | RealKnowledgeSearch;

export function isRealKnowledgeSearch(
  service: KnowledgeSearchService | null,
): service is RealKnowledgeSearch {
  return service !== null && "search" in service;
}
