import type {
  ActionPlan,
  AgeBand,
  Analysis,
  ChatSession,
  DemoUser,
  Evidence,
  Incident,
  KnowledgeArticle,
  PlanItem,
  RoleplaySession,
  SupportDraft,
  TimelineEvent,
  TrustedPerson,
} from "../types";
import type { KnowledgeSearchService } from "./composition/knowledge-types";
import type { CompanionService } from "./composition/companion-types";

export interface WorkspaceProfile {
  user: DemoUser;
  reducedMotion: boolean;
}
export interface ProfilePatch {
  nickname?: string;
  ageBand?: AgeBand;
  reducedMotion?: boolean;
}
export interface SignUpInput {
  email: string;
  password: string;
  nickname: string;
  ageBand: AgeBand;
  startInterest: string;
}
export interface AuthPort {
  getSession(): Promise<{ userId: string } | null>;
  signIn(email: string, password: string): Promise<void>;
  signUp(input: SignUpInput): Promise<{ needsEmailConfirmation: boolean }>;
  signOut(): Promise<void>;
  requestPasswordReset(email: string): Promise<void>;
  updatePassword(password: string): Promise<void>;
}
export interface ProfilePort {
  get(): Promise<WorkspaceProfile>;
  save(patch: ProfilePatch): Promise<WorkspaceProfile>;
  remove(): Promise<void>;
}
export interface CaseQuery {
  status?: Incident["status"];
  q?: string;
  sort?: "updated" | "title";
}
export interface CasePort {
  list(query?: CaseQuery): Promise<Incident[]>;
  get(id: string): Promise<Incident>;
  save(item: Incident): Promise<Incident>;
  remove(id: string): Promise<void>;
  addEvent(caseId: string, event: TimelineEvent): Promise<TimelineEvent>;
  updateEvent(caseId: string, event: TimelineEvent): Promise<TimelineEvent>;
  removeEvent(caseId: string, eventId: string): Promise<void>;
  related(id: string): Promise<Incident[]>;
}
export interface UploadMetadata {
  caseId?: string;
  shownTimestamp?: string;
  capturedAtLabel?: string;
}
export interface UploadCallbacks {
  onProgress?: (percent: number) => void;
  onError?: (error: Error) => void;
}
export interface UploadController {
  pause(): Promise<void>;
  resume(): Promise<void>;
  cancel(): Promise<void>;
  done: Promise<Evidence>;
}
export interface EvidenceNote {
  id?: string;
  caseId?: string;
  originalText: string;
  shownTimestamp?: string;
  capturedAtLabel?: string;
}
export type EvidenceReview = Pick<Evidence, "reviewStatus" | "limitations"> & {
  userEditedText?: string;
};
export interface EvidencePort {
  list(options?: { caseId?: string; unlinked?: boolean }): Promise<Evidence[]>;
  get(id: string): Promise<Evidence>;
  createNote(data: EvidenceNote): Promise<Evidence>;
  save(item: Evidence): Promise<Evidence>;
  upload(
    file: File,
    metadata?: UploadMetadata,
    callbacks?: UploadCallbacks,
  ): UploadController;
  review(id: string, patch: Partial<EvidenceReview>): Promise<Evidence>;
  link(caseId: string, evidenceId: string): Promise<void>;
  unlink(caseId: string, evidenceId: string): Promise<void>;
  remove(id: string): Promise<void>;
  getDownloadUrl(id: string): Promise<{ url: string; expiresAt: string }>;
}
export interface PlanPort {
  save(item: ActionPlan): Promise<ActionPlan>;
  getForCase(caseId: string): Promise<ActionPlan | null>;
  active(): Promise<ActionPlan | null>;
  setItemStatus(
    planId: string,
    itemId: string,
    status: PlanItem["status"],
    notes?: string,
  ): Promise<ActionPlan>;
}
export interface TrustedContactPort {
  list(): Promise<TrustedPerson[]>;
  save(item: TrustedPerson): Promise<TrustedPerson>;
  remove(id: string): Promise<void>;
}
export interface School {
  id: string;
  name: string;
  verificationStatus?: string;
}
export type SharedField =
  | "title"
  | "summary"
  | "occurredAt"
  | "place"
  | "events"
  | "people"
  | "impactTags"
  | "tried";
export interface Share {
  id: string;
  caseId: string | null;
  schoolId: string;
  identityMode: "alias" | "disclose";
  status: "draft" | "submitted" | "in_review" | "closed" | "withdrawn";
  sharedFields: SharedField[];
  evidenceIds: string[];
  version: number;
  snapshot?: Record<string, unknown> | null;
}
export interface ShareInput {
  id: string;
  caseId: string;
  schoolId: string;
  identityMode: "alias" | "disclose";
  sharedFields: SharedField[];
  evidenceIds: string[];
}
export interface SupportPort {
  list(): Promise<SupportDraft[]>;
  save(item: SupportDraft): Promise<SupportDraft>;
  remove(id: string): Promise<void>;
  listSchools(): Promise<School[]>;
  listShares(): Promise<Share[]>;
  createShare(input: ShareInput): Promise<Share>;
  previewShare(
    id: string,
  ): Promise<Record<string, unknown> & { previewHash: string }>;
  submitShare(
    id: string,
    confirmationVersion: string,
    previewHash: string,
  ): Promise<Share>;
  withdrawShare(id: string): Promise<Share>;
}
export interface ArticleState {
  articleId: string;
  bookmarked: boolean;
  readAt: string | null;
}
export interface KnowledgeStatePort {
  list(): Promise<ArticleState[]>;
  toggleBookmark(id: string): Promise<void>;
  markRead(id: string): Promise<void>;
}
export interface SimulatedPort<T> {
  readonly simulated: true;
  save(item: T): Promise<T>;
}
export interface AnalysisPort extends SimulatedPort<Analysis> {
  saveEvidence(item: Evidence): Promise<Evidence>;
}
export interface Services {
  auth: AuthPort;
  profile: ProfilePort;
  cases: CasePort;
  evidence: EvidencePort;
  plans: PlanPort;
  contacts: TrustedContactPort;
  support: SupportPort;
  knowledgeState: KnowledgeStatePort;
  knowledgeCatalog: { list(): KnowledgeArticle[] };
  knowledgeSearch: KnowledgeSearchService | null;
  companion: CompanionService | null;
  chat: SimulatedPort<ChatSession>;
  analysis: AnalysisPort;
  roleplay: SimulatedPort<RoleplaySession>;
  voice: { readonly simulated: true };
  run<T>(work: () => T | Promise<T>, delay?: number): Promise<T>;
}
