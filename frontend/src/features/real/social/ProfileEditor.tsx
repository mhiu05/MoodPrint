import { useCallback, useEffect, useReducer, useRef, useState } from "react";
import { Button, cx, Dialog, StatePanel } from "../../../components/UI";
import type { components } from "../../../api/generated/schema";
import { ApiError } from "../../../api/client";
import { ErrorNotice, useSession } from "../RealApp";
import { FriendshipQuestions } from "./FriendshipQuestions";
import { InterestPickerDialog } from "./InterestPickerDialog";
import { ProfilePublishReview } from "./ProfilePublishReview";
import { PublicProfileCard, ProfilePreviewAside } from "./PublicProfileCard";
import {
  buildPublicProfileView,
  canonicalReady,
  hydrateEditor,
  incompatibleProfile,
  isDirty,
  reduceEditor,
  samePublicProfile,
  toDraftProfile,
  validateReview,
  type ReviewIssue,
} from "./discoveryProfile";
import {
  useProfileNavigationGuard,
  type LeaveRequest,
} from "./useProfileNavigationGuard";
import type { Profile, Taxonomy } from "./profileRules";
import "./social.css";

type Schema = components["schemas"];
type Draft = Schema["DraftView"];
type Published = Schema["PublishedView"];
type UncertainWrite = {
  kind: "draft" | "publication";
  profile: Profile;
  version: number;
  revision: number;
};
export function ProfileEditor({
  taxonomy,
  draft,
  published,
  onDraft,
  onPublished,
  onClose,
  registerLeave,
}: {
  taxonomy: Taxonomy;
  draft: Draft;
  published?: Published | null;
  onDraft: (draft: Draft) => void;
  onPublished: (published: Published) => void;
  onClose: () => void;
  registerLeave?: (guard: LeaveRequest | null) => void;
}) {
  const { api, session, receive } = useSession();
  const [state, dispatch] = useReducer(reduceEditor, undefined, () =>
    hydrateEditor(draft, published),
  );
  const [error, setError] = useState<unknown>();
  const [notice, setNotice] = useState("");
  const [issues, setIssues] = useState<ReviewIssue[]>([]);
  const [picker, setPicker] = useState<
    "all" | "creative" | "active" | "manage" | null
  >(null);
  const [mobilePreview, setMobilePreview] = useState(false);
  const [conflict, setConflict] = useState(false);
  const [latest, setLatest] = useState<Draft>();
  const [overwrite, setOverwrite] = useState(false);
  const [accessDenied, setAccessDenied] = useState(false);
  const [uncertain, setUncertain] = useState<UncertainWrite | null>(null);
  const writeAttempt = useRef<UncertainWrite | null>(null);
  const mounted = useRef(false);
  const operation = useRef(0);
  const running = useRef(false);
  const errorsRef = useRef<HTMLDivElement>(null);
  const reviewRef = useRef<HTMLDivElement>(null);
  const dialogTrigger = useRef<HTMLElement | null>(null);
  const busy = state.operation !== "idle";
  const profile = toDraftProfile(state);
  const guard = useProfileNavigationGuard(
    !accessDenied && isDirty(state),
    !accessDenied && busy,
  );
  const label = (id: string) =>
    ({
      ...taxonomy.interests,
      ...taxonomy.values,
      ...taxonomy.goals,
      ...taxonomy.styles,
      ...taxonomy.languages,
      ...taxonomy.activities,
      ...taxonomy.availability,
    })[id] ?? id;
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      operation.current++;
    };
  }, []);
  useEffect(() => {
    registerLeave?.(guard.requestLeave);
    return () => registerLeave?.(null);
  }, [registerLeave, guard.requestLeave]);
  const question = useCallback((next: 0 | 1 | 2) => {
    dispatch({ type: "SET_QUESTION", question: next });
    requestAnimationFrame(() =>
      document.getElementById(`friendship-q${next}`)?.focus(),
    );
  }, []);
  useEffect(() => {
    if (issues.length) errorsRef.current?.focus();
  }, [issues]);
  useEffect(() => {
    if (state.stage !== "builder") reviewRef.current?.focus();
  }, [state.stage]);
  useEffect(() => {
    setNotice("");
  }, [state.editRevision]);
  function closePreview() {
    setPicker(null);
    setMobilePreview(false);
    requestAnimationFrame(() => {
      if (dialogTrigger.current?.isConnected) dialogTrigger.current.focus();
    });
  }

  async function run(
    kind: "saving" | "previewing" | "publishing",
    action: (current: () => boolean) => Promise<void>,
  ) {
    if (running.current) return;
    running.current = true;
    writeAttempt.current = null;
    const id = ++operation.current,
      epoch = api.epoch;
    const current = () =>
      mounted.current && operation.current === id && api.epoch === epoch;
    dispatch({ type: "OPERATION", operation: kind });
    setError(undefined);
    setNotice("");
    try {
      await action(current);
    } catch (reason) {
      if (!current()) return;
      if (
        writeAttempt.current &&
        (!(reason instanceof ApiError) ||
          reason.status === 0 ||
          reason.status >= 500)
      )
        setUncertain(writeAttempt.current);
      if (reason instanceof ApiError && reason.code === "STALE_VERSION") {
        dispatch({ type: "PREVIEW_INVALIDATED" });
        setConflict(true);
        setLatest(undefined);
        setOverwrite(false);
      } else if (
        reason instanceof ApiError &&
        reason.code === "PREVIEW_CHANGED"
      ) {
        dispatch({ type: "PREVIEW_INVALIDATED" });
        setNotice(
          "Bản xem trước đã thay đổi hoặc hết hạn. Xem lại trước khi hiển thị nhé.",
        );
      } else {
        if (kind === "previewing") dispatch({ type: "PREVIEW_INVALIDATED" });
        setError(reason);
        if (kind === "saving")
          setNotice("Chưa lưu được bản nháp. Lựa chọn của bạn vẫn còn ở đây.");
      }
      if (reason instanceof ApiError && reason.status === 403) {
        // CSRF is recoverable. Only server eligibility/restriction verdicts
        // replace the editor, and those terminal states must not trap exits.
        if (
          [
            "ADULT_REQUIRED",
            "SOCIAL_RESTRICTED",
            "MATCH_UNAVAILABLE",
            "ACCOUNT_SUSPENDED",
            "REGISTERED_REQUIRED",
          ].includes(reason.code)
        )
          setAccessDenied(true);
        void api
          .request<Schema["SessionView"]>("/session")
          .then((value) => {
            if (current()) receive(value);
          })
          .catch(() => {});
      }
    } finally {
      if (current()) {
        running.current = false;
        dispatch({ type: "OPERATION", operation: "idle" });
      }
    }
  }
  async function save(
    current: () => boolean,
    expectedVersion = state.draftVersion,
  ) {
    writeAttempt.current = {
      kind: "draft",
      profile,
      version: expectedVersion,
      revision: state.editRevision,
    };
    const saved = await api.request<Draft>("/profiles/matching-draft", {
      method: "PUT",
      body: { ...profile, expectedVersion } satisfies Schema["DraftInput"],
    });
    if (!current()) return null;
    writeAttempt.current = null;
    setUncertain(null);
    dispatch({ type: "SAVE_SUCCEEDED", draft: saved });
    onDraft(saved);
    setNotice(
      published?.state === "live"
        ? "Đã lưu bản nháp. Hồ sơ đang hiển thị chưa thay đổi."
        : "Đã lưu bản nháp. Hồ sơ chưa được công khai.",
    );
    return saved;
  }
  async function prepare(current: () => boolean) {
    const saved = await save(current);
    if (!saved || !current()) return;
    const preview = await api.request<Schema["PreviewView"]>(
      "/profiles/matching-draft/preview",
      { method: "POST" },
    );
    if (!current()) return;
    if (preview.draftVersion !== saved.version)
      throw new ApiError(409, "PREVIEW_CHANGED", "Bản xem trước đã thay đổi.");
    dispatch({ type: "PREVIEW_SUCCEEDED", preview });
    setNotice("");
  }
  function review() {
    const nextIssues = validateReview(state);
    setIssues(nextIssues);
    if (nextIssues.length) {
      dispatch({ type: "SET_QUESTION", question: nextIssues[0].question });
      return;
    }
    dispatch({ type: "SET_STAGE", stage: "review-preparation" });
    if (canonicalReady(profile, taxonomy)) void run("previewing", prepare);
  }
  async function publish(current: () => boolean) {
    const preview = state.serverPreview;
    if (!preview || state.stage !== "review-ready") return;
    writeAttempt.current = {
      kind: "publication",
      profile: preview.profile,
      version: state.publishedVersion,
      revision: state.editRevision,
    };
    const result = await api.request<Published>("/profiles/published", {
      method: "POST",
      body: {
        draftVersion: preview.draftVersion,
        previewDigest: preview.previewDigest,
        expectedPublishedVersion: state.publishedVersion,
      } satisfies Schema["PublishInput"],
    });
    if (current()) {
      writeAttempt.current = null;
      setUncertain(null);
      onPublished(result);
    }
  }
  async function reconcile(current: () => boolean) {
    if (!uncertain) return;
    if (uncertain.kind === "draft") {
      const saved = await api.request<Draft>("/profiles/matching-draft");
      if (!current()) return;
      if (
        saved.version > uncertain.version &&
        samePublicProfile(saved.profile, uncertain.profile)
      ) {
        setUncertain(null);
        setError(undefined);
        if (state.editRevision === uncertain.revision) {
          dispatch({ type: "SAVE_SUCCEEDED", draft: saved });
          onDraft(saved);
          setNotice(
            published?.state === "live"
              ? "Đã lưu bản nháp. Hồ sơ đang hiển thị chưa thay đổi."
              : "Đã lưu bản nháp. Hồ sơ chưa được công khai.",
          );
        } else {
          setLatest(saved);
          setConflict(true);
        }
      } else if (saved.version > uncertain.version) {
        setLatest(saved);
        setConflict(true);
      } else
        setNotice(
          "Chưa xác nhận được lần lưu trước. Bạn có thể thử lưu lại cùng lựa chọn.",
        );
    } else {
      const result = await api.request<Published | null>(
        "/profiles/published/current",
      );
      if (!current()) return;
      if (
        result?.state === "live" &&
        result.profileVersion > uncertain.version &&
        samePublicProfile(result.profile, uncertain.profile)
      ) {
        if (state.editRevision === uncertain.revision) {
          setUncertain(null);
          onPublished(result);
        } else
          setNotice(
            "Hồ sơ đã được hiển thị. Những chỉnh sửa sau đó vẫn chưa được chia sẻ; hãy lưu lại trước khi rời đi.",
          );
      } else
        setNotice(
          "Chưa xác nhận được hồ sơ đã hiển thị. Hãy kiểm tra lại trước khi thử hiển thị lần nữa.",
        );
    }
  }
  const displayProfile =
    state.stage === "review-ready" && state.serverPreview
      ? state.serverPreview.profile
      : profile;
  const card = (
    <PublicProfileCard
      view={buildPublicProfileView(
        displayProfile,
        label,
        state.stage !== "review-ready",
      )}
      mode={state.stage === "review-ready" ? "owner-reviewed" : "owner-local"}
      label={label}
      publicationState={published?.state}
    />
  );
  if (accessDenied)
    return (
      <StatePanel title="Tìm bạn không còn khả dụng">
        Vui lòng kiểm tra quyền kết nối và trạng thái tài khoản trước khi tiếp
        tục.
      </StatePanel>
    );
  if (incompatibleProfile(profile, taxonomy))
    return (
      <StatePanel
        title="Hồ sơ dùng lựa chọn chưa được hỗ trợ"
        action={
          <Button variant="secondary" onClick={onClose}>
            Đóng
          </Button>
        }
      >
        Tải lại trang để lấy danh mục mới nhất. Dữ liệu đã lưu được giữ nguyên.
      </StatePanel>
    );

  return (
    <section
      className="profile-editor"
      aria-label="Hồ sơ tìm bạn"
      aria-busy={busy}
    >
      <div className="friendship-compact-toolbar">
        <span className="mobile-question-number">
          Câu {state.mobileQuestion + 1}/3
        </span>
        <Button
          variant="secondary"
          aria-haspopup="dialog"
          disabled={busy}
          onClick={(event) => {
            dialogTrigger.current = event.currentTarget;
            setPicker(null);
            setMobilePreview(true);
          }}
        >
          Xem hồ sơ
        </Button>
      </div>
      <div
        className="friendship-layout"
        data-stage={state.stage}
        data-question={state.mobileQuestion}
      >
        <div className="friendship-form">
          {issues.length > 0 && (
            <div
              ref={errorsRef}
              className="friendship-errors"
              tabIndex={-1}
              role="group"
              aria-label="Cần bổ sung thông tin"
            >
              <p>Hãy kiểm tra các mục sau:</p>
              <ul>
                {issues.map((issue) => (
                  <li key={issue.question}>
                    <a
                      href={`#friendship-q${issue.question}`}
                      onClick={(event) => {
                        event.preventDefault();
                        question(issue.question);
                      }}
                    >
                      {issue.text}
                    </a>
                  </li>
                ))}
              </ul>
            </div>
          )}
          {state.stage === "builder" ? (
            <FriendshipQuestions
              state={state}
              dispatch={dispatch}
              taxonomy={taxonomy}
              openPicker={(mode) => {
                dialogTrigger.current = document.activeElement as HTMLElement;
                setPicker(mode);
              }}
            />
          ) : (
            <div ref={reviewRef} tabIndex={-1}>
              <ProfilePublishReview
                state={state}
                dispatch={dispatch}
                taxonomy={taxonomy}
              />
            </div>
          )}
          {state.stage !== "builder" && (
            <div className="friendship-mobile-review-card">{card}</div>
          )}
          <ErrorNotice error={error} />
          {uncertain && (
            <Button
              variant="secondary"
              disabled={busy}
              onClick={() => void run("saving", reconcile)}
            >
              {uncertain.kind === "draft"
                ? "Kiểm tra bản nháp đã lưu"
                : "Kiểm tra hồ sơ đang hiển thị"}
            </Button>
          )}
          <p className="editor-status" role="status" aria-atomic="true">
            {busy
              ? state.operation === "previewing"
                ? "Đang chuẩn bị bản xem trước…"
                : state.operation === "publishing"
                  ? "Đang hiển thị hồ sơ…"
                  : "Đang lưu bản nháp…"
              : notice ||
                (picker
                  ? ""
                  : state.notice ||
                    `${state.featuredInterests.length}/3 sở thích nổi bật`)}
          </p>
          <div className="friendship-actions">
            {state.stage === "builder" ? (
              <>
                <Button
                  className="builder-review-action"
                  disabled={busy}
                  onClick={review}
                >
                  Xem lại trước khi hiển thị
                </Button>
                <Button
                  className="mobile-question-next"
                  disabled={busy}
                  onClick={() => question((state.mobileQuestion + 1) as 1 | 2)}
                >
                  Tiếp tục
                </Button>
                {state.mobileQuestion > 0 && (
                  <Button
                    className="mobile-question-back"
                    variant="secondary"
                    disabled={busy}
                    onClick={() =>
                      question((state.mobileQuestion - 1) as 0 | 1)
                    }
                  >
                    Quay lại
                  </Button>
                )}
              </>
            ) : (
              <>
                {state.serverPreview && state.stage === "review-ready" ? (
                  <div className="publication-confirmation">
                    <p>
                      Bạn đồng ý tham gia gợi ý kết nối khi chọn Hiển thị hồ sơ.
                      Bạn có thể ngừng hiển thị bất cứ lúc nào.
                    </p>
                    {!session.consents.MATCH.enabled && (
                      <p>
                        Quyền tìm bạn đang tắt. Chọn Hiển thị hồ sơ sẽ bật quyền
                        tham gia gợi ý kết nối.
                      </p>
                    )}
                    <Button
                      disabled={busy}
                      onClick={() => void run("publishing", publish)}
                    >
                      {published?.state === "live"
                        ? "Cập nhật hồ sơ hiển thị"
                        : "Hiển thị hồ sơ"}
                    </Button>
                  </div>
                ) : (
                  <Button
                    disabled={busy}
                    onClick={() => {
                      if (!canonicalReady(profile, taxonomy)) {
                        setNotice(
                          "Chọn đủ 2–4 giá trị và ít nhất 1 ngôn ngữ trước khi xem bản được chia sẻ.",
                        );
                        reviewRef.current?.focus();
                      } else void run("previewing", prepare);
                    }}
                  >
                    {notice.includes("hết hạn")
                      ? "Tạo lại bản xem trước"
                      : "Xem bản được chia sẻ"}
                  </Button>
                )}
                <Button
                  variant="secondary"
                  disabled={busy}
                  onClick={() => {
                    dispatch({ type: "SET_STAGE", stage: "builder" });
                    setNotice("");
                  }}
                >
                  Chỉnh lại
                </Button>
              </>
            )}
            <Button
              variant="secondary"
              disabled={busy}
              onClick={() =>
                void run("saving", async (current) => {
                  await save(current);
                })
              }
            >
              Lưu bản nháp
            </Button>
            <Button
              variant="text"
              disabled={busy}
              onClick={() => guard.requestLeave(onClose)}
            >
              Đóng
            </Button>
          </div>
        </div>
        <ProfilePreviewAside>
          <h2>Xem trước hồ sơ</h2>
          {card}
        </ProfilePreviewAside>
      </div>
      {picker && !guard.pending && (
        <InterestPickerDialog
          state={state}
          dispatch={dispatch}
          taxonomy={taxonomy}
          mode={picker}
          onClose={closePreview}
        />
      )}
      {mobilePreview && !guard.pending && (
        <Dialog title="Xem trước hồ sơ" onClose={closePreview}>
          {card}
          <Button onClick={closePreview}>Tiếp tục chỉnh</Button>
        </Dialog>
      )}
      {guard.pending && (
        <Dialog
          title="Bạn muốn lưu thay đổi trước khi rời đi?"
          destructive
          onClose={() => !busy && guard.cancel()}
        >
          <p>
            Bản nháp đã lưu và hồ sơ đang hiển thị không thay đổi khi bạn bỏ
            những chỉnh sửa chưa lưu.
          </p>
          <ErrorNotice error={error} />
          {notice && <p role="status">{notice}</p>}
          <div className={cx.actions}>
            <Button
              variant="secondary"
              data-cancel
              disabled={busy}
              onClick={guard.cancel}
            >
              Tiếp tục chỉnh
            </Button>
            <Button
              disabled={busy}
              onClick={() =>
                void run("saving", async (current) => {
                  const saved = await save(current);
                  if (saved && current()) guard.proceed();
                })
              }
            >
              Lưu bản nháp và rời đi
            </Button>
            <Button variant="text" disabled={busy} onClick={guard.proceed}>
              Bỏ thay đổi
            </Button>
          </div>
        </Dialog>
      )}
      {conflict && !guard.pending && (
        <Dialog
          title="Bản nháp đã được cập nhật ở nơi khác."
          destructive
          onClose={() => setConflict(false)}
        >
          <p>
            Lựa chọn đang chỉnh vẫn được giữ. Xem bản mới nhất trước khi quyết
            định thay thế.
          </p>
          {latest && (
            <PublicProfileCard
              view={buildPublicProfileView(latest.profile, label)}
              mode="owner-reviewed"
              label={label}
            />
          )}
          <div className={cx.actions}>
            <Button
              variant="secondary"
              data-cancel
              disabled={busy}
              onClick={() => setConflict(false)}
            >
              Tiếp tục chỉnh bản này
            </Button>
            <Button
              disabled={busy}
              onClick={() =>
                void run("saving", async (current) => {
                  const result = await api.request<Draft>(
                    "/profiles/matching-draft",
                  );
                  if (current()) setLatest(result);
                })
              }
            >
              Xem bản mới nhất
            </Button>
            {latest && (
              <>
                <Button
                  variant="secondary"
                  disabled={busy}
                  onClick={() => {
                    dispatch({
                      type: "HYDRATE",
                      draft: latest,
                      published: published ?? null,
                    });
                    onDraft(latest);
                    setConflict(false);
                  }}
                >
                  Dùng bản mới nhất và bỏ chỉnh sửa
                </Button>
                {!overwrite ? (
                  <Button
                    variant="text"
                    disabled={busy}
                    onClick={() => setOverwrite(true)}
                  >
                    Ghi đè bằng bản đang chỉnh
                  </Button>
                ) : (
                  <>
                    <p>Thay bản nháp mới nhất bằng các lựa chọn đang chỉnh?</p>
                    <Button
                      disabled={busy}
                      onClick={() =>
                        void run("saving", async (current) => {
                          const saved = await save(current, latest.version);
                          if (saved && current()) setConflict(false);
                        })
                      }
                    >
                      Xác nhận ghi đè bản nháp
                    </Button>
                  </>
                )}
              </>
            )}
          </div>
        </Dialog>
      )}
    </section>
  );
}
