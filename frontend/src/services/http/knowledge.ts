import type { StreamClient } from "../http/client";
import type {
  CorpusInfo,
  KnowledgeDocument,
  KnowledgeSearchResponse,
  KnowledgeSourceInfo,
  RealKnowledgeSearch,
} from "../composition/knowledge-types";

const topicMap: Record<string, string> = {
  "Nhận biết": "definition",
  "Trực tiếp": "physical",
  "Cô lập": "exclusion",
  Online: "cyber",
  "Đe dọa": "cyber",
  "Ảnh riêng tư": "evidence",
  "Nhờ hỗ trợ": "help-seeking",
  "Người chứng kiến": "bystander",
  "Chăm sóc bản thân": "emotional-impact",
};

export function apiTopic(label: string): string | undefined {
  return topicMap[label];
}

export function apiAge(label: string): string | undefined {
  if (!label) return undefined;
  return label.replace("–", "-").replace("—", "-");
}

export function createKnowledgeHttp(client: StreamClient): RealKnowledgeSearch {
  return {
    search(q, filters, signal) {
      const params = new URLSearchParams({ q });
      if (filters.topic) params.set("topic", filters.topic);
      if (filters.age) params.set("age", filters.age);
      return client<KnowledgeSearchResponse>(`/v1/knowledge/search?${params}`, {
        signal,
      });
    },
    document(id, signal) {
      return client<KnowledgeDocument>(
        `/v1/knowledge/documents/${encodeURIComponent(id)}`,
        { signal },
      );
    },
    sources(signal) {
      return client<KnowledgeSourceInfo[]>("/v1/knowledge/sources", { signal });
    },
    corpus(signal) {
      return client<CorpusInfo>("/v1/knowledge/corpus", { signal });
    },
  };
}
