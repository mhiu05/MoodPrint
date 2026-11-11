import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { useDemoStore } from "../../app/store";
import { CaseWizard } from "./wizard";
import type { Incident } from "../../types";

function mountWizard(
  entry:
    | string
    | {
        pathname: string;
        state: { prefill: Partial<Incident> };
      } = "/cases/new",
) {
  const router = createMemoryRouter(
    [
      { path: "/cases/new", element: <CaseWizard /> },
      { path: "/cases/:caseId", element: <h1>Hồ sơ đã lưu</h1> },
    ],
    { initialEntries: [entry] },
  );
  return { ...render(<RouterProvider router={router} />), router };
}
describe("case wizard recovery", () => {
  beforeEach(() => {
    sessionStorage.clear();
    useDemoStore.getState().reset();
    useDemoStore.getState().login("USER-AN");
    HTMLDialogElement.prototype.showModal = function () {
      this.open = true;
    };
    HTMLDialogElement.prototype.close = function () {
      this.open = false;
    };
  });
  afterEach(cleanup);
  it("keeps an imported chat story separate from another draft and retains its source across reload", async () => {
    const manual = mountWizard();
    fireEvent.change(screen.getByLabelText("Đặt tên hồ sơ"), {
      target: { value: "Bản nháp chuyện A" },
    });
    manual.unmount();
    useDemoStore.getState().putChat({
      id: "CHAT-B",
      ownerId: "USER-AN",
      title: "Chuyện B",
      scenarioId: "SC-01",
      messages: [],
      cursor: 0,
    });
    const imported = mountWizard({
      pathname: "/cases/new",
      state: {
        prefill: {
          title: "Chuyện B từ hội thoại",
          summary: "Đây là lời kể đã xác nhận từ B.",
          linkedChatIds: ["CHAT-B"],
          evidenceIds: ["SOURCE-B"],
        },
      },
    });
    expect(screen.getByLabelText("Đặt tên hồ sơ")).toHaveValue(
      "Chuyện B từ hội thoại",
    );
    fireEvent.click(screen.getByRole("button", { name: "Tiếp tục" }));
    expect(screen.getByLabelText("Chuyện gì đã xảy ra?")).toHaveValue(
      "Đây là lời kể đã xác nhận từ B.",
    );
    const resumeUrl = `/cases/new${imported.router.state.location.search}`;
    imported.unmount();
    mountWizard(resumeUrl);
    expect(screen.getByLabelText("Chuyện gì đã xảy ra?")).toHaveValue(
      "Đây là lời kể đã xác nhận từ B.",
    );
    fireEvent.click(screen.getByRole("button", { name: "Lưu nháp" }));
    await screen.findByText("Hồ sơ đã lưu");
    const saved = useDemoStore
      .getState()
      .cases.find((c) => c.title === "Chuyện B từ hội thoại")!;
    expect(saved.summary).toBe("Đây là lời kể đã xác nhận từ B.");
    expect(saved.linkedChatIds).toEqual(["CHAT-B"]);
    expect(saved.evidenceIds).toContain("SOURCE-B");
    expect(
      useDemoStore.getState().chats.find((chat) => chat.id === "CHAT-B")
        ?.linkedCaseId,
    ).toBe(saved.id);
    expect(
      sessionStorage.getItem("safevoice-case-draft-v1:USER-AN:new"),
    ).toContain("Bản nháp chuyện A");
  });
  it("restores the unfinished story and current step after a reload", async () => {
    const first = mountWizard();
    fireEvent.change(screen.getByLabelText("Đặt tên hồ sơ"), {
      target: { value: "Câu chuyện mẫu" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Tiếp tục" }));
    fireEvent.change(screen.getByLabelText("Chuyện gì đã xảy ra?"), {
      target: { value: "Mình chưa nhớ ngày nhưng nhớ lời nói." },
    });
    await waitFor(() =>
      expect(
        sessionStorage.getItem("safevoice-case-draft-v1:USER-AN:new"),
      ).toContain("Mình chưa nhớ ngày"),
    );
    first.unmount();
    mountWizard();
    expect(screen.getByLabelText("Chuyện gì đã xảy ra?")).toHaveValue(
      "Mình chưa nhớ ngày nhưng nhớ lời nói.",
    );
    expect(
      screen.getByText(/Đã khôi phục phần bạn đang viết/),
    ).toBeInTheDocument();
  });
  it("keeps failed-save input and clears the recovery draft only after a successful retry", async () => {
    mountWizard();
    fireEvent.change(screen.getByLabelText("Đặt tên hồ sơ"), {
      target: { value: "Nháp thử lại" },
    });
    useDemoStore.getState().setFailNextSave(true);
    fireEvent.click(screen.getByRole("button", { name: "Lưu nháp" }));
    await screen.findByRole("alert");
    expect(screen.getByLabelText("Đặt tên hồ sơ")).toHaveValue("Nháp thử lại");
    expect(
      useDemoStore.getState().cases.some((c) => c.title === "Nháp thử lại"),
    ).toBe(false);
    expect(
      sessionStorage.getItem("safevoice-case-draft-v1:USER-AN:new"),
    ).toContain("Nháp thử lại");
    fireEvent.click(screen.getByRole("button", { name: "Thử lưu lại" }));
    await screen.findByText("Hồ sơ đã lưu");
    expect(
      useDemoStore.getState().cases.find((c) => c.title === "Nháp thử lại")
        ?.status,
    ).toBe("draft");
    expect(
      sessionStorage.getItem("safevoice-case-draft-v1:USER-AN:new"),
    ).toBeNull();
  });
});
