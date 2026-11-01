import { useRef, useState } from "react";
import { Link } from "react-router-dom";
import { Dialog } from "../../../components/UI";
import { BotAvatar } from "../../../companions/Avatar";
import type { BotId } from "../../../companions/registry";
import { edgeCopy } from "./collaborationCopy";
import "./collaboration.css";

export type Collaboration = { kind: string; companions: string[]; summary: string };

/**
 * One metadata line above a reply group, shown only when the server attached a summary
 * (a completed, used receipt). The sentence is the backend template, rendered verbatim.
 */
export function CollaborationLine({ line }: { line: Collaboration }) {
  const [open, setOpen] = useState(false);
  const trigger = useRef<HTMLButtonElement>(null);
  const copy = edgeCopy(line.kind);
  const [specialist, requester] = line.companions as [BotId, BotId];
  return (
    <div className="collaboration-line">
      <span className="collaboration-avatars" aria-hidden="true">
        <BotAvatar id={specialist} size={16} />
        <BotAvatar id={requester} size={16} />
      </span>
      <p>
        {line.summary}{" "}
        {copy ? (
          <button ref={trigger} type="button" className="collaboration-why" onClick={() => setOpen(true)}>
            Vì sao?
          </button>
        ) : null}
      </p>
      {open && copy ? (
        <Dialog title={copy.whyTitle} onClose={() => setOpen(false)} returnFocus={trigger}>
          <div className="collaboration-why-body">
            <p>{copy.why}</p>
            <p className="collaboration-why-note">Chỉ những gì bạn đã bật ở cài đặt phối hợp mới được chia sẻ.</p>
            <Link to="/companion-sharing" onClick={() => setOpen(false)}>Đổi cài đặt phối hợp</Link>
          </div>
        </Dialog>
      ) : null}
    </div>
  );
}
