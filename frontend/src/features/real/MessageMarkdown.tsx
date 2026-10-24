import Markdown from "react-markdown";

const allowedElements = [
  "p", "strong", "em", "ul", "ol", "li", "blockquote", "pre", "code", "br", "hr",
];

/** Validated bot text may format prose; it cannot embed active content or media. */
export default function MessageMarkdown({ text }: { text: string }) {
  return (
    <div className="ai-markdown">
      <Markdown allowedElements={allowedElements} unwrapDisallowed skipHtml>
        {text}
      </Markdown>
    </div>
  );
}
