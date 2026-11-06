import { useEffect, useRef, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { Plus } from "lucide-react";
import type { components } from "../../../api/generated/schema";
import { botById } from "../../../companions/registry";
import { ErrorNotice, useSession } from "../RealApp";
import { readResource, resourceIsFresh, resourceKey, writeResource } from "../resourceCache";
import { AvatarStack } from "./GroupChat";
import "./groups.css";

type Header = components["schemas"]["GroupHeader"];

/** "Nhóm" in the assistant roster: the user's AI groups and the way to start one. */
export function GroupsSection({ selected }: { selected?: string }) {
  const { api, session } = useSession();
  const location = useLocation();
  const key = resourceKey(session.userId, "/ai/groups");
  const cached = readResource<Header[]>(key);
  const [groups, setGroups] = useState<Header[] | undefined>(cached?.data);
  const [error, setError] = useState<unknown>();
  const [revision, setRevision] = useState(0);
  const place = useRef(cached ? location.pathname : "");
  useEffect(() => {
    if (!location.pathname.startsWith("/assistants")) return;
    const hit = readResource<Header[]>(key);
    const samePlace = place.current === location.pathname;
    if (hit) setGroups(hit.data);
    if (revision === 0 && samePlace && resourceIsFresh(hit)) return;
    const controller = new AbortController();
    api.request<Header[]>("/ai/groups", { signal: controller.signal })
      .then((value) => {
        if (controller.signal.aborted) return;
        place.current = location.pathname;
        writeResource(key, value);
        setGroups(value);
        setError(undefined);
      })
      .catch((reason) => !controller.signal.aborted && setError(reason));
    return () => controller.abort();
  }, [api, key, location.pathname, revision]);
  return (
    <section className="group-roster" aria-labelledby="groups-heading">
      <div className="group-roster-head">
        <h2 id="groups-heading">Nhóm</h2>
        <Link to="/assistants/groups/new" className="group-new"><Plus size={16} aria-hidden="true" /> Tạo nhóm</Link>
      </div>
      {groups === undefined && !error ? <p role="status" className="group-hint">Đang tải nhóm…</p> : null}
      <ErrorNotice error={error} retry={() => setRevision((value) => value + 1)} />
      {groups && !groups.length ? (
        <p className="group-hint">Trò chuyện cùng lúc với nhiều trợ lý: tạo một nhóm và gọi riêng ai bằng @.</p>
      ) : null}
      {groups?.length ? (
        <ul className="group-list">
          {groups.map((group) => {
            const active = group.members.filter((member) => member.status === "active").map((member) => member.botId);
            const names = active.map((id) => botById(id)?.name ?? id).join(", ");
            return (
              <li key={group.groupId}>
                <Link to={`/assistants/groups/${group.groupId}`} className={`group-row ${selected === group.groupId ? "selected" : ""}`}
                  aria-current={selected === group.groupId ? "page" : undefined}
                  aria-label={group.unread ? `${group.name}, nhóm với ${names}, ${group.unread} tin mới` : `${group.name}, nhóm với ${names}`}>
                  <AvatarStack ids={active} size={26} />
                  <span className="group-row-text">
                    <strong>{group.name}</strong>
                    <small>{names}</small>
                  </span>
                  {group.unread ? <span className="roster-unread" aria-hidden="true">{group.unread > 9 ? "9+" : group.unread}</span> : null}
                </Link>
              </li>
            );
          })}
        </ul>
      ) : null}
    </section>
  );
}
