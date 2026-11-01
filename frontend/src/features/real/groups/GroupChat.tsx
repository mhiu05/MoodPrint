import { lazy, Suspense, useCallback, useEffect, useId, useMemo, useRef, useState, type KeyboardEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ArrowLeft, ArrowUp, AtSign, Info, Pause, X } from "lucide-react";
import type { components } from "../../../api/generated/schema";
import { ApiError } from "../../../api/client";
import { BotAvatar } from "../../../companions/Avatar";
import { agents, botById, type BotId } from "../../../companions/registry";
import { Button, cx, Dialog } from "../../../components/UI";
import { ErrorNotice, useSession } from "../RealApp";
import { groupMessages } from "../messageGroups";
import { consumeGroupTurn, type AgentId, type GroupEvent } from "./groupEvents";
import { activeMention, EVERYONE, insertMention, keptMentions, mentionOptions, type MentionTarget } from "./mentions";
import "./groups.css";

const MessageMarkdown = lazy(() => import("../MessageMarkdown"));
type View = components["schemas"]["GroupView"];
type Message = View["messages"][number];
type Turn = { id: string; eventsUrl: string; queue: AgentId[]; speaking: AgentId | null; lastSeq: number };

const nameOf = (id: string) => botById(id)?.name ?? id;
const draftKey = (id: string) => `moodprint:group-draft:${id}`;

export function AvatarStack({ ids, size = 28 }: { ids: string[]; size?: number }) {
  return (
    <span className="avatar-stack" aria-hidden="true">
      {ids.map((id) => <BotAvatar key={id} id={id as BotId} size={size} />)}
    </span>
  );
}

function failureText(reason: unknown): unknown {
  if (reason instanceof ApiError && reason.code === "MENTION_NOT_MEMBER")
    return new ApiError(422, reason.code, "Trợ lý bạn nhắc tên không ở trong nhóm này.");
  return reason;
}

