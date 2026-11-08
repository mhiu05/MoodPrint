import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { getServices } from "../../services/composition";
import { apiAge, apiTopic } from "../../services/http/knowledge";
import {
  isRealKnowledgeSearch,
  type KnowledgeDocument,
  type KnowledgeSearchResponse,
  type RealKnowledgeSearch,
} from "../../services/composition/knowledge-types";
import { Button, EmptyState, Notice } from "../../components/ui";

export function LiveKnowledgeSearch({
  query,
  topic,
  age,
}: {
  query: string;
  topic: string;
  age: string;
}) {
  const service = getServices().knowledgeSearch;
  const live = isRealKnowledgeSearch(service) ? service : null;
  const [params, setParams] = useSearchParams();
  const documentId = params.get("document") || "";
  const [state, setState] = useState<"idle" | "loading" | "ready" | "error">("idle");
  const [result, setResult] = useState<KnowledgeSearchResponse | null>(null);
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);
  const [document, setDocument] = useState<KnowledgeDocument | null>(null);

  useEffect(() => {
    if (!live || query.trim().length < 2) {
      setState("idle");
      setResult(null);
      return;
    }
    const controller = new AbortController();
    setState("loading");
    setError("");
    live
      .search(
        query,
        { topic: apiTopic(topic), age: apiAge(age) },
        controller.signal,
      )
      .then((response) => {
        setResult(response);
        setState("ready");
      })
      .catch((cause: unknown) => {
        if (controller.signal.aborted) return;
        setState("error");
        setError(cause instanceof Error ? cause.message : "Chưa tra cứu được. Hãy thử lại.");
      });
    return () => controller.abort();
  }, [live, query, topic, age, attempt]);

  useEffect(() => {
    if (!live || !documentId) {
      setDocument(null);
      return;
    }
    const controller = new AbortController();
    live
      .document(documentId, controller.signal)
      .then(setDocument)
      .catch(() => setDocument(null));
    return () => controller.abort();
  }, [live, documentId]);

  if (!live) return null;
  return (
    <section className="knowledge-live" data-testid="knowledge-live" aria-label="Tra cứu từ nguồn">
      <div className="knowledge-live-head">
        <h2>Tra cứu từ nguồn</h2>
        <p>Đừng nhập tên thật hoặc thông tin liên hệ.</p>
      </div>
      <div aria-live="polite">
        {state === "idle" && <p>Gõ ít nhất hai ký tự để tra cứu nguồn đã xuất bản.</p>}
        {state === "loading" && <p>Đang tìm trong nguồn…</p>}
        {state === "error" && (
          <Notice tone="error">
            <p>{error}</p>
            <Button variant="secondary" onClick={() => setAttempt((value) => value + 1)}>
              Thử lại
            </Button>
          </Notice>
        )}
        {state === "ready" && result?.degraded && <p>Đang tìm theo từ khóa.</p>}
        {state === "ready" && result?.chunks.length === 0 && (
          <EmptyState
            title="Chưa tìm thấy nguồn phù hợp"
            description="Thử bỏ bớt bộ lọc hoặc dùng từ khác. Bài trong thư viện mẫu vẫn nằm ở danh sách bên dưới."
          />
        )}
        {state === "ready" &&
          result?.chunks.map((chunk) => (
            <article key={chunk.chunkId} className="knowledge-retrieved" data-testid="retrieved-result">
              <h3>{chunk.citation.title}</h3>
              <p>{chunk.text}</p>
              <button
                type="button"
                className="knowledge-citation"
                data-testid="citation-chip"
                onClick={() =>
                  setParams((previous) => {
                    const next = new URLSearchParams(previous);
                    next.set("document", chunk.citation.documentId);
                    return next;
                  })
                }
              >
                {chunk.citation.publisher}
                {chunk.citation.lastReviewed ? ` · ${chunk.citation.lastReviewed}` : ""}
              </button>
            </article>
          ))}
      </div>
      {document && (
        <aside className="knowledge-drawer" role="dialog" aria-label={document.title}>
          <h2>{document.title}</h2>
          <p>{document.citation.applicability}</p>
          {document.sections.map((section) => (
            <section key={section.heading}>
              <h3>{section.heading}</h3>
              <p>{section.text}</p>
            </section>
          ))}
          {document.citation.url && (
            <a href={document.citation.url} target="_blank" rel="noopener noreferrer">
              Mở nguồn
            </a>
          )}
          <Button
            variant="ghost"
            onClick={() =>
              setParams((previous) => {
                const next = new URLSearchParams(previous);
                next.delete("document");
                return next;
              })
            }
          >
            Đóng
          </Button>
        </aside>
      )}
    </section>
  );
}

export type { RealKnowledgeSearch };
