export type AgeBand = "11–13" | "14–17";
export interface DemoUser {
  id: string;
  nickname: string;
  ageBand: AgeBand;
  demo?: boolean;
}
export type CaseStatus = "draft" | "active" | "monitoring" | "closed";
export type Provenance =
  "user_entered" | "mock_extracted" | "ai_extracted" | "user_confirmed";
export interface TimelineEvent {
  id: string;
  caseId: string;
  when: string;
  timePrecision: "exact" | "day" | "week" | "unknown";
  place: string;
  description: string;
  provenance: Provenance;
  evidenceIds: string[];
  needsReview: boolean;
}
export interface Evidence {
  id: string;
  caseId?: string;
  kind:
    | "screenshot"
    | "text_note"
    | "pdf_placeholder"
    | "image"
    | "audio"
    | "video"
    | "document"
    | "other";
  origin: "mock_fixture" | "user_entered" | "user_upload";
  uploadStatus?: "pending" | "uploaded" | "failed" | "deleting";
  originalFilename?: string;
  byteSize?: number;
  storedMimeType?: string;
  capturedAtLabel?: string;
  assetPath?: string;
  shownTimestamp: string;
  originalText: string;
  extractedText: string;
  userEditedText?: string;
  reviewStatus: "unreviewed" | "corrected" | "confirmed" | "rejected";
  limitations: string[];
}
export interface Incident {
  version?: number;
  id: string;
  ownerId: string;
  title: string;
  template: string;
  perspective: "self" | "witness";
  summary: string;
  categoryTags: string[];
  status: CaseStatus;
  impactTags: string[];
  events: TimelineEvent[];
  evidenceIds: string[];
  linkedChatIds: string[];
  linkedPlanId?: string;
  people: string;
  place: string;
  occurredAt: string;
  tried: string;
  trustedPerson: string;
  createdAt: string;
  updatedAt: string;
  demo?: boolean;
}
export interface PlanItem {
  id: string;
  label: string;
  status: "not_started" | "doing" | "done";
  notes: string;
  priority: "high" | "normal";
  reason: string;
}
export interface ActionPlan {
  version?: number;
  outcomeNotes?: string;
  id: string;
  caseId: string;
  goal: string;
  chosenOptionId: string;
  status: "draft" | "active" | "paused" | "completed";
  items: PlanItem[];
  nextReviewDate: string;
  lastUpdated: string;
  demo?: boolean;
}
export interface ChatMessage {
  createdAt?: string;
  id: string;
  speaker: "user" | "ai" | "system";
  body: string;
  sourceIds?: string[];
  rich?: boolean;
}
export interface ChatSession {
  id: string;
  ownerId: string;
  linkedCaseId?: string;
  sourceArticleId?: string;
  sourceArticleSlug?: string;
  sourceIds?: string[];
  scenarioId: string;
  title: string;
  messages: ChatMessage[];
  cursor: number;
  draft?: string;
}
export interface Analysis {
  id: string;
  ownerId: string;
  fixture: string;
  evidenceIds: string[];
  confirmedIds: string[];
  description: string;
  questionAnswer: string;
  status: "idle" | "processing" | "review" | "confirmed" | "error";
  caseId?: string;
}
export interface RoleplaySession {
  id: string;
  ownerId: string;
  role: string;
  scenarioId: string;
  tone: string;
  mode: "text" | "voice_demo";
  turns: ChatMessage[];
  cursor: number;
  status: "active" | "paused" | "completed";
}
export interface SupportDraft {
  version?: number;
  compose?: { purpose: string; detail: string; alias: string };
  id: string;
  ownerId: string;
  caseId?: string;
  recipientType: string;
  identityMode: "alias" | "disclose";
  content: string;
  status:
    "draft" | "prepared" | "demo_submitted" | "demo_reviewing" | "demo_closed";
  createdAt: string;
  demo?: boolean;
}
export interface TrustedPerson {
  id: string;
  label: string;
  role: string;
}
export interface KnowledgeSource {
  id: string;
  publisher: string;
  title: string;
  url: string;
  applicability: string;
  checkedAt: string;
}
export interface KnowledgeArticle {
  id: string;
  slug: string;
  title: string;
  summary: string;
  topics: string[];
  ageBands: AgeBand[];
  readMinutes: number;
  format: "guide" | "scenario" | "quiz" | "checklist" | "template" | "faq";
  sections: { title: string; body: string }[];
  sourceIds: string[];
  lastReviewed: string;
  applicability: string;
  scenario?: {
    question: string;
    options: { label: string; feedback: string; helpful: boolean }[];
  };
  quiz?: {
    question: string;
    options: string[];
    answer: number;
    explanation: string;
  };
}
export interface SchoolReport {
  id: string;
  category: string;
  date: string;
  group: string;
  status: "new" | "reviewing" | "follow_up" | "closed";
  summary: string;
  handledByRole: string;
  notes: string;
  demo?: boolean;
}