export function GroupChat({ groupId }: { groupId: string }) {
  const { api, session } = useSession();
  const navigate = useNavigate();
  const [view, setView] = useState<View>();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>();
  const [draft, setDraft] = useState(() => sessionStorage.getItem(draftKey(groupId)) ?? "");
  const [picked, setPicked] = useState<MentionTarget[]>([]);
  const [picker, setPicker] = useState<{ start: number; caret: number; options: MentionTarget[]; active: number } | null>(null);
  const [turn, setTurn] = useState<Turn | null>(null);
  const [sending, setSending] = useState(false);
  const [notice, setNotice] = useState("");
  const [infoOpen, setInfoOpen] = useState(false);
  const composer = useRef<HTMLTextAreaElement>(null);
  const infoTrigger = useRef<HTMLButtonElement>(null);
  const lifetime = useRef<AbortController | null>(null);
  const attempt = useRef<{ text: string; id: string } | null>(null);
  const pickerId = useId();
  const allowed = session.features.groupChat && session.features.ai;

  const load = useCallback(async (signal?: AbortSignal) => {
    try {
      const next = await api.request<View>(`/ai/groups/${groupId}`, { signal });
      if (!signal?.aborted) {
        setView(next);
        setError(undefined);
      }
      return next;
    } catch (reason) {
      if (!signal?.aborted) setError(reason);
    } finally {
      if (!signal?.aborted) setLoading(false);
    }
  }, [api, groupId]);

  const follow = useCallback(async (turnId: string, eventsUrl: string, signal: AbortSignal) => {
    setTurn({ id: turnId, eventsUrl, queue: [], speaking: null, lastSeq: 0 });
    const apply = (event: GroupEvent) => {
      if (signal.aborted) return;
      setTurn((current) => {
        if (!current) return current;
        if (event.type === "agent_selected") return { ...current, queue: [...current.queue, event.agent] };
        if (event.type === "agent_started") return { ...current, speaking: event.agent };
        if (event.type === "agent_message" || event.type === "agent_failed")
          return { ...current, speaking: null, queue: current.queue.filter((_, index) => index !== 0) };
        return current;
      });
      if (event.type === "agent_message") {
        setView((current) => {
          if (!current) return current;
          const known = new Set(current.messages.map((message) => message.id));
          const added = event.messages.filter((bubble) => !known.has(bubble.messageId)).map((bubble): Message => ({
            id: bubble.messageId, actor: "bot", text: bubble.text, cards: bubble.cards, partIndex: bubble.partIndex,
            partCount: event.messages.length, speaker: event.agent, runId: `${turnId}:${event.ordinal}`,
            createdAt: new Date().toISOString(), origin: "user",
          }));
          return added.length ? { ...current, messages: [...current.messages, ...added] } : current;
        });
      }
      if (event.type === "agent_failed" && event.code !== "not_member")
        setNotice(`${nameOf(event.agent)} chưa trả lời được lần này.`);
    };
    let lastSeq = 0;
    // A dropped connection resumes from the last event seen; the server replays only what follows.
    for (let attempts = 0; attempts < 4 && !signal.aborted; attempts += 1) {
      try {
        const result = await consumeGroupTurn(eventsUrl, signal, (event) => {
          lastSeq += 1;
          apply(event);
        }, lastSeq);
        if (result.outcome === "failed") setNotice("Nhóm chưa trả lời xong. Bạn có thể gửi lại.");
        if (result.outcome === "cancelled") setNotice("Đã dừng lượt trả lời.");
        break;
      } catch (reason) {
        if (signal.aborted) return;
        if (reason instanceof ApiError && reason.code !== "STREAM_UNAVAILABLE") {
          setError(reason);
          break;
        }
        await new Promise((resolve) => setTimeout(resolve, 600 * (attempts + 1)));
      }
    }
    if (signal.aborted) return;
    setTurn(null);
    await load(signal);
  }, [load]);

  useEffect(() => {
    const controller = new AbortController();
    lifetime.current = controller;
    setLoading(true);
    setView(undefined);
    setTurn(null);
    setNotice("");
    setDraft(sessionStorage.getItem(draftKey(groupId)) ?? "");
    void load(controller.signal).then((next) => {
      // A turn still running after a reload or a reconnect: follow it from the start (no duplicates).
      if (next?.activeTurnId && !controller.signal.aborted)
        void follow(next.activeTurnId, `/api/v1/ai/groups/${groupId}/turns/${next.activeTurnId}/events`, controller.signal);
    });
    return () => controller.abort();
  }, [groupId, load, follow]);

  useEffect(() => {
    if (draft) sessionStorage.setItem(draftKey(groupId), draft);
    else sessionStorage.removeItem(draftKey(groupId));
  }, [draft, groupId]);

  // Mark what is on screen as read (content-free watermark).
  const version = view?.version;
  useEffect(() => {
    if (!version || turn) return;
    void api.request(`/ai/groups/${groupId}/read`, { method: "POST", body: { sequence: version } }).catch(() => undefined);
  }, [api, groupId, version, turn]);

  const members = useMemo(() => (view?.members ?? []).filter((member) => member.status === "active"), [view]);
  const targets: MentionTarget[] = useMemo(
    () => [...members.map((member) => ({ id: member.botId, name: nameOf(member.botId) }) as MentionTarget), EVERYONE],
    [members],
  );

  function updatePicker(text: string, caret: number) {
    const open = activeMention(text, caret);
    if (!open) return setPicker(null);
    const options = mentionOptions(targets, open.query);
    setPicker(options.length ? { start: open.start, caret, options, active: 0 } : null);
  }

  function choose(target: MentionTarget) {
    if (!picker) return;
    const next = insertMention(draft, picker.start, picker.caret, target);
    setDraft(next.text);
    setPicked((current) => (current.some((item) => item.id === target.id) ? current : [...current, target]));
    setPicker(null);
    requestAnimationFrame(() => {
      composer.current?.focus();
      composer.current?.setSelectionRange(next.caret, next.caret);
    });
  }

  function openPicker() {
    const field = composer.current;
    const caret = field?.selectionStart ?? draft.length;
    const needsSpace = caret > 0 && !/\s/.test(draft[caret - 1]);
    const text = draft.slice(0, caret) + (needsSpace ? " @" : "@") + draft.slice(caret);
    const position = caret + (needsSpace ? 2 : 1);
    setDraft(text);
    setPicker({ start: position - 1, caret: position, options: targets, active: 0 });
    requestAnimationFrame(() => {
      field?.focus();
      field?.setSelectionRange(position, position);
    });
  }

  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (picker) {
      if (event.key === "ArrowDown" || event.key === "ArrowUp") {
        event.preventDefault();
        const step = event.key === "ArrowDown" ? 1 : -1;
        setPicker({ ...picker, active: (picker.active + step + picker.options.length) % picker.options.length });
        return;
      }
      if (event.key === "Enter" || event.key === "Tab") {
        event.preventDefault();
        choose(picker.options[picker.active]);
        return;
      }
      if (event.key === "Escape") {
        event.preventDefault();
        setPicker(null);
        return;
      }
    }
    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault();
      void send();
    }
  }

  async function send() {
    const text = draft.trim();
    if (!text || !view || sending || turn || !allowed || !lifetime.current) return;
    const signal = lifetime.current.signal;
    setSending(true);
    setError(undefined);
    setNotice("");
    if (attempt.current?.text !== text) attempt.current = { text, id: crypto.randomUUID() };
    try {
      const accepted = await api.request<components["schemas"]["GroupTurnAccepted"]>(`/ai/groups/${groupId}/messages`, {
        method: "POST",
        body: { text, clientMessageId: attempt.current.id, expectedVersion: view.version, mentions: keptMentions(draft, picked) },
        signal,
      });
      attempt.current = null;
      setDraft("");
      setPicked([]);
      setView((current) => current && {
        ...current, version: accepted.version,
        messages: [...current.messages, { id: `self-${accepted.turnId}`, actor: "self", text, cards: [], createdAt: new Date().toISOString(), origin: "user", partIndex: 0, partCount: 1 }],
      });
      void follow(accepted.turnId, accepted.eventsUrl, signal);
    } catch (reason) {
      if (reason instanceof ApiError && reason.code === "STALE_VERSION") await load(signal);
      setError(failureText(reason));
    } finally {
      setSending(false);
    }
  }

  async function stop() {
    if (!turn) return;
    try {
      await api.request(`/ai/groups/${groupId}/turns/${turn.id}/cancel`, { method: "POST", body: {} });
    } catch (reason) {
      setError(reason);
    }
  }

  const groups = useMemo(() => groupMessages(view?.messages ?? []), [view]);
  const log = useRef<HTMLDivElement>(null);
  const count = view?.messages.length ?? 0;
  useEffect(() => {
    const node = log.current;
    if (!node) return;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    node.scrollTo({ top: node.scrollHeight, behavior: reduce ? "auto" : "smooth" });
  }, [count, turn?.speaking]);

  if (!allowed) return <div className="conversation-welcome"><h2>Nhóm trợ lý chưa mở cho tài khoản của bạn</h2><Link to="/assistants">Về danh sách trợ lý</Link></div>;
  if (loading && !view) return <div className="conversation-welcome"><p role="status">Đang mở nhóm…</p></div>;
  if (!view)
    return (
      <div className="conversation-welcome">
        <h2>Chưa mở được nhóm này</h2>
        <ErrorNotice error={error} retry={() => void load()} />
        <Link to="/assistants">Về danh sách trợ lý</Link>
      </div>
    );

  const speakingName = turn?.speaking ? nameOf(turn.speaking) : null;
  const next = turn?.queue.filter((agent) => agent !== turn.speaking) ?? [];
  const busy = sending || Boolean(turn);
  return (
    <div className="bot-conversation ai-conversation group-conversation">
      <header className="conversation-header">
        <Link to="/assistants" className="icon-button mobile-back" aria-label="Về danh sách trợ lý">
          <ArrowLeft size={21} />
        </Link>
        <AvatarStack ids={members.map((member) => member.botId)} size={30} />
        <div>
          <h1 tabIndex={-1} data-route-heading>{view.name}</h1>
          <p>{members.map((member) => nameOf(member.botId)).join(", ")}</p>
        </div>
        <button ref={infoTrigger} type="button" className="icon-button" aria-label="Thông tin nhóm"
          aria-expanded={infoOpen} onClick={() => setInfoOpen((value) => !value)}>
          <Info size={21} />
        </button>
      </header>
      {infoOpen ? (
        <GroupInfo view={view} busy={busy} onChange={setView} onClose={() => { setInfoOpen(false); infoTrigger.current?.focus(); }}
          onDeleted={() => { sessionStorage.removeItem(draftKey(groupId)); navigate("/assistants", { replace: true }); }} />
      ) : null}
      <div className="conversation-log" ref={log}>
        {view.messages.length === 0 ? (
          <div className="group-empty-state">
            <AvatarStack ids={members.map((member) => member.botId)} size={44} />
            <p>Nhắn cho cả nhóm, hoặc gõ <kbd>@</kbd> để gọi riêng một trợ lý.</p>
          </div>
        ) : null}
        {/* Live only after the first load: a reload must not re-announce the whole history. */}
        <div className="conversation-messages" aria-live={loading ? "off" : "polite"} aria-relevant="additions text">
          {groups.map((group) => {
            const lead = group.items[0];
            if (lead.actor === "self")
              return (
                <div key={group.key} className="message-row ai-message-row from-self">
                  <div className="message-content" role="group" aria-label="Tin nhắn của bạn">
                    <div className="chat-bubble"><p>{lead.text}</p></div>
                  </div>
                </div>
              );
            const speaker = lead.speaker ?? "dieuphoi";
            return (
              <div key={group.key} className="group-turn" role="group" aria-label={`Tin nhắn từ ${nameOf(speaker)}`}>
                <div className="group-speaker">
                  <BotAvatar id={speaker as BotId} size={26} />
                  <strong>{nameOf(speaker)}</strong>
                </div>
                {group.items.map((message) => (
                  <div key={message.id} className="message-row ai-message-row from-bot in-group">
                    <div className="message-content">
                      <div className="chat-bubble">
                        <Suspense fallback={<p>{message.text}</p>}><MessageMarkdown text={message.text} /></Suspense>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            );
          })}
        </div>
        <div className={`group-typing ${turn ? "is-shown" : ""}`} role="status">
          {turn ? (
            speakingName ? (
              <>
                <BotAvatar id={turn.speaking as BotId} size={20} />
                <span>{speakingName} đang trả lời…{next.length ? ` Tiếp theo: ${next.map(nameOf).join(", ")}.` : ""}</span>
              </>
            ) : <span>Nhóm đang đọc tin của bạn…</span>
          ) : notice ? <span>{notice}</span> : null}
        </div>
        <ErrorNotice error={error} />
      </div>
      <div className="chat-bottom">
        <form className="bot-composer group-composer" onSubmit={(event) => { event.preventDefault(); void send(); }}>
          {picker ? (
            <div id={pickerId} role="listbox" className="mention-picker" aria-label="Nhắc tên trợ lý">
              {picker.options.map((option, index) => (
                <div key={option.id} id={`${pickerId}-${option.id}`} role="option" aria-selected={index === picker.active}
                  className="mention-option" onMouseDown={(event) => { event.preventDefault(); choose(option); }}>
                  {option.id === "all" ? <AvatarStack ids={members.map((member) => member.botId)} size={18} /> : <BotAvatar id={option.id as BotId} size={22} />}
                  <span>{option.id === "all" ? "Mọi người trong nhóm" : option.name}</span>
                </div>
              ))}
            </div>
          ) : null}
          <button type="button" className="icon-button mention-button" aria-label="Nhắc tên một trợ lý" title="Nhắc tên một trợ lý"
            disabled={busy} onClick={openPicker}>
            <AtSign size={19} aria-hidden="true" />
          </button>
          <textarea
            ref={composer}
            aria-label={`Tin nhắn cho nhóm ${view.name}`}
            placeholder="Nhắn cho cả nhóm… gõ @ để gọi riêng"
            value={draft}
            maxLength={500}
            rows={1}
            aria-autocomplete="list"
            aria-controls={picker ? pickerId : undefined}
            aria-activedescendant={picker ? `${pickerId}-${picker.options[picker.active].id}` : undefined}
            onChange={(event) => {
              setDraft(event.target.value);
              updatePicker(event.target.value, event.target.selectionStart ?? event.target.value.length);
            }}
            onKeyDown={onKeyDown}
            onBlur={() => setPicker(null)}
          />
          {turn ? (
            <button type="button" className="send-button" aria-label="Dừng lượt trả lời" title="Dừng lượt trả lời" onClick={() => void stop()}>
              <Pause size={18} fill="currentColor" strokeWidth={1.5} aria-hidden="true" />
            </button>
          ) : (
            <button type="submit" className="send-button" aria-label="Gửi cho nhóm" title="Gửi cho nhóm" disabled={!draft.trim() || sending}>
              <ArrowUp size={20} strokeWidth={2} aria-hidden="true" />
            </button>
          )}
        </form>
      </div>
    </div>
  );
}

function GroupInfo({ view, busy, onChange, onClose, onDeleted }: {
  view: View;
  busy: boolean;
  onChange: (view: View) => void;
  onClose: () => void;
  onDeleted: () => void;
}) {
  const { api } = useSession();
  const [name, setName] = useState(view.name);
  const [saving, setSaving] = useState<string | null>(null);
  const [error, setError] = useState<unknown>();
  const [status, setStatus] = useState("");
  const [shareHistory, setShareHistory] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const deleteTrigger = useRef<HTMLButtonElement>(null);
  const panel = useRef<HTMLElement>(null);
  useEffect(() => panel.current?.focus(), []);
  const active = view.members.filter((member) => member.status === "active");
  const missing = agents.filter((agent) => !active.some((member) => member.botId === agent.id));

  async function act(key: string, path: string, init: { method: string; body?: unknown }, done: string) {
    if (saving) return;
    setSaving(key);
    setError(undefined);
    setStatus("");
    try {
      const next = await api.request<View>(path, init);
      if (next) onChange(next);
      setStatus(done);
    } catch (reason) {
      setError(reason);
    } finally {
      setSaving(null);
    }
  }
  const base = `/ai/groups/${view.groupId}`;
  return (
    <aside ref={panel} tabIndex={-1} className="group-info" aria-label="Thông tin nhóm"
      onKeyDown={(event) => { if (event.key === "Escape") onClose(); }}>
      <div className="group-info-head">
        <h2>Thông tin nhóm</h2>
        <button type="button" className="icon-button" aria-label="Đóng thông tin nhóm" onClick={onClose}><X size={20} /></button>
      </div>
      <form className="group-rename" onSubmit={(event) => { event.preventDefault(); if (name.trim()) void act("rename", base, { method: "PATCH", body: { name, expectedVersion: view.version } }, "Đã đổi tên nhóm."); }}>
        <label htmlFor="group-name">Tên nhóm</label>
        <div>
          <input id="group-name" value={name} maxLength={60} onChange={(event) => setName(event.target.value)} />
          <Button type="submit" variant="secondary" disabled={saving !== null || !name.trim() || name.trim() === view.name}>Lưu tên</Button>
        </div>
      </form>
      <h3>Thành viên</h3>
      <ul className="group-members">
        {active.map((member) => (
          <li key={member.botId}>
            <BotAvatar id={member.botId as BotId} size={32} />
            <div className="group-member-text">
              <strong>{nameOf(member.botId)}</strong>
              <small>{botById(member.botId)?.role}</small>
            </div>
            <Button variant="text" disabled={busy || saving !== null || active.length <= 2}
              aria-label={`Bỏ ${nameOf(member.botId)} khỏi nhóm`}
              onClick={() => void act(`remove-${member.botId}`, `${base}/members/${member.botId}?expectedVersion=${view.version}`, { method: "DELETE" }, `Đã bỏ ${nameOf(member.botId)} khỏi nhóm.`)}>
              Bỏ khỏi nhóm
            </Button>
            {member.botId === "nhatky" ? (
              <label className="group-journal">
                <input type="checkbox" role="switch" checked={member.journalAccess} disabled={saving !== null}
                  onChange={(event) => void act("journal", `${base}/members/nhatky/journal-access`, { method: "PUT", body: { enabled: event.target.checked, expectedVersion: view.version } }, event.target.checked ? "Nhật ký có thể dùng nhật ký của bạn trong nhóm này." : "Đã tắt. Nhật ký không đọc nhật ký của bạn trong nhóm này nữa.")} />
                <span>Cho Nhật ký dùng nhật ký của bạn trong nhóm này. Câu trả lời của Nhật ký sẽ hiển thị cho các trợ lý khác trong nhóm.</span>
              </label>
            ) : null}
          </li>
        ))}
      </ul>
      {active.length <= 2 ? <p className="group-hint">Nhóm cần ít nhất hai trợ lý.</p> : null}
      {missing.length ? (
        <div className="group-add">
          <h3>Thêm trợ lý</h3>
          <label className="group-share">
            <input type="checkbox" checked={shareHistory} onChange={(event) => setShareHistory(event.target.checked)} />
            <span>Cho trợ lý mới xem các tin nhắn trước đó trong nhóm</span>
          </label>
          {missing.map((agent) => (
            <Button key={agent.id} variant="secondary" disabled={busy || saving !== null}
              onClick={() => void act(`add-${agent.id}`, `${base}/members`, { method: "POST", body: { botId: agent.id, shareHistory, expectedVersion: view.version } }, `Đã thêm ${agent.name}.`)}>
              Thêm {agent.name}
            </Button>
          ))}
        </div>
      ) : null}
      <p className="group-privacy">
        Các trợ lý chỉ thấy tin nhắn trong nhóm này. Cuộc trò chuyện riêng của bạn với từng trợ lý không được đưa vào đây,
        và nhật ký chỉ được dùng khi bạn bật công tắc ở trên.
      </p>
      <p className="group-status" role="status">{status}</p>
      <ErrorNotice error={error} />
      <button ref={deleteTrigger} type="button" className={`${cx.button} ${cx.danger}`} disabled={saving !== null} onClick={() => setConfirmDelete(true)}>Xóa nhóm</button>
      {confirmDelete ? (
        <Dialog destructive title={`Xóa nhóm “${view.name}”?`} returnFocus={deleteTrigger} onClose={() => setConfirmDelete(false)}>
          <p>Toàn bộ tin nhắn trong nhóm sẽ bị xóa và không thể khôi phục. Cuộc trò chuyện riêng với từng trợ lý không bị ảnh hưởng.</p>
          <div className={cx.actions}>
            <Button variant="secondary" data-cancel onClick={() => setConfirmDelete(false)}>Giữ lại</Button>
            <Button variant="danger" disabled={saving !== null} onClick={async () => {
              setSaving("delete");
              try {
                await api.request(`${base}`, { method: "DELETE" });
                onDeleted();
              } catch (reason) {
                setError(reason);
                setConfirmDelete(false);
              } finally {
                setSaving(null);
              }
            }}>Xóa nhóm</Button>
          </div>
        </Dialog>
      ) : null}
    </aside>
  );
}
