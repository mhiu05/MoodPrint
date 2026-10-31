/**
 * User-facing words for companion collaboration (phase-2/04). Plain Vietnamese only: no
 * "agent", "tool", "run", model or technical names. The server never sends these texts; it
 * sends only the edge, so the description of what is shared cannot drift from the code.
 */
export type Edge = "nhip_energy_for_rure" | "nhip_habit_for_may" | "rure_activity_for_guong";

export type EdgeCopy = {
  title: string;
  shared: string;
  notShared: string;
  /** "Vì sao?" sheet: question and the kind of data shared (never the values). */
  whyTitle: string;
  why: string;
  requiresJournal?: boolean;
};

export const EDGE_ORDER: Edge[] = ["nhip_energy_for_rure", "nhip_habit_for_may", "rure_activity_for_guong"];

export const EDGE_COPY: Record<Edge, EdgeCopy> = {
  nhip_energy_for_rure: {
    title: "Nhịp gợi ý mức năng lượng cho Rủ Rê",
    shared: "Chia sẻ: mức năng lượng (thấp/vừa/cao), thời lượng gợi ý.",
    notShared: "Không chia sẻ: nhật ký, cảm xúc, yếu tố, tin nhắn của bạn.",
    whyTitle: "Vì sao Rủ Rê chọn hoạt động này?",
    why:
      "Bạn đã cho phép Nhịp chia sẻ mức năng lượng (thấp / vừa / cao) với Rủ Rê. Lần này Nhịp đọc khoảnh khắc " +
      "bạn đã lưu gần đây và chỉ gửi cho Rủ Rê mức năng lượng và thời lượng gợi ý. Rủ Rê không thấy nhật ký, " +
      "cảm xúc, yếu tố hay câu chữ của bạn.",
    requiresJournal: true,
  },
  nhip_habit_for_may: {
    title: "Nhịp gợi ý thói quen nhỏ cho Mây",
    shared: "Chia sẻ: loại nhu cầu bạn vừa kể (giấc ngủ, căng thẳng, tập trung, năng lượng).",
    notShared: "Không chia sẻ: câu chữ của bạn, nhật ký, ghi nhớ.",
    whyTitle: "Vì sao Mây gợi ý thói quen này?",
    why:
      "Bạn đã cho phép Mây nhờ Nhịp gợi ý một thói quen nhỏ. Mây chỉ cho Nhịp biết loại nhu cầu bạn vừa kể và " +
      "buổi trong ngày. Nhịp không thấy câu chữ của bạn, nhật ký hay ghi nhớ.",
  },
  rure_activity_for_guong: {
    title: "Rủ Rê gợi ý hoạt động cho Gương",
    shared: "Chia sẻ: một chủ đề sở thích (ví dụ: vẽ, âm nhạc) và thời lượng.",
    notShared: "Không chia sẻ: câu chữ của bạn, ghi nhớ.",
    whyTitle: "Vì sao Gương gợi ý hoạt động này?",
    why:
      "Bạn đã cho phép Gương nhờ Rủ Rê gợi ý một hoạt động nhỏ. Gương chỉ cho Rủ Rê biết một chủ đề sở thích " +
      "và thời lượng. Rủ Rê không thấy câu chữ của bạn hay ghi nhớ.",
  },
};

export const CAUNOI_NOTE = "Cầu Nối không nhận thông tin từ trợ lý khác.";

export function edgeCopy(kind: string): EdgeCopy | undefined {
  return Object.hasOwn(EDGE_COPY, kind) ? EDGE_COPY[kind as Edge] : undefined;
}

export function sharingReason(reason: string | null | undefined): string | null {
  if (reason === "journal_context_off") return "Cần bật \"Dùng khoảnh khắc đã lưu hôm qua\" ở Lịch hỏi thăm.";
  if (reason === "ineligible_account") return "Tính năng này chỉ dành cho tài khoản từ 18 tuổi.";
  if (reason === "feature_unavailable") return "Tính năng phối hợp chưa mở cho tài khoản của bạn.";
  return null;
}
