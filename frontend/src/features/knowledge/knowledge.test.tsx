import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ArticlePage, KnowledgeHub } from "./index";
import { knowledgeArticles, filterKnowledge } from "../../mocks/data/knowledge";
import { knowledgeSources } from "../../mocks/data/sources";
import { useDemoStore } from "../../app/store";
import { getServices } from "../../services/composition";

beforeEach(() => {
  cleanup();
  useDemoStore.getState().reset();
});
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});
describe("knowledge discovery", () => {
  it("does not claim a bookmark was saved when its service rejects the write", async () => {
    vi.spyOn(getServices().knowledgeState, "toggleBookmark").mockRejectedValue(
      new Error("Chưa lưu được bài viết."),
    );
    const article = knowledgeArticles.find((item) => item.id === "KB-02")!;
    render(
      <MemoryRouter initialEntries={[`/knowledge/${article.slug}`]}>
        <Routes>
          <Route path="/knowledge/:slug" element={<ArticlePage />} />
        </Routes>
      </MemoryRouter>,
    );
    fireEvent.click(screen.getByRole("button", { name: "Lưu bài viết" }));
    await screen.findByText("Chưa lưu được bài viết.");
    expect(
      screen.getByRole("button", { name: "Lưu bài viết" }),
    ).toHaveAttribute("aria-pressed", "false");
    expect(useDemoStore.getState().bookmarks).not.toContain(article.id);
  });
  it("finds Vietnamese titles without accents and intersects filters", () => {
    expect(
      filterKnowledge(knowledgeArticles, { query: "bat nat online" }).some(
        (a) => a.id === "KB-06",
      ),
    ).toBe(true);
    expect(
      filterKnowledge(knowledgeArticles, { query: "khongtimthaychude" }),
    ).toEqual([]);
    expect(
      filterKnowledge(knowledgeArticles, {
        topic: "Online",
        format: "quiz",
      }).every((a) => a.topics.includes("Online") && a.format === "quiz"),
    ).toBe(true);
  });
  it("has independently authored learning activities and resolvable source records", () => {
    expect(knowledgeArticles.length).toBeGreaterThanOrEqual(24);
    expect(new Set(knowledgeArticles.map((a) => a.slug)).size).toBe(
      knowledgeArticles.length,
    );
    expect(
      knowledgeArticles.filter((a) => a.scenario).length,
    ).toBeGreaterThanOrEqual(10);
    expect(
      knowledgeArticles.filter((a) => a.quiz).length,
    ).toBeGreaterThanOrEqual(5);
    expect(
      knowledgeArticles.every(
        (a) =>
          a.sourceIds.length &&
          a.sourceIds.every((id) => knowledgeSources.some((s) => s.id === id)),
      ),
    ).toBe(true);
  });
  it("gives choice feedback and persists bookmarks and reading state", () => {
    const article = knowledgeArticles.find((a) => a.id === "KB-02")!;
    render(
      <MemoryRouter initialEntries={[`/knowledge/${article.slug}`]}>
        <Routes>
          <Route path="/knowledge/:slug" element={<ArticlePage />} />
        </Routes>
      </MemoryRouter>,
    );
    fireEvent.click(
      screen.getByRole("button", {
        name: new RegExp(article.scenario!.options[0].label),
      }),
    );
    expect(
      screen.getByText(article.scenario!.options[0].feedback),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Lưu bài viết" }));
    expect(useDemoStore.getState().bookmarks).toContain(article.id);
    fireEvent.click(screen.getByRole("button", { name: "Đánh dấu đã đọc" }));
    expect(useDemoStore.getState().readIds).toContain(article.id);
    expect(screen.getByRole("link", { name: /Hỏi AI/ })).toHaveAttribute(
      "href",
      expect.stringContaining("articleId=KB-02"),
    );
  });
  it("lets an empty search recover without losing navigation", () => {
    render(
      <MemoryRouter>
        <KnowledgeHub />
      </MemoryRouter>,
    );
    fireEvent.change(screen.getByRole("searchbox"), {
      target: { value: "zzzzzzzz" },
    });
    expect(screen.getByText("Chưa tìm thấy bài phù hợp")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Xóa bộ lọc" }));
    expect(
      screen.getAllByRole("link", { name: /Bắt nạt là gì/ }).length,
    ).toBeGreaterThan(0);
  });
  it.each([
    ["online", "Online"],
    ["communication", "Nhờ hỗ trợ"],
  ])("applies the Home topic deep link %s", (param, expected) => {
    render(
      <MemoryRouter initialEntries={[`/support/knowledge?topic=${param}`]}>
        <KnowledgeHub />
      </MemoryRouter>,
    );
    expect(screen.getByLabelText("Chủ đề")).toHaveValue(expected);
    expect(
      screen.queryByRole("link", { name: "Bắt nạt là gì?" }),
    ).not.toBeInTheDocument();
  });
  it("applies the Settings search deep link", () => {
    render(
      <MemoryRouter
        initialEntries={["/support/knowledge?search=luu%20anh%20chup"]}
      >
        <KnowledgeHub />
      </MemoryRouter>,
    );
    expect(screen.getByRole("searchbox")).toHaveValue("luu anh chup");
    expect(
      screen.getByRole("link", { name: "Lưu ảnh chụp với đủ ngữ cảnh" }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("link", { name: "Bắt nạt là gì?" }),
    ).not.toBeInTheDocument();
  });
});
