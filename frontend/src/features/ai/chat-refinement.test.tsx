import { afterEach, beforeEach, expect, it, vi } from "vitest";
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

beforeEach(() => {
  vi.stubGlobal("matchMedia", () => ({
    matches: true,
    addEventListener() {},
    removeEventListener() {},
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

function open(path = "/ai/chat") {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/ai/chat" element={<ChatPage />} />
        <Route path="/ai/chat/:sessionId" element={<ChatPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

it("recovers an unsent composer draft after unmount and store rehydration", async () => {
  const view = open();
  fireEvent.change(screen.getByRole("textbox", { name: "Điều bạn muốn kể" }), {
    target: { value: "Mình chưa sẵn sàng gửi" },
  });
  const savedId = useDemoStore.getState().chats[0]?.id;
  expect(savedId).toBeTruthy();
  view.unmount();
  await useDemoStore.persist.rehydrate();
  open(`/ai/chat/${savedId}`);
  expect(screen.getByRole("textbox")).toHaveValue("Mình chưa sẵn sàng gửi");
  expect(useDemoStore.getState().chats[0].messages).toHaveLength(0);
});

it("keeps the composer editable during a failed reply and preserves the next draft on retry", async () => {
  useDemoStore.getState().setFailNextSave(true);
  open();
  fireEvent.click(
    screen.getByRole("button", { name: /Các bạn gọi mình bằng tên mình ghét/ }),
  );
  const input = screen.getByRole("textbox", { name: "Điều bạn muốn kể" });
  expect(input).toBeEnabled();
  fireEvent.change(input, { target: { value: "Lời kể tiếp theo" } });
  // A real simulated save uses a timer; allow the state transition under parallel jsdom load.
  await screen.findByRole(
    "button",
    { name: "Thử lại phản hồi mẫu" },
    { timeout: 5000 },
  );
  expect(input).toHaveValue("Lời kể tiếp theo");
  fireEvent.click(screen.getByRole("button", { name: "Thử lại phản hồi mẫu" }));
  await waitFor(
    () => expect(useDemoStore.getState().chats[0].messages).toHaveLength(2),
    { timeout: 5000 },
  );
  expect(input).toHaveValue("Lời kể tiếp theo");
});

it("does not submit Enter during IME composition or Shift+Enter", () => {
  open();
  const input = screen.getByRole("textbox", { name: "Điều bạn muốn kể" });
  fireEvent.change(input, { target: { value: "Một câu chưa viết xong" } });
  fireEvent.keyDown(input, { key: "Enter", isComposing: true });
  expect(useDemoStore.getState().chats.flatMap((c) => c.messages)).toHaveLength(
    0,
  );
  fireEvent.keyDown(input, { key: "Enter", shiftKey: true });
  expect(useDemoStore.getState().chats.flatMap((c) => c.messages)).toHaveLength(
    0,
  );
});

it("records real local message times and presents them after a successful reply", async () => {
  open();
  fireEvent.change(screen.getByRole("textbox"), {
    target: { value: "Một lời kể" },
  });
  fireEvent.keyDown(screen.getByRole("textbox"), { key: "Enter" });
  await waitFor(() =>
    expect(useDemoStore.getState().chats[0].messages).toHaveLength(2),
  );
  const messages = useDemoStore.getState().chats[0].messages;
  for (const message of messages) {
    expect(message).toHaveProperty("createdAt");
  }
  expect(document.querySelectorAll("time[datetime]")).toHaveLength(2);
});
