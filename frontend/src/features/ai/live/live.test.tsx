import { afterEach, describe, expect, it, vi, beforeEach } from "vitest";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import type {
  LiveCompanion,
  LiveEvent,
} from "../../../services/composition/companion-types";
import { LiveChatPage, Thread } from "./live-chat";
import { LiveAnalysisPage } from "./live-analysis";
import { LiveRoleplayPage } from "./live-roleplay";
import { useWorkspaceStore } from "../../../app/store";

// Minimal stand-in for user-event (not a dependency of this project).
const userEvent = {
  async click(element: Element) {
    fireEvent.click(element);
    await Promise.resolve();
  },
  async clear(element: Element) {
    fireEvent.change(element, { target: { value: "" } });
  },
  async type(element: Element, text: string) {
    const enter = text.endsWith("{Enter}");
    const typed = enter ? text.slice(0, -"{Enter}".length) : text;
    const field = element as HTMLInputElement;
    fireEvent.change(field, { target: { value: field.value + typed } });
    if (enter) fireEvent.keyDown(field, { key: "Enter" });
    await Promise.resolve();
  },
};

const evidenceList = vi.fn();
const evidenceReview = vi.fn();
vi.mock("../../../services/composition", () => ({
  getServices: () => ({
    evidence: { list: evidenceList, review: evidenceReview },
  }),
}));

let seq = 0;
const ev = (event: string, data: unknown): LiveEvent =>
  ({ v: 1, seq: ++seq, runId: "run-1", event, data }) as LiveEvent;
async function* events(...list: LiveEvent[]) {
  for (const item of list) yield item;
}
const citation = {
  sourceId: "S1",
  documentId: "doc-1",
  title: "Tìm người hỗ trợ",
  publisher: "Nguồn thử",
  url: "https://example.org/a",
  section: null,
  publishedAt: null,
  lastReviewed: "2026-11-07",
  applicability: "Tổng hợp",
  countryScope: ["VN"],
};

function fake(overrides: Partial<LiveCompanion> = {}): LiveCompanion {
  const base = {
    live: true,
    conversations: {
      list: vi.fn(async () => []),
      create: vi.fn(),
      remove: vi.fn(),
      messages: vi.fn(async () => []),
      attachments: vi.fn(async () => ({})),
    },
    send: vi.fn(() => events()),
    approve: vi.fn(() => events()),
    cancel: vi.fn(async () => "cancelled"),
    pendingApprovals: vi.fn(async () => []),
    run: vi.fn(),
    memory: {
      candidates: vi.fn(async () => []),
      decide: vi.fn(),
      list: vi.fn(async () => []),
      edit: vi.fn(),
      remove: vi.fn(),
    },
    analyses: { create: vi.fn(), get: vi.fn() },
    roleplay: {
      scenarios: vi.fn(async () => []),
      create: vi.fn(),
      get: vi.fn(),
      list: vi.fn(async () => []),
      complete: vi.fn(),
      abandon: vi.fn(),
    },
  };
  return { ...base, ...overrides } as unknown as LiveCompanion;
}
// Wait until the transcript has loaded (the composer is blocked while recovering), then type.
async function say(text: string) {
  await screen.findByText(/Bạn muốn kể điều gì/);
  await userEvent.type(await screen.findByLabelText("Điều bạn muốn kể"), text);
}
const renderThread = (service: LiveCompanion) =>
  render(
    <MemoryRouter>
      <Thread service={service} conversationId="conv-1" />
    </MemoryRouter>,
  );
const completed = (
  content: string,
  urgency = "none",
  citations: unknown[] = [],
) =>
  ev("message.completed", {
    messageId: "m1",
    content,
    citations,
    structured: { urgency },
  });

afterEach(cleanup);

beforeEach(() => {
  HTMLDialogElement.prototype.showModal ??= function (this: HTMLDialogElement) {
    this.setAttribute("open", "");
  };
  HTMLDialogElement.prototype.close ??= function (this: HTMLDialogElement) {
    this.removeAttribute("open");
  };
  window.matchMedia ??= ((query: string) => ({
    matches: false,
    media: query,
    addEventListener: () => undefined,
    removeEventListener: () => undefined,
    addListener: () => undefined,
    removeListener: () => undefined,
    dispatchEvent: () => false,
    onchange: null,
  })) as unknown as typeof window.matchMedia;
  seq = 0;
  evidenceList.mockReset();
  evidenceReview.mockReset();
});

