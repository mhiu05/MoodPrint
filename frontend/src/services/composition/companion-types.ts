// Live Companion contract (Phase 3). Everything the UI needs from the backend, nothing raw.
import type { components } from "../http/schema.gen";
import type { StreamEvent } from "../http/stream-events";

export type LiveEvent = StreamEvent;
export type Urgency = "none" | "elevated" | "immediate";
export type Citation = components["schemas"]["SourceCitation"];
export type JsonRecord = Record<string, unknown>;

export interface ConversationSummary {
  id: string;
  title: string;
  linkedCaseId: string | null;
  lastMessageAt: string | null;
  createdAt: string;
}
export interface ChatTurn {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  citations: Citation[];
  clientMessageId: string | null;
  runId: string | null;
  createdAt: string;
}
export interface PendingApproval {
  id: string;
  runId: string;
  tool: string;
  toolCallId: string;
  preview: JsonRecord;
  expiresAt: string;
  status: "pending" | "approved" | "rejected" | "expired";
}
export interface RunInfo {
  id: string;
  conversationId: string;
  status: string;
  errorCode: string | null;
}

export interface MemoryCandidateView {
  id: string;
  category: string;
  content: string;
  status: string;
  expiresAt: string;
}
export interface MemoryView {
  id: string;
  category: string;
  content: string;
  status: string;
  updatedAt: string;
}

export interface ExtractedText {
  text: string;
  confidence: "high" | "medium" | "low";
  region: string | null;
}
export interface AnalysisReading {
  extractedText: ExtractedText[];
  visibleMetadata: {
    timestampText: string | null;
    platformGuess: string | null;
    participantsAsShown: string[];
  };
  observations: string[];
  inferences: {
    text: string;
    basis: string;
    confidence: "high" | "medium" | "low";
  }[];
  uncertainties: string[];
  limitations: string[];
  needsUserReview: true;
}
export interface AnalysisView {
  id: string;
  evidenceId: string;
  status: "running" | "succeeded" | "failed" | "cancelled";
  consentVersion: string;
  derivativeId: string | null;
  errorCode: string | null;
  reading: AnalysisReading | null;
  startedAt: string;
  finishedAt: string | null;
}
/** Text the user must agree to before an image is sent to the AI model. */
export const ANALYSIS_CONSENT_VERSION = "evidence-analysis-2026-11-08";

export type RoleplayRole = "teacher" | "parent" | "trusted_adult";
export interface RoleplayScenario {
  key: string;
  role: RoleplayRole;
  title: string;
  context: string;
  defaultGoal: string;
}
export interface RoleplayFeedback {
  summary: string;
  strengths: string[];
  suggestions: string[];
  rephrasings: { original: string; better: string; why: string }[];
  followUps: string[];
  safetyNote: string | null;
}
export interface RoleplaySessionView {
  id: string;
  conversationId: string;
  role: RoleplayRole;
  scenarioKey: string;
  scenarioTitle: string;
  scenarioContext: string;
  userGoal: string;
  difficulty: number;
  useCaseContext: boolean;
  linkedCaseId: string | null;
  status: "active" | "completed" | "abandoned";
  turnCount: number;
  maxTurns: number;
  safetyLocked: boolean;
  feedback: RoleplayFeedback | null;
  createdAt: string;
  completedAt: string | null;
}

/** Frozen marker kept for the composition seam; the full API is ``LiveCompanion``. */
export type CompanionService = { readonly live: true };

export interface LiveCompanion extends CompanionService {
  conversations: {
    list(): Promise<ConversationSummary[]>;
    create(input: {
      id: string;
      title?: string;
      linkedCaseId?: string | null;
    }): Promise<ConversationSummary>;
    remove(id: string): Promise<void>;
    messages(id: string): Promise<ChatTurn[]>;
    attachments(id: string): Promise<Record<string, string[]>>;
  };
  send(
    conversationId: string,
    input: { clientMessageId: string; content: string; attachments?: string[] },
    signal?: AbortSignal,
  ): AsyncIterable<LiveEvent>;
  approve(
    runId: string,
    approvalId: string,
    decision: "approve" | "reject",
    signal?: AbortSignal,
  ): AsyncIterable<LiveEvent>;
  cancel(runId: string): Promise<string>;
  pendingApprovals(runId: string): Promise<PendingApproval[]>;
  run(runId: string): Promise<RunInfo>;
  memory: {
    candidates(): Promise<MemoryCandidateView[]>;
    decide(
      id: string,
      decision: "approve" | "reject",
      editedContent?: string,
    ): Promise<void>;
    list(): Promise<MemoryView[]>;
    edit(id: string, content: string): Promise<void>;
    remove(id: string): Promise<void>;
  };
  analyses: {
    create(input: {
      id: string;
      evidenceId: string;
      consentVersion: string;
    }): Promise<AnalysisView>;
    get(id: string): Promise<AnalysisView>;
  };
  roleplay: {
    scenarios(): Promise<RoleplayScenario[]>;
    create(input: {
      id: string;
      role: RoleplayRole;
      scenarioKey: string;
      userGoal: string;
      difficulty: number;
      linkedCaseId?: string | null;
      useCaseContext: boolean;
    }): Promise<RoleplaySessionView>;
    get(id: string): Promise<RoleplaySessionView>;
    list(): Promise<RoleplaySessionView[]>;
    complete(id: string): Promise<RoleplaySessionView>;
    abandon(id: string): Promise<RoleplaySessionView>;
  };
}

/** Narrow the composition-level marker to the full live API (runtime-checked). */
export function asLive(service: CompanionService | null): LiveCompanion | null {
  return service !== null && "conversations" in service
    ? (service as LiveCompanion)
    : null;
}
