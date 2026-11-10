import { beforeEach, describe, expect, it } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { AuthPage } from "./index";
import { useDemoStore } from "../../app/store";
describe("mock account entry", () => {
  beforeEach(() => {
    cleanup();
    useDemoStore.getState().reset();
  });
  it("does not expose a guest mode and explains mock authentication", () => {
    render(
      <MemoryRouter>
        <AuthPage />
      </MemoryRouter>,
    );
    expect(screen.getByText("Không có chế độ khách")).toBeInTheDocument();
    expect(
      screen.getByText(/Chưa có tài khoản nào được tạo trên server/),
    ).toBeInTheDocument();
    expect(useDemoStore.getState().user).toBeNull();
  });
  it("does not save invalid registration data", () => {
    render(
      <MemoryRouter>
        <AuthPage />
      </MemoryRouter>,
    );
    fireEvent.click(screen.getByRole("button", { name: "Đăng ký demo" }));
    fireEvent.click(
      screen.getByRole("button", { name: /Tạo tài khoản minh họa/ }),
    );
    expect(screen.getByRole("alert")).toHaveTextContent(
      "email demo đúng định dạng",
    );
    expect(useDemoStore.getState().user).toBeNull();
  });
});
