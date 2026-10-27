import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Button, cx, Dialog, StatePanel } from "../../../components/UI";
import type { components } from "../../../api/generated/schema";
import { ErrorNotice, useResource, useSession } from "../RealApp";
import type { SessionView } from "../../../api/contracts";
import { CandidateCard } from "./CandidateCard";
import { ProfileEditor } from "./ProfileEditor";
import { RequestCard } from "./RequestCard";

type Schema = components["schemas"];
type Draft = Schema["DraftView"];
type Published = Schema["PublishedView"];
type Taxonomy = Schema["TaxonomyDTO"];
type RequestView = Schema["RequestView"];

const TABS = ["suggestions", "requests", "profile"] as const;
type Tab = (typeof TABS)[number];
const isTab = (value: string | null): value is Tab => TABS.includes(value as Tab);

/** Tabs per 08 section 2: Gợi ý · Lời mời (count) · Hồ sơ tìm bạn, kept in `?tab=`. */
export function Discovery() {
  const { api, session, receive } = useSession();
  const restricted = session.notices?.some((notice) => notice.kind === "restricted");
  const draft = useResource<Draft>("/profiles/matching-draft");
  const taxonomy = useResource<Taxonomy>("/taxonomy");
  const published = useResource<Published | null>(
    "/profiles/published/current",
  );
  const canMatch =
    session.features.matching && session.ageBand === "adult" &&
    session.consents.MATCH.enabled && published.data?.state === "live" && !restricted;
  const suggestions = useResource<Schema["CandidateListDTO"]>(
    "/matching/candidates",
    canMatch,
  );
  const requests = useResource<RequestView[]>("/connection-requests", canMatch);
  useEffect(() => {
    if (!canMatch) return;
    const timer = setInterval(() => {
      if (document.visibilityState === "visible") requests.refresh();
    }, 5000);
    return () => clearInterval(timer);
  }, [requests.refresh, canMatch]);
  const [params, setParams] = useSearchParams();
  const [editing, setEditing] = useState(false),
    [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(),
    [notice, setNotice] = useState("");
  const [blocking, setBlocking] = useState<string>();
  const [sent, setSent] = useState<string[]>([]);
  const tabRefs = useRef<Partial<Record<Tab, HTMLButtonElement | null>>>({});
  const live = published.data?.state === "live";
  const named = params.get("tab");
  // Without a named tab, a live profile opens on suggestions; otherwise on the editor.
  const tab: Tab = isTab(named) ? named : live ? "suggestions" : "profile";
  const pending =
    requests.data?.filter(
      (item) => item.direction === "incoming" && item.status === "pending",
    ).length ?? 0;
  const titles: Record<Tab, string> = {
    suggestions: "Gợi ý",
    requests: pending ? `Lời mời (${pending})` : "Lời mời",
    profile: "Hồ sơ tìm bạn",
  };
  function select(next: Tab, focus = false) {
    // Replace, so Back leaves Discovery instead of stepping through tabs.
    setParams({ tab: next }, { replace: true });
    if (focus) tabRefs.current[next]?.focus();
  }
  // Move from the tab that has focus, not from state that may not have re-rendered yet.
  function onTabKey(event: KeyboardEvent<HTMLButtonElement>, from: Tab) {
    const index = TABS.indexOf(from);
    const target = {
      ArrowRight: TABS[(index + 1) % TABS.length],
      ArrowLeft: TABS[(index + TABS.length - 1) % TABS.length],
      Home: TABS[0],
      End: TABS[TABS.length - 1],
    }[event.key];
    if (!target) return;
    event.preventDefault();
    select(target, true);
  }
  const refresh = () => {
    published.refresh();
    suggestions.refresh();
    requests.refresh();
  };
  async function act(action: () => Promise<unknown>, success: string) {
    if (busy) return;
    setBusy(true);
    setError(undefined);
    setNotice("");
    try {
      await action();
      setNotice(success);
      refresh();
    } catch (reason) {
      setError(reason);
    } finally {
      setBusy(false);
    }
  }
  const label = (key: string) =>
    (taxonomy.data &&
      {
        ...taxonomy.data.interests,
        ...taxonomy.data.values,
        ...taxonomy.data.styles,
        ...taxonomy.data.goals,
        ...taxonomy.data.languages,
        ...taxonomy.data.activities,
        ...taxonomy.data.availability,
      }[key]) ||
    key;
  if (restricted)
    return (
      <StatePanel title="Tìm bạn đang tạm bị hạn chế">
        Bạn có thể quay lại sau thời gian hạn chế được thông báo ở trên.
        Trong lúc này, không gian riêng của bạn vẫn ở đây.
      </StatePanel>
    );
  if (!session.features.matching)
    return (
      <StatePanel title="Tìm bạn chưa khả dụng">
        Dịch vụ tìm bạn chưa sẵn sàng. Bạn có thể tiếp tục ghi lại cảm xúc.
      </StatePanel>
    );
  if (session.ageBand !== "adult")
    return (
      <StatePanel title="Bạn cần đủ 18 tuổi để kết nối">
        Tìm bạn và nhắn tin người thật dành cho người đã đủ 18 tuổi.
      </StatePanel>
    );
  return (
    <div className={cx.reading}>
      <h1 tabIndex={-1}>Tìm bạn đồng điệu</h1>
      <p className={cx.lede}>
        Bắt đầu từ những điểm chung bạn chủ động chia sẻ.
      </p>
      <ErrorNotice
        error={error || draft.error || taxonomy.error || published.error}
        retry={() => {
          draft.refresh();
          taxonomy.refresh();
          refresh();
        }}
      />
      {notice && <p role="status">{notice}</p>}
      <div className="discovery-tabs" role="tablist" aria-label="Tìm bạn">
        {TABS.map((key) => (
          <button
            key={key}
            ref={(node) => {
              tabRefs.current[key] = node;
            }}
            type="button"
            role="tab"
            id={`discovery-tab-${key}`}
            aria-controls={tab === key ? `discovery-panel-${key}` : undefined}
            aria-selected={tab === key}
            tabIndex={tab === key ? 0 : -1}
            onClick={() => select(key)}
            onKeyDown={(event) => onTabKey(event, key)}
          >
            {titles[key]}
          </button>
        ))}
      </div>
      <div
        className="discovery-panel"
        role="tabpanel"
        id={`discovery-panel-${tab}`}
        aria-labelledby={`discovery-tab-${tab}`}
      >
        {tab === "profile" && (
          <>
            <p>Hồ sơ chỉ hiện với người khác sau khi bạn xem trước và chọn Hiển thị hồ sơ. Trò chuyện AI, nhật ký cảm xúc và ghi nhớ không dùng để gợi ý bạn bè.</p>
            {!session.consents.MATCH.enabled ? (
              <p className={cx.note}>
                Quyền tìm bạn đang tắt. Khi bạn xem lại hồ sơ và chọn Hiển thị
                hồ sơ, quyền này được bật lại và thẻ của bạn hiện với người phù
                hợp.
              </p>
            ) : null}
            {!editing && (
              <Button
                variant="secondary"
                disabled={!draft.data || !taxonomy.data}
                onClick={() => setEditing(true)}
              >
                Chỉnh hồ sơ tìm bạn
              </Button>
            )}
            {editing && taxonomy.data && draft.data && (
              <ProfileEditor
                taxonomy={taxonomy.data}
                draft={draft.data}
                published={published.data}
                onDraft={(saved) => draft.setData(saved)}
                onPublished={(result) => {
                  published.setData(result);
                  void api.request<SessionView>("/session").then(receive).catch(setError);
                  draft.setData(
                    (previous) =>
                      previous && {
                        ...previous,
                        publishedVersion: result.profileVersion,
                      },
                  );
                  setEditing(false);
                  setNotice("Đã hiển thị hồ sơ tìm bạn.");
                  suggestions.refresh();
                  requests.refresh();
                  select("suggestions");
                }}
                onClose={() => setEditing(false)}
              />
            )}
            {published.data && (
              <section className="real-section">
                <h2>{live ? "Hồ sơ đang hiển thị" : "Hồ sơ đang tạm ẩn"}</h2>
                {published.data.state === "needs_republish" && (
                  <p className={cx.note}>
                    Hồ sơ này không xuất hiện trong gợi ý (ví dụ sau khi bạn tắt
                    rồi bật lại quyền tìm bạn). Hãy xem lại và chọn Hiển thị hồ
                    sơ nếu bạn muốn chia sẻ tiếp; hệ thống không tự chia sẻ lại.
                  </p>
                )}
                {published.data.state === "stale" && (
                  <p className={cx.note}>
                    Hồ sơ tạm ẩn vì lâu chưa cập nhật. Mở “Chỉnh hồ sơ tìm bạn”,
                    xem lại và chọn Hiển thị hồ sơ để xác nhận hồ sơ vẫn đúng.
                  </p>
                )}
                <p>
                  {[
                    ...(published.data.profile.interests || []),
                    ...(published.data.profile.values || []),
                  ]
                    .map(label)
                    .join(" · ")}
                </p>
                <Button
                  variant="text"
                  disabled={busy}
                  onClick={() =>
                    void act(async () => {
                      await api.request("/profiles/published/current", {
                        method: "DELETE",
                        body: { expectedVersion: published.data!.profileVersion },
                      });
                      published.setData(null);
                      draft.refresh();
                    }, "Đã ngừng hiển thị hồ sơ.")
                  }
                >
                  Ngừng hiển thị hồ sơ
                </Button>
              </section>
            )}
          </>
        )}
        {tab === "suggestions" &&
          (
            <section className="real-section">
              <h2>Gợi ý từ những điểm chung</h2>
              <Button
                variant="text"
                disabled={suggestions.loading}
                onClick={suggestions.refresh}
              >
                Tải lại gợi ý
              </Button>
              {suggestions.loading && <p role="status">Đang tải gợi ý kết nối…</p>}
              {!suggestions.loading && !live && (
                <p>
                  Hãy hiển thị hồ sơ tìm bạn để nhận gợi ý.{" "}
                  <Button variant="text" onClick={() => select("profile", true)}>
                    Mở hồ sơ tìm bạn
                  </Button>
                </p>
              )}
              {Boolean(suggestions.error) && live && (
                <ErrorNotice
                  error={suggestions.error}
                  retry={suggestions.refresh}
                />
              )}
              {live && suggestions.data?.candidates.length === 0 && (
                <>
                  <p>Chưa có gợi ý kết nối.</p>
                  <p className={cx.footnote}>
                    Có thể hiện chưa có người cùng điểm chung, hoặc họ chưa bật
                    chia sẻ hồ sơ. Bạn có thể quay lại sau; không cần thay đổi
                    điều mình thích để nhận gợi ý.
                  </p>
                  <Button variant="secondary" onClick={() => select("profile", true)}>
                    Mở rộng hồ sơ tìm bạn
                  </Button>
                </>
              )}
              <div className="peer-grid">
                {suggestions.data?.candidates.map((candidate) => (
                  <CandidateCard
                    key={candidate.candidateRef}
                    card={candidate}
                    label={label}
                    busy={busy}
                    sent={sent.includes(candidate.candidateRef)}
                    onGreet={() =>
                      void act(async () => {
                        await api.request("/connection-requests", {
                          method: "POST",
                          body: { candidateRef: candidate.candidateRef },
                        });
                        setSent((value) => [...value, candidate.candidateRef]);
                      }, "Đã gửi lời mời kết nối.")
                    }
                    onSkip={() =>
                      void act(
                        () =>
                          api.request("/matching/skips", {
                            method: "POST",
                            body: { candidateRef: candidate.candidateRef },
                          }),
                        "Đã bỏ qua gợi ý.",
                      )
                    }
                    onBlock={() => setBlocking(candidate.candidateRef)}
                  />
                ))}
              </div>
              {Boolean(suggestions.data?.candidates.length) && (
                <p className="discovery-footnote">
                  Gợi ý dựa trên những điểm chung bạn và họ tự chọn chia sẻ —
                  không phải đánh giá mức độ hợp nhau.
                </p>
              )}
            </section>
          )}
        {tab === "requests" &&
          (
            <section className="real-section">
              <h2>Lời mời kết nối</h2>
              <ErrorNotice error={requests.error} retry={requests.refresh} />
              {requests.loading && !requests.data && (
                <p role="status">Đang tải lời mời…</p>
              )}
              {requests.data?.length === 0 && (
                <>
                  <p>Bạn chưa có lời mời nào.</p>
                  <Button variant="secondary" onClick={() => select("suggestions", true)}>
                    Xem gợi ý
                  </Button>
                </>
              )}
              {requests.data?.map((item) => (
                <RequestCard
                  key={item.id}
                  item={item}
                  label={label}
                  busy={busy}
                  onDecide={(row, decision) =>
                    void act(
                      () =>
                        api.request(
                          `/connection-requests/${row.id}/${decision}`,
                          {
                            method: "POST",
                            body: { expectedVersion: row.version },
                          },
                        ),
                      decision === "accept"
                        ? "Đã kết nối. Bạn có thể bắt đầu trò chuyện."
                        : "Đã cập nhật lời mời.",
                    )
                  }
                />
              ))}
              <Button variant="text" onClick={requests.refresh}>
                Tải lại lời mời
              </Button>
            </section>
          )}
      </div>
      {blocking && (
        <Dialog
          title="Chặn người này?"
          destructive
          onClose={() => !busy && setBlocking(undefined)}
        >
          <p>
            Hai bạn sẽ không được gợi ý cho nhau và không thể gửi lời mời hay
            tin nhắn cho nhau nữa. Việc chặn không thể hoàn tác trong ứng dụng.
          </p>
          <div className={cx.actions}>
            <Button
              variant="secondary"
              data-cancel
              disabled={busy}
              onClick={() => setBlocking(undefined)}
            >
              Không chặn
            </Button>
            <Button
              variant="danger"
              disabled={busy}
              onClick={() =>
                void act(async () => {
                  await api.request("/blocks", {
                    method: "POST",
                    body: { peerRef: blocking },
                  });
                  setBlocking(undefined);
                }, "Đã chặn kết nối.")
              }
            >
              Chặn người này
            </Button>
          </div>
        </Dialog>
      )}
    </div>
  );
}
