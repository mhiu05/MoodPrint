import { describe, expect, it } from "vitest";
import { initialState, sampleProfile } from "../mocks/fixtures";
import { reducer } from "../state/reducer";
import { canMatch } from "../domain/policies";
import { recommendations } from "../domain/matching";
import { bots, type BotId } from "./registry";
import type { State } from "../domain/types";
const start = () =>
  reducer(initialState(), {
    type: "START",
    age: "adult",
    permissions: { AI: true, MEM: true, MATCH: true, VOICE: false },
  });
const send = (s: State, botId: BotId, text = "Chào bạn") =>
  reducer(s, { type: "AI_BOT_SEND", botId, text });
const finish = (s: State) => s.jobs.reduce((n, j) => reducer(n, j.event), s);
describe("Me2We bot conversations", () => {
  it("creates five separate identities and threads", () => {
    const s = start();
    expect(Object.keys(s.bots)).toHaveLength(5);
    expect(new Set(bots.map((b) => b.intro)).size).toBe(5);
    s.bots.may.messages.push({ id: "private", actor: "self", text: "riêng" });
    expect(s.bots.guong.messages).toHaveLength(1);
  });
  it("scopes simultaneous replies to the originating bot and consumes each once", () => {
    let s = send(
      send(start(), "may", "Chuyện riêng của Mây"),
      "guong",
      "Sở thích riêng của Gương",
    );
    const events = s.jobs.map((j) => j.event);
    s = finish(s);
    expect(s.bots.may.messages).toHaveLength(3);
    expect(s.bots.guong.messages).toHaveLength(3);
    expect(JSON.stringify(s.bots.guong)).not.toContain("Chuyện riêng của Mây");
    expect(JSON.stringify(s.bots.may)).not.toContain(
      "Sở thích riêng của Gương",
    );
    expect(reducer(s, events[0])).toBe(s);
  });
  it("canceling one bot leaves another pending reply intact", () => {
    let s = send(send(start(), "may"), "guong");
    const old = s.jobs[0].event;
    s = reducer(s, { type: "AI_BOT_STOP", botId: "may" });
    expect(s.jobs).toHaveLength(1);
    s = finish(s);
    expect(s.bots.may.messages).toHaveLength(2);
    expect(s.bots.guong.messages).toHaveLength(3);
    expect(reducer(s, old)).toBe(s);
  });
  it("AI revoke cancels every bot, and re-enable does not revive callbacks", () => {
    let s = send(send(start(), "may"), "nhip");
    const events = s.jobs.map((j) => j.event);
    s = reducer(s, { type: "PERMISSION", permission: "AI", on: false });
    expect(s.jobs).toHaveLength(0);
    expect(Object.values(s.bots).every((t) => !t.pending)).toBe(true);
    expect(send(s, "rure")).toBe(s);
    s = reducer(s, { type: "PERMISSION", permission: "AI", on: true });
    for (const event of events) expect(reducer(s, event)).toBe(s);
  });
  it("reset and delete cancel callbacks and remove private messages from all bots", () => {
    let s = send(start(), "may", "secret");
    const old = s.jobs[0].event;
    s = reducer(s, { type: "DELETE_TYPE", outcome: "ai" });
    expect(JSON.stringify(s.bots)).not.toContain("secret");
    expect(reducer(s, old)).toBe(s);
    s = reducer(s, { type: "RESET" });
    expect(s.epoch).toBe(2);
    expect(reducer(s, old)).toBe(s);
  });
  it("rejects oversized, empty and duplicate pending sends", () => {
    const s = start();
    expect(send(s, "may", " ")).toBe(s);
    expect(send(s, "may", "x".repeat(501))).toBe(s);
    const pending = send(s, "may");
    expect(send(pending, "may")).toBe(pending);
  });
  it("requires a valid scheduler token and matching pending key", () => {
    const s = send(start(), "may");
    expect(reducer(s, { type: "AI_BOT_FINISH", botId: "may" })).toBe(s);
    const forged = { ...s.jobs[0].event, botId: "guong" as const };
    expect(reducer(s, forged)).toBe(s);
  });
  it("supports error, retry and read without adding a duplicate user message", () => {
    let s = reducer(start(), { type: "ERROR_ONCE" });
    s = finish(send(s, "may"));
    expect(s.bots.may.error).toBe(true);
    s = finish(reducer(s, { type: "AI_BOT_RETRY", botId: "may" }));
    expect(s.bots.may.messages).toHaveLength(3);
    expect(s.bots.may.unread).toBe(true);
    s = reducer(s, { type: "AI_BOT_READ", botId: "may" });
    expect(s.bots.may.unread).toBe(false);
  });
  it("saves edited Gương suggestions only after confirmation, without memory or publication", () => {
    let s = finish(send(start(), "guong", "Mình thích đọc sách"));
    s = finish(send(s, "guong", "Khoảng yên tĩnh khi đọc sách"));
    const before = s.privateItems.length;
    const message = s.bots.guong.messages.at(-1)!;
    expect(message.card?.kind).toBe("profile");
    expect(s.published).toBeUndefined();
    s = reducer(s, {
      type: "AI_BOT_CARD",
      botId: "guong",
      id: message.id,
      outcome: "save",
      text: "Mình thích đọc thơ",
    });
    expect(s.privateItems).toHaveLength(before + 1);
    expect(s.privateItems.at(-1)).toMatchObject({
      text: "Mình thích đọc thơ",
      status: "confirmed",
      memoryApproved: false,
    });
    expect(s.published).toBeUndefined();
    expect(
      reducer(s, {
        type: "AI_BOT_CARD",
        botId: "guong",
        id: message.id,
        outcome: "save",
      }).privateItems,
    ).toHaveLength(before + 1);
  });
  it("skipping a suggestion never adds a private item", () => {
    let s = finish(send(start(), "guong"));
    s = finish(send(s, "guong"));
    const count = s.privateItems.length;
    s = reducer(s, {
      type: "AI_BOT_CARD",
      botId: "guong",
      id: s.bots.guong.messages.at(-1)!.id,
      outcome: "skip",
    });
    expect(s.privateItems).toHaveLength(count);
  });
  it("mood and private text never affect matching ranking or shared profile", () => {
    let s = reducer(start(), { type: "DRAFT", profile: sampleProfile() });
    s = reducer(s, { type: "PUBLISH", profile: sampleProfile() });
    expect(canMatch(s)).toBe(true);
    const shared = structuredClone(s.published);
    const ranked = recommendations(s).map((r) => [r.candidate.id, r.score]);
    s = reducer(s, {
      type: "AI_BOT_CARD",
      botId: "nhip",
      id: "nhip-intro",
      outcome: "mood",
      value: 2,
    });
    s = finish(send(s, "may", "Mình thích điều không có trong hồ sơ"));
    expect(s.published).toEqual(shared);
    expect(recommendations(s).map((r) => [r.candidate.id, r.score])).toEqual(
      ranked,
    );
  });
  it("has role-specific cards and never creates unsolicited connections", () => {
    let s = start();
    s = finish(send(s, "may", "Ghi lại cảm xúc"));
    s = finish(send(s, "rure", "Giải đố"));
    s = finish(send(s, "caunoi", "Cùng học tiếng Anh"));
    expect(s.bots.may.messages.at(-1)?.card).toEqual({
      kind: "handoff",
      botId: "nhip",
    });
    expect(s.bots.rure.messages.at(-1)?.card?.kind).toBe("activity");
    expect(s.bots.caunoi.messages.at(-1)?.card?.kind).toBe("match");
    expect(s.requests).toHaveLength(0);
    expect(s.connections).toHaveLength(0);
    expect(s.bots.nhip.messages).toHaveLength(1);
  });
});
