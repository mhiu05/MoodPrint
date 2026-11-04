import { useState } from "react";
import type { components } from "../../../api/generated/schema";
import { Button, cx } from "../../../components/UI";
import { ErrorNotice } from "../../../components/ErrorNotice";
import { useResource, useSession } from "../RealApp";
import { noticeText, toggleLabel } from "./journalAiSettingsModel";

type View = components["schemas"]["JournalAiSettingsView"];

export function JournalAiSettings() {
  const { session } = useSession();
  return session.accountKind === "guest" ? null : <RegisteredJournalAiSettings />;
}

function RegisteredJournalAiSettings() {
  const { api } = useSession();
  const resource = useResource<View>("/journal/ai-settings");
  const [updated, setUpdated] = useState<View>();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>();
  const [notice, setNotice] = useState("");
  const view = updated ?? resource.data;
  async function change(kind: "embedding" | "memory", enabled: boolean) {
    if (!view || busy) return;
    setBusy(true);
    setError(undefined);
    setNotice("");
    setUpdated({ ...view,
      embeddingEnabled: kind === "embedding" ? enabled : view.embeddingEnabled,
      autoMemoryEnabled: kind === "memory" ? enabled : view.autoMemoryEnabled,
    });
    try {
      setUpdated(await api.request<View>("/journal/ai-settings", {
        method: "PUT",
        body: {
          embeddingEnabled: kind === "embedding" ? enabled : view.embeddingEnabled,
          autoMemoryEnabled: kind === "memory" ? enabled : view.autoMemoryEnabled,
          noticeVersion: "journal-ai-v1", expectedVersion: view.version,
        },
      }));
      setNotice("Đã lưu tùy chọn nhật ký.");
    } catch (reason) {
      setUpdated(view);
      setError(reason);
    } finally {
      setBusy(false);
    }
  }
  return <section className="real-section" aria-labelledby="journal-ai-heading" aria-busy={busy}>
    <h2 id="journal-ai-heading">Nhật ký và trợ lý AI</h2>
    <p>{noticeText()}</p>
    {resource.loading ? <p role="status">Đang tải tùy chọn nhật ký…</p> : null}
    <ErrorNotice error={error ?? resource.error} retry={() => { setError(undefined); setUpdated(undefined); resource.refresh(); }} />
    {view ? <>
      <label className="real-check"><input type="checkbox" checked={view.embeddingEnabled} disabled={busy}
        onChange={(event) => void change("embedding", event.target.checked)} /><span>{toggleLabel("embedding")}</span></label>
      {!view.embeddingAvailable ? <p>Tính năng này chưa sẵn sàng trên máy chủ. Trợ lý vẫn tìm theo từ khóa.</p> : null}
      {view.autoMemoryAvailable ? <>
        <label className="real-check"><input type="checkbox" checked={view.autoMemoryEnabled} disabled={busy}
          onChange={(event) => void change("memory", event.target.checked)} /><span>{toggleLabel("memory")}</span></label>
        <p>Ghi nhớ tự động có nhãn riêng trong mục Ghi nhớ; bạn sửa hoặc xóa được.</p>
      </> : null}
      <p className={cx.footnote}>Đã lập chỉ mục {view.indexedEntries} trang · đang chờ {view.pendingEntries}</p>
    </> : null}
    <p role="status">{busy ? "Đang lưu…" : notice}</p>
    {!view && !resource.loading && resource.error ? <Button variant="secondary" onClick={resource.refresh}>Tải lại tùy chọn nhật ký</Button> : null}
  </section>;
}
