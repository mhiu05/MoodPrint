import { describe, expect, it } from "vitest";
import {
  canInvite,
  endedMessage,
  isMyTurn,
  shortStatus,
  waitingLabel,
  type Session,
} from "./activityView";

function session(patch: Partial<Session> = {}): Session {
  return {
    id: "s1",
    connectionId: "c1",
    kind: "icebreaker",
    definitionVersion: "icebreaker-v1",
    state: "active",
    version: 3,
    role: "inviter",
    createdAt: "2026-10-25T09:00:00Z",
    serverTime: "2026-10-25T09:01:00Z",
    self: { accepted: true, readyRound: 0, feedbackGiven: false },
    peer: { accepted: true, readyRound: 0 },
    progress: { round: 1, totalRounds: 3, phase: "answering" },
    current: {
      item: { id: "i1", prompt: "?", options: ["a", "b", "c"], allowText: true },
      peerSubmitted: false,
    },
    history: [],
    ...patch,
  } as Session;
}

describe("activity view helpers", () => {
  it("knows whose turn it is", () => {
    expect(isMyTurn(session())).toBe(true);
    const answered = session({
      current: { ...session().current!, selfResponse: { choice: 0, skipped: false } },
    });
    expect(isMyTurn(answered)).toBe(false);
    const revealed = session({ progress: { round: 1, totalRounds: 3, phase: "revealed" } });
    expect(isMyTurn(revealed)).toBe(true);
    expect(isMyTurn(session({ ...revealed, self: { accepted: true, readyRound: 1, feedbackGiven: false } }))).toBe(false);
    expect(isMyTurn(session({ state: "invited" }))).toBe(false);
    expect(isMyTurn(null)).toBe(false);
  });

  it("explains what we are waiting for", () => {
    expect(waitingLabel(session({ state: "invited" }), "B")).toBe("Đang chờ B đồng ý…");
    expect(waitingLabel(session({ state: "invited", role: "invitee" }), "B")).toBeNull();
    const answered = session({
      current: { ...session().current!, selfResponse: { choice: 0, skipped: false } },
    });
    expect(waitingLabel(answered, "B")).toBe("Đang chờ B trả lời…");
    const ready = session({
      progress: { round: 2, totalRounds: 3, phase: "revealed" },
      self: { accepted: true, readyRound: 2, feedbackGiven: false },
      peer: { accepted: true, readyRound: 1 },
    });
    expect(waitingLabel(ready, "B")).toBe("Đang chờ B…");
  });

  it("summarizes progress for the collapsed bar", () => {
    expect(shortStatus(session())).toBe("Câu 1/3 · Đến lượt bạn");
    expect(shortStatus(session({ kind: "coop_quiz", progress: { round: 2, totalRounds: 5, phase: "revealed" }, self: { accepted: true, readyRound: 2, feedbackGiven: false } }))).toBe("Vòng 2/5");
    expect(shortStatus(session({ state: "invited", role: "invitee" }))).toBe("Lời mời mới");
  });

  it("allows an invite only without an open session or a decline cooldown", () => {
    const now = Date.parse("2026-10-25T09:00:00Z");
    expect(canInvite(null, "icebreaker", {}, now)).toBe(true);
    expect(canInvite(session(), "icebreaker", {}, now)).toBe(false);
    expect(canInvite(session({ state: "completed" }), "icebreaker", {}, now)).toBe(true);
    expect(canInvite(null, "icebreaker", { icebreaker: now + 60_000 }, now)).toBe(false);
    expect(canInvite(null, "focus", { icebreaker: now + 60_000 }, now)).toBe(true);
  });

  it("describes endings relative to the viewer", () => {
    expect(endedMessage(session({ state: "declined", endReason: "invite_declined" }), "B")).toBe(
      "B chưa muốn chơi lúc này",
    );
    expect(endedMessage(session({ state: "aborted", endReason: "blocked" }), "B")).toBe(
      "Hoạt động đã dừng vì kết nối không còn khả dụng",
    );
  });
});
