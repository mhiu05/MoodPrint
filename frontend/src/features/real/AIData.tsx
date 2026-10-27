import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useId,
  useState,
  type ReactNode,
} from "react";
import { Link, useLocation } from "react-router-dom";
import { Button, cx } from "../../components/UI";
import { ErrorNotice, useSession } from "./RealApp";
import { botById } from "../../companions/registry";
import type { ConversationHeader, ConversationView } from "../../api/contracts";
import type { components } from "../../api/generated/schema";

export type AIDataPreferences = components["schemas"]["AiPreferenceView"];
export type SavedConversationHeader = ConversationHeader;
export type SavedConversation = ConversationView;

type DataContext = {
  preferences?: AIDataPreferences;
  loading: boolean;
  error: unknown;
  reload: () => void;
  receive: (value: AIDataPreferences) => void;
  historyRevision: number;
  refreshHistory: () => void;
};
const Context = createContext<DataContext | null>(null);
export function AIDataProvider({ children }: { children: ReactNode }) {
  const { api, session } = useSession();
  const [preferences, receive] = useState<AIDataPreferences>();
  const [loading, setLoading] = useState(true),
    [error, setError] = useState<unknown>();
  const [revision, setRevision] = useState(0),
    [historyRevision, setHistoryRevision] = useState(0);
  const reload = useCallback(() => setRevision((value) => value + 1), []);
  const refreshHistory = useCallback(
    () => setHistoryRevision((value) => value + 1),
    [],
  );
  useEffect(() => {
    const recheck = () => {
      if (document.visibilityState === "visible") reload();
    };
    window.addEventListener("focus", recheck);
    document.addEventListener("visibilitychange", recheck);
    return () => {
      window.removeEventListener("focus", recheck);
      document.removeEventListener("visibilitychange", recheck);
    };
  }, [reload]);
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError(undefined);
    void api
      .request<AIDataPreferences>("/ai/preferences", {
        signal: controller.signal,
      })
      .then((value) => {
        if (!controller.signal.aborted) receive(value);
      })
      .catch((reason) => {
        if (!controller.signal.aborted) {
          setError(reason);
          receive(undefined);
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [
    api,
    revision,
    session.consents.AI.version,
    session.consents.MEM.version,
  ]);
  return (
    <Context.Provider
      value={{
        preferences,
        loading,
        error,
        reload,
        receive,
        historyRevision,
        refreshHistory,
      }}
    >
      {children}
    </Context.Provider>
  );
}
export function useAIData() {
  const value = useContext(Context);
  if (!value) throw new Error("AI data settings are required");
  return value;
}

export function AIDataControls({ historyOnly = false }: { historyOnly?: boolean }) {
  const { api, session } = useSession();
  const { preferences, loading, error, reload, receive } = useAIData();
  const [busy, setBusy] = useState(false),
    [saveError, setSaveError] = useState<unknown>(),
    [notice, setNotice] = useState("");
  async function change(
    key: "historyEnabled" | "semanticMemoryEnabled",
    enabled: boolean,
  ) {
    if (!preferences || busy) return;
    setBusy(true);
    setSaveError(undefined);
    setNotice("");
    try {
      const next = await api.request<AIDataPreferences>("/ai/preferences", {
        method: "PUT",
        body: {
          historyEnabled: preferences.historyEnabled,
          semanticMemoryEnabled: preferences.semanticMemoryEnabled,
          [key]: enabled,
          expectedVersion: preferences.version,
          policyVersion: "ai-data-v1",
        },
      });
      receive(next);
      setNotice("Đã cập nhật lựa chọn dữ liệu AI.");
    } catch (reason) {
      setSaveError(reason);
      reload();
    } finally {
      setBusy(false);
    }
  }
  return (
    <section
      className="real-section ai-data-controls"
      aria-labelledby="ai-data-heading"
    >
      <h2 id="ai-data-heading">{historyOnly ? "Lưu lịch sử trò chuyện" : "Lịch sử và tìm ghi nhớ"}</h2>
      {!historyOnly ? <p>Hai lựa chọn lưu lịch sử và dùng Voyage độc lập, mặc định tắt.</p> : null}
      {loading ? <p role="status">Đang tải lựa chọn dữ liệu AI…</p> : null}
      <ErrorNotice error={error} retry={reload} />
      <ErrorNotice error={saveError} />
      {preferences ? (
        <>
          <label className="ai-data-choice">
            <input
              type="checkbox"
              checked={preferences.historyEnabled}
              disabled={
                busy ||
                loading ||
                (!preferences.historyAvailable && !preferences.historyEnabled)
              }
              onChange={(event) =>
                void change("historyEnabled", event.target.checked)
              }
            />
            Lưu lịch sử trò chuyện
          </label>
          <p>
            Lưu các cuộc trò chuyện mới trên máy chủ trong{" "}
            {preferences.retentionDays} ngày để bạn tiếp tục trên thiết bị khác.
            Tắt lựa chọn này sẽ dừng lưu mới; lịch sử cũ vẫn xem, xuất và xóa
            được cho đến khi hết hạn. Hội thoại tạm trước đó không được chuyển
            sang lịch sử.
          </p>
          {!preferences.historyAvailable ? (
            <p>Lưu lịch sử hiện chưa khả dụng.</p>
          ) : null}
          {!historyOnly ? <><label className="ai-data-choice">
            <input
              type="checkbox"
              checked={
                preferences.semanticMemoryEnabled
              }
              disabled={
                busy ||
                loading ||
                (!preferences.semanticMemoryEnabled &&
                  (!session.consents.AI.enabled || !session.consents.MEM.enabled)) ||
                (!preferences.semanticMemoryAvailable &&
                  !preferences.semanticMemoryEnabled)
              }
              onChange={(event) =>
                void change("semanticMemoryEnabled", event.target.checked)
              }
            />
            Tìm ghi nhớ theo ngữ nghĩa qua Voyage
          </label>
          <p>
            Khi bạn bật, Voyage xử lý bên ngoài chỉ nội dung ghi nhớ bạn đã
            duyệt và truy vấn hiện tại để tìm ghi nhớ liên quan. Nhật ký và toàn
            bộ bản chép hội thoại không được gửi tới Voyage. Chỉ dùng khi quyền
            AI và ghi nhớ đã duyệt cùng bật. Tắt lựa chọn này sẽ ngừng xử lý và
            loại bỏ dữ liệu tìm kiếm dẫn xuất.
          </p>
          {(!session.consents.AI.enabled || !session.consents.MEM.enabled) ? (
            <p>Để dùng Voyage, hãy gửi tin nhắn AI và duyệt ít nhất một ghi nhớ trước.</p>
          ) : null}
          {!preferences.semanticMemoryAvailable ? (
            <p>Tìm ghi nhớ qua Voyage hiện chưa khả dụng.</p>
          ) : null}</> : null}
        </>
      ) : null}
      {notice ? <p role="status">{notice}</p> : null}
      {!historyOnly ? <Link to="/memory">Quản lý ghi nhớ đã duyệt</Link> : null}
    </section>
  );
}

export function ConversationHistory({ onSelect }: { onSelect?: () => void }) {
  const { api, session } = useSession();
  const { historyRevision } = useAIData();
  const location = useLocation();
  const selected = new URLSearchParams(location.search).get("conversation");
  const [items, setItems] = useState<SavedConversationHeader[]>([]),
    [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>(),
    [hasMore, setHasMore] = useState(false),
    [revision, setRevision] = useState(0);
  const [olderBusy, setOlderBusy] = useState(false);
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError(undefined);
    void api
      .request<SavedConversationHeader[]>("/ai/conversations?limit=30", {
        signal: controller.signal,
      })
      .then((value) => {
        if (!controller.signal.aborted) {
          setItems(value);
          setHasMore(value.length === 30);
        }
      })
      .catch((reason) => {
        if (!controller.signal.aborted) setError(reason);
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [api, historyRevision, revision]);
  async function older() {
    if (olderBusy || !items.length) return;
    setOlderBusy(true);
    setError(undefined);
    try {
      const page = await api.request<SavedConversationHeader[]>(
        `/ai/conversations?limit=30&before=${encodeURIComponent(items[items.length - 1].conversationId)}`,
      );
      setItems((previous) => [
        ...previous,
        ...page.filter(
          (value) =>
            !previous.some(
              (item) => item.conversationId === value.conversationId,
            ),
        ),
      ]);
      setHasMore(page.length === 30);
    } catch (reason) {
      setError(reason);
    } finally {
      setOlderBusy(false);
    }
  }
  // Grouped by assistant; each group keeps most-recent-activity order.
  const groupId = useId();
  const groups: [
    SavedConversationHeader["botId"],
    SavedConversationHeader[],
  ][] = [];
  for (const item of items) {
    const group = groups.find(([botId]) => botId === item.botId);
    if (group) group[1].push(item);
    else groups.push([item.botId, [item]]);
  }
  return (
    <section className="conversation-history" aria-label="Lịch sử trò chuyện">
      <div className="history-heading">
        <h2>Lịch sử trò chuyện</h2>
        <Button
          variant="text"
          disabled={loading}
          onClick={() => setRevision((value) => value + 1)}
        >
          Làm mới
        </Button>
      </div>
      {loading ? <p role="status">Đang tải lịch sử trò chuyện…</p> : null}
      <ErrorNotice
        error={error}
        retry={() => setRevision((value) => value + 1)}
      />
      {!loading && !error && !items.length ? (
        <p>Chưa có cuộc trò chuyện nào. Chọn một trợ lý để bắt đầu.</p>
      ) : null}
      {groups.map(([botId, group]) => (
        <div className="history-group" key={botId}>
          <h3 id={`${groupId}-${botId}`}>{botById(botId)?.name || botId}</h3>
          <ul aria-labelledby={`${groupId}-${botId}`}>
            {group.map((item) => (
              <li key={item.conversationId}>
                <Link
                  to={`/assistants/${item.botId}?conversation=${encodeURIComponent(item.conversationId)}`}
                  onClick={onSelect}
                  aria-current={
                    selected === item.conversationId ? "page" : undefined
                  }
                >
                  <strong>{item.title?.trim() || "Cuộc trò chuyện mới"}</strong>
                  <span>{item.persistent ? "Đã lưu" : "Tạm thời"}</span>
                  {item.updatedAt ? (
                    <time dateTime={item.updatedAt}>
                      {new Intl.DateTimeFormat("vi-VN", {
                        timeZone: session.timezone,
                        dateStyle: "short",
                        timeStyle: "short",
                      }).format(new Date(item.updatedAt))}
                    </time>
                  ) : null}
                </Link>
              </li>
            ))}
          </ul>
        </div>
      ))}
      {hasMore ? (
        <Button
          variant="secondary"
          disabled={olderBusy || loading}
          onClick={() => void older()}
        >
          {olderBusy ? "Đang tải…" : "Tải cuộc trò chuyện cũ hơn"}
        </Button>
      ) : null}
      <p>
        <Link to="/settings" onClick={onSelect}>
          Cài đặt lưu lịch sử
        </Link>
      </p>
    </section>
  );
}

export function downloadConversation(value: unknown, id: string) {
  const url = URL.createObjectURL(
    new Blob([JSON.stringify(value, null, 2)], { type: "application/json" }),
  );
  const link = document.createElement("a");
  link.href = url;
  link.download = `moodprint-conversation-${id}.json`;
  link.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}
