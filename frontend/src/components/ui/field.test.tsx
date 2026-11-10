import { render, screen } from "@testing-library/react";
import { expect, it } from "vitest";
import { Field, Modal } from "./index";
it("does not restore old focus when an unopened modal unmounts", () => {
  const trigger = document.createElement("button");
  const destination = document.createElement("button");
  document.body.append(trigger, destination);
  trigger.focus();
  const view = render(
    <Modal open={false} title="Mẫu" onClose={() => {}}>
      Nội dung mẫu
    </Modal>,
  );
  destination.focus();
  view.unmount();
  expect(document.activeElement).toBe(destination);
  trigger.remove();
  destination.remove();
});
it("associates a custom textarea label and validation error with the control", () => {
  render(
    <Field label="Nội dung mẫu" error="Bạn cần ghi một điều đã xảy ra">
      <textarea />
    </Field>,
  );
  const control = screen.getByRole("textbox", { name: "Nội dung mẫu" });
  expect(control).toHaveAccessibleDescription("Bạn cần ghi một điều đã xảy ra");
  expect(control).toHaveAttribute("aria-invalid", "true");
});
