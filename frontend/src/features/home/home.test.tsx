import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { useDemoStore } from "../../app/store";
import { getServices } from "../../services/composition";
import { HomePage } from "./index";

beforeEach(() => {
  useDemoStore.getState().reset();
  useDemoStore.getState().login("USER-AN");
});
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});
it("keeps the canonical checkbox unchanged when saving a Home step fails", async () => {
  vi.spyOn(getServices().plans, "setItemStatus").mockRejectedValue(
    new Error("Chưa cập nhật được bước."),
  );
  render(
    <MemoryRouter>
      <HomePage />
    </MemoryRouter>,
  );
  const checkbox = screen
    .getAllByRole("checkbox")
    .find((input) => !(input as HTMLInputElement).checked)!;
  fireEvent.click(checkbox);
  await screen.findByText("Chưa cập nhật được bước.");
  expect(checkbox).not.toBeChecked();
});
