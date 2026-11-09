import { useCallback, useEffect, useState } from "react";
import { Button, Notice } from "../../../components/ui";
import type {
  LiveCompanion,
  MemoryCandidateView,
  MemoryView,
} from "../../../services/composition/companion-types";

/** Pending suggestions: nothing is remembered until the user says yes. */
export function MemoryCandidates({
  service,
  refreshKey,
}: {
  service: LiveCompanion;
  refreshKey: string | number;
}) {
  const [items, setItems] = useState<MemoryCandidateView[]>([]);
  const [editing, setEditing] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [error, setError] = useState(false);
  const [reload, setReload] = useState(0);
  useEffect(() => {
    let current = true;
    service.memory
      .candidates()
      .then((list) => {
        if (current) {
          setItems(list.filter((c) => c.status === "pending"));
          setError(false);
        }
      })
      .catch(() => {
        if (current) setError(true);
      });
    return () => {
      current = false;
    };
  }, [service, refreshKey, reload]);
  const load = useCallback(async () => setReload((n) => n + 1), []);
  const decide = async (
    id: string,
    decision: "approve" | "reject",
    edited?: string,
  ) => {
    try {
      await service.memory.decide(id, decision, edited);
      setEditing(null);
      await load();
    } catch {
      setError(true);
    }
  };
  if (error)
    return (
      <Notice>Chưa tải được gợi ý ghi nhớ. Bạn có thể thử lại sau.</Notice>
    );
  if (!items.length) return null;
  return (
    <section className="live-memory" aria-label="Gợi ý ghi nhớ">
      {items.map((item) => (
        <article key={item.id} className="live-memory-card">
          <h3>Ghi nhớ điều này?</h3>
          {editing === item.id ? (
            <>
              <label className="sr-only" htmlFor={`memory-${item.id}`}>
                Nội dung ghi nhớ
              </label>
              <textarea
                id={`memory-${item.id}`}
                value={draft}
                maxLength={500}
                onChange={(event) => setDraft(event.target.value)}
              />
              <div className="actions">
                <Button
                  disabled={!draft.trim()}
                  onClick={() => void decide(item.id, "approve", draft.trim())}
                >
                  Lưu bản sửa
                </Button>
                <Button variant="ghost" onClick={() => setEditing(null)}>
                  Hủy
                </Button>
              </div>
            </>
          ) : (
            <>
              <p>{item.content}</p>
              <div className="actions">
                <Button onClick={() => void decide(item.id, "approve")}>
                  Có
                </Button>
                <Button
                  variant="secondary"
                  onClick={() => {
                    setEditing(item.id);
                    setDraft(item.content);
                  }}
                >
                  Sửa
                </Button>
                <Button
                  variant="ghost"
                  onClick={() => void decide(item.id, "reject")}
                >
                  Không
                </Button>
              </div>
            </>
          )}
        </article>
      ))}
    </section>
  );
}

/** What the AI remembers about the user, with edit and delete. */
export function MemoryManager({ service }: { service: LiveCompanion }) {
  const [items, setItems] = useState<MemoryView[] | null>(null);
  const [error, setError] = useState(false);
  const [reload, setReload] = useState(0);
  useEffect(() => {
    let current = true;
    service.memory
      .list()
      .then((list) => {
        if (current) {
          setItems(list);
          setError(false);
        }
      })
      .catch(() => {
        if (current) setError(true);
      });
    return () => {
      current = false;
    };
  }, [service, reload]);
  const load = useCallback(async () => setReload((n) => n + 1), []);
  if (error) return <Notice>Chưa tải được danh sách ghi nhớ.</Notice>;
  if (!items) return <p>Đang tải…</p>;
  if (!items.length)
    return <p>AI chưa ghi nhớ điều gì. Bạn quyết định điều được nhớ.</p>;
  return (
    <ul className="live-memory-list">
      {items.map((item) => (
        <li key={item.id}>
          <span>{item.content}</span>
          <Button
            variant="ghost"
            aria-label={`Xóa ghi nhớ: ${item.content}`}
            onClick={async () => {
              await service.memory.remove(item.id);
              await load();
            }}
          >
            Xóa
          </Button>
        </li>
      ))}
    </ul>
  );
}
