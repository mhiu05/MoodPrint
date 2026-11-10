// Frozen v1 transport contract. Raw SDK events never cross this boundary.
import type { components } from "./schema.gen";

type JsonValue =
  string | number | boolean | null | JsonValue[] | { [key: string]: JsonValue };
type Finding = { text: string; sourceIds: string[] };
type Event<K extends string, D> = {
  v: 1;
  seq: number;
  runId: string;
  event: K;
  data: D;
};
export type StreamEvent =
  | Event<
      "run.started",
      { runId: string; conversationId: string; messageId: string }
    >
  | Event<"message.delta", { messageId: string; text: string }>
  | Event<
      "message.completed",
      {
        messageId: string;
        content: string;
        citations: components["schemas"]["SourceCitation"][];
        structured?: {
          reply: string;
          observedFacts: Finding[];
          userReportedFacts: Finding[];
          possiblePatterns: Finding[];
          uncertainties: string[];
          clarifyingQuestion: string | null;
          safeOptions: { label: string; description: string }[];
          urgency: "none" | "elevated" | "immediate";
          citations: components["schemas"]["SourceCitation"][];
        } | null;
      }
    >
  | Event<"tool.started", { callId: string; tool: string; label: string }>
  | Event<"tool.completed", { callId: string; tool: string; ok: boolean }>
  | Event<
      "approval.required",
      {
        approvalId: string;
        tool: string;
        label: string;
        preview: Record<string, JsonValue>;
        expiresAt: string;
      }
    >
  | Event<
      "run.usage",
      {
        inputTokens: number;
        outputTokens: number;
        totalTokens: number;
        requests: number;
        toolCalls: number;
        latencyMs: number;
      }
    >
  | Event<
      "run.completed",
      { status: "completed" | "awaiting_approval" | "cancelled" }
    >
  | Event<
      "run.failed",
      {
        code:
          | "model_timeout"
          | "model_refusal"
          | "max_turns"
          | "tool_budget_exceeded"
          | "run_timeout"
          | "upstream_error"
          | "internal_error";
        message: string;
        retryable: boolean;
      }
    >
  | Event<"heartbeat", Record<string, never>>;
