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

  it("renders a validated Google Maps search link", () => {
    const target = "https://www.google.com/maps/search/?api=1&query=Ho+Van+Quan";
    const html = renderToStaticMarkup(
      createElement(MessageMarkdown, { text: `[Hồ Văn Quán](${target})` }),
    );
    expect(html).toContain(`href="${target.replaceAll("&", "&amp;")}"`);
    expect(html).toContain('target="_blank"');
    expect(html).toContain('rel="noopener noreferrer"');
    expect(html).toContain('referrerPolicy="no-referrer"');
    expect(html).toContain("Hồ Văn Quán");
  });

  it.each([
    "https://example.com",
    "https://www.google.com/search?q=maps",
    "https://maps.google.com/maps/search/?api=1&query=Ho",
    "http://www.google.com/maps/search/?api=1&query=Ho",
    "https://user:pass@www.google.com/maps/search/?api=1&query=Ho",
    "https://www.google.com/maps",
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
