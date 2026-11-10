import { useDemoStore } from "../../app/store";
import type { ActionPlan, Incident, SupportDraft } from "../../types";
export interface DemoService {
  run<T>(work: () => T, delay?: number): Promise<T>;
  saveCase(item: Incident): Promise<void>;
  savePlan(item: ActionPlan): Promise<void>;
  saveDraft(item: SupportDraft): Promise<void>;
}
const run = async <T>(work: () => T, delay = 360): Promise<T> => {
  await new Promise((resolve) => setTimeout(resolve, delay));
  const store = useDemoStore.getState();
  if (store.failNextSave) {
    store.setFailNextSave(false);
    throw new Error(
      "Lỗi lưu mô phỏng. Dữ liệu nhập vẫn được giữ. Hãy thử lại.",
    );
  }
  return work();
};
export const demoService: DemoService = {
  run,
  saveCase: (item) => run(() => useDemoStore.getState().putCase(item)),
  savePlan: (item) => run(() => useDemoStore.getState().putPlan(item)),
  saveDraft: (item) => run(() => useDemoStore.getState().putDraft(item)),
};
