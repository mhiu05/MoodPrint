import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Button, EmptyState, Notice } from "../../components/ui";
import { getServices } from "../../services/composition";
import {
  isRealKnowledgeSearch,
  type KnowledgeDocument,
  type KnowledgeSearchResponse,
} from "../../services/composition/knowledge-types";
import { apiAge, apiTopic } from "../../services/http/knowledge";

type SearchSnapshot = {
  key: string;
  status: "loading" | "ready" | "error";
  result: KnowledgeSearchResponse | null;
  error: string;
};

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
  const [attempt, setAttempt] = useState(0);
  const [snapshot, setSnapshot] = useState<SearchSnapshot | null>(null);
  const [opened, setOpened] = useState<{
    id: string;
    document: KnowledgeDocument;
  } | null>(null);
  const trimmed = query.trim();
  const active = Boolean(live) && trimmed.length >= 2;
  const requestKey = `${trimmed}|${topic}|${age}|${attempt}`;

  useEffect(() => {
    if (!live || trimmed.length < 2) return;
    const controller = new AbortController();
    let ignore = false;
    live
      .search(
        trimmed,
        { topic: apiTopic(topic), age: apiAge(age) },
        controller.signal,
      )
      .then((response) => {
        if (!ignore) {
          setSnapshot({
            key: requestKey,
            status: "ready",
            result: response,
            error: "",
          });
        }
      })
      .catch((cause: unknown) => {
        if (ignore || controller.signal.aborted) return;
        setSnapshot({
          key: requestKey,
          status: "error",
          result: null,
          error:
            cause instanceof Error
              ? cause.message
              : "Chưa tra cứu được. Hãy thử lại.",
        });
      });
    return () => {
      ignore = true;
      controller.abort();
    };
  }, [live, trimmed, topic, age, attempt, requestKey]);

  useEffect(() => {
    if (!live || !documentId) return;
    const controller = new AbortController();
    let ignore = false;
    live
      .document(documentId, controller.signal)
      .then((document) => {
        if (!ignore) setOpened({ id: documentId, document });
      })
      .catch(() => {
        if (!ignore) setOpened(null);
      });
    return () => {
      ignore = true;
      controller.abort();
    };
  }, [live, documentId]);

  if (!live) return null;
  const current = active && snapshot?.key === requestKey ? snapshot : null;
  const status = !active ? "idle" : (current?.status ?? "loading");
  const result = current?.result ?? null;
  const error = current?.error ?? "";
  const document = opened?.id === documentId ? opened.document : null;

  return (
    <section
      className="knowledge-live"
      data-testid="knowledge-live"
      aria-label="Tra cứu từ nguồn"
    >
      <div className="knowledge-live-head">
        <h2>Tra cứu từ nguồn</h2>
        <p>Đừng nhập tên thật hoặc thông tin liên hệ.</p>
      </div>
      <div aria-live="polite">
        {status === "idle" && (
          <p>Gõ ít nhất hai ký tự để tra cứu nguồn đã xuất bản.</p>
        )}
        {status === "loading" && <p>Đang tìm trong nguồn…</p>}
        {status === "error" && (
          <Notice tone="error">
            <p>{error}</p>
            <Button
              variant="secondary"
              onClick={() => setAttempt((value) => value + 1)}
            >
              Thử lại
            </Button>
          </Notice>
        )}
        {status === "ready" && result?.degraded && (
          <p>Đang tìm theo từ khóa.</p>
        )}
        {status === "ready" && result?.chunks.length === 0 && (
          <EmptyState
            title="Chưa tìm thấy nguồn phù hợp"
            description="Kho tri thức hiện tại chưa có đủ thông tin cho câu hỏi này. Bạn có thể kiểm tra nguồn chính thức hoặc hỏi thầy cô, nhà trường. Nếu cần, thử dùng từ khác hoặc bỏ bớt bộ lọc."
          />
        )}
        {status === "ready" &&
          result?.chunks.map((chunk) => (
            <article
              key={chunk.chunkId}
              className="knowledge-retrieved"
              data-testid="retrieved-result"
            >
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
                {chunk.citation.lastReviewed
                  ? ` · ${chunk.citation.lastReviewed}`
                  : ""}
              </button>
            </article>
          ))}
      </div>
      {document && (
        <aside
          className="knowledge-drawer"
          role="dialog"
          aria-label={document.title}
        >
          <h2>{document.title}</h2>
          <p>{document.citation.applicability}</p>
          {document.sections.map((section) => (
            <section key={section.heading}>
              <h3>{section.heading}</h3>
              <p>{section.text}</p>
            </section>
          ))}
          {document.citation.url && (
            <a
              href={document.citation.url}
              target="_blank"
              rel="noopener noreferrer"
            >
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
