import { useEffect, useState } from "react";
import { Button, cx, Dialog } from "../../components/UI";
import type { components } from "../../api/generated/schema";
import { ErrorNotice, useResource, useSession } from "./RealApp";

type Schema = components["schemas"];
const fields = { displayName: "Tên hiển thị", gender: "Giới tính" } as const;

export function OwnIdentity() {
  const { api } = useSession();
  const resource = useResource<Schema["IdentityView"][]>("/users/me/identity");
  const [values, setValues] = useState({ displayName: "", gender: "" }),
    [busy, setBusy] = useState(false),
    [error, setError] = useState<unknown>(),
    [notice, setNotice] = useState("");
  useEffect(() => {
    if (resource.data)
      setValues({
        displayName:
          resource.data.find((item) => item.field === "displayName")?.value ||
          "",
        gender:
          resource.data.find((item) => item.field === "gender")?.value || "",
      });
  }, [resource.data]);
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
            disabled={!resource.data || busy}
            maxLength={40}
            value={values[field]}
            onChange={(event) =>
              setValues({ ...values, [field]: event.target.value })
            }
          />
          <Button
            variant="secondary"
            disabled={busy || !resource.data || !values[field].trim()}
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
}: {
  connectionId: string;
  messages: Schema["MessageView"][];
  onBlocked: () => void;
}) {
  const { api } = useSession();
  const reveals = useResource<Schema["RevealView"][]>(
    `/connections/${connectionId}/reveal-requests`,
  );
  const [shown, setShown] = useState<Record<string, string>>({}),
    [busy, setBusy] = useState(false),
    [error, setError] = useState<unknown>(),
    [notice, setNotice] = useState("");
  const [reason, setReason] = useState(""),
    [selected, setSelected] = useState<string[]>([]),
    [blocking, setBlocking] = useState(false);
  useEffect(() => {
    const timer = setInterval(() => {
      if (document.visibilityState === "visible") reveals.refresh();
    }, 5000);
    return () => clearInterval(timer);
  }, [reveals.refresh]);
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
      reveals.refresh();
    } catch (failure) {
      setError(failure);
    } finally {
      setBusy(false);
    }
  }
  return (
    <details className="real-safety">
      <summary>Chia s&#7867; v&#224; an to&#224;n</summary>
      <h2>Chia sẻ theo lựa chọn của bạn</h2>
      <p>
        Mỗi thông tin có quyền riêng. Chia sẻ không mở quyền xem các ghi chép
        hay hội thoại khác.
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
                  api.request(`/connections/${connectionId}/reveal-requests`, {
                    method: "POST",
                    body: {
                      field,
                      ownerSide: "peer",
                      expectedIdentityVersion: 0,
                    } satisfies Schema["RevealInput"],
                  }),
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
                          api.request(`/reveal-requests/${item.id}/decline`, {
                            method: "POST",
                            body: { expectedVersion: item.version },
                          }),
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
                } satisfies Schema["ReportInput"],
              });
              setReason("");
              setSelected([]);
            }, "Đã nhận báo cáo.")
          }
        >
          Gửi báo cáo
        </Button>
      </section>
      <Button variant="text" disabled={busy} onClick={() => setBlocking(true)}>
        Chặn kết nối này
      </Button>
      {blocking && (
        <Dialog
          title="Chặn kết nối này?"
          destructive
          onClose={() => !busy && setBlocking(false)}
        >
          <p>
            Hai người sẽ không thể tiếp tục xem hoặc gửi tin trong kết nối này.
            Bỏ chặn sau này không khôi phục cuộc trò chuyện hay quyền chia sẻ
            cũ.
          </p>
          <div className={cx.actions}>
            <Button
              variant="secondary"
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
    </details>
  );
}
