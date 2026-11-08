import type { Evidence, Incident, TimelineEvent } from "../../types";
export interface CaseDraft {
  clientId?: string;
  firstEventId?: string;
  baseVersion?: number;
  title: string;
  template: string;
  perspective: Incident["perspective"];
  summary: string;
  categoryTags: string[];
  impactTags: string[];
  people: string;
  place: string;
  occurredAt: string;
  timePrecision: TimelineEvent["timePrecision"];
  tried: string;
  trustedPerson: string;
  attachments: Evidence[];
  linkedChatIds: string[];
  sourceEvidenceIds: string[];
  step: number;
}
export function caseDraftIdentity(prefill: Partial<Incident>): string {
  const source = JSON.stringify(prefill);
  let hash = 2166136261;
  for (let index = 0; index < source.length; index++)
    hash = Math.imul(hash ^ source.charCodeAt(index), 16777619);
  return `new:import:${prefill.linkedChatIds?.join(",") || "story"}:${(hash >>> 0).toString(36)}`;
}
export const templates = [
  {
    id: "TPL-VERBAL",
    label: "Trêu chọc / xúc phạm",
    hint: "Điều này xảy ra lần gần nhất khi nào?",
  },
  {
    id: "TPL-THREAT",
    label: "Tin nhắn đe dọa",
    hint: "Bạn đang ở nơi an toàn chứ? Có người lớn nào ở gần bạn không?",
  },
  {
    id: "TPL-EXCLUSION",
    label: "Bị cô lập",
    hint: "Việc này xảy ra một lần hay nhiều lần?",
  },
  {
    id: "TPL-PHYSICAL",
    label: "Xô đẩy / động chạm",
    hint: "Hiện có ai có thể giúp bạn an toàn?",
  },
  {
    id: "TPL-IMAGE",
    label: "Ảnh bị chia sẻ",
    hint: "Bạn nhớ ảnh xuất hiện ở đâu? Chỉ dùng nội dung mẫu trong bản demo.",
  },
  {
    id: "TPL-IMPERSONATION",
    label: "Mạo danh",
    hint: "Bạn nhớ tài khoản, bài đăng hay thời điểm nào?",
  },
  {
    id: "TPL-WITNESS",
    label: "Mình chứng kiến",
    hint: "Phần nào bạn trực tiếp thấy? Phần nào được kể lại?",
  },
  {
    id: "TPL-FREE",
    label: "Kể theo cách của mình",
    hint: "Bạn muốn bắt đầu từ điều gì?",
  },
];
export const statusLabels: Record<Incident["status"], string> = {
  draft: "Bản nháp",
  active: "Đang ghi nhận",
  monitoring: "Đang theo dõi",
  closed: "Đã khép lại",
};
export const provenanceLabels: Record<TimelineEvent["provenance"], string> = {
  user_entered: "Mình kể",
  mock_extracted: "Từ ảnh mẫu",
  ai_extracted: "Từ phân tích AI",
  user_confirmed: "Đã xác nhận lại",
};
export const createCaseDraft = (item?: Partial<Incident>): CaseDraft => ({
  clientId: item?.id,
  firstEventId: item?.events?.[0]?.id,
  baseVersion: item?.version,
  title: item?.title ?? "",
  template: item?.template ?? "TPL-FREE",
  perspective: item?.perspective ?? "self",
  summary: item?.summary ?? "",
  categoryTags: item?.categoryTags ?? [],
  impactTags: item?.impactTags ?? [],
  people: item?.people ?? "",
  place: item?.place ?? "",
  occurredAt: item?.occurredAt ?? "",
  timePrecision:
    item?.events?.[0]?.timePrecision ?? (item?.occurredAt ? "day" : "unknown"),
  tried: item?.tried ?? "",
  trustedPerson: item?.trustedPerson ?? "",
  attachments: [],
  linkedChatIds: item?.linkedChatIds ?? [],
  sourceEvidenceIds: item?.evidenceIds ?? [],
  step: 0,
});
export const validateCaseDraft = (
  draft: CaseDraft,
  partial: boolean,
): Record<string, string> => {
  const errors: Record<string, string> = {};
  if (!partial && !draft.summary.trim())
    errors.summary = "Bạn hãy ghi một điều đã xảy ra. Bạn có thể kể ngắn thôi.";
  if (draft.timePrecision !== "unknown" && !draft.occurredAt)
    errors.occurredAt = "Chọn thời gian, hoặc chọn “Không nhớ chính xác”.";
  return errors;
};
export const incidentFromDraft = (
  draft: CaseDraft,
  id: string,
  ownerId: string,
  status: Incident["status"],
  existing?: Incident,
): Incident => {
  const now = new Date().toISOString();
  const when = draft.timePrecision === "unknown" ? "" : draft.occurredAt;
  const first: TimelineEvent = {
    ...(existing?.events[0] ?? {
      id: draft.firstEventId ?? `${id}-first`,
      caseId: id,
      provenance: "user_entered" as const,
      needsReview: false,
    }),
    when,
    timePrecision: draft.timePrecision,
    place: draft.place,
    description: draft.summary.trim(),
    evidenceIds: [
      ...new Set([
        ...(existing?.events[0]?.evidenceIds ?? []),
        ...draft.sourceEvidenceIds,
        ...draft.attachments.map((e) => e.id),
      ]),
    ],
  };
  return {
    id,
    ownerId,
    title: draft.title.trim() || "Điều mình muốn ghi lại",
    template: draft.template,
    perspective: draft.perspective,
    summary: draft.summary.trim(),
    categoryTags: draft.categoryTags,
    status,
    impactTags: draft.impactTags,
    events: draft.summary.trim()
      ? [first, ...(existing?.events.slice(1) ?? [])]
      : (existing?.events ?? []),
    evidenceIds: [
      ...new Set([
        ...(existing?.evidenceIds ?? []),
        ...draft.sourceEvidenceIds,
        ...draft.attachments.map((e) => e.id),
      ]),
    ],
    linkedChatIds: [
      ...new Set([...(existing?.linkedChatIds ?? []), ...draft.linkedChatIds]),
    ],
    linkedPlanId: existing?.linkedPlanId,
    people: draft.people,
    place: draft.place,
    occurredAt: when,
    tried: draft.tried,
    trustedPerson: draft.trustedPerson,
    createdAt: existing?.createdAt ?? now,
    updatedAt: now,
    version: draft.baseVersion ?? existing?.version,
    demo: true,
  };
};
export function mergeCaseEdits(
  base: Incident,
  edited: Incident,
  latest: Incident,
): Incident {
  const merged = { ...latest };
  const scalars = [
    "title",
    "template",
    "perspective",
    "summary",
    "categoryTags",
    "impactTags",
    "status",
    "people",
    "place",
    "occurredAt",
    "tried",
    "trustedPerson",
  ] as const;
  for (const key of scalars) {
    if (JSON.stringify(base[key]) !== JSON.stringify(edited[key]))
      Object.assign(merged, { [key]: edited[key] });
  }
  const events = new Map(latest.events.map((event) => [event.id, event]));
  for (const event of base.events)
    if (!edited.events.some((next) => next.id === event.id))
      events.delete(event.id);
  for (const event of edited.events) {
    const previous = base.events.find((value) => value.id === event.id);
    if (JSON.stringify(previous) !== JSON.stringify(event))
      events.set(event.id, event);
  }
  merged.events = [...events.values()];
  const removed = new Set(
    base.evidenceIds.filter((id) => !edited.evidenceIds.includes(id)),
  );
  merged.evidenceIds = [
    ...new Set([
      ...latest.evidenceIds.filter((id) => !removed.has(id)),
      ...edited.evidenceIds.filter((id) => !base.evidenceIds.includes(id)),
    ]),
  ];
  return merged;
}

