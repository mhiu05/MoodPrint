import type { ReactNode } from "react";
import Markdown from "react-markdown";
import type { Citation } from "../../../api/contracts";
import { validCitations } from "../../../api/stream";
import MessageMarkdown, { MessageLink, messageMarkdownElements } from "../MessageMarkdown";

type MdNode = { type: string; value?: string; url?: string; children?: MdNode[] };

/** Private-use sentinels survive CommonMark and mark citation offsets in the source text. */
function withMarkers(text: string, citations: Citation[]) {
  const points = Array.from(text);
  const at = new Map<number, number[]>();
  citations.forEach((citation, index) => {
    const list = at.get(citation.end) ?? [];
    list.push(index);
    at.set(citation.end, list);
  });
  let marked = "";
  for (let index = 0; index <= points.length; index += 1) {
    for (const citationIndex of at.get(index) ?? []) marked += String.fromCodePoint(0xe000 + citationIndex);
    if (index < points.length) marked += points[index];
  }
  return marked;
}

function citationMarkers() {
  return (tree: MdNode) => {
    const visit = (node: MdNode) => {
      if (!node.children) return;
      const next: MdNode[] = [];
      for (const child of node.children) {
        if (child.type === "text" && child.value && /[\uE000-\uE007]/.test(child.value)) {
          let buffer = "";
          for (const character of child.value) {
            const code = character.codePointAt(0) ?? 0;
            if (code >= 0xe000 && code <= 0xe007) {
              if (buffer) next.push({ type: "text", value: buffer });
              buffer = "";
              next.push({
                type: "link",
                url: `#cite-${code - 0xe000}`,
                children: [{ type: "text", value: "\u200b" }],
              });
            } else buffer += character;
          }
          if (buffer) next.push({ type: "text", value: buffer });
        } else {
          visit(child);
          next.push(child);
        }
      }
      node.children = next;
    };
    visit(tree);
  };
}

function CitedAnchor({ href, children, citations }: { href?: string; children?: ReactNode; citations: Citation[] }) {
  const match = /^#cite-(\d+)$/.exec(href ?? "");
  if (!match) return <MessageLink href={href}>{children}</MessageLink>;
  const citation = citations[Number(match[1])];
  if (!citation) return <span>{children}</span>;
  const sources = [...new Map(citations.map((item) => [item.url, item])).values()];
  const number = sources.findIndex((item) => item.url === citation.url) + 1;
  return (
    <a href={citation.url} target="_blank" rel="noopener noreferrer" referrerPolicy="no-referrer" className="citation-marker" aria-label={`Nguồn: ${citation.title}`}>
      [{number}]
    </a>
  );
}

export function CitationText({ text, citations = [] }: { text: string; citations?: Citation[] }) {
  if (!citations.length) return <MessageMarkdown text={text} />;
  if (!validCitations(citations, text)) return <p>Chưa hiển thị được nguồn. Hãy tải lại cuộc trò chuyện.</p>;
  const sources = [...new Map(citations.map((item) => [item.url, item])).values()];
  return (
    <div className="ai-cited-text">
      <div className="ai-markdown">
        <Markdown
          allowedElements={messageMarkdownElements}
          unwrapDisallowed
          skipHtml
          remarkPlugins={[citationMarkers]}
          components={{ a: ({ href, children }) => <CitedAnchor href={href} citations={citations}>{children}</CitedAnchor> }}
        >
          {withMarkers(text, citations)}
        </Markdown>
      </div>
      <details className="ai-sources">
        <summary>Nguồn ({sources.length})</summary>
        <ol>
          {sources.map((source) => (
            <li key={source.url}>
              <a href={source.url} target="_blank" rel="noopener noreferrer" referrerPolicy="no-referrer">
                {source.title}
                <small>{new URL(source.url).hostname}</small>
              </a>
            </li>
          ))}
        </ol>
      </details>
    </div>
  );
}
