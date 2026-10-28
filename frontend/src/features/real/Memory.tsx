import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Button, cx } from "../../components/UI";
import type { components } from "../../api/generated/schema";
import { ErrorNotice, useResource, useSession } from "./RealApp";
import { botById, type BotId } from "../../companions/registry";
import type { SessionView } from "../../api/contracts";

type MemoryDTO = components["schemas"]["MemoryDTO"];
type Proposal = components["schemas"]["ProposalDTO"];

function ProposalReview({
  proposal,
  completed,
}: {
  proposal: Proposal;
  completed: () => void;
}) {
  const { api, session, receive } = useSession();
  const [text, setText] = useState(proposal.text),
    [busy, setBusy] = useState(false),
    [error, setError] = useState<unknown>();
  const [now, setNow] = useState(Date.now);
  const expiry = proposal.expiresAt
    ? new Date(proposal.expiresAt).getTime()
    : Infinity;
  const status =
    (proposal.status || "pending") === "pending" && expiry <= now
      ? "expired"
      : proposal.status || "pending";
  const allowed = session.consents.AI.enabled;
  useEffect(() => {
    if (
      !Number.isFinite(expiry) ||
      expiry <= Date.now() ||
      status !== "pending"
    )
      return;
    const timer = window.setTimeout(
      () => setNow(Date.now()),
      Math.min(expiry - Date.now() + 20, 2_147_483_647),
    );
    return () => window.clearTimeout(timer);
  }, [expiry, status]);
  return (
    <article className="real-item">
      <h3>
        {proposal.purpose === "memory"
          ? "Đề xuất ghi nhớ"
          : "Đề xuất cho hồ sơ riêng"}{" "}
        từ {botById(proposal.botId)?.name}
        {status === "pending" ? <span className="memory-state">Chưa lưu</span> : null}
      </h3>
      {status !== "pending" ? (
        <p>
          {status === "expired"
            ? "Đề xuất đã hết hạn. Bạn có thể nhờ trợ lý tạo đề xuất mới."
            : status === "approved"
              ? "Bạn đã duyệt đề xuất này. Có thể sửa hoặc xóa nội dung đã lưu."
              : "Bạn đã chọn không lưu đề xuất này."}
        </p>
      ) : (
        <>
          <p>
            Bạn có thể sửa trước khi duyệt. Nội dung chỉ được lưu khi bạn chọn “Duyệt và lưu”.
          </p>
          {proposal.expiresAt ? (
            <p>
              Hết hạn:{" "}
              <time dateTime={proposal.expiresAt}>
                {new Intl.DateTimeFormat("vi-VN", {
                  timeZone: session.timezone,
                  dateStyle: "short",
                  timeStyle: "short",
                }).format(new Date(proposal.expiresAt))}
              </time>
            </p>
          ) : null}
          {!allowed ? (
            <p>
              Quyền xử lý AI đang tắt nên chưa thể duyệt đề xuất này. Bạn vẫn có
              thể chọn không lưu. Để dùng trợ lý trở lại, mở cuộc trò chuyện và
              chọn Gửi khi bạn muốn chia sẻ tin nhắn.{" "}
              <Link to="/assistants">Mở trợ lý</Link>
            </p>
          ) : null}
          {proposal.purpose === "memory" ? <p>Chọn “Duyệt và lưu” sẽ cho phép trợ lý dùng các ghi nhớ bạn đã duyệt trong những lần trò chuyện sau. Bạn có thể rút quyền và xóa từng ghi nhớ.</p> : null}
          <label htmlFor={`proposal-${proposal.id}`}>
            Nội dung sẽ lưu
          </label>
          <textarea
            id={`proposal-${proposal.id}`}
            value={text}
            maxLength={120}
            rows={3}
            onChange={(event) => setText(event.target.value)}
          />
          <ErrorNotice error={error} />
          <div className={cx.actions}>
            <Button
              disabled={busy || !text.trim() || !allowed}
              onClick={() => {
                setBusy(true);
                void api
                  .request(`/proposals/${proposal.id}/confirm`, {
                    method: "POST",
                    body: {
                      expectedVersion: proposal.version,
                      editedText: text,
                    },
                  })
                  .then(async () => {
                    completed();
                    try { receive(await api.request<SessionView>("/session")); }
                    catch (reason) { setError(reason); }
                  })
                  .catch(setError)
                  .finally(() => setBusy(false));
              }}
            >
              Duyệt và lưu
            </Button>
            <Button
              variant="secondary"
              disabled={busy}
              onClick={() => {
                setBusy(true);
                void api
                  .request(`/proposals/${proposal.id}/reject`, {
                    method: "POST",
                    body: { expectedVersion: proposal.version },
                  })
                  .then(completed)
                  .catch(setError)
                  .finally(() => setBusy(false));
              }}
            >
              Không lưu
            </Button>
          </div>
        </>
      )}
    </article>
  );
}

