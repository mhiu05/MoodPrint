import { useState } from "react";
import { Link } from "react-router-dom";
import type { Citation } from "../../../services/composition/companion-types";

const safeHref = (url: string | null | undefined) =>
  url && /^https?:\/\//i.test(url) ? url : null;

/** Chips come only from the citations the backend verified for this very answer. */
export function CitationChips({ citations }: { citations: Citation[] }) {
  const [open, setOpen] = useState<number | null>(null);
  if (!citations.length) return null;
  const active = open === null ? null : citations[open];
  const href = safeHref(active?.url);
  return (
    <div className="live-citations" aria-label="Nguồn tham khảo">
      <ul>
        {citations.map((citation, index) => (
          <li key={citation.sourceId}>
            <button
              type="button"
              className="live-chip"
              aria-expanded={open === index}
              aria-label={`Nguồn ${index + 1}: ${citation.title}`}
              onClick={() => setOpen(open === index ? null : index)}
            >
              [{index + 1}]
            </button>
          </li>
        ))}
      </ul>
      {active && (
        <div
          className="live-citation-card"
          role="region"
          aria-label={active.title}
        >
          <strong>{active.title}</strong>
          <span>{active.publisher}</span>
          {active.section && <span>Mục: {active.section}</span>}
          {active.lastReviewed && <span>Rà soát: {active.lastReviewed}</span>}
          <span>{active.applicability}</span>
          <div className="live-citation-links">
            {href && (
              <a href={href} target="_blank" rel="noopener noreferrer">
                Mở nguồn
              </a>
            )}
            <Link
              to={`/knowledge?document=${encodeURIComponent(active.documentId)}`}
            >
              Xem trong Thư viện
            </Link>
          </div>
        </div>
      )}
    </div>
  );
}
