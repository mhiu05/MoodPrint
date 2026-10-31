import { BotAvatar } from "../../../companions/Avatar";
import { botById, type BotId } from "../../../companions/registry";
import { Button } from "../../../components/UI";
import "./orchestration.css";

export type AgentStep = { kind: "consult" | "handoff"; companion: "nhatky" | "hoatdong" };

const nameOf = (id: string) => botById(id)?.name ?? id;

/** "Điều phối đã hỏi ý Nhật ký và Hoạt động": only from receipt-backed steps the server sent. */
export function AgentStepsLine({ requester, steps }: { requester: string; steps: AgentStep[] }) {
  if (!steps.length) return null;
  const consulted = steps.filter((step) => step.kind === "consult").map((step) => step.companion);
  const handedOver = steps.find((step) => step.kind === "handoff")?.companion;
  const sentence = handedOver
    ? `${nameOf(requester)} đã mời ${nameOf(handedOver)} trò chuyện trực tiếp với bạn.`
    : `${nameOf(requester)} đã hỏi ý ${consulted.map(nameOf).join(" và ")} để trả lời bạn.`;
  return (
    <div className="agent-steps-line">
      <span className="agent-steps-avatars" aria-hidden="true">
        {steps.map((step) => <BotAvatar key={step.companion} id={step.companion as BotId} size={16} />)}
      </span>
      <p>{sentence}</p>
    </div>
  );
}

/** Who actually answered, when it is not the conversation's own agent (a handoff). */
export function SpeakerTag({ id }: { id: string }) {
  const profile = botById(id);
  if (!profile) return null;
  return (
    <div className="speaker-tag">
      <BotAvatar id={profile.id} size={22} />
      <strong>{profile.name}</strong>
    </div>
  );
}

/** Shown while a specialist keeps answering in this conversation, with the way back. */
export function HandoffBanner({
  agent, owner, busy, onReturn,
}: {
  agent: string;
  owner: string;
  busy: boolean;
  onReturn: () => void;
}) {
  return (
    <div className="handoff-banner" role="status">
      <BotAvatar id={agent as BotId} size={28} />
      <p>Bạn đang trò chuyện trực tiếp với <strong>{nameOf(agent)}</strong> trong cuộc này.</p>
      <Button variant="secondary" disabled={busy} onClick={onReturn}>Quay lại {owner}</Button>
    </div>
  );
}
