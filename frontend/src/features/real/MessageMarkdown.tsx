import Markdown from "react-markdown";

const allowedElements = [
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

/** Validated bot text may format prose; it cannot embed active content or media. */
export default function MessageMarkdown({ text }: { text: string }) {
  return (
    <div className="ai-markdown">
      <Markdown
        allowedElements={allowedElements}
        unwrapDisallowed
        skipHtml
        components={{
          a: ({ href, children }) =>
            /^\/self\/entry\/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(
              href ?? "",
            ) ? (
              <a href={`#${href}`}>{children}</a>
            ) : (
              <span>{children}</span>
            ),
        }}
      >
        {text}
      </Markdown>
    </div>
  );
}
