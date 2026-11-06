import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import type { Citation } from "../../../api/contracts";
import { CitationText } from "./CitationText";

function cite(text: string, url = "https://www.python.org/doc/"): Citation {
  return {
    sourceId: "py-docs",
    title: "Our Documentation | Python.org",
    url,
    start: 0,
    end: Array.from(text).length,
  };
}

describe("cited reply markdown", () => {
  it("renders emphasis and keeps the citation marker", () => {
    const text = "Tài liệu có tại **Python.org**. Xem thêm.";
    const html = renderToStaticMarkup(createElement(CitationText, { text, citations: [cite(text)] }));
    expect(html).toContain("<strong>Python.org</strong>");
    expect(html).not.toContain("**");
    expect(html).toContain('href="https://www.python.org/doc/"');
    expect(html).toContain(">[1]<");
    expect(html).toContain("Nguồn (1)");
  });

  it("keeps a non-maps markdown link inert beside a real citation", () => {
    const text = "Xem [ngoài](https://example.com) và **đậm**.";
    const html = renderToStaticMarkup(createElement(CitationText, { text, citations: [cite(text)] }));
    expect(html).toContain("<strong>đậm</strong>");
    expect(html).not.toContain("example.com");
    expect(html).toContain("ngoài");
    expect(html).toContain('href="https://www.python.org/doc/"');
  });
});
