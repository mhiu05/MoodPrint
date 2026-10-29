import { Link, useSearchParams } from "react-router-dom";
import type { JournalCollection } from "../../../api/journal";
import { ErrorNotice, useResource, useSession } from "../RealApp";
import { localDate } from "../Mood";
import { JournalEditor } from "./JournalEditor";
import { JournalNav } from "./JournalShared";
import { entryQuery, formatJournalDate, writingPrompts } from "./journalModel";
import "./journal.css";

export function useJournalToday() {
  const { session } = useSession();
  const offset = useMemo(
    () => new Date(session.serverTime).getTime() - Date.now(),
    [session.serverTime],
  );
  const [clock, setClock] = useState(Date.now);
  useEffect(() => {
    const tick = () => setClock(Date.now());
    const interval = setInterval(tick, 60_000);
    window.addEventListener("focus", tick);
    document.addEventListener("visibilitychange", tick);
    return () => {
      clearInterval(interval);
      window.removeEventListener("focus", tick);
      document.removeEventListener("visibilitychange", tick);
    };
  }, []);
  return localDate(clock + offset, session.timezone);
}

export function JournalPage() {
  const today = useJournalToday();
  const [params] = useSearchParams();
  const seedDate = params.get("date") || today;
  const drafts = useResource<JournalCollection>(
    `/journal/entries?${entryQuery({ status: "draft", limit: 5 })}`,
  );
  const promptNumber = Number(params.get("prompt"));
  const prompt =
    params.has("prompt") && Number.isInteger(promptNumber)
      ? writingPrompts[promptNumber]
      : undefined;
  function saved() {
    drafts.refresh();
  }
  return (
    <div className="journal-page">
      <JournalNav />
      <div className="journal-page-content">
        {drafts.data?.items.length ? (
          <details className="journal-drafts">
            <summary>{drafts.data.total} bản nháp đã lưu</summary>
            <ul>
              {drafts.data.items.map((draft) => (
                <li key={draft.id}>
                  <span>
                    {formatJournalDate(draft.localDate)} ·{" "}
                    {draft.text.slice(0, 60) || "Chưa có lời viết"}
                  </span>
                  <Link to={`/self/entry/${draft.id}`}>
                    Mở bản nháp
                    <span className="sr-only">
                      {" "}
                      ngày {formatJournalDate(draft.localDate)}
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          </details>
        ) : null}
        <ErrorNotice error={drafts.error} retry={drafts.refresh} />
        <JournalEditor
          key={`${params.get("date") || "current"}-${params.get("prompt") || ""}`}
          today={today}
          seedDate={seedDate}
          prompt={prompt}
          onSaved={saved}
        />
      </div>
    </div>
  );
}
import { useEffect, useMemo, useState } from "react";
