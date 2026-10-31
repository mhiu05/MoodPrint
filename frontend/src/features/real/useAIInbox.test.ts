import { describe, expect, it } from "vitest";
import { EMPTY_INBOX, inboxLabel, otherUnread, unreadFor, withoutConversation } from "./useAIInbox";

const inbox = {
  badgesEnabled: true,
  unreadTotal: 3,
  bots: [
    { botId: "nhip" as const, unread: 2, latest: { conversationId: "c1", runId: "r1", slot: "morning" as const, deliveredAt: "2026-10-31T00:31:00Z", firstSequence: 4 } },
    { botId: "rure" as const, unread: 1, latest: { conversationId: "c2", runId: "r2", slot: "evening" as const, deliveredAt: "2026-10-31T13:00:00Z", firstSequence: 2 } },
  ],
};

describe("assistant inbox helpers", () => {
  it("counts unread per companion and for the others", () => {
    expect(unreadFor(inbox, "nhip")).toBe(2);
    expect(unreadFor(inbox, "may")).toBe(0);
    expect(otherUnread(inbox, "nhip")).toBe(1);
    expect(otherUnread(EMPTY_INBOX, "nhip")).toBe(0);
  });

  it("optimistically clears a conversation that was just read", () => {
    const next = withoutConversation(inbox, "c1");
    expect(next.unreadTotal).toBe(1);
    expect(next.bots.map((bot) => bot.botId)).toEqual(["rure"]);
    expect(withoutConversation(inbox, "unknown")).toBe(inbox);
  });

  it("labels a delivery without any message content", () => {
    expect(inboxLabel(inbox.bots[0].latest, "Nhịp", "Asia/Ho_Chi_Minh")).toBe("Nhịp · Lời hỏi thăm buổi sáng · 07:31");
    expect(inboxLabel(inbox.bots[1].latest, "Rủ Rê", "Asia/Ho_Chi_Minh")).toBe("Rủ Rê · Lời hỏi thăm buổi tối · 20:00");
  });
});
