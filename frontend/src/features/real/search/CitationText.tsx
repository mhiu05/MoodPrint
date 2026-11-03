import { Fragment } from "react";
import type { Citation } from "../../../api/contracts";
import { validCitations } from "../../../api/stream";
import MessageMarkdown from "../MessageMarkdown";

export function CitationText({ text, citations = [] }: { text: string; citations?: Citation[] }) {
  if (!citations.length) return <MessageMarkdown text={text} />;
  if (!validCitations(citations, text)) return <p>Chưa hiển thị được nguồn. Hãy tải lại cuộc trò chuyện.</p>;
  const points = Array.from(text), ends = [...new Set(citations.map(c => c.end))].sort((a,b) => a-b);
  const sources = [...new Map(citations.map(c => [c.url, c])).values()];
  let start = 0;
  return <div className="ai-cited-text"><p>{ends.map(end => {
    const segment = points.slice(start, end).join(""); start = end;
    return <Fragment key={end}>{segment}{citations.filter(c => c.end === end).map(c =>
      <a key={`${c.sourceId}-${c.end}`} href={c.url} target="_blank" rel="noopener noreferrer" referrerPolicy="no-referrer"
        className="citation-marker" aria-label={`Nguồn: ${c.title}`}>[{sources.findIndex(s => s.url === c.url)+1}]</a>)}</Fragment>;
  })}{points.slice(start).join("")}</p><details className="ai-sources"><summary>Nguồn ({sources.length})</summary><ol>{sources.map(s =>
    <li key={s.url}><a href={s.url} target="_blank" rel="noopener noreferrer" referrerPolicy="no-referrer">{s.title}<small>{new URL(s.url).hostname}</small></a></li>)}</ol></details></div>;
}