describe("live chat", () => {
  it("keeps a way back to history and urgent support inside the immersive conversation", async () => {
    render(
      <MemoryRouter initialEntries={["/ai/chat/conv-1"]}>
        <Routes>
          <Route
            path="/ai/chat/:sessionId"
            element={<LiveChatPage service={fake()} />}
          />
        </Routes>
      </MemoryRouter>,
    );
    expect(
      screen.getByRole("link", { name: "Lịch sử trò chuyện" }),
    ).toHaveAttribute("href", "/ai/chat");
    expect(
      screen.getByRole("link", { name: "Tìm hỗ trợ ngay" }),
    ).toHaveAttribute("href", "/support/urgent");
  });
  it("streams, shows tool progress and chips only for verified citations", async () => {
    const service = fake({
      send: vi.fn(() =>
        events(
          ev("run.started", {
            runId: "run-1",
            conversationId: "conv-1",
            messageId: "m1",
          }),
          ev("tool.started", {
            callId: "c1",
            tool: "knowledge_search",
            label: "Tra cứu nguồn tin cậy",
          }),
          ev("tool.completed", {
            callId: "c1",
            tool: "knowledge_search",
            ok: true,
          }),
          ev("message.delta", { messageId: "m1", text: "Bạn có thể nhờ " }),
          completed("Bạn có thể nhờ cô chủ nhiệm [1].", "none", [citation]),
          ev("run.usage", { totalTokens: 5 }),
          ev("run.completed", { status: "completed" }),
        ),
      ),
    });
    renderThread(service);
    await say("Nhờ ai?{Enter}");
    expect(await screen.findByText(/Bạn có thể nhờ cô chủ nhiệm/)).toBeTruthy();
    expect(screen.getByText(/Tra cứu nguồn tin cậy/)).toBeTruthy();
    expect(
      screen.getByRole("button", { name: /Nguồn 1: Tìm người hỗ trợ/ }),
    ).toBeTruthy();
    await userEvent.click(screen.getByRole("button", { name: /Nguồn 1/ }));
    const link = screen.getByRole("link", { name: "Mở nguồn" });
    expect(link.getAttribute("rel")).toBe("noopener noreferrer");
    expect(
      screen
        .getByRole("link", { name: "Xem trong Thư viện" })
        .getAttribute("href"),
    ).toContain("document=doc-1");
  });

  it("shows no chips when the answer carries no citations", async () => {
    const service = fake({
      send: vi.fn(() =>
        events(
          completed("Mình nghe đây."),
          ev("run.completed", { status: "completed" }),
        ),
      ),
    });
    renderThread(service);
    await say("Chào{Enter}");
    await screen.findByText("Mình nghe đây.");
    expect(screen.queryByLabelText("Nguồn tham khảo")).toBeNull();
  });

  it("renders model text as text, never as HTML", async () => {
    const service = fake({
      send: vi.fn(() =>
        events(
          completed('<img src=x onerror="window.__xss=1">'),
          ev("run.completed", { status: "completed" }),
        ),
      ),
    });
    const { container } = renderThread(service);
    await say("x{Enter}");
    await screen.findByText(/<img src=x/);
    expect(container.querySelector("img")).toBeNull();
  });

  it("shows the emergency block for an immediate answer", async () => {
    const service = fake({
      send: vi.fn(() =>
        events(
          completed("Hãy nói với người lớn.", "immediate"),
          ev("run.completed", { status: "completed" }),
        ),
      ),
    });
    renderThread(service);
    await say("x{Enter}");
    const block = await screen.findByRole("note", { name: "Hỗ trợ khẩn cấp" });
    expect(
      within(block).getByRole("link", { name: "Gọi 111" }).getAttribute("href"),
    ).toBe("tel:111");
  });

  it("maps a failure to Vietnamese copy and retries with the SAME clientMessageId", async () => {
    const send = vi
      .fn()
      .mockImplementationOnce(() =>
        events(
          ev("run.failed", {
            code: "model_timeout",
            message: "raw provider text",
            retryable: true,
          }),
        ),
      )
      .mockImplementationOnce(() =>
        events(
          completed("Đã ổn."),
          ev("run.completed", { status: "completed" }),
        ),
      );
    renderThread(fake({ send }));
    await say("Xin chào{Enter}");
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain("AI trả lời quá lâu");
    expect(alert.textContent).not.toContain("raw provider text");
    await userEvent.click(screen.getByRole("button", { name: "Thử lại" }));
    await screen.findByText("Đã ổn.");
    expect(send).toHaveBeenCalledTimes(2);
    expect(send.mock.calls[1][1].clientMessageId).toBe(
      send.mock.calls[0][1].clientMessageId,
    );
    expect(screen.getAllByText("Xin chào")).toHaveLength(1); // the user's text is not duplicated
  });

  it("stop calls cancel for the running run", async () => {
    let release: () => void = () => undefined;
    const gate = new Promise<void>((resolve) => (release = resolve));
    const service = fake({
      send: vi.fn(async function* () {
        yield ev("run.started", {
          runId: "run-9",
          conversationId: "conv-1",
          messageId: "m",
        });
        await gate;
        yield ev("run.completed", { status: "cancelled" });
      }),
    });
    renderThread(service);
    await say("x{Enter}");
    await userEvent.click(await screen.findByRole("button", { name: /Dừng/ }));
    expect(service.cancel).toHaveBeenCalledWith("run-9");
    release();
    await waitFor(() =>
      expect(screen.getByRole("button", { name: /Gửi/ })).toBeTruthy(),
    );
  });

  it("stop pressed before the run id arrives cancels as soon as it does", async () => {
    // The first click can land before run.started: it used to do nothing at all.
    let startRun: () => void = () => undefined;
    const started = new Promise<void>((resolve) => (startRun = resolve));
    let release: () => void = () => undefined;
    const gate = new Promise<void>((resolve) => (release = resolve));
    const service = fake({
      send: vi.fn(async function* () {
        await started;
        yield ev("run.started", {
          runId: "run-late",
          conversationId: "conv-1",
          messageId: "m",
        });
        await gate;
        yield ev("run.completed", { status: "cancelled" });
      }),
    });
    renderThread(service);
    await say("x{Enter}");
    await userEvent.click(await screen.findByRole("button", { name: /Dừng/ }));
    expect(service.cancel).not.toHaveBeenCalled(); // no id yet, nothing to cancel
    startRun();
    await waitFor(() =>
      expect(service.cancel).toHaveBeenCalledWith("run-late"),
    );
    release();
    await waitFor(() =>
      expect(screen.getByRole("button", { name: /Gửi/ })).toBeTruthy(),
    );
  });
});

