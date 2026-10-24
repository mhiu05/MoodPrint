import { useState } from "react";
import { Link } from "react-router-dom";
import { Button, cx } from "../../components/UI";
import type { components } from "../../api/generated/schema";
import { ErrorNotice, useResource, useSession } from "./RealApp";
import { botById, type BotId } from "../../companions/registry";

type MemoryDTO = components["schemas"]["MemoryDTO"];
type Proposal = {
  id: string;
  text: string;
  botId: BotId;
  purpose: "memory" | "private_item";
  version: number;
};

function ProposalReview({
  proposal,
  completed,
}: {
  proposal: Proposal;
  completed: () => void;
}) {
  const { api } = useSession();
  const [text, setText] = useState(proposal.text),
    [busy, setBusy] = useState(false),
    [error, setError] = useState<unknown>();
  return (
    <article className="real-item">
      <h3>
        {proposal.purpose === "memory"
          ? "Đề xuất ghi nhớ"
          : "Đề xuất cho hồ sơ riêng"}{" "}
        từ {botById(proposal.botId)?.name}
      </h3>
      <p>Đây là đề xuất để bạn xem lại. Chỉ nội dung bạn duyệt mới được lưu.</p>
      <label htmlFor={`proposal-${proposal.id}`}>Nội dung bạn muốn duyệt</label>
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
          disabled={busy || !text.trim()}
          onClick={() => {
            setBusy(true);
            void api
              .request(`/proposals/${proposal.id}/confirm`, {
                method: "POST",
                body: { expectedVersion: proposal.version, editedText: text },
              })
              .then(completed)
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
          <label htmlFor={`memory-${memory.id}`}>Chỉnh mục ghi nhớ</label>
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
          {editing ? "Lưu chỉnh sửa" : "Sửa"}
        </Button>
        <Button
          variant="text"
          disabled={busy}
          onClick={() => void modify(true)}
        >
          Xóa ghi nhớ
        </Button>
        {editing && (
          <Button
            variant="text"
            onClick={() => {
              setText(memory.text);
              setEditing(false);
            }}
          >
            Hủy chỉnh sửa
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
  return (
    <div className={cx.reading}>
      <h1 tabIndex={-1}>Ghi nhớ bạn đã duyệt</h1>
      <p className={cx.lede}>
        Mỗi trợ lý chỉ dùng những mục bạn đã duyệt cho trợ lý đó. Hồ sơ kết nối
        không dùng các ghi nhớ này để xếp gợi ý.
      </p>
      <Link to="/profile">Về hồ sơ riêng</Link>
      {notice && <p role="status">{notice}</p>}
      <ErrorNotice error={memories.error} retry={memories.refresh} />
      {!session.consents.AI.enabled || !session.consents.MEM.enabled ? (
        <p>
          Trợ lý hiện không dùng ghi nhớ. Bạn vẫn có thể sửa và xóa các mục đã
          lưu. <Link to="/settings">Xem quyền ghi nhớ</Link>
        </p>
      ) : null}
      {session.consents.AI.enabled && proposals.data && (
        <section className="real-section">
          <h2>Đang chờ bạn xem lại</h2>
          {proposals.data.length === 0 && <p>Không có đề xuất đang chờ.</p>}
          {proposals.data.map((proposal) => (
            <ProposalReview
              key={proposal.id}
              proposal={proposal}
              completed={refresh}
            />
          ))}
        </section>
      )}
      <section className="real-section">
        <h2>Những mục đã lưu</h2>
        {memories.loading && <p role="status">Đang tải ghi nhớ…</p>}
        {memories.data?.length === 0 && <p>Bạn chưa duyệt mục ghi nhớ nào.</p>}
        {memories.data?.map((memory) => (
          <MemoryItem
            key={`${memory.id}-${memory.version}`}
            memory={memory}
            completed={refresh}
          />
        ))}
      </section>
    </div>
  );
}
