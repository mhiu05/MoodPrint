import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { useDemoStore } from "../../app/store";
import { ChatPage } from "./chat";
import { AnalysisPage } from "./analysis";
import { startFixtureAnalysis } from "./analysis-workflow";

beforeEach(() => {
  vi.stubGlobal("matchMedia", () => ({
    matches: true,
    addEventListener: () => {},
    removeEventListener: () => {},
  }));
  Element.prototype.scrollIntoView = () => {};
  useDemoStore.getState().reset();
  useDemoStore.getState().login("USER-AN");
  useDemoStore.getState().setPreferences({ reducedMotion: true });
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("AI journey continuity", () => {
  it("keeps the originating knowledge source when the first reply changes the route to a session", async () => {
    render(
      <MemoryRouter
        initialEntries={[
          "/ai/chat?articleId=KB-08&articleSlug=luu-anh-chup-co-ngu-canh&sourceIds=SRC-UNICEF,SRC-ESAFETY",
        ]}
      >
        <Routes>
          <Route path="/ai/chat" element={<ChatPage />} />
          <Route path="/ai/chat/:sessionId" element={<ChatPage />} />
        </Routes>
      </MemoryRouter>,
    );
    fireEvent.click(
      screen.getByRole("button", {
        name: /Các bạn gọi mình bằng tên mình ghét/,
      }),
    );
    await waitFor(() =>
      expect(
        screen.getByRole("link", { name: /Mở bài đã tham khảo/ }),
      ).toHaveAttribute("href", "/knowledge/luu-anh-chup-co-ngu-canh"),
    );
    const saved = useDemoStore.getState().chats[0];
    expect(saved).toMatchObject({
      sourceArticleId: "KB-08",
      sourceArticleSlug: "luu-anh-chup-co-ngu-canh",
      sourceIds: ["SRC-UNICEF", "SRC-ESAFETY"],
    });
  });
  it("provides recovery when a processing analysis is reopened without an active task", () => {
    const analysis = startFixtureAnalysis("multi");
    useDemoStore.getState().putAnalysis({ ...analysis, status: "processing" });
    render(
      <MemoryRouter initialEntries={[`/ai/analysis/${analysis.id}`]}>
        <Routes>
          <Route path="/ai/analysis/:analysisId" element={<AnalysisPage />} />
        </Routes>
      </MemoryRouter>,
    );
    expect(
      screen.getByRole("button", { name: /Thử mở lại kết quả/ }),
    ).toBeEnabled();
    expect(screen.queryByText("Đang mở kết quả mẫu…")).not.toBeInTheDocument();
  });
});