describe("approval dialog", () => {
  const proposal = ev("approval.required", {
    approvalId: "a-1",
    tool: "save_confirmed_event",
    label: "Lưu mốc vào hồ sơ",
    preview: {
      kind: "case_event",
      when: "2026-11-03",
      place: "Nhóm chat lớp",
      description: "Bạn A nhắn tin chế giễu",
      evidence: [],
      rationale: "Bạn vừa kể",
    },
    expiresAt: new Date(Date.now() + 600_000).toISOString(),
  });
  const waiting = () =>
    fake({
      send: vi.fn(() =>
        events(
          ev("run.started", {
            runId: "run-1",
            conversationId: "conv-1",
            messageId: "m",
          }),
          proposal,
          ev("run.completed", { status: "awaiting_approval" }),
        ),
      ),
      approve: vi.fn(() =>
        events(
          completed("Đã lưu."),
          ev("run.completed", { status: "completed" }),
        ),
      ),
    });

  it("shows the stored content, does not focus Save, and closing never decides", async () => {
    const service = waiting();
    renderThread(service);
    await say("Lưu đi{Enter}");
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText("Bạn A nhắn tin chế giễu")).toBeTruthy();
    expect(within(dialog).getByText(/Chưa có gì được thay đổi/)).toBeTruthy();
    expect(document.activeElement).not.toBe(
      within(dialog).getByRole("button", { name: "Lưu" }),
    );
    await userEvent.click(within(dialog).getByRole("button", { name: "Đóng" }));
    expect(service.approve).not.toHaveBeenCalled();
    expect(
      await screen.findByText(/đề xuất đang chờ bạn quyết định/),
    ).toBeTruthy(); // stays pending
  });

  it("Save approves, Don't save rejects, and the stream continues", async () => {
    const service = waiting();
    renderThread(service);
    await say("Lưu đi{Enter}");
    await userEvent.click(await screen.findByRole("button", { name: "Lưu" }));
    expect(service.approve).toHaveBeenCalledWith(
      "run-1",
      "a-1",
      "approve",
      expect.anything(),
    );
    await screen.findByText("Đã lưu.");
  });

  it("an expired proposal cannot be saved", async () => {
    const expired = fake({
      send: vi.fn(() =>
        events(
          ev("run.started", {
            runId: "r",
            conversationId: "c",
            messageId: "m",
          }),
          ev("approval.required", {
            approvalId: "a-2",
            tool: "save_plan",
            label: "Lưu kế hoạch",
            preview: { kind: "action_plan", goal: "G", steps: [] },
            expiresAt: new Date(Date.now() - 1000).toISOString(),
          }),
          ev("run.completed", { status: "awaiting_approval" }),
        ),
      ),
    });
    renderThread(expired);
    await say("x{Enter}");
    const save = await screen.findByRole("button", { name: "Lưu" });
    expect((save as HTMLButtonElement).disabled).toBe(true);
    expect(screen.getByText(/đã hết hạn/)).toBeTruthy();
  });
});