export const eventTime = (event: TimelineEvent): string =>
  event.timePrecision === "unknown" || !event.when
    ? "Chưa rõ thời gian"
    : event.timePrecision === "week"
      ? `Khoảng tuần ${event.when}`
      : event.timePrecision === "exact"
        ? new Date(event.when).toLocaleString("vi-VN")
        : new Date(`${event.when.slice(0, 10)}T12:00:00`).toLocaleDateString(
            "vi-VN",
          );
export const caseSummary = (item: Incident, evidence: Evidence[]): string => {
  const confirmed = item.events.filter(
    (e) => !e.needsReview && e.provenance !== "mock_extracted",
  );
  const uncertain = item.events.filter(
    (e) => e.needsReview || e.provenance === "mock_extracted",
  );
  const row = (e: TimelineEvent) =>
    `- ${eventTime(e)} | ${e.place || "Chưa ghi địa điểm"} | ${e.description} [${provenanceLabels[e.provenance]}]${e.evidenceIds.length ? ` — Nguồn: ${e.evidenceIds.join(", ")}` : ""}`;
  return [
    `MOODPRINT — BẢN TÓM TẮT DEMO`,
    item.title,
    `Trạng thái do người dùng đặt: ${statusLabels[item.status]}`,
    `Góc nhìn: ${item.perspective === "witness" ? "Người chứng kiến" : "Người trải qua"}`,
    "",
    "NỘI DUNG NGƯỜI DÙNG GHI LẠI",
    item.summary || "Chưa có mô tả.",
    `Người liên quan (vai trò / bí danh): ${item.people || "Chưa bổ sung"}`,
    ...confirmed.map(row),
    "",
    "ẢNH HƯỞNG VÀ ĐIỀU ĐÃ THỬ",
    `Ảnh hưởng: ${item.impactTags.join(", ") || "Chưa chia sẻ"}`,
    `Đã thử: ${item.tried || "Chưa bổ sung"}`,
    `Người có thể hỗ trợ: ${item.trustedPerson || "Chưa chọn"}`,
    "",
    "ĐIỀU CHƯA RÕ / CẦN KIỂM TRA",
    ...(!item.occurredAt ? ["- Chưa rõ thời gian của sự việc đầu tiên."] : []),
    ...uncertain.map(row),
    ...evidence
      .filter(
        (e) =>
          item.evidenceIds.includes(e.id) && e.reviewStatus !== "confirmed",
      )
      .map(
        (e) =>
          `- ${e.id}: ${e.reviewStatus === "rejected" ? "Đã loại khỏi phần xác nhận" : "Chưa được xác nhận"}; ${e.limitations.join("; ")}`,
      ),
    ...(uncertain.length === 0 && item.occurredAt
      ? [
          "Chưa bổ sung điều chưa rõ. Điều này không có nghĩa mọi nội dung đã được kiểm chứng.",
        ]
      : []),
    "",
    "NGUỒN ĐÍNH KÈM",
    ...evidence
      .filter((e) => item.evidenceIds.includes(e.id))
      .map(
        (e) =>
          `- ${e.id} | ${e.origin === "mock_fixture" ? "Tệp mẫu giả lập" : "Văn bản người dùng nhập"} | Mốc hiển thị: ${e.shownTimestamp || "Chưa rõ"}`,
      ),
    "",
    "Đây là bản ghi cá nhân từ dữ liệu demo, chưa được kiểm chứng độc lập; không phải kết luận hay chứng cứ pháp lý. Không có nội dung nào được gửi cho nhà trường hoặc người khác.",
  ].join("\n");
};
