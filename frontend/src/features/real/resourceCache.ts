/** Session-scoped reads. A tab can paint the last result and skip a repeat request while it is still fresh. */

const FRESH_MS = 60_000;

type Entry = { data: unknown; at: number; stamp: number };

const store = new Map<string, Entry>();

export function resourceKey(userId: string, path: string) {
  return `${userId}\0${path}`;
}

export function readResource<T>(key: string): { data: T; at: number; stamp: number } | undefined {
  const entry = store.get(key);
  return entry ? { data: entry.data as T, at: entry.at, stamp: entry.stamp } : undefined;
}

export function writeResource(key: string, data: unknown, stamp = 0) {
  store.set(key, { data, at: Date.now(), stamp });
}

export function dropResource(key: string) {
  store.delete(key);
}

export function dropResourcesWithPrefix(userId: string, pathPrefix: string) {
  const prefix = resourceKey(userId, pathPrefix);
  for (const key of store.keys()) {
    if (key.startsWith(prefix)) store.delete(key);
  }
}

export function clearResources() {
  store.clear();
}

export function resourceIsFresh(entry: { at: number; stamp: number } | undefined, stamp = 0) {
  return Boolean(entry && entry.stamp === stamp && Date.now() - entry.at < FRESH_MS);
}
