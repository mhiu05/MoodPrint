import { describe, it, expect, vi } from "vitest";
import {
  initialState,
  sampleProfile,
  candidateSeed,
  scenarios,
} from "../mocks/fixtures";
import {
  reducer,
  visibleChat,
  visibleReveal,
  safeExport,
} from "../state/reducer";
import {
  canChat,
  canMatch,
  effectiveAI,
  effectiveMemory,
  effectiveVoice,
  memoryContext,
  validProfile,
} from "./policies";
import { score, halfUp, recommendations } from "./matching";
import { demoDate, moodSummary } from "./mood";
import { Scheduler } from "../mocks/scheduler";
import type { Action, State, Profile } from "./types";
describe("T-C03 / independently scoped revocation", () => {
  it("MATCH revocation cancels human/activity/reveal while private AI still replies", () => {
    let s = enableAI(connected());
    const id = s.connections[0].id;
    s = reducer(s, { type: "AI_SEND", text: "Ví dụ" });
    s = reducer(s, { type: "HUMAN_SEND", connectionId: id, text: "Chào mẫu" });
    s = reducer(s, {
      type: "REVEAL_REQUEST",
      connectionId: id,
      field: "displayName",
      owner: "self",
    });
    s = reducer(s, {
      type: "REVEAL_DECIDE",
      id: s.reveals[0].id,
      outcome: "accept",
    });
    s = reducer(s, {
      type: "ACTIVITY_INVITE",
      connectionId: id,
      activityId: "ACT01",
    });
    s = reducer(s, {
      type: "ACTIVITY_DECIDE",
      id: s.activities[0].id,
      outcome: "accept",
    });
    s = reducer(s, {
      type: "ACTIVITY_ANSWER",
      id: s.activities[0].id,
      step: 0,
      outcome: "skip",
    });
    const old = s.jobs.filter((j) => j.scope !== "ai").map((j) => j.event);
    s = reducer(s, { type: "PERMISSION", permission: "MATCH", on: false });
    expect(s.reveals[0].status).toBe("revoked");
    expect(s.activities[0].status).toBe("stopped");
    expect(s.jobs.map((j) => j.scope)).toEqual(["ai"]);
    for (const event of old) expect(reducer(s, event)).toBe(s);
    s = runJobs(s);
    expect(s.ai.messages).toHaveLength(2);
    expect(visibleChat(s, id)).toBeUndefined();
  });
  it("a granted field is never inherited by a third connection", () => {
    let s = connected();
    const id = s.connections[0].id;
    s = reducer(s, {
      type: "REVEAL_REQUEST",
      connectionId: id,
      field: "displayName",
      owner: "self",
    });
    s = reducer(s, {
      type: "REVEAL_DECIDE",
      id: s.reveals[0].id,
      outcome: "accept",
    });
    s = reducer(s, { type: "REQUEST_SEND", candidateId: "C03" });
    s = reducer(s, {
      type: "REQUEST_DECIDE",
      id: s.requests.at(-1)!.id,
      outcome: "accept",
    });
    expect(
      visibleReveal(s, s.connections.at(-1)!.id, "displayName", "self", "peer"),
    ).toBeUndefined();
    expect(visibleReveal(s, id, "displayName", "self", "peer")).toBe("An");
  });
});
const adult = () => reducer(initialState(), { type: "START", age: "adult" });
function ready(link = false) {
  let s = adult();
  s = reducer(s, { type: "PERMISSION", permission: "MATCH", on: true });
  const p = sampleProfile();
  if (link) p.sources = [{ id: "PI01", version: 1 }];
  s = reducer(s, { type: "DRAFT", profile: p });
  return reducer(s, { type: "PUBLISH", profile: p });
}
function connected(link = false) {
  let s = ready(link);
  s = reducer(s, { type: "REQUEST_SEND", candidateId: "C01" });
  return reducer(s, {
    type: "REQUEST_DECIDE",
    id: s.requests[0].id,
    outcome: "accept",
  });
}
const enableAI = (s: State) =>
  reducer(s, { type: "PERMISSION", permission: "AI", on: true });