function MemoryItem({
  memory,
  completed,
}: {
  memory: MemoryDTO;
  completed: () => void;
}) {
  const { api } = useSession();
  const [text, setText] = useState(memory.text),
    [editing, setEditing] = useState(false),
    [confirmDelete, setConfirmDelete] = useState(false),
    [busy, setBusy] = useState(false),
    [error, setError] = useState<unknown>();
  async function modify(deleting: boolean) {
    setBusy(true);
    setError(undefined);
    try {
      await api.request(`/memories/${memory.id}`, {
        method: deleting ? "DELETE" : "PATCH",
        body: deleting
          ? { expectedVersion: memory.version }
          : { expectedVersion: memory.version, text },
      });
      setEditing(false);
      completed();
    } catch (reason) {
      setError(reason);
    } finally {
      setBusy(false);
    }
  }
  return (
    <article className="real-item">
      <h3>{botById(memory.botId)?.name}</h3>
      {editing ? (
        <>
          <label htmlFor={`memory-${memory.id}`}>Sửa ghi nhớ</label>
          <textarea
            id={`memory-${memory.id}`}
            value={text}
            maxLength={120}
            onChange={(event) => setText(event.target.value)}
          />
        </>
      ) : (
        <p>{memory.text}</p>
      )}
      <ErrorNotice error={error} />
      <div className={cx.actions}>
        <Button
          variant="secondary"
          disabled={busy}
          onClick={() => (editing ? void modify(false) : setEditing(true))}
        >
          {editing ? "Lưu thay đổi" : "Sửa"}
        </Button>
        {confirmDelete ? (
          <>
            <Button
              variant="danger"
              disabled={busy}
              onClick={() => void modify(true)}
            >
              Xóa ghi nhớ này
            </Button>
            <Button
              variant="text"
              disabled={busy}
              onClick={() => setConfirmDelete(false)}
            >
              Giữ lại
            </Button>
          </>
        ) : (
          <Button
            variant="text"
            disabled={busy}
            onClick={() => setConfirmDelete(true)}
          >
            Xóa ghi nhớ
          </Button>
        )}
        {editing && (
          <Button
            variant="text"
            onClick={() => {
              setText(memory.text);
              setEditing(false);
            }}
          >
            Hủy sửa
          </Button>
        )}
      </div>
    </article>
  );
}

export function ApprovedMemories() {
  const { session } = useSession();
  const memories = useResource<MemoryDTO[]>("/memories");
  const proposals = useResource<Proposal[]>("/proposals");
  const [notice, setNotice] = useState("");
  const refresh = () => {
    memories.refresh();
    proposals.refresh();
    setNotice("Đã cập nhật ghi nhớ.");
  };
  const now = Date.now();
  const waiting = proposals.data?.filter(
    (proposal) => (proposal.status || "pending") === "pending" && new Date(proposal.expiresAt).getTime() > now,
  );
  const decided = proposals.data?.filter((proposal) => !waiting?.includes(proposal));
  return (
    <div className={cx.reading}>
      <h1 tabIndex={-1} data-tour="memory-intro">Thông tin AI ghi nhớ</h1>
      <p className={cx.lede}>
        Mỗi trợ lý chỉ dùng những mục bạn đã duyệt cho trợ lý đó. Hồ sơ tìm bạn
        không dùng các ghi nhớ này để gợi ý.
      </p>
      <Link to="/profile">Về hồ sơ riêng</Link>
      {notice && <p role="status">{notice}</p>}
      {!session.consents.AI.enabled ? (
        <p>
          Trợ lý hiện không dùng ghi nhớ vì quyền xử lý AI đang tắt. Bạn vẫn có
          thể sửa và xóa các mục đã lưu. Để dùng trợ lý trở lại, mở cuộc trò
          chuyện và chọn Gửi khi bạn muốn chia sẻ tin nhắn.{" "}
          <Link to="/assistants">Mở trợ lý</Link>
        </p>
      ) : !session.consents.MEM.enabled ? (
        <p>
          Trợ lý hiện không dùng ghi nhớ. Bạn vẫn có thể sửa và xóa các mục đã
          lưu. Trợ lý chỉ dùng lại ghi nhớ sau khi bạn duyệt một đề xuất mới.
        </p>
      ) : null}
      <section className="real-section" aria-labelledby="memory-waiting">
        <h2 id="memory-waiting">Đề xuất chờ duyệt</h2>
        <ErrorNotice error={proposals.error} retry={proposals.refresh} />
        {proposals.loading ? <p role="status">Đang tải đề xuất…</p> : null}
        {waiting && !waiting.length ? <p>Không có đề xuất đang chờ.</p> : null}
        {waiting?.map((proposal) => (
          <ProposalReview key={proposal.id} proposal={proposal} completed={refresh} />
        ))}
      </section>
      <section className="real-section" aria-labelledby="memory-approved">
        <h2 id="memory-approved">Đã duyệt</h2>
        <ErrorNotice error={memories.error} retry={memories.refresh} />
        {memories.loading && <p role="status">Đang tải ghi nhớ…</p>}
        {memories.data?.length === 0 && <p>Bạn chưa lưu ghi nhớ nào. Khi trò chuyện, bạn có thể nhờ trợ lý đề xuất điều cần nhớ rồi duyệt tại đây.</p>}
        {memories.data?.map((memory) => (
          <MemoryItem
            key={`${memory.id}-${memory.version}`}
            memory={memory}
            completed={refresh}
          />
        ))}
      </section>
      {decided?.length ? (
        <section className="real-section" aria-labelledby="memory-decided">
          <h2 id="memory-decided">Đề xuất đã xử lý</h2>
          {decided.map((proposal) => (
            <ProposalReview key={proposal.id} proposal={proposal} completed={refresh} />
          ))}
        </section>
      ) : null}
    </div>
  );
}
