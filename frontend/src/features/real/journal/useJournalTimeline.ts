import { useEffect, useState } from "react";
import type { JournalCollection, JournalEntry } from "../../../api/journal";
import { useSession } from "../RealApp";
import { entryQuery, mergeTimelineEntries } from "./journalModel";
import { useJournalToday } from "./JournalPage";

const pageSize = 12;

function initialDepth() {
  // Only navigation metadata is stored, never journal text or media capabilities.
  if (!sessionStorage.getItem("journal-feed-scroll")) return pageSize;
  const depth = Number(sessionStorage.getItem("journal-feed-depth"));
  return Number.isFinite(depth)
    ? Math.max(pageSize, Math.min(10000, depth))
    : pageSize;
}

export function useJournalTimeline() {
  const { api, paused } = useSession();
  const today = useJournalToday();
  const [depth, setDepth] = useState(initialDepth);
  const [revision, setRevision] = useState(0);
  const [items, setItems] = useState<JournalEntry[]>([]);
  const [total, setTotal] = useState<number>();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>();

  useEffect(() => {
    if (paused) {
      setLoading(false);
      return;
    }
    const controller = new AbortController();
    setLoading(true);
    setError(undefined);
    async function read() {
      // Reconcile the visible prefix: insertions/deletions between clicks must
      // not skip an older moment or leave a ghost row from a stale offset.
      let collected: JournalEntry[] = [];
      let offset = 0;
      let count = 0;
      do {
        const page = await api.request<JournalCollection>(
          `/journal/entries?${entryQuery({ offset, limit: Math.min(50, depth - offset) })}`,
          { signal: controller.signal },
        );
        collected = mergeTimelineEntries(collected, page.items);
        count = page.total;
        offset += page.items.length;
        if (!page.items.length) break;
      } while (offset < Math.min(depth, count));
      if (!controller.signal.aborted) {
        setItems(collected);
        setTotal(count);
      }
    }
    void read()
      .catch((reason) => {
        if (!controller.signal.aborted) setError(reason);
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [api, paused, depth, revision, today]);

  useEffect(() => {
    if (!error || paused) return;
    const retry = () => setRevision((value) => value + 1);
    window.addEventListener("online", retry);
    return () => window.removeEventListener("online", retry);
  }, [error, paused]);

  function remove(id: string) {
    setItems((previous) => previous.filter((entry) => entry.id !== id));
    setTotal((previous) =>
      previous === undefined ? previous : Math.max(0, previous - 1),
    );
    setRevision((value) => value + 1);
  }
  return {
    items,
    total,
    loading,
    error,
    paused,
    hasMore: total !== undefined && items.length < total,
    loadMore: () => {
      if (!loading && !paused) setDepth((value) => value + pageSize);
    },
    refresh: () => setRevision((value) => value + 1),
    remove,
    remember: () => sessionStorage.setItem("journal-feed-depth", String(depth)),
  };
}
