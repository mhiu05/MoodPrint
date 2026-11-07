import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { useDemoStore } from "../../app/store";
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
  afterEach(cleanup);
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
      sessionStorage.getItem("moodprint-plan-draft-v1:USER-AN:CASE-AN-001"),
    ).toBeNull();
  });
});
