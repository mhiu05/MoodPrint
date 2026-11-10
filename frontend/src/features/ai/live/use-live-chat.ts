import { useCallback, useEffect, useRef, useState } from "react";
import type {
  ChatTurn,
  Citation,
  LiveCompanion,
  JsonRecord,
  LiveEvent,
  Urgency,
} from "../../../services/composition/companion-types";

export interface LiveMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations: Citation[];
  urgency?: Urgency;
  clientMessageId?: string;
  streaming?: boolean;
}
export interface ToolChip {
  callId: string;
  label: string;
  done: boolean;
  ok?: boolean;
}
export interface ApprovalView {
  runId: string;
  approvalId: string;
  tool: string;
  label: string;
  preview: JsonRecord;
  expiresAt: string;
}
export interface RunError {
  code: string;
  message: string;
  retryable: boolean;
}
export type ChatStatus =
  "idle" | "streaming" | "awaiting_approval" | "failed" | "recovering";

/** Vietnamese copy for each backend failure code; never the raw provider text. */
export const failureCopy: Record<string, string> = {
  model_timeout: "AI trả lời quá lâu. Bạn có thể thử lại.",
  model_refusal: "AI không thể trả lời nội dung này. Hãy thử diễn đạt khác.",
  max_turns: "Lượt trò chuyện quá dài. Hãy thử một câu ngắn hơn.",
  tool_budget_exceeded: "AI đã dùng hết số lần tra cứu cho lượt này.",
  run_timeout: "Lượt trò chuyện đã quá thời gian. Bạn có thể thử lại.",
  upstream_error: "Dịch vụ AI tạm thời chưa phản hồi. Bạn có thể thử lại.",
  internal_error: "Chưa thể hoàn tất lượt trò chuyện. Bạn có thể thử lại.",
  network_error: "Mất kết nối. Nội dung của bạn vẫn được giữ; hãy thử lại.",
  heartbeat_lost:
    "Lượt trả lời bị gián đoạn. Nội dung của bạn vẫn được giữ; bạn có thể thử lại.",
  quota_exceeded: "Hôm nay bạn đã dùng hết lượt trò chuyện với AI.",
  rate_limited: "Bạn đã gửi nhiều tin nhắn. Hãy thử lại sau ít phút.",
  not_ready: "Trò chuyện AI chưa được cấu hình.",
  roleplay_turn_limit:
    "Buổi diễn tập đã đủ số lượt. Hãy kết thúc để nhận phản hồi.",
  roleplay_ended: "Buổi diễn tập này đã kết thúc.",
};
export const describeFailure = (code: string, fallback?: string) =>
  failureCopy[code] ?? fallback ?? failureCopy.internal_error;

const toMessage = (turn: ChatTurn): LiveMessage | null =>
  turn.role === "system"
    ? null
    : {
        id: turn.id,
        role: turn.role,
        content: turn.content,
        citations: turn.citations,
        clientMessageId: turn.clientMessageId ?? undefined,
      };

const newId = () => globalThis.crypto.randomUUID();

