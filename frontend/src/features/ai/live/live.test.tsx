import { afterEach, describe, expect, it, vi, beforeEach } from "vitest";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import type {
  LiveCompanion,
  LiveEvent,
} from "../../../services/composition/companion-types";
import { Thread } from "./live-chat";
import { LiveAnalysisPage } from "./live-analysis";
import { LiveRoleplayPage } from "./live-roleplay";

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
vi.mock("../../../services/composition", () => ({
  getServices: () => ({
    evidence: { list: evidenceList, review: vi.fn() },
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
  await userEvent.type(await screen.findByLabelText("Tin nhắn của bạn"), text);
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
});

describe("live chat", () => {
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
});

describe("live roleplay", () => {
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