describe("restore and failure behaviour", () => {
  it("keeps the chosen own case when starting a conversation from a case link", async () => {
    useWorkspaceStore.getState().reset();
    useWorkspaceStore.getState().login("USER-AN");
    const service = fake();
    service.conversations.create = vi
      .fn()
      .mockImplementation(async (input) => ({
        ...input,
        linkedCaseId: input.linkedCaseId ?? null,
        createdAt: "2026-11-10",
        lastMessageAt: null,
      }));
    render(
      <MemoryRouter initialEntries={["/ai/chat?caseId=CASE-AN-001"]}>
        <Routes>
          <Route path="/ai/chat" element={<LiveChatPage service={service} />} />
          <Route
            path="/ai/chat/:sessionId"
            element={<LiveChatPage service={service} />}
          />
        </Routes>
      </MemoryRouter>,
    );
    expect(screen.getByLabelText("Hồ sơ muốn trao đổi")).toHaveValue(
      "CASE-AN-001",
    );
    await userEvent.click(
      screen.getByRole("button", { name: /Cuộc trò chuyện mới/ }),
    );
    expect(service.conversations.create).toHaveBeenCalledWith(
      expect.objectContaining({ linkedCaseId: "CASE-AN-001" }),
    );
    expect(
      await screen.findByRole("link", { name: /Trở lại hồ sơ/ }),
    ).toHaveAttribute("href", "/cases/CASE-AN-001");
  });
  it("cancels a pending recovery poll before a new streamed message starts", async () => {
    const turns = [
      {
        id: "old-u",
        role: "user",
        content: "Lượt cũ",
        citations: [],
        clientMessageId: "old",
        runId: "old-run",
        createdAt: "",
      },
    ];
    let cancelled = false;
    let release: () => void = () => undefined;
    const gate = new Promise<void>((resolve) => {
      release = resolve;
    });
    const service = fake({
      conversations: {
        ...fake().conversations,
        messages: vi.fn(async () => turns),
      } as LiveCompanion["conversations"],
      run: vi.fn(async () => ({
        id: "old-run",
        conversationId: "conv-1",
        status: cancelled ? "cancelled" : "running",
        errorCode: null,
      })),
      cancel: vi.fn(async () => {
        cancelled = true;
        return "cancelled";
      }),
      send: vi.fn(async function* () {
        yield ev("run.started", {
          runId: "new-run",
          conversationId: "conv-1",
          messageId: "m",
        });
        await gate;
        yield completed("Lượt mới vẫn hoạt động");
        yield ev("run.completed", { status: "completed" });
      }),
    });
    renderThread(service);
    await userEvent.click(await screen.findByRole("button", { name: /Dừng/ }));
    await waitFor(() =>
      expect(screen.queryByRole("button", { name: /Dừng/ })).toBeNull(),
    );
    await userEvent.type(
      screen.getByLabelText("Điều bạn muốn kể"),
      "Lời nhắn mới{Enter}",
    );
    await new Promise((resolve) => setTimeout(resolve, 1700));
    expect(screen.getByText("Lời nhắn mới")).toBeTruthy();
    expect(screen.getByRole("button", { name: /Dừng/ })).toBeTruthy();
    release();
    expect(await screen.findByText("Lượt mới vẫn hoạt động")).toBeTruthy();
  });
  it("keeps a message and an actionable error when submission fails before a run is created", async () => {
    const service = fake({
      send: vi.fn(async function* () {
        yield await Promise.reject({ code: "internal_error" });
      }),
    });
    renderThread(service);
    await say("Mình muốn hiểu trước{Enter}");
    expect((await screen.findByRole("alert")).textContent).toContain(
      "Chưa thể hoàn tất",
    );
    expect(screen.getByText("Mình muốn hiểu trước")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Thử lại" })).toBeTruthy();
  });
  it("lets the user retry loading a conversation before sending any message", async () => {
    const service = fake();
    service.conversations.messages = vi
      .fn()
      .mockRejectedValueOnce({ code: "network_error" })
      .mockResolvedValueOnce([]);
    renderThread(service);
    await screen.findByRole("alert");
    await userEvent.click(screen.getByRole("button", { name: "Thử lại" }));
    await waitFor(() => expect(screen.queryByRole("alert")).toBeNull());
    expect(screen.getByText(/Bạn muốn kể điều gì/)).toBeTruthy();
  });

  it("shows an actionable create error and preserves a usable new-conversation button", async () => {
    const service = fake();
    service.conversations.create = vi
      .fn()
      .mockRejectedValue({ code: "network_error" });
    render(
      <MemoryRouter>
        <LiveChatPage service={service} />
      </MemoryRouter>,
    );
    await userEvent.click(
      screen.getByRole("button", { name: /Cuộc trò chuyện mới/ }),
    );
    expect((await screen.findByRole("alert")).textContent).toContain("kết nối");
    expect(
      screen.getByRole("button", { name: /Cuộc trò chuyện mới/ }),
    ).not.toBeDisabled();
  });
  it("reopening restores the transcript and a pending approval", async () => {
    const service = fake({
      conversations: {
        ...fake().conversations,
        messages: vi.fn(async () => [
          {
            id: "u",
            role: "user",
            content: "Lưu giúp mình",
            citations: [],
            clientMessageId: "c",
            runId: "run-7",
            createdAt: "",
          },
        ]),
      } as LiveCompanion["conversations"],
      run: vi.fn(async () => ({
        id: "run-7",
        conversationId: "conv-1",
        status: "awaiting_approval",
        errorCode: null,
      })),
      pendingApprovals: vi.fn(async () => [
        {
          id: "a-7",
          runId: "run-7",
          tool: "save_plan",
          toolCallId: "t",
          preview: {
            kind: "action_plan",
            goal: "Nói với cô",
            steps: [{ label: "Hẹn gặp", priority: "high" }],
          },
          expiresAt: new Date(Date.now() + 600_000).toISOString(),
          status: "pending" as const,
        },
      ]),
    });
    renderThread(service);
    expect(await screen.findByText("Lưu giúp mình")).toBeTruthy();
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText(/Hẹn gặp/)).toBeTruthy();
  });

  it("an API failure shows an error, never sample conversations", async () => {
    const service = fake({
      conversations: {
        ...fake().conversations,
        messages: vi.fn(async () => {
          throw Object.assign(new Error("x"), { code: "network_error" });
        }),
      } as LiveCompanion["conversations"],
    });
    renderThread(service);
    expect(await screen.findByRole("alert")).toBeTruthy();
    expect(screen.queryByText(/mẫu/i)).toBeNull();
  });
});

