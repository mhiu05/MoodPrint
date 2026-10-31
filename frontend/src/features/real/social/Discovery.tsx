import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type KeyboardEvent,
} from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Button, cx, Dialog, StatePanel } from "../../../components/UI";
import type { components } from "../../../api/generated/schema";
import { ErrorNotice, useResource, useSession } from "../RealApp";
import type { SessionView } from "../../../api/contracts";
import { CandidateCard } from "./CandidateCard";
import { ProfileEditor } from "./ProfileEditor";
import { RequestCard } from "./RequestCard";
import { OwnIdentity } from "../Safety";
import type { LeaveRequest } from "./useProfileNavigationGuard";
import { ApiError, errorMessage } from "../../../api/client";

type Schema = components["schemas"];
type Draft = Schema["DraftView"];
type Published = Schema["PublishedView"];
type Taxonomy = Schema["TaxonomyDTO"];
type RequestView = Schema["RequestView"];

const TABS = ["suggestions", "requests", "profile", "identity"] as const;
const IDENTITY_TAB = ["identity"] as const;
type Tab = (typeof TABS)[number];
const isTab = (value: string | null): value is Tab =>
  TABS.includes(value as Tab);

/** Matching and identity tabs, kept in `?tab=`. */
export function Discovery() {
  const { api, session, receive } = useSession();
  const restricted = session.notices?.some(
    (notice) => notice.kind === "restricted",
  );
  const matchingAvailable =
    session.features.matching && session.ageBand === "adult" && !restricted;
  const [params, setParams] = useSearchParams();
  const draft = useResource<Draft>(
    "/profiles/matching-draft",
    matchingAvailable,
  );
  const taxonomy = useResource<Taxonomy>("/taxonomy", matchingAvailable);
  const published = useResource<Published | null>(
    "/profiles/published/current",
    matchingAvailable,
  );
  const canMatch =
    matchingAvailable &&
    session.consents.MATCH.enabled &&
    published.data?.state === "live";
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
  const [editing, setEditing] = useState(false),
    [busy, setBusy] = useState(false);
  const [closedNewEditor, setClosedNewEditor] = useState(false);
  const editorLeave = useRef<LeaveRequest | null>(null);
  const registerLeave = useCallback((guard: LeaveRequest | null) => {
    editorLeave.current = guard;
  }, []);
  const [error, setError] = useState<unknown>(),
    [notice, setNotice] = useState("");
  const [blocking, setBlocking] = useState<string>();
  const [sent, setSent] = useState<string[]>([]);
  const [candidateErrors, setCandidateErrors] = useState<
    Record<string, { message: string; expired: boolean }>
  >({});
  const acting = useRef(false);
  const mounted = useRef(false);
  const focusNext = useRef<number | null>(null);
  const suggestionsHeading = useRef<HTMLHeadingElement>(null);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);
  useEffect(() => {
    if (focusNext.current === null) return;
    const index = focusNext.current;
    focusNext.current = null;
    requestAnimationFrame(() => {
      const headings = document.querySelectorAll<HTMLElement>(
        ".peer-grid [data-peer-heading]",
      );
      (
        headings[Math.min(index, headings.length - 1)] ??
        suggestionsHeading.current
      )?.focus();
    });
  }, [suggestions.data]);
  const tabRefs = useRef<Partial<Record<Tab, HTMLButtonElement | null>>>({});
  const live = published.data?.state === "live";
  useEffect(() => {
    // Own the auto-opened editor independently of draft.version: its first save
    // must not unmount it between PUT and the authoritative preview response.
    if (
      matchingAvailable &&
      draft.data?.version === 0 &&
      published.data === null &&
      !closedNewEditor
    )
      setEditing(true);
  }, [matchingAvailable, draft.data?.version, published.data, closedNewEditor]);
  const named = params.get("tab");
  // Without a named tab, a live profile opens on suggestions; otherwise on the editor.
  const tab: Tab = !matchingAvailable
    ? "identity"
    : isTab(named)
      ? named
      : live
        ? "suggestions"
        : "profile";
  const visibleTabs: readonly Tab[] = matchingAvailable ? TABS : IDENTITY_TAB;
  useEffect(() => {
    if (!matchingAvailable && params.get("tab") !== "identity")
      setParams({ tab: "identity" }, { replace: true });
  }, [matchingAvailable, params, setParams]);
  const pending =
    requests.data?.filter(
      (item) => item.direction === "incoming" && item.status === "pending",
    ).length ?? 0;
  const titles: Record<Tab, string> = {
    suggestions: "Gợi ý",
    requests: pending ? `Lời mời (${pending})` : "Lời mời",
    profile: "Hồ sơ tìm bạn",
    identity: "Thông tin riêng",
  };
  function select(next: Tab, focus = false) {
    if (!visibleTabs.includes(next)) return;
    const leave = () => {
      if (next !== tab) {
        setEditing(false);
        setClosedNewEditor(true);
      }
      // Replace, so Back leaves Discovery instead of stepping through tabs.
      setParams({ tab: next }, { replace: true });
      if (focus) tabRefs.current[next]?.focus();
    };
    if (tab === "profile" && next !== "profile" && editorLeave.current)
      editorLeave.current(leave);
    else leave();
  }
  // Move from the tab that has focus, not from state that may not have re-rendered yet.
  function onTabKey(event: KeyboardEvent<HTMLButtonElement>, from: Tab) {
    const index = visibleTabs.indexOf(from);
    const target = {
      ArrowRight: visibleTabs[(index + 1) % visibleTabs.length],
      ArrowLeft:
        visibleTabs[(index + visibleTabs.length - 1) % visibleTabs.length],
      Home: visibleTabs[0],
      End: visibleTabs[visibleTabs.length - 1],
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
  async function candidateAct(ref: string, kind: "invite" | "skip" | "block") {
    if (acting.current || busy || suggestions.loading || !canMatch) return;
    acting.current = true;
    setBusy(true);
    setNotice("");
    const epoch = api.epoch;
    const current = () => mounted.current && api.epoch === epoch;
    setCandidateErrors((previous) => {
      const next = { ...previous };
      delete next[ref];
      return next;
    });
    try {
      await api.request(
        kind === "invite"
          ? "/connection-requests"
          : kind === "skip"
            ? "/matching/skips"
            : "/blocks",
        {
          method: "POST",
          body: kind === "block" ? { peerRef: ref } : { candidateRef: ref },
        },
      );
      if (!current()) return;
      if (kind === "invite") {
        // Retain this reviewed card and its block action; don't immediately erase
        // the sent status by fetching a list that excludes pending invitations.
        setSent((previous) => [...previous, ref]);
        requests.refresh();
        setNotice("Đã gửi lời mời kết nối.");
      } else {
        focusNext.current =
          suggestions.data?.candidates.findIndex(
            (card) => card.candidateRef === ref,
          ) ?? 0;
        suggestions.setData(
          (previous) =>
            previous && {
              ...previous,
              candidates: previous.candidates.filter(
                (card) => card.candidateRef !== ref,
              ),
            },
        );
        setNotice(kind === "block" ? "Đã chặn kết nối." : "Đã bỏ qua gợi ý.");
        if (kind === "block") setBlocking(undefined);
        requests.refresh();
      }
    } catch (reason) {
      if (!current()) return;
      const expired =
        reason instanceof ApiError &&
        ["CANDIDATE_EXPIRED", "CANDIDATE_CHANGED"].includes(reason.code);
      setCandidateErrors((previous) => ({
        ...previous,
        [ref]: { message: errorMessage(reason), expired },
      }));
      if (reason instanceof ApiError && reason.status === 403)
        void api
          .request<SessionView>("/session")
          .then((value) => {
            if (current()) receive(value);
          })
          .catch(() => {});
    } finally {
      if (current()) {
        acting.current = false;
        setBusy(false);
      }
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
  return (
    <div className={`${cx.reading} discovery-page`}>
      <h1 tabIndex={-1} data-tour="matching-intro">
        Tìm một người bạn hợp gu 🌷
      </h1>
      <p className={cx.lede}>
        Bắt đầu từ những điểm chung bạn chủ động chia sẻ.
      </p>
      {!matchingAvailable ? (
        <StatePanel
          title={
            restricted
              ? "Tìm bạn đang tạm bị hạn chế"
              : !session.features.matching
                ? "Tìm bạn chưa khả dụng"
                : "Bạn cần đủ 18 tuổi để kết nối"
          }
        >
          {restricted
            ? "Bạn có thể quay lại sau thời gian hạn chế được thông báo ở trên."
            : !session.features.matching
              ? "Dịch vụ tìm bạn chưa sẵn sàng."
              : "Tìm bạn và nhắn tin người thật dành cho người đã đủ 18 tuổi."}
        </StatePanel>
      ) : null}
      <ErrorNotice
        error={
          error ||
          (matchingAvailable
            ? draft.error || taxonomy.error || published.error
            : undefined)
        }
        retry={() => {
          draft.refresh();
          taxonomy.refresh();
          refresh();
        }}
      />
      {notice && <p role="status">{notice}</p>}
      <div className="discovery-tabs" role="tablist" aria-label="Tìm bạn">
        {visibleTabs.map((key) => (
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
        {tab === "identity" && <OwnIdentity />}
        {tab === "profile" && (
          <>
            <p>
              Hồ sơ chỉ hiện với người khác sau khi bạn xem trước và chọn Hiển
              thị hồ sơ. Trò chuyện AI, nhật ký cảm xúc và ghi nhớ không dùng để
              gợi ý bạn bè.
            </p>
            {!session.consents.MATCH.enabled ? (
              <p className={cx.note}>
                Quyền tìm bạn đang tắt. Khi bạn xem lại hồ sơ và chọn Hiển thị
                hồ sơ, quyền này được bật lại và thẻ của bạn hiện với người phù
                hợp.
              </p>
            ) : null}
            {(draft.loading || taxonomy.loading || published.loading) &&
              !draft.data && (
                <div className="friendship-loading" aria-busy="true">
                  <p role="status">Đang tải hồ sơ…</p>
                  <div className="friendship-skeleton" />
                </div>
              )}
            {!editing &&
              !(
                draft.data?.version === 0 &&
                published.data === null &&
                !closedNewEditor
              ) && (
                <Button
                  variant="secondary"
                  disabled={
                    !draft.data ||
                    !taxonomy.data ||
                    published.data === undefined ||
                    Boolean(draft.error || taxonomy.error || published.error)
                  }
                  onClick={() => setEditing(true)}
                >
                  Chỉnh hồ sơ tìm bạn
                </Button>
              )}
            {(editing ||
              (draft.data?.version === 0 &&
                published.data === null &&
                !closedNewEditor)) &&
              taxonomy.data &&
              draft.data &&
              published.data !== undefined &&
              (editing ||
                !(draft.error || taxonomy.error || published.error)) && (
                <ProfileEditor
                  key={session.userId}
                  taxonomy={taxonomy.data}
                  draft={draft.data}
                  published={published.data}
                  registerLeave={registerLeave}
                  onDraft={(saved) => draft.setData(saved)}
                  onPublished={(result) => {
                    published.setData(result);
                    void api
                      .request<SessionView>("/session")
                      .then(receive)
                      .catch(setError);
                    draft.setData(
                      (previous) =>
                        previous && {
                          ...previous,
                          publishedVersion: result.profileVersion,
                        },
                    );
                    setEditing(false);
                    setNotice(
                      live
                        ? "Đã cập nhật hồ sơ hiển thị."
                        : "Đã hiển thị hồ sơ tìm bạn.",
                    );
                    suggestions.refresh();
                    requests.refresh();
                    setParams({ tab: "suggestions" }, { replace: true });
                  }}
                  onClose={() => {
                    setEditing(false);
                    setClosedNewEditor(true);
                  }}
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
                        body: {
                          expectedVersion: published.data!.profileVersion,
                        },
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
        {tab === "suggestions" && (
          <section className="real-section">
            <h2 ref={suggestionsHeading} tabIndex={-1}>
              Gợi ý từ những điểm chung
            </h2>
            <Button
              variant="text"
              disabled={suggestions.loading}
              onClick={suggestions.refresh}
            >
              Tải lại gợi ý
            </Button>
            {suggestions.loading && (
              <p role="status">Đang tải gợi ý kết nối…</p>
            )}
            {suggestions.loading && !suggestions.data && canMatch && (
              <div className="peer-grid" aria-hidden="true">
                <div className="friendship-skeleton" />
                <div className="friendship-skeleton" />
              </div>
            )}
            {busy && <p role="status">Đang cập nhật kết nối…</p>}
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
                <p>Chưa có gợi ý phù hợp lúc này.</p>
                <p className={cx.footnote}>
                  Bạn có thể quay lại sau hoặc cập nhật những điều muốn chia sẻ.
                </p>
                <Button
                  variant="secondary"
                  onClick={() => select("profile", true)}
                >
                  Chỉnh hồ sơ
                </Button>
              </>
            )}
            <div className="peer-grid" aria-busy={suggestions.loading}>
              {canMatch &&
                suggestions.data?.candidates.map((candidate) => (
                  <CandidateCard
                    key={candidate.candidateRef}
                    card={candidate}
                    label={label}
                    taxonomy={taxonomy.data}
                    busy={
                      busy || suggestions.loading || Boolean(suggestions.error)
                    }
                    sent={sent.includes(candidate.candidateRef)}
                    error={candidateErrors[candidate.candidateRef]?.message}
                    onReload={
                      candidateErrors[candidate.candidateRef]?.expired
                        ? () => {
                            setCandidateErrors({});
                            suggestions.refresh();
                          }
                        : undefined
                    }
                    onGreet={() =>
                      void candidateAct(candidate.candidateRef, "invite")
                    }
                    onSkip={() =>
                      void candidateAct(candidate.candidateRef, "skip")
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
        {tab === "requests" && (
          <section className="real-section">
            <h2>Lời mời kết nối</h2>
            <ErrorNotice error={requests.error} retry={requests.refresh} />
            {requests.loading && !requests.data && (
              <p role="status">Đang tải lời mời…</p>
            )}
            {requests.data?.length === 0 && (
              <>
                <p>Bạn chưa có lời mời nào.</p>
                <Button
                  variant="secondary"
                  onClick={() => select("suggestions", true)}
                >
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
          {candidateErrors[blocking] && (
            <p role="alert">{candidateErrors[blocking].message}</p>
          )}
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
              onClick={() => void candidateAct(blocking, "block")}
            >
              Chặn người này
            </Button>
          </div>
        </Dialog>
      )}
    </div>
  );
}
