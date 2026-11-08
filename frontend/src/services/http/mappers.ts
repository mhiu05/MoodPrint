import type {
  ActionPlan,
  AgeBand,
  DemoUser,
  Evidence,
  Incident,
  SupportDraft,
  TimelineEvent,
} from "../../types";
import type { components } from "./schema.gen";

export type ProfileDTO = components["schemas"]["Profile"];
export const mapAgeBand = (value: ProfileDTO["ageBand"]): AgeBand =>
  value === "14-17" ? "14–17" : "11–13";
export const serializeAgeBand = (value: AgeBand) =>
  value === "14–17" ? ("14-17" as const) : ("11-13" as const);
export const mapUser = (data: ProfileDTO): DemoUser => ({
  id: data.userId,
  nickname: data.nickname,
  ageBand: mapAgeBand(data.ageBand),
  demo: false,
});
export type CaseDTO = Omit<
  Partial<components["schemas"]["CaseDetail"]>,
  "events"
> &
  Pick<Partial<Incident>, "events"> & {
    id: string;
  };
export function mapIncident(data: CaseDTO): Incident {
  return {
    id: data.id,
    ownerId: data.ownerId ?? "",
    title: data.title ?? "",
    template: data.template ?? "TPL-FREE",
    perspective: data.perspective ?? "self",
    summary: data.summary ?? "",
    categoryTags: data.categoryTags ?? [],
    impactTags: data.impactTags ?? [],
    status: data.status ?? "draft",
    people: data.people ?? "",
    place: data.place ?? "",
    occurredAt: data.occurredAt ?? "",
    tried: data.tried ?? "",
    trustedPerson: data.trustedPerson ?? "",
    events: data.events ?? [],
    evidenceIds: data.evidenceIds ?? [],
    linkedChatIds: [],
    linkedPlanId: data.linkedPlanId ?? undefined,
    version: data.version,
    createdAt: data.createdAt ?? "",
    updatedAt: data.updatedAt ?? "",
    demo: false,
  };
}
export function serializeCase(item: Incident) {
  const {
    id,
    title,
    template,
    perspective,
    summary,
    categoryTags,
    impactTags,
    status,
    people,
    place,
    occurredAt,
    tried,
    trustedPerson,
    version,
  } = item;
  return {
    id,
    title,
    template,
    perspective,
    summary,
    categoryTags,
    impactTags,
    status,
    people,
    place,
    occurredAt,
    tried,
    trustedPerson,
    ...(version === undefined ? {} : { version }),
  };
}
export function serializeEvent(item: TimelineEvent) {
  if (item.provenance === "mock_extracted")
    throw new Error("Mốc mô phỏng không thể lưu vào hồ sơ thật.");
  const {
    id,
    when,
    timePrecision,
    place,
    description,
    provenance,
    evidenceIds,
    needsReview,
  } = item;
  return {
    id,
    when:
      timePrecision === "exact" && when ? new Date(when).toISOString() : when,
    timePrecision,
    place,
    description,
    provenance,
    evidenceIds,
    needsReview,
  };
}
export type PlanDTO = Omit<Partial<ActionPlan>, "nextReviewDate" | "items"> & {
  id: string;
  nextReviewDate?: string | null;
  updatedAt?: string;
  items?: (Partial<ActionPlan["items"][number]> & {
    id: string;
    label: string;
  })[];
};
export function mapPlan(data: PlanDTO): ActionPlan {
  return {
    id: data.id,
    caseId: data.caseId ?? "",
    goal: data.goal ?? "",
    chosenOptionId: data.chosenOptionId ?? "",
    status: data.status ?? "draft",
    items: (data.items ?? []).map((item) => ({
      id: item.id,
      label: item.label,
      status: item.status ?? "not_started",
      notes: item.notes ?? "",
      priority: item.priority ?? "normal",
      reason: item.reason ?? "",
    })),
    nextReviewDate: data.nextReviewDate ?? "",
    outcomeNotes: data.outcomeNotes ?? "",
    lastUpdated: data.lastUpdated ?? data.updatedAt ?? "",
    version: data.version,
    demo: false,
  };
}
export function serializePlan(item: ActionPlan) {
  const { id, goal, chosenOptionId, status, items, outcomeNotes, version } =
    item;
  return {
    id,
    goal,
    chosenOptionId,
    status,
    items,
    nextReviewDate: item.nextReviewDate || null,
    outcomeNotes: outcomeNotes ?? "",
    ...(version === undefined ? {} : { version }),
  };
}
export type EvidenceDTO = Omit<
  Partial<Evidence>,
  | "caseId"
  | "originalText"
  | "userEditedText"
  | "originalFilename"
  | "byteSize"
  | "storedMimeType"
> & {
  id: string;
  caseId?: string | null;
  originalText?: string | null;
  userEditedText?: string | null;
  originalFilename?: string | null;
  byteSize?: number | null;
  storedMimeType?: string | null;
};
export function mapEvidence(data: EvidenceDTO): Evidence {
  return {
    id: data.id,
    caseId: data.caseId ?? undefined,
    kind: data.kind ?? "other",
    origin: data.origin ?? "user_upload",
    shownTimestamp: data.shownTimestamp ?? "",
    originalText: data.originalText ?? "",
    extractedText: data.extractedText ?? "",
    userEditedText: data.userEditedText ?? undefined,
    reviewStatus: data.reviewStatus ?? "unreviewed",
    limitations: data.limitations ?? [],
    uploadStatus: data.uploadStatus,
    originalFilename: data.originalFilename ?? undefined,
    byteSize: data.byteSize ?? undefined,
    storedMimeType: data.storedMimeType ?? undefined,
    capturedAtLabel: data.capturedAtLabel,
  };
}
export function mapSupport(
  data: Omit<SupportDraft, "caseId"> & { caseId?: string | null },
): SupportDraft {
  return { ...data, caseId: data.caseId ?? undefined, demo: false };
}
