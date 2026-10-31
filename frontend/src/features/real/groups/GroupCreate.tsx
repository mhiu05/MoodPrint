import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import type { components } from "../../../api/generated/schema";
import { BotAvatar } from "../../../companions/Avatar";
import { agents, type AgentId } from "../../../companions/registry";
import { Button } from "../../../components/UI";
import { ErrorNotice, useSession } from "../RealApp";
import "./groups.css";

/** Create an AI group: a name and two or three of the three agents. */
export function GroupCreate() {
  const { api } = useSession();
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [members, setMembers] = useState<AgentId[]>(["dieuphoi", "nhatky", "hoatdong"]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>();
  const [attempted, setAttempted] = useState(false);
  const suggested = members.map((id) => agents.find((agent) => agent.id === id)?.name).join(", ");
  const tooFew = members.length < 2;

  async function create() {
    setAttempted(true);
    if (tooFew || busy) return;
    setBusy(true);
    setError(undefined);
    try {
      const group = await api.request<components["schemas"]["GroupView"]>("/ai/groups", {
        method: "POST",
        body: { name: name.trim() || `Nhóm ${suggested}`.slice(0, 60), members },
      });
      navigate(`/assistants/groups/${group.groupId}`, { replace: true });
    } catch (reason) {
      setError(reason);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="bot-conversation ai-conversation group-create">
      <header className="conversation-header">
        <Link to="/assistants" className="icon-button mobile-back" aria-label="Về danh sách trợ lý"><ArrowLeft size={21} /></Link>
        <div>
          <h1 tabIndex={-1} data-route-heading>Tạo nhóm trợ lý</h1>
          <p>Trò chuyện cùng lúc với nhiều trợ lý</p>
        </div>
      </header>
      <form className="group-create-form" onSubmit={(event) => { event.preventDefault(); void create(); }}>
        <label htmlFor="new-group-name">Tên nhóm</label>
        <input id="new-group-name" value={name} maxLength={60} placeholder={`Ví dụ: Kế hoạch cuối tuần`}
          onChange={(event) => setName(event.target.value)} />
        <fieldset aria-describedby="group-members-help">
          <legend>Ai trong nhóm?</legend>
          <p id="group-members-help" className="group-hint">Chọn ít nhất hai trợ lý.</p>
          {agents.map((agent) => {
            const checked = members.includes(agent.id as AgentId);
            return (
              <label key={agent.id} className={`group-pick ${checked ? "is-checked" : ""}`}>
                <input type="checkbox" checked={checked} onChange={(event) => setMembers((current) =>
                  event.target.checked ? [...current, agent.id as AgentId] : current.filter((id) => id !== agent.id))} />
                <BotAvatar id={agent.id} size={40} />
                <span>
                  <strong>{agent.name}</strong>
                  <small>{agent.description}</small>
                </span>
              </label>
            );
          })}
        </fieldset>
        {attempted && tooFew ? <p className="group-error" role="alert">Hãy chọn ít nhất hai trợ lý.</p> : null}
        <p className="group-privacy">
          Mỗi tin bạn gửi trong nhóm có thể được một hoặc vài trợ lý trả lời; gõ @ để gọi riêng ai đó. Các trợ lý chỉ thấy
          tin nhắn trong nhóm. Nhật ký riêng của bạn không được dùng trừ khi bạn cho phép trong phần thông tin nhóm.
        </p>
        <ErrorNotice error={error} />
        <Button type="submit" disabled={busy}>{busy ? "Đang tạo nhóm…" : "Tạo nhóm"}</Button>
      </form>
    </div>
  );
}
