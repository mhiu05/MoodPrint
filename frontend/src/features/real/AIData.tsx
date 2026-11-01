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
import { Button } from "../../components/UI";
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
        if (!controller.signal.aborted) receive({ ...value, historyEnabled: value.historyAvailable });
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
          <h3 id={`${groupId}-${botId}`}>
            {botById(botId)?.name || botId}
            {session.features.threeAgents && group[0]?.legacy ? <span className="history-legacy">Cuộc trò chuyện cũ</span> : null}
          </h3>
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
    </section>
  );
}

