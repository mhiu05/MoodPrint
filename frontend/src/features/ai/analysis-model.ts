import type { Evidence, TimelineEvent } from "../../types";
export type AnalysisVariant = "multi" | "conflict" | "duplicate";
export const analysisVariants: {
  id: AnalysisVariant;
  label: string;
  description: string;
}[] = [
  {
    id: "multi",
    label: "8 ảnh nhóm lớp",
    description: "Nhiều ngày, ảnh bị cắt và tên người gửi bị che.",
  },
  {
    id: "conflict",
    label: "Mốc giờ khác lời kể",
    description: "Giữ lời nhớ 18:00 cạnh giờ 20:10 trong ảnh.",
  },
  {
    id: "duplicate",
    label: "Hai ảnh có thể trùng",
    description: "Rà soát ảnh 07 và 08; không đếm thêm sự việc.",
  },
];
export const fixtureSources = [
  {
    text: "Một bạn gọi Minh bằng biệt danh Minh không thích.",
    time: "2026-10-12T19:40:00+07:00",
    limitations: [],
  },
  {
    text: "Có biểu tượng cười theo sau lời trêu chọc.",
    time: "2026-10-12T20:04:00+07:00",
    limitations: [
      "Một phần tin nhắn khó đọc; không biết ai tham gia hay đồng tình.",
    ],
  },
  {
    text: "Ngày mai ra cổng gặp tụi mình.",
    time: "2026-10-13T20:10:00+07:00",
    limitations: ["Chưa rõ ngữ cảnh và ý định của lời hẹn."],
  },
  {
    text: "Đoạn chat bị cắt mất phần đầu; không đủ ngữ cảnh.",
    time: "2026-10-13T20:13:00+07:00",
    limitations: ["Ảnh bị cắt; phần trước không nhìn thấy."],
  },
  {
    text: "Một tin nhắn tiếp tục gọi biệt danh cũ.",
    time: "2026-10-14T21:02:00+07:00",
    limitations: [],
  },
  {
    text: "Một bạn khác nhắn: Đừng làm vậy nữa.",
    time: "2026-10-15T18:33:00+07:00",
    limitations: ["Một câu phản đối không bảo đảm tình huống đã an toàn."],
  },
  {
    text: "Nhiều tin nhắn trong nhóm; tên người gửi bị che.",
    time: "2026-10-16T19:55:00+07:00",
    limitations: ["Tên bị che, không thể gán danh tính."],
  },
  {
    text: "Nhiều tin nhắn trong nhóm; tên người gửi bị che.",
    time: "2026-10-16",
    limitations: [
      "Không rõ giờ.",
      "Có thể trùng MEDIA-07; không tạo sự việc thứ hai.",
    ],
  },
];
export function createFixtureEvidence(
  analysisId: string,
  variant: string,
): Evidence[] {
  return fixtureSources.map((source, index) => ({
    id: `${analysisId}-MEDIA-${String(index + 1).padStart(2, "0")}`,
    kind: "screenshot",
    origin: "mock_fixture",
    assetPath: `/fixtures/messenger_${String(index + 1).padStart(2, "0")}.svg`,
    shownTimestamp: source.time,
    originalText: source.text,
    extractedText: source.text,
    reviewStatus: "unreviewed",
    limitations: [
      ...source.limitations,
      ...(variant === "conflict" && index === 2
        ? [
            "Lời kể nhớ khoảng 18:00, khác giờ 20:10 hiển thị; giữ cả hai để hỏi lại.",
          ]
        : []),
    ],
  }));
}
export function correctEvidence(item: Evidence, text: string): Evidence {
  return { ...item, userEditedText: text, reviewStatus: "corrected" };
}
export function buildConfirmedTimeline(
  caseId: string,
  items: Evidence[],
  confirmedIds: string[],
): TimelineEvent[] {
  const events: TimelineEvent[] = [];
  const normalize = (value: string) =>
    value.normalize("NFC").trim().replace(/\s+/g, " ").toLocaleLowerCase("vi");
  for (const item of items) {
    if (item.reviewStatus !== "confirmed" || !confirmedIds.includes(item.id))
      continue;
    const description = item.userEditedText ?? item.extractedText;
    const duplicateGroup =
      item.id.endsWith("MEDIA-07") || item.id.endsWith("MEDIA-08");
    const existing = duplicateGroup
      ? events.find(
          (event) =>
            event.evidenceIds.some(
              (id) => id.endsWith("MEDIA-07") || id.endsWith("MEDIA-08"),
            ) && normalize(event.description) === normalize(description),
        )
      : undefined;
    if (existing) {
      existing.evidenceIds.push(item.id);
      continue;
    }
    events.push({
      id: `${caseId}-event-${events.length + 1}`,
      caseId,
      when: item.shownTimestamp,
      timePrecision: item.shownTimestamp.includes("T") ? "exact" : "day",
      place: "Nhóm chat lớp (mẫu)",
      description,
      provenance: "user_confirmed",
      evidenceIds: [item.id],
      needsReview: item.limitations.length > 0,
    });
  }
  return events;
}