function runJobs(s: State) {
  for (const j of [...s.jobs]) s = reducer(s, j.event);
  return s;
}
describe("T-E01–04 / âge, session, guards", () => {
  it.each(["unknown", "under16"] as const)(
    "refuses %s without private fixtures",
    (age) => {
      const s = reducer(initialState(), { type: "START", age });
      expect(s.ready).toBe(false);
      expect(s.privateItems).toHaveLength(0);
      expect(reducer(s, { type: "PRIVATE_ADD", text: "x" })).toBe(s);
    },
  );
  it("adult starts with all four permissions off", () => {
    expect(Object.values(adult().consent)).toEqual([
      false,
      false,
      false,
      false,
    ]);
  });
  it("teen rejects every executable connection action and adult preset", () => {
    let s = reducer(initialState(), { type: "START", age: "teen" });
    for (const a of [
      { type: "PERMISSION", permission: "MATCH", on: true },
      { type: "PUBLISH", profile: sampleProfile() },
      { type: "REQUEST_SEND", candidateId: "C01" },
      { type: "REQUEST_INBOUND", candidateId: "C03" },
      {
        type: "ACTIVITY_INVITE",
        connectionId: "CON-C01-001",
        activityId: "ACT01",
      },
      { type: "REVEAL_REQUEST", connectionId: "CON-C01-001", field: "gender" },
      { type: "PRESET", preset: "adult-connected" },
    ] as Action[])
      s = reducer(s, a);
    expect(s.age).toBe("teen");
    expect(s.published).toBeUndefined();
    expect(s.requests).toHaveLength(0);
    expect(s.connections).toHaveLength(0);
    expect(s.activities).toHaveLength(0);
    expect(s.reveals).toHaveLength(0);
    expect(visibleChat(s, "CON-C01-001")).toBeUndefined();
    expect(recommendations(s)).toEqual([]);
  });
  it("cannot change age by a second START in-session", () => {
    const s = connected();
    expect(reducer(s, { type: "START", age: "teen" })).toBe(s);
  });
  it("reset makes new epoch and all permissions off, then teen has no adult data", () => {
    const s = connected();
    let n = reducer(s, { type: "RESET" });
    expect(n.epoch).toBe(s.epoch + 1);
    n = reducer(n, { type: "START", age: "teen" });
    expect(n.connections).toEqual([]);
    expect(n.consent.MATCH).toBe(false);
  });
});
describe("T-B01 / matching exact arithmetic", () => {
  it("T-C02 discovery view models exclude identity and private source references", () => {
    const cards = recommendations(ready());
    const payload = JSON.stringify(cards);
    for (const key of [
      "identity",
      "displayName",
      "gender",
      "sources",
      "privateItems",
      "moods",
      "messages",
    ])
      expect(payload).not.toContain(`"${key}"`);
    expect(cards).toHaveLength(4);
  });
  it("gives exact fixture order and filters C05", () => {
    expect(
      recommendations(ready()).map((x) => [x.candidate.id, x.score]),
    ).toEqual([
      ["C04", 90],
      ["C01", 78],
      ["C03", 68],
      ["C02", 44],
    ]);
  });
  it("rounds just below, exactly at and above half correctly", () => {
    expect([
      halfUp(77499, 1000),
      halfUp(77500, 1000),
      halfUp(77501, 1000),
    ]).toEqual([77, 78, 78]);
  });
  it("removes duplicate tags before scoring", () => {
    const a = sampleProfile();
    a.interests.push("reading");
    expect(score(a, candidateSeed()[0].profile)).toBe(78);
  });
  it("rejects unknown tags, insufficient fields, and incompatible styles", () => {
    expect(validProfile({ ...sampleProfile(), interests: ["unknown"] })).toBe(
      false,
    );
    const a = { ...sampleProfile(), style: "direct" };
    expect(score(a, { ...a, style: "listening" })).toBe(80);
  });
  it("uses ASCII pair ID to break ties", () => {
    const s = ready();
    s.candidates.forEach((c) => (c.profile = sampleProfile()));
    expect(recommendations(s).map((r) => r.candidate.id)).toEqual([
      "C01",
      "C02",
      "C03",
      "C04",
      "C05",
    ]);
  });
  it("recomputes on profile change and filters goal/language", () => {
    let s = ready();
    const p = {
      ...sampleProfile(),
      interests: ["english", "puzzles", "cooking"],
      goal: "friendship",
    };
    s = reducer(s, { type: "DRAFT", profile: p });
    s = reducer(s, { type: "PUBLISH", profile: p });
    expect(recommendations(s)).toHaveLength(0);
  });
});
describe("T-A02 / mood arithmetic, latest day and missing data", () => {
  it("3.2 → 3.0 → 3.2 and repeated save is not a duplicate", () => {
    let s = adult();
    expect(moodSummary(s.moods, s.clock).mean).toBe(3.2);
    s = reducer(s, { type: "MOOD_SAVE", value: 2 });
    s = reducer(s, { type: "MOOD_SAVE", value: 2 });
    expect(s.moods).toHaveLength(6);
    expect(moodSummary(s.moods, s.clock).mean).toBe(3);
    s = reducer(s, { type: "MOOD_DELETE", id: s.moods.at(-1)!.id });
    expect(moodSummary(s.moods, s.clock).mean).toBe(3.2);
  });
  it.each([0, 6, 2.5])("rejects invalid value %s", (value) => {
    const s = adult();
    expect(reducer(s, { type: "MOOD_SAVE", value }).moods).toEqual(s.moods);
  });
  it("edits and calculates last record, null never becomes zero", () => {
    let s = adult();
    s = reducer(s, { type: "MOOD_SAVE", value: 5 });
    const sum = moodSummary(s.moods, s.clock);
    expect(sum.buckets[3].entry).toBeNull();
    expect(sum.mean).toBe(3.5);
    const extra = { ...s.moods[0], id: "NEW", value: 1, time: s.clock };
    expect(
      moodSummary([...s.moods, extra], s.clock).buckets[0].entry?.value,
    ).toBe(1);
  });
  it("empty and insufficient have correct number of distinct days", () => {
    let s = adult();
    s = reducer(s, { type: "PRESET", preset: "empty" });
    expect(moodSummary(s.moods, s.clock).mean).toBeNull();
    s = adult();
    s = reducer(s, { type: "PRESET", preset: "insufficient" });
    expect(moodSummary(s.moods, s.clock).count).toBe(2);
    expect(demoDate(s.clock)).toBe("2026-10-22");
  });
});
describe("T-A01/03/04, T-C01 / AI, memory, voice", () => {
  it.each(Object.keys(scenarios))(
    "completes both turns of %s and fallback without publishing",
    (id) => {
      let s = enableAI(adult());
      s = reducer(s, { type: "AI_SCENARIO", id });
      for (let i = 0; i < 3; i++) {
        s = reducer(s, { type: "AI_SEND", text: "Câu mẫu" });
        s = runJobs(s);
      }
      expect(s.ai.messages).toHaveLength(6);
      expect(s.ai.messages.at(-1)!.text).toContain("soạn sẵn");
      expect(s.published).toBeUndefined();
    },
  );
  it("error-once retry adds exactly one reply and does not duplicate user message", () => {
    let s = enableAI(adult());
    s = reducer(s, { type: "ERROR_ONCE" });
    s = reducer(s, { type: "AI_SEND", text: "Ví dụ" });
    s = runJobs(s);
    expect(s.ai.error).toBe(true);
    expect(s.ai.messages).toHaveLength(1);
    s = reducer(s, { type: "AI_RETRY" });
    s = runJobs(s);
    expect(s.ai.messages).toHaveLength(2);
  });
  it.each(["AI_STOP", "RESET", "revoke"] as const)(
    "rejects queued AI after %s",
    (type) => {
      let s = enableAI(adult());
      s = reducer(s, { type: "AI_SEND", text: "Ví dụ" });
      const event = s.jobs[0].event;
      s =
        type === "revoke"
          ? reducer(s, { type: "PERMISSION", permission: "AI", on: false })
          : reducer(s, { type });
      expect(reducer(s, event)).toBe(s);
    },
  );
  it.each([
    [false, false],
    [false, true],
    [true, false],
    [true, true],
  ])("memory effective only when AI=%s and MEM=%s", (ai, mem) => {
    let s = adult();
    s = reducer(s, { type: "PERMISSION", permission: "AI", on: ai });
    s = reducer(s, { type: "PERMISSION", permission: "MEM", on: mem });
    s = reducer(s, { type: "PRIVATE_CHANGE", id: "AI01", outcome: "confirm" });
    expect(s.privateItems[2].memoryApproved).toBe(false);
    s = reducer(s, { type: "PRIVATE_CHANGE", id: "AI01", outcome: "memory" });
    expect(s.privateItems[2].memoryApproved).toBe(ai && mem);
    expect(memoryContext(s).length).toBe(ai && mem ? 1 : 0);
  });
  it("voice requires AI and VOICE, transcript is editable and cancel removes queued result", () => {
    let s = adult();
    s = reducer(s, { type: "PERMISSION", permission: "VOICE", on: true });
    expect(effectiveVoice(s)).toBe(false);
    s = enableAI(s);
    s = reducer(s, { type: "VOICE_START" });
    const event = s.jobs[0].event;
    s = runJobs(s);
    expect(s.ai.voice).toBe("draft");
    s = reducer(s, { type: "VOICE_EDIT", text: "Đã sửa mẫu" });
    expect(s.ai.transcript).toBe("Đã sửa mẫu");
    expect(s.ai.messages).toHaveLength(0);
    s = reducer(s, { type: "VOICE_CANCEL" });
    expect(s.ai.transcript).toBe("");
    expect(reducer(s, event)).toBe(s);
  });
  it("turning AI off preserves mood and independent matching", () => {
    let s = enableAI(ready());
    s = reducer(s, { type: "PERMISSION", permission: "AI", on: false });
    expect(s.moods.length).toBe(5);
    expect(canMatch(s)).toBe(true);
  });
});
describe("T-C02–05 / allowlist, preview, source versions", () => {
  it("refuses injected fields and invalid tags even in incomplete drafts", () => {
    let s = ready();
    const p = { ...sampleProfile(), mood: 2 } as Profile;
    s = reducer(s, { type: "DRAFT", profile: p });
    expect(s.draft).toEqual(sampleProfile());
    const v = s.profileVersion;
    s = reducer(s, { type: "PUBLISH", profile: p });
    expect(s.profileVersion).toBe(v);
    s = reducer(s, {
      type: "DRAFT",
      profile: { ...sampleProfile(), interests: ["unknown"] },
    });
    expect(s.draft.interests).toEqual(sampleProfile().interests);
  });
  it("mood and unlinked private edits do not change score or close room", () => {
    let s = connected();
    const before = s.published;
    s = reducer(s, { type: "MOOD_SAVE", value: 1 });
    s = reducer(s, {
      type: "PRIVATE_CHANGE",
      id: "PI01",
      outcome: "edit",
      text: "Mình đổi ý",
    });
    expect(s.published).toEqual(before);
    expect(canChat(s, s.connections[0])).toBe(true);
  });
  it("editing only a draft leaves published snapshot and open room untouched", () => {
    let s = connected();
    s = reducer(s, {
      type: "DRAFT",
      profile: { ...sampleProfile(), style: "direct" },
    });
    expect(canChat(s, s.connections[0])).toBe(true);
    expect(s.published?.style).toBe("balanced");
  });
  it.each(["edit", "delete"])(
    "linked source %s invalidates entire snapshot and derivatives",
    (outcome) => {
      let s = connected(true);
      s = reducer(s, {
        type: "ACTIVITY_INVITE",
        connectionId: s.connections[0].id,
        activityId: "ACT01",
      });
      s = reducer(s, {
        type: "PRIVATE_CHANGE",
        id: "PI01",
        outcome,
        text: "Đã sửa",
      });
      expect(canMatch(s)).toBe(false);
      expect(s.connections[0].status).toBe("closed");
      expect(s.activities[0].status).toBe("cancelled");
    },
  );
  it("republication closes old rooms and never reuses old IDs", () => {
    let s = connected();
    const old = s.connections[0].id;
    s = reducer(s, { type: "PUBLISH", profile: s.draft });
    expect(visibleChat(s, old)).toBeUndefined();
    s = reducer(s, { type: "CLOCK", days: 31 });
    s = reducer(s, { type: "REQUEST_SEND", candidateId: "C01" });
    s = reducer(s, {
      type: "REQUEST_DECIDE",
      id: s.requests.at(-1)!.id,
      outcome: "accept",
    });
    expect(s.connections.at(-1)!.id).toBe("CON-C01-002");
  });
  it("revoke and re-enable MATCH does not resurrect published data or room", () => {
    let s = connected();
    s = reducer(s, { type: "PERMISSION", permission: "MATCH", on: false });
    s = reducer(s, { type: "PERMISSION", permission: "MATCH", on: true });
    expect(canMatch(s)).toBe(false);
    expect(visibleChat(s, s.connections[0].id)).toBeUndefined();
  });
});
describe("T-B02–04 / mutual, terminal requests, quotas", () => {
  it("pending cannot read chat; accepted twice gives one room", () => {
    let s = ready();
    s = reducer(s, { type: "REQUEST_SEND", candidateId: "C01" });
    expect(visibleChat(s, "CON-C01-001")).toBeUndefined();
    const a = {
      type: "REQUEST_DECIDE",
      id: s.requests[0].id,
      outcome: "accept",
    };
    s = reducer(s, a);
    s = reducer(s, a);
    expect(s.connections).toHaveLength(1);
    expect(canChat(s, s.connections[0])).toBe(true);
  });
  it.each(["cancel", "decline", "expire"])(
    "%s remains terminal after old accept",
    (outcome) => {
      let s = ready();
      s = reducer(s, { type: "REQUEST_SEND", candidateId: "C01" });
      s = reducer(s, { type: "REQUEST_DECIDE", id: s.requests[0].id, outcome });
      s = reducer(s, {
        type: "REQUEST_DECIDE",
        id: s.requests[0].id,
        outcome: "accept",
      });
      expect(s.connections).toHaveLength(0);
    },
  );
  it("inbound and cross requests create one room", () => {
    let s = ready();
    s = reducer(s, { type: "REQUEST_INBOUND", candidateId: "C03" });
    s = reducer(s, { type: "REQUEST_SEND", candidateId: "C03" });
    s = reducer(s, { type: "REQUEST_SEND", candidateId: "C03" });
    expect(s.connections).toHaveLength(1);
  });
  it.each(["stale-request", "expired-request"])(
    "refuses %s fixture",
    (preset) => {
      let s = reducer(ready(), { type: "PRESET", preset });
      s = reducer(s, {
        type: "REQUEST_DECIDE",
        id: s.requests[0].id,
        outcome: "accept",
      });
      expect(s.connections).toHaveLength(0);
    },
  );
  it("expires at seven days and preserves pair cooldown", () => {
    let s = ready();
    s = reducer(s, { type: "REQUEST_SEND", candidateId: "C01" });
    s = reducer(s, { type: "CLOCK", days: 7 });
    expect(s.requests[0].status).toBe("expired");
    expect(recommendations(s).some((r) => r.candidate.id === "C01")).toBe(
      false,
    );
  });
  it("enforces ten outgoing requests / day and ten pending", () => {
    let s = ready();
    s = reducer(s, { type: "REQUEST_SEND", candidateId: "C01" });
    const template = s.requests[0];
    s.requests = Array.from({ length: 10 }, (_, i) => ({
      ...template,
      id: "R" + i,
      candidateId: "other" + i,
    }));
    expect(
      reducer(s, { type: "REQUEST_SEND", candidateId: "C03" }).requests,
    ).toHaveLength(10);
    s.requests.forEach((r) => (r.status = "cancelled"));
    expect(
      reducer(s, { type: "REQUEST_SEND", candidateId: "C03" }).requests,
    ).toHaveLength(10);
  });
  it("human message length, account quota, delayed reply and block guard", () => {
    let s = connected();
    const id = s.connections[0].id;
    for (const text of ["", " ".repeat(2), "x".repeat(501)])
      s = reducer(s, { type: "HUMAN_SEND", connectionId: id, text });
    expect(s.connections[0].messages).toHaveLength(2);
    for (let i = 0; i < 21; i++)
      s = reducer(s, {
        type: "HUMAN_SEND",
        connectionId: id,
        text: "Mẫu " + i,
      });
    expect(s.connections[0].messages).toHaveLength(22);
    const old = s.jobs[0].event;
    s = reducer(s, { type: "BLOCK", candidateId: "C01" });
    expect(reducer(s, old)).toBe(s);
    expect(visibleChat(s, id)).toBeUndefined();
  });
});
describe("T-D01–04 / field, direction, version and safety", () => {
  it("self identity edits leave peer grants and other fields intact", () => {
    let s = reducer(connected(), { type: "PRESET", preset: "reveal-gender" });
    const id = s.connections[0].id;
    for (const [owner, field] of [
      ["self", "displayName"],
      ["peer", "displayName"],
      ["self", "gender"],
    ] as const) {
      s = reducer(s, {
        type: "REVEAL_REQUEST",
        connectionId: id,
        owner,
        field,
      });
      s = reducer(s, {
        type: "REVEAL_DECIDE",
        id: s.reveals.at(-1)!.id,
        outcome: "accept",
      });
    }
    s = reducer(s, { type: "IDENTITY", field: "displayName", text: "Mây Mới" });
    expect(visibleReveal(s, id, "displayName", "self", "peer")).toBeUndefined();
    expect(visibleReveal(s, id, "displayName", "peer", "self")).toBe("Lá");
    expect(visibleReveal(s, id, "gender", "self", "peer")).toBe("Nữ");
  });
  it("one field and direction only; identity change revokes grant", () => {
    let s = connected();
    const id = s.connections[0].id;
    s = reducer(s, {
      type: "REVEAL_REQUEST",
      connectionId: id,
      field: "displayName",
      owner: "self",
    });
    expect(visibleReveal(s, id, "displayName", "self", "peer")).toBeUndefined();
    s = reducer(s, {
      type: "REVEAL_DECIDE",
      id: s.reveals[0].id,
      outcome: "accept",
    });
    expect(visibleReveal(s, id, "displayName", "self", "peer")).toBe("An");
    expect(visibleReveal(s, id, "displayName", "peer", "self")).toBeUndefined();
    expect(visibleReveal(s, id, "gender", "self", "peer")).toBeUndefined();
    s = reducer(s, { type: "IDENTITY", field: "displayName", text: "Mây Mới" });
    expect(visibleReveal(s, id, "displayName", "self", "peer")).toBeUndefined();
  });
  it("gender fixture grants only gender, not name or reverse direction", () => {
    let s = reducer(connected(), { type: "PRESET", preset: "reveal-gender" });
    const id = s.connections[0].id;
    s = reducer(s, {
      type: "REVEAL_REQUEST",
      connectionId: id,
      field: "gender",
      owner: "self",
    });
    s = reducer(s, {
      type: "REVEAL_DECIDE",
      id: s.reveals[0].id,
      outcome: "accept",
    });
    expect(visibleReveal(s, id, "gender", "self", "peer")).toBe("Nữ");
    expect(visibleReveal(s, id, "displayName", "self", "peer")).toBeUndefined();
  });
  it("decline enforces field-direction cooldown and pending expires", () => {
    let s = connected();
    const id = s.connections[0].id;
    const request: Action = {
      type: "REVEAL_REQUEST",
      connectionId: id,
      field: "displayName",
      owner: "self",
    };
    s = reducer(s, request);
    s = reducer(s, {
      type: "REVEAL_DECIDE",
      id: s.reveals[0].id,
      outcome: "decline",
    });
    s = reducer(s, request);
    expect(s.reveals).toHaveLength(1);
    s = reducer(s, { type: "CLOCK", days: 8 });
    s = reducer(s, request);
    expect(s.reveals).toHaveLength(2);
    s = reducer(s, { type: "CLOCK", days: 7 });
    expect(s.reveals[1].status).toBe("expired");
  });
  it("report after block is local, bounded and idempotent, unblock does not reopen", () => {
    let s = reducer(connected(), { type: "BLOCK", candidateId: "C01" });
    s = reducer(s, { type: "REPORT", candidateId: "C01", key: "one" });
    expect(s.reports).toHaveLength(0);
    const a: Action = {
      type: "REPORT",
      candidateId: "C01",
      reason: "pressure",
      key: "one",
      evidence: ["sample-1", "sample-2"],
    };
    s = reducer(s, a);
    s = reducer(s, a);
    expect(s.reports[0].id).toBe("DEMO-R001");
    expect(s.reports).toHaveLength(1);
    s = reducer(s, { type: "UNBLOCK", candidateId: "C01" });
    expect(visibleChat(s, s.connections[0].id)).toBeUndefined();
    expect(JSON.stringify(safeExport(s))).not.toContain("Chào bạn");
  });
});
describe("T-F01–03 / ACT01 contract, cancellation, previews", () => {
  it("two accepts then three distinct answer/skip steps, completion and one feedback", () => {
    let s = connected();
    const connectionId = s.connections[0].id;
    s = reducer(s, {
      type: "ACTIVITY_INVITE",
      connectionId,
      activityId: "ACT01",
    });
    const id = s.activities[0].id;
    s = reducer(s, { type: "ACTIVITY_ANSWER", id, step: 0, outcome: "skip" });
    expect(s.activities[0].answers).toHaveLength(0);
    s = reducer(s, { type: "ACTIVITY_DECIDE", id, outcome: "accept" });
    for (let i = 0; i < 3; i++) {
      s = reducer(s, { type: "ACTIVITY_ANSWER", id, step: i, outcome: "skip" });
      s = runJobs(s);
      s = reducer(s, { type: "ACTIVITY_NEXT", id, step: i });
      s = reducer(s, { type: "ACTIVITY_NEXT", id, step: i });
    }
    expect(s.activities[0].status).toBe("completed");
    s = reducer(s, { type: "ACTIVITY_FEEDBACK", id, outcome: "useful" });
    s = reducer(s, { type: "ACTIVITY_FEEDBACK", id, outcome: "not-useful" });
    expect(s.activities[0].feedback).toBe("useful");
  });
  it("rejects duplicate invitation, preview activity IDs and action query bypass", () => {
    let s = connected();
    const connectionId = s.connections[0].id;
    for (const activityId of ["ACT02", "ACT03", "ACT04"])
      s = reducer(s, { type: "ACTIVITY_INVITE", connectionId, activityId });
    expect(s.activities).toHaveLength(0);
    s = reducer(s, {
      type: "ACTIVITY_INVITE",
      connectionId,
      activityId: "ACT01",
    });
    s = reducer(s, {
      type: "ACTIVITY_INVITE",
      connectionId,
      activityId: "ACT01",
    });
    expect(s.activities).toHaveLength(1);
  });
  it.each(["ACTIVITY_STOP", "BLOCK", "WITHDRAW", "RESET"])(
    "%s invalidates activity pending callback",
    (type) => {
      let s = connected();
      const connectionId = s.connections[0].id;
      s = reducer(s, {
        type: "ACTIVITY_INVITE",
        connectionId,
        activityId: "ACT01",
      });
      const id = s.activities[0].id;
      s = reducer(s, { type: "ACTIVITY_DECIDE", id, outcome: "accept" });
      s = reducer(s, { type: "ACTIVITY_ANSWER", id, step: 0, outcome: "skip" });
      const event = s.jobs[0].event;
      s = reducer(s, { type, id, candidateId: "C01" });
      expect(reducer(s, event)).toBe(s);
    },
  );
});
describe("T-R01–02 / scheduler and transactional reset", () => {
  it("connected setup is explicit before the session and never bypasses teen eligibility", () => {
    const s = reducer(initialState(), {
      type: "START",
      age: "adult",
      preset: "adult-connected",
    });
    expect(s.connections).toHaveLength(1);
    expect(canChat(s, s.connections[0])).toBe(true);
    const teen = reducer(initialState(), {
      type: "START",
      age: "teen",
      preset: "adult-connected",
    });
    expect(teen.consent.MATCH).toBe(false);
    expect(teen.connections).toHaveLength(0);
  });
  it("scheduler cancels obsolete jobs and all timers at reset", () => {
    vi.useFakeTimers();
    const scheduler = new Scheduler();
    const dispatch = vi.fn();
    let s = enableAI(adult());
    s = reducer(s, { type: "AI_SEND", text: "Mẫu" });
    scheduler.sync(s.jobs, dispatch);
    expect(scheduler.size).toBe(1);
    scheduler.sync([], dispatch);
    vi.runAllTimers();
    expect(dispatch).not.toHaveBeenCalled();
    scheduler.sync(s.jobs, dispatch);
    scheduler.clear();
    expect(scheduler.size).toBe(0);
    vi.useRealTimers();
  });
  it("multiple resource jobs reject old epoch even when replayed after new session", () => {
    let s = enableAI(connected());
    s = reducer(s, { type: "AI_SEND", text: "Mẫu" });
    s = reducer(s, {
      type: "HUMAN_SEND",
      connectionId: s.connections[0].id,
      text: "Mẫu",
    });
    const jobs = s.jobs;
    s = reducer(s, { type: "RESET" });
    s = reducer(s, { type: "START", age: "adult" });
    for (const j of jobs) expect(reducer(s, j.event)).toBe(s);
    expect(s.moods).toHaveLength(5);
    expect(s.seq).toBe(0);
  });
});
