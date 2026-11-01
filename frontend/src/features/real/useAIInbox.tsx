import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import type { components } from "../../api/generated/schema";
import { useLocation } from "react-router-dom";
import type { ApiClient } from "../../api/client";

export type Inbox = components["schemas"]["InboxView"];
type Latest = components["schemas"]["InboxLatest"];

export const EMPTY_INBOX: Inbox = { badgesEnabled: false, unreadTotal: 0, bots: [] };
const CHANNEL = "moodprint-ai-inbox";
const POLL_MS = 30_000;

export function unreadFor(inbox: Inbox, botId: string) {
  return inbox.bots.find((bot) => bot.botId === botId)?.unread ?? 0;
}

export function otherUnread(inbox: Inbox, botId: string) {
  return inbox.unreadTotal - unreadFor(inbox, botId);
}

/** Drop a conversation the user just read (the next poll confirms the exact counts). */
export function withoutConversation(inbox: Inbox, conversationId: string): Inbox {
  const bots = inbox.bots.filter((bot) => bot.latest.conversationId !== conversationId);
  if (bots.length === inbox.bots.length) return inbox;
  return { ...inbox, bots, unreadTotal: bots.reduce((sum, bot) => sum + bot.unread, 0) };
}

export function deliveryTime(latest: Latest, timeZone: string) {
  return new Intl.DateTimeFormat("vi-VN", { timeZone, hour: "2-digit", minute: "2-digit", hourCycle: "h23" })
    .format(new Date(latest.deliveredAt));
}

export function inboxLabel(latest: Latest, botName: string, timeZone: string) {
  const slot = latest.slot === "morning" ? "buổi sáng" : "buổi tối";
  return `${botName} · Lời hỏi thăm ${slot} · ${deliveryTime(latest, timeZone)}`;
}

type InboxContext = {
  inbox: Inbox;
  refresh: () => void;
  markRead: (conversationId: string, sequence: number) => Promise<void>;
  markAll: () => Promise<void>;
};

const Context = createContext<InboxContext>({
  inbox: EMPTY_INBOX,
  refresh: () => undefined,
  markRead: async () => undefined,
  markAll: async () => undefined,
});

export function useAIInbox() {
  return useContext(Context);
}

/**
 * Unread check-ins: polled every 30 s while visible, refreshed on focus, and shared across
 * tabs through a BroadcastChannel that carries only ids and sequences, never message text.
 */
export function AIInboxProvider({ api, enabled, children }: { api: ApiClient; enabled: boolean; children: ReactNode }) {
  const [inbox, setInbox] = useState<Inbox>(EMPTY_INBOX);
  const channel = useRef<BroadcastChannel | null>(null);
  const { pathname } = useLocation();
  const refresh = useCallback(() => {
    if (!enabled) return;
    // Advisory counts: a failed poll keeps the last known state.
    api.request<Inbox>("/ai/inbox").then(setInbox).catch(() => undefined);
  }, [api, enabled]);
  useEffect(() => {
    if (!enabled) {
      setInbox(EMPTY_INBOX);
      return;
    }
    refresh();
    const visible = () => {
      if (document.visibilityState === "visible") refresh();
    };
    const timer = window.setInterval(visible, POLL_MS);
    window.addEventListener("focus", refresh);
    document.addEventListener("visibilitychange", visible);
    let peer: BroadcastChannel | null = null;
    if (typeof BroadcastChannel !== "undefined") {
      peer = new BroadcastChannel(CHANNEL);
      peer.onmessage = (event: MessageEvent<{ type?: string; conversationId?: string }>) => {
        if (event.data?.type === "read" && typeof event.data.conversationId === "string") {
          setInbox((value) => withoutConversation(value, event.data.conversationId!));
        }
        refresh();
      };
      channel.current = peer;
    }
    return () => {
      window.clearInterval(timer);
      window.removeEventListener("focus", refresh);
      document.removeEventListener("visibilitychange", visible);
      peer?.close();
      channel.current = null;
    };
  }, [enabled, refresh]);
  useEffect(() => {
    // Moving between screens is a natural moment to pick up a check-in that just arrived.
    refresh();
  }, [pathname, refresh]);
  const markRead = useCallback(async (conversationId: string, sequence: number) => {
    if (!enabled) return;
    await api.request(`/ai/conversations/${encodeURIComponent(conversationId)}/read`, {
      method: "PUT",
      body: { lastReadSequence: sequence },
    });
    setInbox((value) => withoutConversation(value, conversationId));
    channel.current?.postMessage({ type: "read", conversationId, sequence });
    refresh();
  }, [api, enabled, refresh]);
  const markAll = useCallback(async () => {
    if (!enabled) return;
    const value = await api.request<Inbox>("/ai/inbox/read-all", { method: "POST", body: {} });
    setInbox(value);
    channel.current?.postMessage({ type: "refresh" });
  }, [api, enabled]);
  const value = useMemo(() => ({ inbox, refresh, markRead, markAll }), [inbox, refresh, markRead, markAll]);
  return <Context.Provider value={value}>{children}</Context.Provider>;
}
