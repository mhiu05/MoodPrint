import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  act,
} from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useDemoStore } from "../../app/store";
import { getServices } from "../../services/composition";
import { ApiError } from "../../services/http/client";
import { PlanPage } from "./index";

describe("action plan integration", () => {
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
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });
  it("waits for the canonical plan when navigating to another real case", async () => {
    const state = useDemoStore.getState();
    const original = state.plans.find((plan) => plan.caseId === "CASE-AN-001")!;
    const firstCase = state.cases.find((item) => item.id === "CASE-AN-001")!;
    state.putCase({ ...firstCase, id: "CASE-OTHER", title: "Hồ sơ tiếp theo" });
    const otherPlan = {
      ...original,
      id: "PLAN-OTHER",
      caseId: "CASE-OTHER",
      goal: "Mục tiêu trong bộ nhớ cũ",
      version: 1,
    };
    state.putPlan(otherPlan);
    useDemoStore.setState({
      workspace: { kind: "real", userId: state.user!.id },
    });
    let finish!: () => void;
    vi.spyOn(getServices().plans, "getForCase")
      .mockResolvedValueOnce(original)
      .mockImplementationOnce(
        () =>
          new Promise((resolve) => {
            finish = () => {
              const canonical = {
                ...otherPlan,
                goal: "Mục tiêu mới từ máy chủ",
                version: 2,
              };
              useDemoStore.getState().putPlan(canonical);
              resolve(canonical);
            };
          }),
      );
    const router = createMemoryRouter(
      [{ path: "/cases/:caseId/plan", element: <PlanPage /> }],
      { initialEntries: ["/cases/CASE-AN-001/plan"] },
    );
    render(<RouterProvider router={router} />);
    await screen.findByLabelText("Mục tiêu của bạn");
    await act(async () => {
      await router.navigate("/cases/CASE-OTHER/plan");
    });
    expect(screen.queryByLabelText("Mục tiêu của bạn")).not.toBeInTheDocument();
    await act(async () => {
      finish();
    });
    expect(await screen.findByLabelText("Mục tiêu của bạn")).toHaveValue(
      "Mục tiêu mới từ máy chủ",
    );
  });
  it("keeps edits typed while a save is pending and uses its canonical version for the next save", async () => {
    const original = useDemoStore
      .getState()
      .plans.find((p) => p.caseId === "CASE-AN-001")!;
    useDemoStore.getState().putPlan({ ...original, version: 1 });
    let finish!: () => void;
    const save = vi.spyOn(getServices().plans, "save").mockImplementationOnce(
      (item) =>
        new Promise((resolve) => {
          finish = () => {
            const canonical = { ...item, version: 2 };
            useDemoStore.getState().putPlan(canonical);
            resolve(canonical);
          };
        }),
    );
    render(
      <RouterProvider
        router={createMemoryRouter(
          [{ path: "/cases/:caseId/plan", element: <PlanPage /> }],
          { initialEntries: ["/cases/CASE-AN-001/plan"] },
        )}
      />,
    );
    fireEvent.change(screen.getByLabelText("Mục tiêu của bạn"), {
      target: { value: "Mục tiêu gửi lên" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Lưu thay đổi" }));
    fireEvent.change(screen.getByLabelText("Mục tiêu của bạn"), {
      target: { value: "Lời mới đang viết tiếp" },
    });
    finish();
    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: "Lưu thay đổi" }),
      ).toBeEnabled(),
    );
    expect(screen.getByLabelText("Mục tiêu của bạn")).toHaveValue(
      "Lời mới đang viết tiếp",
    );
    expect(save.mock.calls[0][0].goal).toBe("Mục tiêu gửi lên");
    expect(
      useDemoStore.getState().plans.find((item) => item.id === original.id)
        ?.goal,
    ).toBe("Mục tiêu gửi lên");
  });
  it("keeps the edited goal on a server version conflict and saves with the merged latest version", async () => {
    const original = useDemoStore
      .getState()
      .plans.find((p) => p.caseId === "CASE-AN-001")!;
    useDemoStore.getState().putPlan({ ...original, version: 1 });
    const latest = {
      ...original,
      version: 2,
      items: original.items.map((step, index) =>
        index === 1 ? { ...step, status: "done" as const } : step,
      ),
    };
    const save = vi
      .spyOn(getServices().plans, "save")
      .mockRejectedValueOnce(
        new ApiError(409, "version_conflict", "Dữ liệu đã thay đổi.", {
          latest,
        }),
      )
      .mockImplementationOnce(async (item) => {
        const canonical = {
          ...item,
          version: 3,
          lastUpdated: "2026-11-09T00:00:00Z",
        };
        useDemoStore.getState().putPlan(canonical);
        return canonical;
      });
    render(
      <RouterProvider
        router={createMemoryRouter(
          [{ path: "/cases/:caseId/plan", element: <PlanPage /> }],
          { initialEntries: ["/cases/CASE-AN-001/plan"] },
        )}
      />,
    );
    fireEvent.change(screen.getByLabelText("Mục tiêu của bạn"), {
      target: { value: "Mục tiêu đang viết khi có xung đột" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Lưu thay đổi" }));
    await screen.findByRole("button", {
      name: "Giữ chỉnh sửa và cập nhật tiến độ mới",
    });
    expect(screen.getByLabelText("Mục tiêu của bạn")).toHaveValue(
      "Mục tiêu đang viết khi có xung đột",
    );
    fireEvent.click(
      screen.getByRole("button", {
        name: "Giữ chỉnh sửa và cập nhật tiến độ mới",
      }),
    );
    expect(
      screen.getByRole("combobox", { name: "Trạng thái bước 2" }),
    ).toHaveValue("done");
    fireEvent.click(screen.getByRole("button", { name: "Lưu thay đổi" }));
    await waitFor(() => expect(save).toHaveBeenCalledTimes(2));
    expect(save.mock.calls[1][0]).toMatchObject({
      version: 2,
      goal: "Mục tiêu đang viết khi có xung đột",
    });
    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: "Lưu thay đổi" }),
      ).toBeDisabled(),
    );
  });
  it("preserves a newer Home completion when recovering an older goal edit", async () => {
    const mount = () =>
      render(
        <RouterProvider
          router={createMemoryRouter(
            [{ path: "/cases/:caseId/plan", element: <PlanPage /> }],
            { initialEntries: ["/cases/CASE-AN-001/plan"] },
          )}
        />,
      );
    const first = mount();
    fireEvent.change(screen.getByLabelText("Mục tiêu của bạn"), {
      target: { value: "Mục tiêu đang viết dở" },
    });
    first.unmount();
    const beforeHome = useDemoStore
      .getState()
      .plans.find((p) => p.caseId === "CASE-AN-001")!;
    useDemoStore.getState().putPlan({
      ...beforeHome,
      lastUpdated: "2026-11-08T10:30:00+07:00",
      items: beforeHome.items.map((step, index) =>
        index === 1 ? { ...step, status: "done" } : step,
      ),
    });
    mount();
    expect(screen.getByLabelText("Mục tiêu của bạn")).toHaveValue(
      "Mục tiêu đang viết dở",
    );
    expect(screen.getByRole("button", { name: "Lưu thay đổi" })).toBeDisabled();
    fireEvent.click(
      screen.getByRole("button", {
        name: "Giữ chỉnh sửa và cập nhật tiến độ mới",
      }),
    );
    expect(
      screen.getByRole("combobox", { name: "Trạng thái bước 2" }),
    ).toHaveValue("done");
    expect(screen.getByLabelText("Mục tiêu của bạn")).toHaveValue(
      "Mục tiêu đang viết dở",
    );
    fireEvent.click(screen.getByRole("button", { name: "Lưu thay đổi" }));
    await screen.findAllByText("Đã lưu trong demo. Home đã được cập nhật.");
    const saved = useDemoStore
      .getState()
      .plans.find((p) => p.caseId === "CASE-AN-001")!;
    expect(saved.goal).toBe("Mục tiêu đang viết dở");
    expect(saved.items[1].status).toBe("done");
  });
  it("retries a failed save and writes the edited goal into the canonical Home store", async () => {
    render(
      <RouterProvider
        router={createMemoryRouter(
          [{ path: "/cases/:caseId/plan", element: <PlanPage /> }],
          { initialEntries: ["/cases/CASE-AN-001/plan"] },
        )}
      />,
    );
    const original = useDemoStore
      .getState()
      .plans.find((p) => p.caseId === "CASE-AN-001")!;
    fireEvent.change(screen.getByLabelText("Mục tiêu của bạn"), {
      target: { value: "Chuẩn bị một câu mở đầu ngắn" },
    });
    useDemoStore.getState().setFailNextSave(true);
    fireEvent.click(screen.getByRole("button", { name: "Lưu thay đổi" }));
    await screen.findByRole("alert");
    expect(
      useDemoStore.getState().plans.find((p) => p.id === original.id)?.goal,
    ).toBe(original.goal);
    expect(screen.getByLabelText("Mục tiêu của bạn")).toHaveValue(
      "Chuẩn bị một câu mở đầu ngắn",
    );
    fireEvent.click(screen.getByRole("button", { name: "Thử lưu lại" }));
    await screen.findAllByText("Đã lưu trong demo. Home đã được cập nhật.");
    expect(
      useDemoStore.getState().plans.find((p) => p.id === original.id)?.goal,
    ).toBe("Chuẩn bị một câu mở đầu ngắn");
    expect(
      useDemoStore.getState().cases.find((c) => c.id === "CASE-AN-001")
        ?.linkedPlanId,
    ).toBe(original.id);
    expect(
      sessionStorage.getItem("safevoice-plan-draft-v1:USER-AN:CASE-AN-001"),
    ).toBeNull();
  });
});
