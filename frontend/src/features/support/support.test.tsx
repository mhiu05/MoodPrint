import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import {
  createMemoryRouter,
  MemoryRouter,
  RouterProvider,
} from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { SupportPreparePage, UrgentPage, FindHelpPage } from "./index";
import { useDemoStore } from "../../app/store";
import { getServices } from "../../services/composition";

beforeEach(() => {
  cleanup();
  sessionStorage.clear();
  useDemoStore.getState().reset();
  useDemoStore.getState().login("student-1", "Mây");
  // jsdom does not implement the native dialog methods used by the shared Modal.
  HTMLDialogElement.prototype.showModal = function () {
    this.open = true;
  };
  HTMLDialogElement.prototype.close = function () {
    this.open = false;
  };
});
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});
function renderComposer(
  entry:
    | string
    | {
        pathname: string;
        search?: string;
        state?: { content: string };
      } = "/support/prepare",
) {
  const router = createMemoryRouter(
    [
      { path: "/support/prepare", element: <SupportPreparePage /> },
      { path: "/support", element: <h1>Support destination</h1> },
    ],
    { initialEntries: [entry] },
  );
  return { ...render(<RouterProvider router={router} />), router };
}
describe("support preparation", () => {
  it("keeps a failed trusted-contact save editable without claiming it was added", async () => {
    vi.spyOn(getServices().contacts, "save").mockRejectedValue(
      new Error("Chưa lưu được người tin cậy."),
    );
    render(
      <MemoryRouter>
        <FindHelpPage />
      </MemoryRouter>,
    );
    fireEvent.change(screen.getByLabelText("Tên gọi dễ nhớ"), {
      target: { value: "Cô mới" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Thêm người tin cậy" }));
    await screen.findByText("Chưa lưu được người tin cậy.");
    expect(screen.getByLabelText("Tên gọi dễ nhớ")).toHaveValue("Cô mới");
    expect(
      screen.queryByRole("button", { name: "Xóa Cô mới" }),
    ).not.toBeInTheDocument();
  });
  it("shows an empty connected-school state in a real workspace and saves a server draft without demo status", async () => {
    const demoUser = useDemoStore.getState().user!;
    useDemoStore.setState({
      workspace: { kind: "real", userId: demoUser.id },
      cases: [],
      plans: [],
      drafts: [],
      trustedPeople: [],
    });
    vi.spyOn(getServices().support, "listSchools").mockResolvedValue([]);
    const save = vi
      .spyOn(getServices().support, "save")
      .mockImplementation(async (draft) => {
        const canonical = { ...draft, version: 1 };
        useDemoStore.getState().putDraft(canonical);
        return canonical;
      });
    renderComposer();
    await screen.findByText("Chưa có trường kết nối");
    expect(
      screen.queryByRole("button", { name: "Lưu báo cáo demo" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("option", { name: "Trường Mẫu A (demo)" }),
    ).not.toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Nội dung xem trước"), {
      target: { value: "Lời nhắn thật đã chuẩn bị" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Lưu bản nháp" }));
    await screen.findByText(
      "Đã lưu bản nháp trong tài khoản. Chưa gửi cho ai.",
    );
    expect(save.mock.calls[0][0]).toMatchObject({
      status: "draft",
      demo: false,
      content: "Lời nhắn thật đã chuẩn bị",
    });
  });
  it("shows urgent contacts with no signed-in user", () => {
    useDemoStore.getState().logout();
    render(
      <MemoryRouter>
        <UrgentPage />
      </MemoryRouter>,
    );
    expect(screen.getByRole("link", { name: /Gọi 111/ })).toHaveAttribute(
      "href",
      "tel:111",
    );
    expect(screen.getByText(/24\/24/)).toBeInTheDocument();
  });
  it("adds and removes a trusted adult locally", async () => {
    render(
      <MemoryRouter>
        <FindHelpPage />
      </MemoryRouter>,
    );
    fireEvent.change(screen.getByLabelText("Tên gọi dễ nhớ"), {
      target: { value: "Cô thư viện" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Thêm người tin cậy" }));
    await waitFor(() =>
      expect(
        useDemoStore
          .getState()
          .trustedPeople.some((p) => p.label === "Cô thư viện"),
      ).toBe(true),
    );
    fireEvent.click(screen.getByRole("button", { name: "Xóa Cô thư viện" }));
    await waitFor(() =>
      expect(
        useDemoStore
          .getState()
          .trustedPeople.some((p) => p.label === "Cô thư viện"),
      ).toBe(false),
    );
  });
  it("preserves an editable roleplay draft after a failed save, then saves with its owner", async () => {
    useDemoStore.getState().setFailNextSave(true);
    renderComposer({
      pathname: "/support/prepare",
      state: { content: "Em muốn nhờ cô giúp." },
    });
    expect(screen.getByLabelText("Nội dung xem trước")).toHaveValue(
      "Em muốn nhờ cô giúp.",
    );
    fireEvent.click(screen.getByRole("button", { name: "Lưu bản nháp" }));
    await waitFor(() => expect(screen.getByRole("alert")).toBeInTheDocument());
    expect(screen.getByLabelText("Nội dung xem trước")).toHaveValue(
      "Em muốn nhờ cô giúp.",
    );
    fireEvent.click(screen.getByRole("button", { name: "Lưu bản nháp" }));
    await waitFor(() => expect(useDemoStore.getState().drafts).toHaveLength(1));
    expect(useDemoStore.getState().drafts[0].ownerId).toBe(
      useDemoStore.getState().user?.id,
    );
    expect(useDemoStore.getState().drafts[0].status).toBe("draft");
  });
  it("keeps saved custom text when recipient and identity change, with accurate saved metadata", async () => {
    const custom =
      "Cô Hạnh ơi,\n\nEm chỉ muốn nói phần em đã chọn. Đây là lời viết riêng của em.";
    const ownerId = useDemoStore.getState().user!.id;
    useDemoStore.getState().putDraft({
      id: "CUSTOM-DRAFT",
      ownerId,
      recipientType: "Giáo viên",
      identityMode: "alias",
      content: custom,
      status: "draft",
      createdAt: "2026-11-07T12:00:00Z",
      demo: true,
    });
    renderComposer("/support/prepare?draftId=CUSTOM-DRAFT");
    fireEvent.change(screen.getByLabelText("Người bạn muốn nhờ"), {
      target: { value: "Người chăm sóc" },
    });
    fireEvent.click(
      screen.getByRole("radio", { name: /Dùng tên hiển thị demo/ }),
    );
    expect(screen.getByLabelText("Nội dung xem trước")).toHaveValue(custom);
    fireEvent.click(screen.getByRole("button", { name: "Lưu bản nháp" }));
    await waitFor(() =>
      expect(
        useDemoStore.getState().drafts.find((d) => d.id === "CUSTOM-DRAFT")
          ?.recipientType,
      ).toBe("Người chăm sóc"),
    );
    expect(
      useDemoStore.getState().drafts.find((d) => d.id === "CUSTOM-DRAFT"),
    ).toMatchObject({ content: custom, identityMode: "disclose" });
  });
  it("keeps only the selected roleplay lines primary when a case is linked", () => {
    const caseId = useDemoStore
      .getState()
      .cases.find((c) => c.ownerId === useDemoStore.getState().user!.id)!.id;
    const selected =
      "Em chỉ chọn câu này từ buổi tập, không phải toàn bộ hồ sơ.";
    renderComposer({
      pathname: "/support/prepare",
      search: `?caseId=${caseId}`,
      state: { content: selected },
    });
    expect(
      screen.getByLabelText("Điều đã xảy ra và điều muốn nhờ"),
    ).toHaveValue(selected);
    fireEvent.change(screen.getByLabelText("Người bạn muốn nhờ"), {
      target: { value: "Người chăm sóc" },
    });
    expect(screen.getByLabelText("Nội dung xem trước")).toHaveValue(selected);
  });
  it("recovers unsaved content for the same student without replacing another incoming roleplay", async () => {
    const first = renderComposer();
    fireEvent.change(screen.getByLabelText("Nội dung xem trước"), {
      target: { value: "Lời nhắn chưa lưu mà em muốn giữ." },
    });
    await waitFor(() =>
      expect(Object.values(sessionStorage).join(" ")).toContain(
        "Lời nhắn chưa lưu",
      ),
    );
    first.unmount();
    const restored = renderComposer();
    expect(screen.getByLabelText("Nội dung xem trước")).toHaveValue(
      "Lời nhắn chưa lưu mà em muốn giữ.",
    );
    restored.unmount();
    renderComposer({
      pathname: "/support/prepare",
      state: { content: "Một đoạn mới được chọn từ roleplay khác." },
    });
    expect(screen.getByLabelText("Nội dung xem trước")).toHaveValue(
      "Một đoạn mới được chọn từ roleplay khác.",
    );
  });
  it("warns before leaving unsaved content and lets the student stay", async () => {
    renderComposer();
    fireEvent.change(screen.getByLabelText("Nội dung xem trước"), {
      target: { value: "Em chưa lưu lời nhắn này." },
    });
    fireEvent.click(screen.getByRole("link", { name: "Quay lại" }));
    expect(
      await screen.findByRole("button", { name: "Ở lại chỉnh sửa" }),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Ở lại chỉnh sửa" }));
    expect(screen.getByLabelText("Nội dung xem trước")).toHaveValue(
      "Em chưa lưu lời nhắn này.",
    );
  });
  it("requires confirmation before replacing a custom preview with a template", () => {
    renderComposer({
      pathname: "/support/prepare",
      state: { content: "Lời từ buổi tập phải được giữ." },
    });
    fireEvent.click(
      screen.getByRole("button", { name: /Cập nhật bản xem trước/ }),
    );
    expect(screen.getByLabelText("Nội dung xem trước")).toHaveValue(
      "Lời từ buổi tập phải được giữ.",
    );
    fireEvent.click(screen.getByRole("button", { name: "Giữ lời hiện tại" }));
    expect(screen.getByLabelText("Nội dung xem trước")).toHaveValue(
      "Lời từ buổi tập phải được giữ.",
    );
  });
  it("recovers later unsaved edits when a newly saved draft is reopened by its ID", async () => {
    const first = renderComposer();
    fireEvent.change(screen.getByLabelText("Nội dung xem trước"), {
      target: { value: "Bản đầu tiên đã lưu." },
    });
    fireEvent.click(screen.getByRole("button", { name: "Lưu bản nháp" }));
    await waitFor(() => expect(useDemoStore.getState().drafts).toHaveLength(1));
    const id = useDemoStore.getState().drafts[0].id;
    fireEvent.change(screen.getByLabelText("Nội dung xem trước"), {
      target: { value: "Chỉnh sửa tiếp theo chưa lưu." },
    });
    first.unmount();
    renderComposer(`/support/prepare?draftId=${id}`);
    expect(screen.getByLabelText("Nội dung xem trước")).toHaveValue(
      "Chỉnh sửa tiếp theo chưa lưu.",
    );
  });
});
