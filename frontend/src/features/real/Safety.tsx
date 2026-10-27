import { useEffect, useState } from "react";
import { Button, cx, Dialog } from "../../components/UI";
import type { components } from "../../api/generated/schema";
import { ErrorNotice, useResource, useSession } from "./RealApp";
import { answerText } from "./activities/ActivitySummary";

type Schema = components["schemas"];
const fields = { displayName: "Tên hiển thị", gender: "Giới tính" } as const;

export function OwnIdentity() {
  const { api } = useSession();
  const resource = useResource<Schema["IdentityView"][]>("/users/me/identity");
  const [values, setValues] = useState({ displayName: "", gender: "" }),
    [busy, setBusy] = useState(false),
    [error, setError] = useState<unknown>(),
    [notice, setNotice] = useState(""),
    [loaded, setLoaded] = useState(false);
  useEffect(() => {
    // Apply stored values once; inputs stay disabled until then so typing is never
    // overwritten by a late load or by the refresh that follows a save.
    if (resource.data && !loaded) {
      setLoaded(true);
      setValues({
        displayName:
          resource.data.find((item) => item.field === "displayName")?.value ||
          "",
        gender:
          resource.data.find((item) => item.field === "gender")?.value || "",
      });
    }
  }, [resource.data, loaded]);
  return (
    <section className="real-section">
      <h2>Thông tin bạn có thể chọn chia sẻ</h2>
      <p>
        Thông tin này được giữ riêng. Chỉ người bạn chọn trong một kết nối mới
        được xem sau khi bạn đồng ý. Sửa giá trị sẽ thu hồi quyền chia sẻ cũ.
      </p>
      <ErrorNotice error={error || resource.error} retry={resource.refresh} />
      {notice && <p role="status">{notice}</p>}
      {(Object.keys(fields) as (keyof typeof fields)[]).map((field) => (
        <div className="real-item" key={field}>
          <label htmlFor={`identity-${field}`}>{fields[field]}</label>
          <input
            id={`identity-${field}`}
            disabled={!loaded || busy}
            maxLength={40}
            value={values[field]}
            onChange={(event) =>
              setValues({ ...values, [field]: event.target.value })
            }
          />
          <Button
            variant="secondary"
            disabled={busy || !loaded || !values[field].trim()}
            onClick={() => {
              setBusy(true);
              setError(undefined);
              setNotice("");
              void api
                .request<Schema["IdentityView"]>("/users/me/identity", {
                  method: "PATCH",
                  body: {
                    field,
                    value: values[field],
                    expectedVersion:
                      resource.data?.find((item) => item.field === field)
                        ?.version || 0,
                  } satisfies Schema["IdentityEdit"],
                })
                .then(() => {
                  resource.refresh();
                  setNotice("Đã cập nhật thông tin riêng.");
                })
                .catch(setError)
                .finally(() => setBusy(false));
            }}
          >
            Lưu {fields[field].toLocaleLowerCase("vi-VN")}
          </Button>
        </div>
      ))}
    </section>
  );
}