describe("live analysis", () => {
  const image = {
    id: "e1",
    kind: "image",
    origin: "user_upload",
    uploadStatus: "uploaded",
    originalFilename: "man-hinh.png",
    storedMimeType: "image/png",
  };
  it("waits for a slow recovery read before scheduling another poll", async () => {
    evidenceList.mockResolvedValue([image]);
    const service = fake();
    service.analyses.get = vi
      .fn()
      .mockResolvedValueOnce({
        id: "slow",
        evidenceId: "e1",
        status: "running",
      })
      .mockImplementation(async () => {
        await new Promise((resolve) => setTimeout(resolve, 1800));
        return {
          id: "slow",
          evidenceId: "e1",
          status: "succeeded",
          reading: {
            extractedText: [],
            observations: ["Kết quả tải chậm"],
            inferences: [],
            uncertainties: [],
            limitations: [],
            needsUserReview: true,
          },
        };
      });
    render(
      <MemoryRouter initialEntries={["/ai/analysis/slow"]}>
        <Routes>
          <Route
            path="/ai/analysis/:analysisId"
            element={<LiveAnalysisPage service={service} />}
          />
        </Routes>
      </MemoryRouter>,
    );
    expect(
      await screen.findByText("Kết quả tải chậm", {}, { timeout: 6000 }),
    ).toBeTruthy();
  }, 9000);
  it("restores a saved reading from its URL without requesting another analysis", async () => {
    evidenceList.mockResolvedValue([image, { ...image, id: "e2" }]);
    const service = fake();
    service.analyses.get = vi.fn().mockResolvedValue({
      id: "analysis-saved",
      evidenceId: "e2",
      status: "succeeded",
      reading: {
        extractedText: [],
        observations: ["Nội dung đã lưu"],
        inferences: [],
        uncertainties: [],
        limitations: [],
        needsUserReview: true,
      },
    });
    render(
      <MemoryRouter
        initialEntries={["/ai/analysis/analysis-saved?evidenceId=e1"]}
      >
        <Routes>
          <Route
            path="/ai/analysis/:analysisId"
            element={<LiveAnalysisPage service={service} />}
          />
        </Routes>
      </MemoryRouter>,
    );
    expect(await screen.findByText("Nội dung đã lưu")).toBeTruthy();
    expect(service.analyses.create).not.toHaveBeenCalled();
    evidenceReview.mockRejectedValueOnce({ code: "network_error" });
    await userEvent.type(
      screen.getByLabelText("Nội dung bạn sửa"),
      "Phần mình chỉnh lại",
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Lưu bản chỉnh" }),
    );
    expect((await screen.findByRole("alert")).textContent).toContain("lưu");
    expect(screen.getByLabelText("Nội dung bạn sửa")).toHaveValue(
      "Phần mình chỉnh lại",
    );
    expect(screen.queryByText("Đã lưu bản bạn chỉnh.")).toBeNull();
    evidenceReview.mockResolvedValueOnce(image);
    await userEvent.click(
      screen.getByRole("button", { name: "Lưu bản chỉnh" }),
    );
    expect(await screen.findByText("Đã lưu bản bạn chỉnh.")).toBeTruthy();
    expect(evidenceReview).toHaveBeenLastCalledWith(
      "e2",
      expect.objectContaining({ userEditedText: "Phần mình chỉnh lại" }),
    );
  });
  it("requires fresh consent when the selected image changes", async () => {
    evidenceList.mockResolvedValue([
      image,
      { ...image, id: "e2", originalFilename: "anh-khac.png" },
    ]);
    render(
      <MemoryRouter>
        <LiveAnalysisPage service={fake()} />
      </MemoryRouter>,
    );
    await userEvent.click(await screen.findByLabelText(/man-hinh\.png/));
    await userEvent.click(screen.getByLabelText(/Tôi đồng ý gửi ảnh này/));
    await userEvent.click(screen.getByLabelText(/anh-khac\.png/));
    expect(screen.getByLabelText(/Tôi đồng ý gửi ảnh này/)).not.toBeChecked();
    expect(
      screen.getByRole("button", { name: "Phân tích ảnh" }),
    ).toBeDisabled();
  });
  it("sends nothing until the user consents, and lists only supported images", async () => {
    evidenceList.mockResolvedValue([
      image,
      {
        ...image,
        id: "e2",
        originalFilename: "ve.svg",
        storedMimeType: "image/svg+xml",
      },
    ]);
    const service = fake();
    render(
      <MemoryRouter>
        <LiveAnalysisPage service={service} />
      </MemoryRouter>,
    );
    await userEvent.click(await screen.findByLabelText(/man-hinh\.png/));
    expect(screen.queryByLabelText(/ve\.svg/)).toBeNull();
    const run = screen.getByRole("button", {
      name: "Phân tích ảnh",
    }) as HTMLButtonElement;
    expect(run.disabled).toBe(true);
    await userEvent.click(run);
    expect(service.analyses.create).not.toHaveBeenCalled();
    await userEvent.click(screen.getByLabelText(/Tôi đồng ý gửi ảnh này/));
    service.analyses.create = vi.fn(async () => ({
      id: "a",
      evidenceId: "e1",
      status: "succeeded",
      consentVersion: "v",
      derivativeId: "d",
      errorCode: null,
      startedAt: "",
      finishedAt: "",
      reading: {
        extractedText: [{ text: "Xin chào", confidence: "high", region: null }],
        visibleMetadata: {
          timestampText: null,
          platformGuess: null,
          participantsAsShown: [],
        },
        observations: ["Có một tin nhắn"],
        inferences: [
          { text: "Có thể là trêu chọc", basis: "câu chữ", confidence: "low" },
        ],
        uncertainties: ["Thiếu ngữ cảnh"],
        limitations: ["Không xác minh được ảnh"],
        needsUserReview: true,
      },
    })) as never;
    await userEvent.click(
      screen.getByRole("button", { name: "Phân tích ảnh" }),
    );
    const result = await screen.findByTestId("analysis-result");
    expect(
      within(result).getByText(/AI suy đoán \(chưa xác minh\)/),
    ).toBeTruthy();
    expect(within(result).getByText(/Điều chưa chắc và hạn chế/)).toBeTruthy();
    expect(service.analyses.create).toHaveBeenCalledWith(
      expect.objectContaining({
        evidenceId: "e1",
        consentVersion: "evidence-analysis-2026-11-08",
      }),
    );
  });

  it("a failed analysis shows a message and offers retry without sample data", async () => {
    evidenceList.mockResolvedValue([image]);
    const service = fake();
    service.analyses.create = vi.fn(async () => {
      throw Object.assign(new Error("x"), { code: "upstream_error" });
    }) as never;
    service.analyses.get = vi.fn(async () => {
      throw new Error("gone");
    }) as never;
    render(
      <MemoryRouter>
        <LiveAnalysisPage service={service} />
      </MemoryRouter>,
    );
    await userEvent.click(await screen.findByLabelText(/man-hinh\.png/));
    await userEvent.click(screen.getByLabelText(/Tôi đồng ý gửi ảnh này/));
    await userEvent.click(
      screen.getByRole("button", { name: "Phân tích ảnh" }),
    );
    expect((await screen.findByRole("alert")).textContent).toContain(
      "Dịch vụ AI tạm thời",
    );
    expect(screen.getByRole("button", { name: "Thử lại" })).toBeTruthy();
  });
  it("a terminal analysis failure can start a fresh consented request instead of reloading the same failed result", async () => {
    evidenceList.mockResolvedValue([image]);
    const service = fake();
    const failed = {
      id: "failed-reading",
      evidenceId: "e1",
      status: "failed",
      errorCode: "upstream_error",
      reading: null,
    };
    service.analyses.get = vi.fn().mockResolvedValue(failed);
    render(
      <MemoryRouter initialEntries={["/ai/analysis/failed-reading"]}>
        <Routes>
          <Route
            path="/ai/analysis/:analysisId"
            element={<LiveAnalysisPage service={service} />}
          />
        </Routes>
      </MemoryRouter>,
    );
    await screen.findByRole("alert");
    await userEvent.click(screen.getByRole("button", { name: "Thử lại" }));
    expect(await screen.findByLabelText(/man-hinh\.png/)).toBeTruthy();
    expect(screen.queryByRole("alert")).toBeNull();
  });
});

