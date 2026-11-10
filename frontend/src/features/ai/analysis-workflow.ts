import { uid, useWorkspaceStore } from "../../app/store";
import type { Analysis } from "../../types";
import { getServices } from "../../services/composition";
import { createFixtureEvidence } from "./analysis-model";
import type { AnalysisVariant } from "./analysis-model";

export function startFixtureAnalysis(
  variant: AnalysisVariant,
  chatId?: string,
): Analysis {
  const store = useWorkspaceStore.getState();
  const id = uid("ANALYSIS");
  const evidence = createFixtureEvidence(id, variant);
  const analysis: Analysis = {
    id,
    ownerId: store.user?.id ?? "USER-AN",
    fixture: variant,
    evidenceIds: evidence.map((item) => item.id),
    confirmedIds: [],
    description: "",
    questionAnswer:
      variant === "conflict"
        ? "Lời kể mẫu: mình nhớ khoảng 18:00, chưa chắc ngày giờ."
        : "",
    status: "idle",
  };
  evidence.forEach((item) => void getServices().analysis.saveEvidence(item));
  void getServices().analysis.save(analysis);
  if (chatId) {
    const chat = store.chats.find(
      (item) => item.id === chatId && item.ownerId === store.user?.id,
    );
    if (chat)
      void getServices().chat.save({
        ...chat,
        messages: [
          ...chat.messages,
          {
            id: uid("message"),
            createdAt: new Date().toISOString(),
            speaker: "ai",
            body: "Đã đính kèm bộ ảnh hư cấu. Mở phân tích để rà soát từng ảnh; chưa có nội dung nào được xác nhận.",
            rich: true,
            sourceIds: [id],
          },
        ],
      });
  }
  return analysis;
}