export function ConnectionSafety({
  connectionId,
  messages,
  onBlocked,
  reportOnly = false,
  panel = false,
}: {
  connectionId: string;
  messages: Schema["MessageView"][];
  onBlocked: () => void;
  /** After the room closed: identity sharing is gone, but reporting stays possible. */
  reportOnly?: boolean;
  /** Rendered inside the header's safety dialog instead of a disclosure. */
  panel?: boolean;
}) {
  const { api } = useSession();
  const reveals = useResource<Schema["RevealView"][]>(
    `/connections/${connectionId}/reveal-requests`,
    !reportOnly,
  );
  const [shown, setShown] = useState<Record<string, string>>({}),
    [busy, setBusy] = useState(false),
    [error, setError] = useState<unknown>(),
    [notice, setNotice] = useState("");
  const [reason, setReason] = useState(""),
    [selected, setSelected] = useState<string[]>([]),
    [blocking, setBlocking] = useState(false);
  // Revealed activity answers from the peer (only ones this user could see) may be
  // attached as evidence too; they are copied into the report on submission.
  const finished = useResource<Schema["ActivitySessionView"][]>(
    `/connections/${connectionId}/activities?limit=10`,
    !reportOnly,
  );
  const running = useResource<Schema["ActivitySessionView"] | null>(
    `/connections/${connectionId}/activities/current`,
    !reportOnly,
  );
  const answers = [...(running.data ? [running.data] : []), ...(finished.data ?? [])]
    .flatMap((session) =>
      (session.history ?? []).map((row) => ({ session, row })),
    )
    .filter(
      ({ row }) =>
        typeof row.reveal.peer === "object" &&
        row.reveal.peer !== null &&
        !row.reveal.peer.skipped &&
        row.reveal.self &&
        !row.reveal.self.skipped,
    )
    .map(({ session, row }) => ({
      key: `${session.id}:${row.round}`,
      sessionId: session.id,
      round: row.round,
      label: `${row.item.prompt} — ${answerText(
        typeof row.reveal.peer === "object" ? row.reveal.peer : null,
        row.item.options,
      )}`,
    }));
  const [chosenAnswers, setChosenAnswers] = useState<string[]>([]);
  useEffect(() => {
    if (reportOnly) return;
    const timer = setInterval(() => {
      if (document.visibilityState === "visible") reveals.refresh();
    }, 5000);
    return () => clearInterval(timer);
  }, [reveals.refresh, reportOnly]);
  useEffect(() => {
    if (reveals.data)
      setShown((previous) =>
        Object.fromEntries(
          Object.entries(previous).filter(([id]) =>
            reveals.data?.some(
              (item) => item.id === id && item.status === "granted",
            ),
          ),
        ),
      );
  }, [reveals.data]);
  async function act(work: () => Promise<unknown>, success: string) {
    if (busy) return;
    setBusy(true);
    setError(undefined);
    setNotice("");
    try {
      await work();
      setNotice(success);
      if (!reportOnly) reveals.refresh();
    } catch (failure) {
      setError(failure);
    } finally {
      setBusy(false);
    }
  }
  const Wrapper = panel ? "div" : "details";
  return (
    <Wrapper className={panel ? "real-safety-panel" : "real-safety"} open={!panel && reportOnly ? true : undefined}>
      {panel ? null : (
        <summary>
          {reportOnly ? "Báo cáo nội dung" : "Chia sẻ và an toàn"}
        </summary>
      )}
      {reportOnly ? (
        <>
          <ErrorNotice error={error} />
          {notice && <p role="status">{notice}</p>}
        </>
      ) : (
        <>
          <h2>Chia sẻ theo lựa chọn của bạn</h2>
          <p>
            Mỗi thông tin có quyền riêng. Chia sẻ không mở quyền xem các ghi
            chép hay hội thoại khác.
          </p>
          <ErrorNotice error={error || reveals.error} retry={reveals.refresh} />
          {notice && <p role="status">{notice}</p>}
          <div className={cx.actions}>
            {(Object.keys(fields) as (keyof typeof fields)[]).map((field) => (
              <Button
                key={field}
                variant="secondary"
                disabled={busy}
                onClick={() =>
                  void act(
                    () =>
                      api.request(
                        `/connections/${connectionId}/reveal-requests`,
                        {
                          method: "POST",
                          body: {
                            field,
                            ownerSide: "peer",
                            expectedIdentityVersion: 0,
                          } satisfies Schema["RevealInput"],
                        },
                      ),
                    "Đã gửi yêu cầu chia sẻ.",
                  )
                }
              >
                Xin xem {fields[field].toLocaleLowerCase("vi-VN")}
              </Button>
            ))}
          </div>
          {reveals.data?.map((item) => (
            <article className="real-item" key={item.id}>
              <h3>
                {fields[item.field]} ·{" "}
                {item.ownerSide === "self"
                  ? "Thông tin của bạn"
                  : "Thông tin của người kia"}
              </h3>
              <p>
                {item.status === "pending"
                  ? "Đang chờ chủ thông tin quyết định"
                  : item.status === "granted"
                    ? "Đang được chia sẻ"
                    : "Yêu cầu chia sẻ đã kết thúc"}
              </p>
              {item.ownerSide === "self" &&
                item.status === "pending" &&
                item.previewDigest && (
                  <>
                    <p>
                      Bạn sắp chia sẻ: <strong>{item.previewValue}</strong>
                    </p>
                    <div className={cx.actions}>
                      <Button
                        disabled={busy}
                        onClick={() =>
                          void act(
                            () =>
                              api.request(`/reveal-requests/${item.id}/grant`, {
                                method: "POST",
                                body: {
                                  expectedVersion: item.version,
                                  previewDigest: item.previewDigest!,
                                } satisfies Schema["RevealDecision"],
                              }),
                            "Đã cập nhật quyền chia sẻ.",
                          )
                        }
                      >
                        Đồng ý chia sẻ
                      </Button>
                      <Button
                        variant="secondary"
                        disabled={busy}
                        onClick={() =>
                          void act(
                            () =>
                              api.request(
                                `/reveal-requests/${item.id}/decline`,
                                {
                                  method: "POST",
                                  body: { expectedVersion: item.version },
                                },
                              ),
                            "Đã từ chối chia sẻ.",
                          )
                        }
                      >
                        Không chia sẻ
                      </Button>
                    </div>
                  </>
                )}
              {item.ownerSide === "self" && item.status === "granted" && (
                <Button
                  variant="text"
                  disabled={busy}
                  onClick={() =>
                    void act(
                      () =>
                        api.request(`/reveal-grants/${item.id}`, {
                          method: "DELETE",
                          body: { expectedVersion: item.version },
                        }),
                      "Đã thu hồi quyền xem tiếp theo.",
                    )
                  }
                >
                  Thu hồi chia sẻ
                </Button>
              )}
              {item.ownerSide === "peer" && item.status === "granted" && (
                <>
                  <Button
                    variant="text"
                    disabled={busy}
                    onClick={() =>
                      void act(async () => {
                        const value = await api.request<Schema["IdentityView"]>(
                          `/reveal-grants/${item.id}/value`,
                        );
                        setShown((previous) => ({
                          ...previous,
                          [item.id]: value.value,
                        }));
                      }, "")
                    }
                  >
                    Xem thông tin đã được chia sẻ
                  </Button>
                  {shown[item.id] && <p>{shown[item.id]}</p>}
                </>
              )}
            </article>
          ))}
        </>
      )}
      <section className="real-section">
        <h2>Báo cáo nội dung</h2>
        <p>
          Bạn có thể chọn tối đa hai tin nhắn làm bằng chứng. Chặn kết nối là
          một lựa chọn riêng.
        </p>
        <label htmlFor="report-reason">Lý do báo cáo</label>
        <textarea
          id="report-reason"
          maxLength={120}
          value={reason}
          onChange={(event) => setReason(event.target.value)}
        />
        <fieldset className="real-choices">
          <legend>Tin nhắn bạn muốn chọn</legend>
          {messages.slice(-20).map((message) => (
            <label key={message.id}>
              <input
                type="checkbox"
                checked={selected.includes(message.id)}
                disabled={
                  !selected.includes(message.id) && selected.length >= 2
                }
                onChange={(event) =>
                  setSelected((current) =>
                    event.target.checked
                      ? [...current, message.id]
                      : current.filter((id) => id !== message.id),
                  )
                }
              />
              {message.text}
            </label>
          ))}
        </fieldset>
        {answers.length > 0 && (
          <fieldset className="real-choices">
            <legend>Câu trả lời trong hoạt động chung (tối đa hai)</legend>
            {answers.map((answer) => (
              <label key={answer.key}>
                <input
                  type="checkbox"
                  checked={chosenAnswers.includes(answer.key)}
                  disabled={
                    !chosenAnswers.includes(answer.key) && chosenAnswers.length >= 2
                  }
                  onChange={(event) =>
                    setChosenAnswers((current) =>
                      event.target.checked
                        ? [...current, answer.key]
                        : current.filter((key) => key !== answer.key),
                    )
                  }
                />
                {answer.label}
              </label>
            ))}
          </fieldset>
        )}
        <Button
          variant="secondary"
          disabled={busy || !reason.trim()}
          onClick={() =>
            void act(async () => {
              const ref = await api.request<Schema["PeerReferenceView"]>(
                `/connections/${connectionId}/peer-reference`,
                { method: "POST", body: {} },
              );
              await api.request("/reports", {
                method: "POST",
                body: {
                  peerRef: ref.peerRef,
                  reason,
                  selectedMessageIds: selected,
                  selectedActivityResponses: answers
                    .filter((answer) => chosenAnswers.includes(answer.key))
                    .map(({ sessionId, round }) => ({ sessionId, round })),
                } satisfies Schema["ReportInput"],
              });
              setReason("");
              setSelected([]);
              setChosenAnswers([]);
            }, "Đã nhận báo cáo.")
          }
        >
          Gửi báo cáo
        </Button>
      </section>
      {!reportOnly && (
        <Button
          variant="text"
          disabled={busy}
          onClick={() => setBlocking(true)}
        >
          Chặn kết nối này
        </Button>
      )}
      {blocking && (
        <Dialog
          title="Chặn kết nối này?"
          destructive
          onClose={() => !busy && setBlocking(false)}
        >
          <p>
            Hai bạn sẽ không thể xem hoặc gửi tiếp tin nhắn trong kết nối này.
            Việc chặn không thể hoàn tác trong ứng dụng.
          </p>
          <p>Chặn không tự gửi báo cáo. Bạn vẫn có thể báo cáo sau khi chặn.</p>
          <div className={cx.actions}>
            <Button
              variant="secondary"
              data-cancel
              disabled={busy}
              onClick={() => setBlocking(false)}
            >
              Giữ kết nối
            </Button>
            <Button
              variant="danger"
              disabled={busy}
              onClick={() =>
                void act(async () => {
                  await api.request(`/connections/${connectionId}/block`, {
                    method: "POST",
                    body: {},
                  });
                  setBlocking(false);
                  onBlocked();
                }, "Đã chặn kết nối.")
              }
            >
              Xác nhận chặn
            </Button>
          </div>
        </Dialog>
      )}
    </Wrapper>
  );
}
