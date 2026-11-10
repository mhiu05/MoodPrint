import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
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
  HTMLDialogElement.prototype.showModal = function () {
    this.open = true;
  };
  HTMLDialogElement.prototype.close = function () {
    this.open = false;
  };
  useDemoStore.getState().reset();
  useDemoStore.getState().login("USER-AN");
  useDemoStore.getState().setPreferences({ reducedMotion: true });
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("AI journey continuity", () => {
  it("keeps fixture analysis on the device and hides real-case creation", () => {
    const userId = useDemoStore.getState().user!.id;
    useDemoStore.setState({ workspace: { kind: "real", userId } });
    const analysis = startFixtureAnalysis("multi");
    useDemoStore.getState().putAnalysis({
      ...analysis,
      status: "review",
      confirmedIds: [analysis.evidenceIds[0]],
    });
    const first = useDemoStore
      .getState()
      .evidence.find((item) => item.id === analysis.evidenceIds[0])!;
    useDemoStore
      .getState()
      .putEvidence({ ...first, reviewStatus: "confirmed" });
    render(
      <MemoryRouter initialEntries={[`/ai/analysis/${analysis.id}`]}>
        <Routes>
          <Route path="/ai/analysis/:analysisId" element={<AnalysisPage />} />
        </Routes>
      </MemoryRouter>,
    );
    expect(
      screen.queryByRole("button", {
        name: "Tạo hồ sơ từ nội dung đã xác nhận",
      }),
    ).not.toBeInTheDocument();
    expect(
      screen.getAllByText(/Bộ ảnh mẫu không thể lưu vào hồ sơ thật/).length,
    ).toBeGreaterThan(0);
    expect(localStorage.getItem(`moodprint-sim-v1:${userId}`)).toContain(
      analysis.id,
    );
  });
  it("prefills real-case text from simulated chat without linking a local chat ID", () => {
    const userId = useDemoStore.getState().user!.id;
    useDemoStore.setState({ workspace: { kind: "real", userId } });
    useDemoStore.getState().putChat({
      id: "CHAT-LOCAL",
      ownerId: userId,
      title: "Lời kể",
      scenarioId: "SC-01",
      cursor: 0,
      messages: [
        { id: "USER-TEXT", speaker: "user", body: "Lời em tự kể" },
        { id: "AI-TEXT", speaker: "ai", body: "Phản hồi mô phỏng" },
      ],
    });
    function Destination() {
      const location = useLocation();
      return <pre>{JSON.stringify(location.state)}</pre>;
    }
    render(
      <MemoryRouter initialEntries={["/ai/chat/CHAT-LOCAL"]}>
        <Routes>
          <Route path="/ai/chat/:sessionId" element={<ChatPage />} />
          <Route path="/cases/new" element={<Destination />} />
        </Routes>
      </MemoryRouter>,
    );
    fireEvent.click(
      screen.getByRole("button", { name: /Tùy chọn cuộc trò chuyện/ }),
    );
    fireEvent.click(
      screen.getByRole("button", { name: "Lưu lời kể vào hồ sơ" }),
    );
    fireEvent.click(screen.getByRole("checkbox", { name: /Mình đã kiểm tra/ }));
    fireEvent.click(
      screen.getByRole("button", { name: "Xác nhận và tiếp tục" }),
    );
    expect(screen.getByText(/Lời em tự kể/)).not.toHaveTextContent(
      "linkedChatIds",
    );
  });
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
