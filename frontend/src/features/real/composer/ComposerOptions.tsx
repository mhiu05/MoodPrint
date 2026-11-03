import { useEffect, useId, useRef, useState } from "react";
import { Plus, X } from "lucide-react";
import type { PromptCapabilities, PromptOptions } from "../../../api/contracts";
import type { ApiClient } from "../../../api/client";
import "./composer.css";

type Props = { api: ApiClient; botId: string; enabled: boolean; options: PromptOptions;
  onChange: (options: PromptOptions) => void; onFocusComposer: () => void };

export function ComposerOptions({ api, botId, enabled, options, onChange, onFocusComposer }: Props) {
  const [open, setOpen] = useState(false), [skills, setSkills] = useState(false);
  const [view, setView] = useState<PromptCapabilities>(), [failed, setFailed] = useState(false);
  const trigger = useRef<HTMLButtonElement>(null), menu = useRef<HTMLDivElement>(null);
  const id = useId();
  useEffect(() => {
    if (!enabled) return;
    const controller = new AbortController();
    api.request<PromptCapabilities>(`/ai/prompt-capabilities?botId=${encodeURIComponent(botId)}`, { signal: controller.signal })
      .then(v => { if (!controller.signal.aborted) { setView(v); setFailed(false); } })
      .catch(() => { if (!controller.signal.aborted) setFailed(true); });
    return () => controller.abort();
  }, [api, botId, enabled]);
  useEffect(() => {
    if (!open) return;
    menu.current?.querySelector<HTMLButtonElement>("button")?.focus();
    const outside = (event: PointerEvent) => {
      if (!menu.current?.contains(event.target as Node) && !trigger.current?.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener("pointerdown", outside);
    return () => document.removeEventListener("pointerdown", outside);
  }, [open, skills, view]);
  if (!enabled) return null;
  const choose = (next: PromptOptions) => { onChange(next); setOpen(false); setSkills(false); onFocusComposer(); };
  return <div className="composer-option-control" onKeyDown={event => {
    if (event.key === "Escape" && open) { event.preventDefault(); event.stopPropagation(); setOpen(false); trigger.current?.focus(); }
  }}>
    <button type="button" className="icon-button" ref={trigger} aria-label="Thêm kỹ năng hoặc công cụ" aria-expanded={open}
      aria-controls={open ? id : undefined} onClick={() => { setSkills(false); setOpen(v => !v); }}><Plus size={20} /></button>
    {open ? <div id={id} ref={menu} className="composer-options" role="group" aria-label={skills ? "Kỹ năng" : "Kỹ năng và công cụ"}
      onKeyDown={event => { if (event.key === "Escape") { event.preventDefault(); event.stopPropagation(); setOpen(false); trigger.current?.focus(); } }}>
      {failed ? <p role="status">Chưa tải được lựa chọn. Bạn vẫn có thể trò chuyện.</p> : !view ? <p role="status">Đang tải lựa chọn…</p> : skills ? <>
        <button type="button" onClick={() => setSkills(false)}>Quay lại công cụ</button>
        {view.skills.map(skill => <button key={skill.id} type="button" disabled={!skill.available} title={skill.reason ?? undefined}
          onClick={() => choose({ ...options, skillId: skill.id as PromptOptions["skillId"] })}><strong>{skill.name}</strong><small>{skill.available ? skill.description : skill.reason}</small></button>)}
      </> : <>
        {view.tools.map(tool => <button key={tool.id} type="button" disabled={!tool.available} title={tool.reason ?? undefined}
          onClick={() => choose({ ...options, tools: [...new Set([...(options.tools ?? []), tool.id as "web_search" | "maps_search"]) ] })}>
          <strong>{tool.name}</strong><small>{tool.available ? tool.description : tool.reason}</small></button>)}
        <button type="button" onClick={() => setSkills(true)}><strong>Kỹ năng</strong><small>Đi chơi hoặc học điều mới</small></button>
      </>}
    </div> : null}
  </div>;
}

export function PromptChips({ options, onChange, onFocusComposer }: Pick<Props, "options" | "onChange" | "onFocusComposer">) {
  const areaId = useId();
  const remove = (next: PromptOptions) => { onChange(next); onFocusComposer(); };
  return <div className="prompt-options-selection">
    <div className="prompt-chips">
      {options.skillId ? <span>{options.skillId === "hangout" ? "Đi chơi" : "Học điều mới"}<button type="button" aria-label="Bỏ kỹ năng" onClick={() => remove({ ...options, skillId: undefined })}><X size={14} /></button></span> : null}
      {(options.tools ?? []).map(tool => <span key={tool}>{tool === "web_search" ? "Web Search" : "Maps Search"}<button type="button" aria-label={`Bỏ ${tool === "web_search" ? "Web Search" : "Maps Search"}`} onClick={() => remove({ ...options, tools: options.tools?.filter(t => t !== tool), ...(tool === "maps_search" ? { area: undefined } : {}) })}><X size={14} /></button></span>)}
      {options.mapsSearchId ? <span>Kết quả địa điểm<button type="button" aria-label="Bỏ kết quả địa điểm" onClick={() => remove({ ...options, mapsSearchId: undefined })}><X size={14} /></button></span> : null}
    </div>
    {options.tools?.includes("maps_search") ? <div className="maps-area"><label htmlFor={areaId}>Khu vực</label><input id={areaId} aria-describedby={`${areaId}-help`} value={options.area ?? ""} maxLength={120} placeholder="Ví dụ: Quận 3, TP.HCM"
      onChange={e => onChange({ ...options, area: e.target.value })} /><small id={`${areaId}-help`}>Chỉ dùng cho lượt này. Không lấy vị trí tự động.</small></div> : null}
  </div>;
}
