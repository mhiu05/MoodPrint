import type { ReactNode } from "react";
import Markdown from "react-markdown";
import { safeSourceUrl } from "../../api/stream";

export const messageMarkdownElements = [
  "p",
  "strong",
  "em",
  "ul",
  "ol",
  "li",
  "blockquote",
  "pre",
  "code",
  "br",
  "hr",
  "a",
];

const journalEntry = /^\/self\/entry\/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/** Same host and path the places card already allows. */
function mapsHref(href: string | undefined): string | null {
  if (!safeSourceUrl(href)) return null;
  const url = new URL(href);
  return url.hostname === "www.google.com" && url.pathname.startsWith("/maps/") ? href : null;
}

export function MessageLink({ href, children }: { href?: string; children?: ReactNode }) {
  if (journalEntry.test(href ?? "")) return <a href={`#${href}`}>{children}</a>;
  const maps = mapsHref(href);
  if (maps) {
    return (
      <a href={maps} target="_blank" rel="noopener noreferrer" referrerPolicy="no-referrer">
        {children}
      </a>
    );
  }
  return <span>{children}</span>;
}

/** Validated bot text may format prose; it cannot embed active content or media. */
export default function MessageMarkdown({ text }: { text: string }) {
  return (
    <div className="ai-markdown">
      <Markdown
        allowedElements={messageMarkdownElements}
        unwrapDisallowed
        skipHtml
        components={{ a: MessageLink }}
      >
        {text}
      </Markdown>
    </div>
  );
}
