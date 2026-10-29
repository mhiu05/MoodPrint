import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import MessageMarkdown from "./MessageMarkdown";

describe("journal evidence links", () => {
  it("renders only an internal UUID entry link as navigable", () => {
    const html = renderToStaticMarkup(
      createElement(MessageMarkdown, {
        text: "[Bài viết](/self/entry/7ceaa454-e73a-4dd6-aaaf-145914c8a416)",
      }),
    );
    expect(html).toContain(
      'href="#/self/entry/7ceaa454-e73a-4dd6-aaaf-145914c8a416"',
    );
  });

  it.each([
    "https://example.com",
    "//example.com",
    "/self/entry/not-an-id",
    "/self/entry/7ceaa454-e73a-4dd6-aaaf-145914c8a416?token=secret",
    "javascript:alert(1)",
    "/privacy",
  ])("keeps unsupported target %s inert", (target) => {
    const html = renderToStaticMarkup(
      createElement(MessageMarkdown, { text: `[Nguồn](${target})` }),
    );
    expect(html).not.toContain("href=");
    expect(html).toContain("Nguồn");
  });
});
import { createElement } from "react";