describe("live roleplay", () => {
  it("starts another practice with case-context consent off again", async () => {
    useWorkspaceStore.getState().reset();
    useWorkspaceStore.getState().login("USER-AN");
    const scenario = {
      key: "teacher-k",
      role: "teacher",
      title: "Kể với cô",
      context: "c",
      defaultGoal: "Mở lời",
    };
    const session = {
      id: "s-reset",
      conversationId: "c-reset",
      role: "teacher",
      scenarioKey: scenario.key,
      scenarioTitle: scenario.title,
      scenarioContext: "",
      userGoal: "Mở lời",
      difficulty: 1,
      useCaseContext: true,
      linkedCaseId: "CASE-AN-001",
      status: "active",
      turnCount: 0,
      maxTurns: 30,
      safetyLocked: false,
      feedback: null,
      createdAt: "",
      completedAt: null,
    };
    const service = fake();
    service.roleplay.scenarios = vi.fn().mockResolvedValue([scenario]);
    service.roleplay.create = vi.fn().mockResolvedValue(session);
    service.roleplay.get = vi.fn().mockResolvedValue(session);
    service.roleplay.abandon = vi
      .fn()
      .mockResolvedValue({ ...session, status: "abandoned" });
    render(
      <MemoryRouter initialEntries={["/ai/roleplay?caseId=CASE-AN-001"]}>
        <LiveRoleplayPage service={service} />
      </MemoryRouter>,
    );
    await userEvent.click(await screen.findByLabelText(/Kể với cô/));
    await userEvent.click(screen.getByLabelText(/Cho AI dùng tóm tắt hồ sơ/));
    await userEvent.click(
      screen.getByRole("button", { name: "Bắt đầu diễn tập" }),
    );
    await userEvent.click(
      await screen.findByRole("button", { name: "Thoát, không cần phản hồi" }),
    );
    await userEvent.click(
      await screen.findByRole("button", { name: "Luyện một tình huống khác" }),
    );
    expect(
      screen.getByLabelText(/Cho AI dùng tóm tắt hồ sơ/),
    ).not.toBeChecked();
    await userEvent.click(
      screen.getByRole("button", { name: "Bắt đầu diễn tập" }),
    );
    expect(service.roleplay.create).toHaveBeenLastCalledWith(
      expect.objectContaining({ linkedCaseId: null, useCaseContext: false }),
    );
  });
  it("does not continuously fetch the session after an idle transcript is restored", async () => {
    const service = fake();
    const session = {
      id: "s-loop",
      conversationId: "c-loop",
      role: "teacher",
      scenarioKey: "k",
      scenarioTitle: "Thử nói với cô",
      scenarioContext: "",
      userGoal: "Mở lời",
      difficulty: 1,
      useCaseContext: false,
      linkedCaseId: null,
      status: "active",
      turnCount: 0,
      maxTurns: 30,
      safetyLocked: false,
      feedback: null,
      createdAt: "",
      completedAt: null,
    };
    let reads = 0;
    service.roleplay.get = vi.fn(async () => {
      reads++;
      if (reads > 3) return new Promise(() => {});
      return { ...session };
    }) as never;
    render(
      <MemoryRouter initialEntries={["/ai/roleplay?session=s-loop"]}>
        <LiveRoleplayPage service={service} />
      </MemoryRouter>,
    );
    await screen.findByText(/Bạn muốn kể điều gì/);
    await new Promise((resolve) => setTimeout(resolve, 30));
    expect(reads).toBeLessThanOrEqual(2);
  });

  it("offers persisted sessions so a returning student can resume after leaving the page", async () => {
    const service = fake();
    service.roleplay.list = vi.fn().mockResolvedValue([
      {
        id: "s-old",
        scenarioTitle: "Kể chuyện với mẹ",
        role: "parent",
        status: "active",
        turnCount: 2,
      },
    ]);
    render(
      <MemoryRouter>
        <LiveRoleplayPage service={service} />
      </MemoryRouter>,
    );
    expect(
      await screen.findByRole("button", { name: /Tiếp tục.*Kể chuyện với mẹ/ }),
    ).toBeTruthy();
  });
  it("labels the partner as not a real person and creates a session from the chosen scenario", async () => {
    const scenario = {
      key: "teacher-group-chat",
      role: "teacher",
      title: "Báo với giáo viên",
      context: "Nhóm chat có tin đe dọa",
      defaultGoal: "Nói rõ sự việc",
    };
    const service = fake();
    service.roleplay.scenarios = vi.fn(async () => [scenario]) as never;
    const created = {
      id: "s1",
      conversationId: "conv-rp",
      role: "teacher",
      scenarioKey: scenario.key,
      scenarioTitle: scenario.title,
      scenarioContext: "",
      userGoal: "Nói rõ sự việc",
      difficulty: 1,
      useCaseContext: false,
      linkedCaseId: null,
      status: "active",
      turnCount: 0,
      maxTurns: 30,
      safetyLocked: false,
      feedback: null,
      createdAt: "",
      completedAt: null,
    };
    service.roleplay.create = vi.fn(async () => created) as never;
    service.roleplay.get = vi.fn(async () => created) as never;
    render(
      <MemoryRouter>
        <LiveRoleplayPage service={service} />
      </MemoryRouter>,
    );
    await userEvent.click(await screen.findByLabelText(/Báo với giáo viên/));
    expect(screen.getByText(/Mặc định AI không đọc hồ sơ/)).toBeTruthy();
    await userEvent.click(
      screen.getByRole("button", { name: "Bắt đầu diễn tập" }),
    );
    expect(service.roleplay.create).toHaveBeenCalledWith(
      expect.objectContaining({
        role: "teacher",
        useCaseContext: false,
        difficulty: 1,
      }),
    );
    expect(await screen.findByText(/đây không phải người thật/)).toBeTruthy();
    expect(
      screen.getByRole("button", { name: /Kết thúc & nhận phản hồi/ }),
    ).toBeTruthy();
  });

  it("keeps the typed goal when creating the session fails", async () => {
    const scenario = {
      key: "k",
      role: "parent",
      title: "Kể với mẹ",
      context: "c",
      defaultGoal: "Mở lời",
    };
    const service = fake();
    service.roleplay.scenarios = vi.fn(async () => [scenario]) as never;
    service.roleplay.create = vi.fn(async () => {
      throw Object.assign(new Error("x"), { code: "upstream_error" });
    }) as never;
    render(
      <MemoryRouter>
        <LiveRoleplayPage service={service} />
      </MemoryRouter>,
    );
    await userEvent.click(await screen.findByLabelText(/Kể với mẹ/));
    const goal = screen.getByLabelText(
      "Mục tiêu của bạn",
    ) as HTMLTextAreaElement;
    await userEvent.clear(goal);
    await userEvent.type(goal, "Mục tiêu của riêng mình");
    await userEvent.click(
      screen.getByRole("button", { name: "Bắt đầu diễn tập" }),
    );
    expect(await screen.findByRole("alert")).toBeTruthy();
    expect(
      (screen.getByLabelText("Mục tiêu của bạn") as HTMLTextAreaElement).value,
    ).toBe("Mục tiêu của riêng mình");
  });
});