export function useLiveChat(service: LiveCompanion, conversationId: string) {
  const [messages, setMessages] = useState<LiveMessage[]>([]);
  const [status, setStatus] = useState<ChatStatus>("idle");
  const [tools, setTools] = useState<ToolChip[]>([]);
  const [approval, setApproval] = useState<ApprovalView | null>(null);
  const [error, setError] = useState<RunError | null>(null);
  const [loaded, setLoaded] = useState(false);
  const runId = useRef<string | null>(null);
  // Stop was pressed before the server told us the run id: cancel as soon as it arrives.
  const stopRequested = useRef(false);
  const abort = useRef<AbortController | null>(null);
  const failed = useRef<{ clientMessageId: string; content: string } | null>(
    null,
  );
  const buffer = useRef("");
  const frame = useRef<number | null>(null);
  const alive = useRef(true);
  const recoveryTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const recoveryGeneration = useRef(0);
  const invalidateRecovery = useCallback(() => {
    recoveryGeneration.current += 1;
  }, []);

  const flush = useCallback(() => {
    frame.current = null;
    const text = buffer.current;
    buffer.current = "";
    if (!text || !alive.current) return;
    setMessages((current) => {
      const last = current.at(-1);
      return last?.streaming
        ? [...current.slice(0, -1), { ...last, content: last.content + text }]
        : current;
    });
  }, []);
  const queueDelta = useCallback(
    (text: string) => {
      buffer.current += text;
      frame.current ??= requestAnimationFrame(flush);
    },
    [flush],
  );

  const restore = useCallback(
    async function restoreTranscript() {
      if (recoveryTimer.current !== null) clearTimeout(recoveryTimer.current);
      recoveryTimer.current = null;
      const generation = ++recoveryGeneration.current;
      const current = () =>
        alive.current && generation === recoveryGeneration.current;
      setStatus("recovering");
      setError(null);
      try {
        const turns = await service.conversations.messages(conversationId);
        if (!current()) return;
        setMessages(
          turns.map(toMessage).filter((m): m is LiveMessage => m !== null),
        );
        const lastRun = [...turns].reverse().find((t) => t.runId)?.runId;
        setApproval(null);
        if (lastRun) {
          const run = await service.run(lastRun);
          if (!current()) return;
          if (run.status === "running" || run.status === "queued") {
            runId.current = lastRun;
            recoveryTimer.current = setTimeout(
              () => void restoreTranscript(),
              1500,
            );
            return;
          }
          if (run.status === "awaiting_approval") {
            const [pending] = await service.pendingApprovals(lastRun);
            if (!current()) return;
            if (pending) {
              setApproval({
                runId: lastRun,
                approvalId: pending.id,
                tool: pending.tool,
                label: String(pending.preview.summary ?? pending.tool),
                preview: pending.preview,
                expiresAt: pending.expiresAt,
              });
              runId.current = lastRun;
              setStatus("awaiting_approval");
              setLoaded(true);
              return;
            }
          }
          const unanswered = [...turns]
            .reverse()
            .find(
              (turn) =>
                turn.runId === lastRun &&
                turn.role === "user" &&
                turn.clientMessageId,
            );
          const hasAnswer = turns.some(
            (turn) => turn.runId === lastRun && turn.role === "assistant",
          );
          if (
            ["interrupted", "failed"].includes(run.status) &&
            unanswered &&
            !hasAnswer
          ) {
            failed.current = {
              clientMessageId: unanswered.clientMessageId!,
              content: unanswered.content,
            };
            const code =
              run.status === "interrupted"
                ? "heartbeat_lost"
                : (run.errorCode ?? "internal_error");
            setError({ code, message: describeFailure(code), retryable: true });
            setStatus("failed");
            return;
          }
        }
        setStatus("idle");
      } catch (cause) {
        if (!current()) return;
        const code = (cause as { code?: string }).code ?? "network_error";
        setError({ code, message: describeFailure(code), retryable: true });
        setStatus("failed");
      } finally {
        if (current()) setLoaded(true);
      }
    },
    [service, conversationId],
  );

  useEffect(() => {
    alive.current = true;
    // Deferred one tick: loading never sets state synchronously inside the effect body.
    queueMicrotask(() => {
      if (alive.current) void restore();
    });
    return () => {
      alive.current = false; // leaving the page or switching workspace stops all state writes
      invalidateRecovery();
      abort.current?.abort();
      if (frame.current !== null) cancelAnimationFrame(frame.current);
      if (recoveryTimer.current !== null) clearTimeout(recoveryTimer.current);
    };
  }, [restore, invalidateRecovery]);

  const consume = useCallback(
    async (events: AsyncIterable<LiveEvent>) => {
      let terminal = false;
      try {
        for await (const event of events) {
          if (!alive.current) return;
          switch (event.event) {
            case "run.started":
              runId.current = event.data.runId;
              if (stopRequested.current) {
                stopRequested.current = false;
                void service.cancel(event.data.runId).catch(() => undefined);
              }
              break;
            case "message.delta":
              queueDelta(event.data.text);
              break;
            case "tool.started":
              setTools((current) => [
                ...current,
                {
                  callId: event.data.callId,
                  label: event.data.label,
                  done: false,
                },
              ]);
              break;
            case "tool.completed":
              setTools((current) =>
                current.map((chip) =>
                  chip.callId === event.data.callId
                    ? { ...chip, done: true, ok: event.data.ok }
                    : chip,
                ),
              );
              break;
            case "message.completed": {
              if (frame.current !== null) cancelAnimationFrame(frame.current);
              frame.current = null;
              buffer.current = "";
              const { messageId, content, citations, structured } = event.data;
              setMessages((current) => {
                const base = current.at(-1)?.streaming
                  ? current.slice(0, -1)
                  : current;
                return [
                  ...base,
                  {
                    id: messageId,
                    role: "assistant",
                    content,
                    citations,
                    urgency: structured?.urgency ?? "none",
                  },
                ];
              });
              break;
            }
            case "approval.required":
              setApproval({
                runId: runId.current ?? "",
                approvalId: event.data.approvalId,
                tool: event.data.tool,
                label: event.data.label,
                preview: event.data.preview,
                expiresAt: event.data.expiresAt,
              });
              break;
            case "run.completed":
              terminal = true;
              setStatus(
                event.data.status === "awaiting_approval"
                  ? "awaiting_approval"
                  : "idle",
              );
              break;
            case "run.failed":
              terminal = true;
              setError({
                code: event.data.code,
                message: describeFailure(event.data.code),
                retryable: event.data.retryable,
              });
              setStatus("failed");
              break;
            default:
              break;
          }
        }
        if (!terminal && alive.current) throw new Error("stream ended early");
      } catch (cause) {
        if (!alive.current || abort.current?.signal.aborted) return;
        // No run was created: restoring an empty server transcript would erase the
        // user's unsent text and hide the failed submit. Let begin keep it for retry.
        if (!runId.current) throw cause;
        // The run keeps going on the server: recover the transcript instead of guessing.
        setError({
          code: "network_error",
          message: describeFailure("network_error"),
          retryable: true,
        });
        void cause;
        await restore();
      } finally {
        setMessages((current) =>
          current.at(-1)?.streaming ? current.slice(0, -1) : current,
        );
      }
    },
    [queueDelta, restore, service],
  );

  const begin = useCallback(
    async (content: string, clientMessageId: string, appendUser: boolean) => {
      recoveryGeneration.current++;
      if (recoveryTimer.current !== null) clearTimeout(recoveryTimer.current);
      abort.current = new AbortController();
      runId.current = null; // never cancel the previous turn's run by mistake
      stopRequested.current = false;
      setError(null);
      setTools([]);
      setApproval(null);
      setStatus("streaming");
      failed.current = { clientMessageId, content };
      setMessages((current) => [
        ...current.filter((m) => !m.streaming),
        ...(appendUser
          ? [
              {
                id: clientMessageId,
                role: "user" as const,
                content,
                citations: [],
                clientMessageId,
              },
            ]
          : []),
        {
          id: `pending-${clientMessageId}`,
          role: "assistant",
          content: "",
          citations: [],
          streaming: true,
        },
      ]);
      try {
        await consume(
          service.send(
            conversationId,
            { clientMessageId, content },
            abort.current.signal,
          ),
        );
      } catch (cause) {
        if (!alive.current) return;
        const code = (cause as { code?: string }).code ?? "network_error";
        setError({
          code,
          message: describeFailure(code),
          retryable: ![
            "not_ready",
            "quota_exceeded",
            "unauthorized",
            "forbidden",
            "not_found",
          ].includes(code),
        });
        setStatus("failed");
        setMessages((current) => current.filter((m) => !m.streaming));
      }
    },
    [consume, service, conversationId],
  );

  const send = useCallback(
    (content: string) => begin(content.trim(), newId(), true),
    [begin],
  );
  /** Retry re-sends the *same* clientMessageId so the server never duplicates the turn. */
  const retry = useCallback(async () => {
    const last = failed.current;
    if (!last) return restore();
    await begin(last.content, last.clientMessageId, false);
  }, [begin, restore]);

  const stop = useCallback(async () => {
    if (runId.current) {
      try {
        await service.cancel(runId.current);
        if (status === "awaiting_approval" || status === "recovering")
          await restore();
      } catch {
        setError({
          code: "network_error",
          message: "Chưa dừng được lượt này. Hãy kiểm tra kết nối và thử lại.",
          retryable: false,
        });
      }
    } else stopRequested.current = true;
  }, [service, status, restore]);

  const decide = useCallback(
    async (decision: "approve" | "reject") => {
      const current = approval;
      if (!current) return;
      recoveryGeneration.current++;
      if (recoveryTimer.current !== null) clearTimeout(recoveryTimer.current);
      abort.current = new AbortController();
      setApproval(null);
      setError(null);
      setStatus("streaming");
      try {
        await consume(
          service.approve(
            current.runId,
            current.approvalId,
            decision,
            abort.current.signal,
          ),
        );
      } catch (cause) {
        if (!alive.current) return;
        const code = (cause as { code?: string }).code ?? "network_error";
        setError({ code, message: describeFailure(code), retryable: true });
        setApproval(current); // the decision did not go through: keep the dialog available
        setStatus("awaiting_approval");
      }
    },
    [approval, consume, service],
  );
  /** Closing the dialog defers the decision; it never approves or rejects anything. */
  const dismissApproval = useCallback(() => undefined, []);

  return {
    messages,
    status,
    tools,
    approval,
    error,
    loaded,
    send,
    retry,
    stop,
    decide,
    dismissApproval,
    restore,
    canRetry: status === "failed",
  };
}
