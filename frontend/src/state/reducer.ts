import { scriptedReply } from "../companions/scenarios";
import { botById, initialThreads } from "../companions/registry";
import type { Action, Connection, Job, Profile, State } from "../domain/types";
import {
  initialState,
  seedSession,
  scenarios,
  fallback,
  humanReplies,
  peerReplies,
  questions,
  sampleProfile,
  interests,
  values,
  languages,
  styles,
  goals,
} from "../mocks/fixtures";
import {
  canChat,
  canMatch,
  effectiveAI,
  effectiveMemory,
  effectiveVoice,
  sessionAllowed,
  sourceValid,
  tokenFor,
  tokenValid,
  validProfile,
} from "../domain/policies";
import { eligibility, recommendations } from "../domain/matching";
import { demoDate } from "../domain/mood";
const DAY = 86400000;
const uid = (s: State, prefix: string) =>
  `${prefix}-${String(++s.seq).padStart(3, "0")}`;
const tell = (s: State, text: string) => {
  s.notice = text;
  return s;
};
function close(s: State, candidateId?: string, blocked = false) {
  const affected = (id: string) => !candidateId || id === candidateId;
  s.requests.forEach((r) => {
    if (affected(r.candidateId) && r.status === "pending") {
      r.status = "invalidated";
      s.cooldowns[r.candidateId] = s.clock + 30 * DAY;
    }
  });
  s.connections.forEach((c) => {
    if (affected(c.candidateId) && c.status === "open") {
      c.status = blocked ? "blocked" : "closed";
      c.pending = undefined;
      s.cooldowns[c.candidateId] = s.clock + 30 * DAY;
    }
  });
  const ids = s.connections
    .filter((c) => affected(c.candidateId))
    .map((c) => c.id);
  s.reveals.forEach((r) => {
    if (
      ids.includes(r.connectionId) &&
      ["pending", "granted"].includes(r.status)
    )
      r.status = "revoked";
  });
  s.activities.forEach((a) => {
    if (
      ids.includes(a.connectionId) &&
      ["pending", "active"].includes(a.status)
    ) {
      a.status = a.status === "active" ? "stopped" : "cancelled";
      a.pending = undefined;
    }
  });
  s.jobs = s.jobs.filter(
    (j) => j.scope === "ai" || j.scope === "voice" || !ids.includes(j.scope),
  );
}
function invalidate(s: State) {
  if (s.published) s.published.valid = false;
  close(s);
}
function stopAI(s: State) {
  Object.values(s.bots).forEach((t) => {
    t.pending = undefined;
    t.error = false;
  });
  s.ai.pending = undefined;
  s.ai.voice = "idle";
  s.ai.transcript = "";
  s.jobs = s.jobs.filter((j) => j.scope !== "ai" && j.scope !== "voice");
}
function job(
  s: State,
  scope: string,
  delay: number,
  event: Action,
  candidateId?: string,
) {
  const id = uid(s, "JOB");
  const token = tokenFor(s, candidateId);
  s.jobs.push({
    id,
    scope,
    delay,
    token,
    event: { ...event, token, epoch: s.epoch, key: id },
  });
  return id;
}
function expire(s: State) {
  s.requests.forEach((r) => {
    if (r.status === "pending" && r.expires <= s.clock) {
      r.status = "expired";
      s.cooldowns[r.candidateId] = s.clock + 30 * DAY;
    }
  });
  s.reveals.forEach((r) => {
    if (r.status === "pending" && r.expires <= s.clock) r.status = "expired";
  });
}
function requestValid(s: State, r: State["requests"][number]) {
  const p = s.candidates.find((c) => c.id === r.candidateId);
  return (
    canMatch(s) &&
    r.status === "pending" &&
    r.expires > s.clock &&
    !s.blocked.includes(r.candidateId) &&
    r.profileVersion === s.published!.version &&
    r.matchVersion === s.versions.MATCH &&
    !!p &&
    p.allowed &&
    p.version === r.peerVersion &&
    p.consentVersion === r.peerConsentVersion &&
    eligibility(s.published!, p)
  );
}
function openConnection(s: State, r: State["requests"][number]) {
  if (!requestValid(s, r)) {
    r.status = "invalidated";
    return tell(s, "Lời mời này đã hết hạn hoặc không còn hợp lệ.");
  }
  r.status = "accepted";
  if (
    s.connections.some((c) => c.candidateId === r.candidateId && canChat(s, c))
  )
    return s;
  const count =
    s.connections.filter((c) => c.candidateId === r.candidateId).length + 1;
  const c: Connection = {
    id: `CON-${r.candidateId}-${String(count).padStart(3, "0")}`,
    candidateId: r.candidateId,
    status: "open",
    profileVersion: r.profileVersion,
    matchVersion: r.matchVersion,
    peerVersion: r.peerVersion,
    peerConsentVersion: r.peerConsentVersion,
    selfAccepted: true,
    peerAccepted: true,
    replyTurn: 0,
    messages: [
      {
        id: uid(s, "MSG"),
        actor: "peer",
        text: `Chào bạn! Mình cũng thích ${
          s
            .published!.interests.filter((x) =>
              s.candidates
                .find((p) => p.id === r.candidateId)!
                .profile.interests.includes(x),
            )
            .slice(0, 2)
            .map((x) =>
              interests[x as keyof typeof interests].toLocaleLowerCase("vi-VN"),
            )
            .join(" và ") || "khám phá điều mới"
        }. Rất vui được làm quen!`,
        scripted: true,
        at: s.clock,
      },
      {
        id: uid(s, "MSG"),
        actor: "self",
        text: "Mình muốn thử một câu hỏi làm quen",
        scripted: true,
        at: s.clock,
      },
    ],
  };
  s.connections.push(c);
  return tell(s, "Hai nhân vật đã đồng ý kết nối. Bạn có thể mở trò chuyện.");
}
export function reducer(state: State, a: Action): State {
  if (a.type === "RESET") return initialState(state.epoch + 1);
  if (a.epoch !== undefined && a.epoch !== state.epoch) return state;
  if (a.type === "START") {
    if (state.ready || !["teen", "adult"].includes(a.age || "")) return state;
    const s = initialState(state.epoch);
    s.ready = true;
    s.age = a.age!;
    seedSession(s);
    if (a.permissions)
      for (const p of ["AI", "MEM", "MATCH", "VOICE"] as const) {
        s.consent[p] =
          !!a.permissions[p] && (p !== "MATCH" || s.age === "adult");
        if (s.consent[p]) s.versions[p]++;
      }
    s.fixtureId = a.preset || "fresh";
    if (a.preset === "adult-ready-to-publish") s.draft = sampleProfile();
    if (a.preset === "empty") s.moods = [];
    if (a.preset === "insufficient") s.moods = s.moods.slice(-2);
    if (a.preset === "adult-connected" && s.age === "adult") {
      // Explicit facilitator setup only, selected before the age/session is created.
      let n = reducer(s, { type: "PERMISSION", permission: "MATCH", on: true });
      n = reducer(n, { type: "DRAFT", profile: sampleProfile() });
      n = reducer(n, { type: "PUBLISH", profile: sampleProfile() });
      n = reducer(n, { type: "REQUEST_SEND", candidateId: "C01" });
      n = reducer(n, {
        type: "REQUEST_DECIDE",
        id: n.requests[0].id,
        outcome: "accept",
      });
      return tell(
        n,
        "Phiên kiểm thử nội bộ: hồ sơ và hai đồng ý kết nối được nạp sẵn từ dữ liệu giả.",
      );
    }
    return tell(s, "Đã sẵn sàng cho phiên demo.");
  }
  if (!sessionAllowed(state)) return state;
  const s = structuredClone(state);
  s.notice = "";
  expire(s);
  const c = s.connections.find((x) => x.id === a.connectionId);
  const peer = s.candidates.find(
    (x) => x.id === (a.candidateId || c?.candidateId),
  );
  if (
    a.token &&
    !tokenValid(
      s,
      a.token,
      a.type.startsWith("AI_")
        ? "ai"
        : a.type.startsWith("VOICE_")
          ? "voice"
          : "connection",
      peer?.id,
    )
  )
    return state;
  // A callback can only consume its still-pending scheduler job once.
  if (a.token) {
    if (!a.key || !s.jobs.some((j) => j.id === a.key)) return state;
    s.jobs = s.jobs.filter((j) => j.id !== a.key);
  }
  const thread = a.botId && botById(a.botId) ? s.bots[a.botId] : undefined;
  if (a.type.startsWith("AI_BOT_")) {
    if (!effectiveAI(s) || !thread || !a.botId) return state;
    switch (a.type) {
      case "AI_BOT_READ":
        thread.unread = false;
        return s;
      case "AI_BOT_STOP":
        s.jobs = s.jobs.filter((j) => j.id !== thread.pending);
        thread.pending = undefined;
        return s;
      case "AI_BOT_SEND":
        if (thread.pending || !a.text?.trim() || a.text.trim().length > 500)
          return state;
        thread.lastInput = a.text.trim();
        thread.error = false;
        thread.messages.push({
          id: uid(s, "BOTMSG"),
          actor: "self",
          text: thread.lastInput,
        });
        thread.pending = job(s, "ai", 650, {
          type: "AI_BOT_FINISH",
          botId: a.botId,
          outcome: s.errorOnce ? "error" : "reply",
        });
        s.errorOnce = false;
        return s;
      case "AI_BOT_RETRY":
        if (thread.pending || !thread.error) return state;
        thread.error = false;
        thread.pending = job(s, "ai", 650, {
          type: "AI_BOT_FINISH",
          botId: a.botId,
          outcome: "reply",
        });
        return s;
      case "AI_BOT_FINISH":
        if (!a.token || thread.pending !== a.key) return state;
        thread.pending = undefined;
        if (a.outcome === "error") {
          thread.error = true;
          return s;
        }
        thread.messages.push({
          id: uid(s, "BOTMSG"),
          actor: "bot",
          ...scriptedReply(a.botId, thread.lastInput, thread.turn),
        });
        thread.turn++;
        thread.unread = true;
        return s;
      case "AI_BOT_CARD": {
        const card = thread.messages.find((m) => m.id === a.id)?.card;
        if (!card) return state;
        if (card.kind === "profile" && !card.decision) {
          if (a.outcome === "save") {
            const text = (a.text || card.text).trim();
            if (!text || text.length > 120) return state;
            card.text = text;
            card.decision = "saved";
            s.privateItems.push({
              id: uid(s, "PI"),
              text,
              origin: "ai",
              status: "confirmed",
              version: 1,
              memoryApproved: false,
            });
          } else if (a.outcome === "skip") card.decision = "skipped";
        }
        if (card.kind === "activity") card.revealed = true;
        if (
          card.kind === "mood" &&
          Number.isInteger(a.value) &&
          a.value! >= 1 &&
          a.value! <= 5
        ) {
          card.value = a.value;
          return reducer(s, {
            type: "MOOD_SAVE",
            value: a.value,
            date: demoDate(s.clock),
            text: "",
          });
        }
        return s;
      }
      default:
        return state;
    }
  }
  switch (a.type) {
    case "NOTICE":
      return tell(s, a.text || "");
    case "PERMISSION": {
      const p = a.permission;
      if (!p || !["AI", "MEM", "MATCH", "VOICE"].includes(p)) return state;
      if (p === "MATCH" && s.age !== "adult")
        return tell(s, "Nhân vật 16–17 tuổi chỉ xem nháp và ví dụ kết nối.");
      if (s.consent[p] === !!a.on) return state;
      s.consent[p] = !!a.on;
      s.versions[p]++;
      if (!a.on) {
        if (p === "AI") stopAI(s);
        if (p === "VOICE") {
          s.ai.voice = "idle";
          s.ai.transcript = "";
          s.jobs = s.jobs.filter((j) => j.scope !== "voice");
        }
        if (p === "MATCH") invalidate(s);
      }
      return tell(
        s,
        a.on
          ? "Đã bật quyền trong phiên demo."
          : "Đã ngừng sử dụng mục đích này trong demo.",
      );
    }
    case "AI_SCENARIO":
      if (!effectiveAI(s)) return state;
      stopAI(s);
      s.ai.scenario = Object.hasOwn(scenarios, a.id || "") ? a.id! : "";
      s.ai.turn = 0;
      s.ai.error = false;
      return s;
    case "AI_SEND": {
      if (
        !effectiveAI(s) ||
        s.ai.pending ||
        !a.text?.trim() ||
        a.text.trim().length > 500
      )
        return tell(s, "Bạn viết một câu từ 1 đến 500 ký tự nhé.");
      s.ai.last = a.text.trim();
      s.ai.error = false;
      s.ai.messages.push({
        id: uid(s, "MSG"),
        actor: "self",
        text: a.text.trim(),
        scripted: false,
        at: s.clock,
      });
      const fail = s.errorOnce;
      s.errorOnce = false;
      s.ai.pending = job(s, "ai", 700, {
        type: "AI_FINISH",
        outcome: fail ? "error" : "reply",
      });
      return s;
    }
    case "AI_RETRY": {
      if (!effectiveAI(s) || !s.ai.error || s.ai.pending) return state;
      s.ai.error = false;
      s.ai.pending = job(s, "ai", 700, { type: "AI_FINISH", outcome: "reply" });
      return s;
    }
    case "AI_FINISH": {
      if (!a.token || !effectiveAI(s) || s.ai.pending !== a.key) return state;
      s.ai.pending = undefined;
      if (a.outcome === "error") {
        s.ai.error = true;
        return tell(s, "Chưa hiện được phản hồi mẫu. Bạn có thể thử lại.");
      }
      const scenario = scenarios[s.ai.scenario as keyof typeof scenarios];
      const text = scenario?.replies[s.ai.turn] || fallback;
      s.ai.messages.push({
        id: uid(s, "MSG"),
        actor: "ai",
        text,
        scripted: true,
        at: s.clock,
      });
      if (
        s.ai.turn === 1 &&
        s.ai.scenario === "AIC02" &&
        !s.privateItems.some((x) => x.id === "AI02")
      )
        s.privateItems.push({
          id: "AI02",
          text: "Có thể bạn thích đọc sách vào lúc nghỉ",
          origin: "ai",
          status: "proposed",
          version: 1,
          memoryApproved: false,
        });
      s.ai.turn++;
      return s;
    }
    case "AI_STOP":
      if (!s.ai.pending && s.ai.voice === "idle" && !s.ai.transcript)
        return state;
      stopAI(s);
      return tell(s, "Đã dừng phản hồi mẫu.");
    case "VOICE_START":
      if (!effectiveVoice(s) || s.ai.voice === "loading") return state;
      s.ai.voice = "loading";
      s.ai.transcript = "";
      job(s, "voice", 700, {
        type: "VOICE_FINISH",
        outcome: s.errorOnce ? "error" : "reply",
      });
      s.errorOnce = false;
      return s;
    case "VOICE_FINISH":
      if (!a.token || !effectiveVoice(s) || s.ai.voice !== "loading")
        return state;
      s.ai.voice = a.outcome === "error" ? "error" : "draft";
      s.ai.transcript =
        a.outcome === "error"
          ? ""
          : "Hôm nay mình muốn dành chút thời gian đọc sách";
      return s;
    case "VOICE_EDIT":
      if (!effectiveVoice(s) || s.ai.voice !== "draft") return state;
      s.ai.transcript = (a.text || "").slice(0, 500);
      return s;
    case "VOICE_CANCEL":
      s.ai.voice = "idle";
      s.ai.transcript = "";
      s.jobs = s.jobs.filter((j) => j.scope !== "voice");
      return s;
    case "MOOD_SAVE": {
      if (
        !Number.isInteger(a.value) ||
        a.value! < 1 ||
        a.value! > 5 ||
        (a.text || "").length > 120
      )
        return tell(
          s,
          "Bạn chọn một mức từ 1 đến 5 và ghi chú tối đa 120 ký tự nhé.",
        );
      const date = a.date || demoDate(s.clock);
      if (
        !/^\d{4}-\d{2}-\d{2}$/.test(date) ||
        !Number.isFinite(Date.parse(date)) ||
        new Date(date).toISOString().slice(0, 10) !== date ||
        date > demoDate(s.clock)
      )
        return state;
      const old = s.moods.find((m) => (a.id ? m.id === a.id : m.date === date));
      if (a.id && !old) return state;
      if (old) {
        old.value = a.value!;
        old.note = a.text || "";
        old.version++;
        old.time = ++s.seq + s.clock;
      } else
        s.moods.push({
          id: uid(s, "MD"),
          date,
          value: a.value!,
          note: a.text || "",
          version: 1,
          time: s.clock + s.seq,
        });
      return tell(s, "Đã lưu tâm trạng trong phiên demo.");
    }
    case "MOOD_DELETE":
      s.moods = s.moods.filter((x) => x.id !== a.id);
      return tell(s, "Đã xóa ghi nhận trong phiên demo.");
    case "PRIVATE_ADD":
      if (!a.text?.trim() || a.text.length > 120)
        return tell(s, "Bạn viết từ 1 đến 120 ký tự nhé.");
      s.privateItems.push({
        id: uid(s, "PI"),
        text: a.text.trim(),
        origin: "declared",
        status: "confirmed",
        version: 1,
        memoryApproved: false,
      });
      return tell(s, "Đã thêm mục riêng trong phiên demo.");
    case "PRIVATE_CHANGE": {
      const item = s.privateItems.find((x) => x.id === a.id);
      if (!item || item.status === "deleted" || item.status === "rejected")
        return state;
      if (a.outcome === "memory") {
        if (
          !effectiveMemory(s) ||
          item.origin !== "ai" ||
          !["confirmed", "edited"].includes(item.status)
        )
          return tell(
            s,
            "Cần bật trò chuyện AI và ghi nhớ, rồi xác nhận nhận xét trước.",
          );
        item.memoryApproved = true;
        return tell(s, "Đã lưu ghi nhớ trong phiên demo.");
      }
      if (!["confirm", "edit", "reject", "delete"].includes(a.outcome || ""))
        return state;
      if (a.outcome === "edit" && (!a.text?.trim() || a.text.length > 120))
        return tell(s, "Bạn viết từ 1 đến 120 ký tự nhé.");
      if (
        ["edit", "delete", "reject"].includes(a.outcome!) &&
        s.published?.valid &&
        s.published.sources.some(
          (r) => r.id === item.id && r.version === item.version,
        )
      )
        invalidate(s);
      item.status =
        a.outcome === "confirm"
          ? "confirmed"
          : a.outcome === "edit"
            ? "edited"
            : a.outcome === "reject"
              ? "rejected"
              : "deleted";
      if (a.outcome === "edit") item.text = a.text!.trim();
      item.version++;
      return tell(s, "Đã cập nhật mục hồ sơ trong phiên demo.");
    }
    case "DRAFT": {
      const p = a.profile;
      if (
        !p ||
        Object.keys(p).some(
          (k) =>
            ![
              "interests",
              "values",
              "style",
              "goal",
              "languages",
              "sources",
            ].includes(k),
        )
      )
        return tell(
          s,
          "Chỉ các mục trong danh sách mới được dùng cho hồ sơ kết nối.",
        );
      // Draft may be incomplete; every individual value must still belong to the taxonomy.
      const allowed = (list: unknown, dict: object) =>
        Array.isArray(list) &&
        list.every((x) => typeof x === "string" && Object.hasOwn(dict, x)) &&
        list.length === new Set(list).size;
      if (
        !allowed(p.interests, interests) ||
        !allowed(p.values, values) ||
        !allowed(p.languages, languages) ||
        (!Object.hasOwn(styles, p.style) && p.style !== "") ||
        (!Object.hasOwn(goals, p.goal) && p.goal !== "") ||
        !Array.isArray(p.sources) ||
        !sourceValid(s, p)
      )
        return tell(s, "Lựa chọn hoặc nguồn liên kết chưa hợp lệ.");
      s.draft = structuredClone(p);
      return s;
    }
    case "PUBLISH": {
      if (s.age !== "adult" || !s.consent.MATCH)
        return tell(s, "Cần đủ 18 tuổi và cho phép dùng hồ sơ để kết nối.");
      if (
        !a.profile ||
        Object.keys(a.profile).some(
          (k) =>
            ![
              "interests",
              "values",
              "style",
              "goal",
              "languages",
              "sources",
            ].includes(k),
        ) ||
        !validProfile(a.profile) ||
        !sourceValid(s, a.profile) ||
        JSON.stringify(a.profile) !== JSON.stringify(s.draft)
      )
        return tell(
          s,
          "Chưa đủ 3 sở thích, 2 giá trị, cách trò chuyện, mục tiêu và ngôn ngữ. Bạn xem lại bản nháp nhé.",
        );
      invalidate(s);
      s.profileVersion++;
      s.published = {
        ...structuredClone(a.profile),
        version: s.profileVersion,
        valid: true,
      };
      return tell(s, "Hồ sơ kết nối đã được cập nhật.");
    }
    case "WITHDRAW":
      invalidate(s);
      return tell(s, "Đã ngừng chia sẻ hồ sơ và đóng các kết nối dùng bản cũ.");
    case "SKIP":
      if (!canMatch(s) || !peer) return state;
      s.cooldowns[peer.id] = s.clock + 30 * DAY;
      return tell(s, "Đã bỏ qua gợi ý trong phiên demo.");
    case "REQUEST_SEND":
    case "REQUEST_INBOUND": {
      if (
        !canMatch(s) ||
        !peer ||
        !eligibility(s.published!, peer) ||
        s.blocked.includes(peer.id) ||
        (s.cooldowns[peer.id] || 0) > s.clock
      )
        return tell(s, "Chưa thể tạo lời mời cho hồ sơ này.");
      const pending = s.requests.find(
        (r) => r.candidateId === peer.id && r.status === "pending",
      );
      if (pending) {
        if (
          (pending.direction === "in" && a.type === "REQUEST_SEND") ||
          (pending.direction === "out" && a.type === "REQUEST_INBOUND")
        )
          return openConnection(s, pending);
        return state;
      }
      if (
        s.connections.some(
          (x) => x.candidateId === peer.id && x.status === "open",
        )
      )
        return state;
      if (
        s.requests.filter((r) => r.status === "pending").length >= 10 ||
        (a.type === "REQUEST_SEND" &&
          s.requests.filter(
            (r) => r.direction === "out" && r.created > s.clock - DAY,
          ).length >= 10)
      )
        return tell(
          s,
          "Bản demo giới hạn 10 lời mời trong 24 giờ và 10 lời đang chờ. Bạn có thể thử lại khi bớt lời chờ hoặc sau 24 giờ demo.",
        );
      if (!recommendations(s).some((r) => r.candidate.id === peer.id))
        return state;
      s.requests.push({
        id: uid(s, "REQ"),
        candidateId: peer.id,
        direction: a.type === "REQUEST_INBOUND" ? "in" : "out",
        status: "pending",
        profileVersion: s.published!.version,
        matchVersion: s.versions.MATCH,
        peerVersion: peer.version,
        peerConsentVersion: peer.consentVersion,
        created: s.clock,
        expires: s.clock + 7 * DAY,
      });
      return tell(
        s,
        "Đã tạo lời mời demo. Chưa thể nhắn tin khi chưa có hai đồng ý.",
      );
    }
    case "REQUEST_DECIDE": {
      const r = s.requests.find((x) => x.id === a.id);
      if (!r || r.status !== "pending")
        return tell(s, "Lời mời không còn ở trạng thái chờ.");
      if (a.outcome === "accept") return openConnection(s, r);
      if (!["cancel", "decline", "expire"].includes(a.outcome || ""))
        return state;
      r.status =
        a.outcome === "cancel"
          ? "cancelled"
          : a.outcome === "decline"
            ? "declined"
            : "expired";
      s.cooldowns[r.candidateId] = s.clock + 30 * DAY;
      return tell(s, "Đã cập nhật lời mời. Kết nối chưa được mở.");
    }
    case "HUMAN_SEND": {
      if (!canChat(s, c) || !a.text?.trim() || a.text.trim().length > 500)
        return tell(
          s,
          "Tin chưa gửi. Cần phòng đang mở và nội dung từ 1 đến 500 ký tự.",
        );
      if (
        s.connections
          .flatMap((c) => c.messages)
          .filter(
            (m) => m.actor === "self" && !m.scripted && m.at > s.clock - 60000,
          ).length >= 20
      )
        return tell(
          s,
          "Bạn đã gửi 20 tin trong một phút demo. Bạn có thể thử lại sau một phút demo.",
        );
      c!.messages.push({
        id: uid(s, "MSG"),
        actor: "self",
        text: a.text.trim(),
        scripted: false,
        at: s.clock,
      });
      if (s.outcome === "reply" && !c!.pending)
        c!.pending = job(
          s,
          c!.id,
          900,
          {
            type: "HUMAN_FINISH",
            connectionId: c!.id,
            candidateId: c!.candidateId,
          },
          c!.candidateId,
        );
      return s;
    }
    case "HUMAN_FINISH":
      if (!a.token || !canChat(s, c) || c!.pending !== a.key) return state;
      c!.pending = undefined;
      c!.messages.push({
        id: uid(s, "MSG"),
        actor: "peer",
        text: (peerReplies[c!.candidateId] || humanReplies)[
          Math.min(c!.replyTurn++, 2)
        ],
        scripted: true,
        at: s.clock,
      });
      return s;
    case "END":
    case "BLOCK": {
      const id = a.candidateId || c?.candidateId;
      if (s.age !== "adult" || !id || !s.candidates.some((p) => p.id === id))
        return state;
      if (a.type === "BLOCK" && !s.blocked.includes(id)) s.blocked.push(id);
      close(s, id, a.type === "BLOCK");
      return tell(
        s,
        a.type === "BLOCK"
          ? "Đã chặn nhân vật và đóng kết nối. Bạn vẫn có thể tạo báo cáo demo."
          : "Kết nối đã đóng.",
      );
    }
    case "UNBLOCK":
      s.blocked = s.blocked.filter((x) => x !== a.candidateId);
      return tell(s, "Đã bỏ chặn. Phòng cũ và quyền chia sẻ cũ vẫn đóng.");
    case "REVEAL_REQUEST": {
      if (!canChat(s, c) || !["displayName", "gender"].includes(a.field || ""))
        return state;
      const owner = a.owner === "self" ? "self" : "peer";
      const field = a.field!;
      const identity = owner === "self" ? s.identities : peer!.identity;
      const val = identity[field];
      if (!val || val === "Không chia sẻ")
        return tell(s, "Trường này chưa có thông tin demo để chia sẻ.");
      if (
        s.reveals.some(
          (r) =>
            r.connectionId === c!.id &&
            r.field === field &&
            r.owner === owner &&
            (["pending", "granted"].includes(r.status) || r.cooldown > s.clock),
        )
      )
        return tell(
          s,
          "Yêu cầu này đang chờ, đã được cho phép hoặc còn thời gian chờ 7 ngày.",
        );
      s.reveals.push({
        id: uid(s, "REV"),
        connectionId: c!.id,
        field,
        owner,
        recipient: owner === "self" ? "peer" : "self",
        fieldVersion:
          identity[
            field === "displayName" ? "displayNameVersion" : "genderVersion"
          ],
        status: "pending",
        expires: s.clock + 7 * DAY,
        cooldown: 0,
      });
      return tell(
        s,
        "Đã tạo yêu cầu chia sẻ demo. Chưa có thông tin nào được mở.",
      );
    }
    case "REVEAL_DECIDE": {
      const r = s.reveals.find((x) => x.id === a.id);
      const room = s.connections.find((x) => x.id === r?.connectionId);
      if (
        !r ||
        !canChat(s, room) ||
        r.status !== "pending" ||
        r.expires <= s.clock
      )
        return state;
      const identity =
        r.owner === "self"
          ? s.identities
          : s.candidates.find((p) => p.id === room!.candidateId)!.identity;
      if (
        r.fieldVersion !==
        identity[
          r.field === "displayName" ? "displayNameVersion" : "genderVersion"
        ]
      )
        return state;
      if (!["accept", "decline"].includes(a.outcome || "")) return state;
      r.status = a.outcome === "accept" ? "granted" : "declined";
      if (a.outcome === "decline") r.cooldown = s.clock + 7 * DAY;
      return tell(
        s,
        a.outcome === "accept"
          ? "Chỉ trường và người nhận đã chọn được cho phép trong demo."
          : "Đã từ chối. Hai bạn vẫn có thể trò chuyện.",
      );
    }
    case "REVEAL_REVOKE": {
      const r = s.reveals.find((x) => x.id === a.id);
      if (!r || r.status !== "granted") return state;
      r.status = "revoked";
      return tell(s, "Đã thu hồi quyền xem trường này.");
    }
    case "IDENTITY": {
      if (
        !["displayName", "gender"].includes(a.field || "") ||
        !a.text?.trim() ||
        a.text.length > 40
      )
        return state;
      if (a.owner === "peer" && (!peer || s.age !== "adult")) return state;
      const identity = a.owner === "peer" ? peer!.identity : s.identities;
      identity[a.field!] = a.text.trim();
      identity[
        a.field === "displayName" ? "displayNameVersion" : "genderVersion"
      ]++;
      s.reveals.forEach((r) => {
        const room = s.connections.find((c) => c.id === r.connectionId);
        if (
          r.field === a.field &&
          r.owner === (a.owner === "peer" ? "peer" : "self") &&
          (a.owner !== "peer" || room?.candidateId === peer!.id)
        )
          r.status = "revoked";
      });
      return tell(
        s,
        "Đã sửa thông tin demo và thu hồi quyền xem đúng trường của người sở hữu bản trước.",
      );
    }
    case "REPORT": {
      if (
        !peer ||
        !["uncomfortable", "pressure", "spam", "other"].includes(a.reason || "")
      )
        return tell(s, "Bạn chọn một lý do trước khi tạo phiếu nhé.");
      if (!a.key || s.reports.some((r) => r.key === a.key)) return state;
      const evidence = (a.evidence || []).filter((x) =>
        ["sample-1", "sample-2"].includes(x),
      );
      if (evidence.length > 2) return state;
      s.reports.push({
        id: `DEMO-R${String(s.reports.length + 1).padStart(3, "0")}`,
        candidateId: peer.id,
        reason: a.reason!,
        evidence,
        key: a.key,
      });
      return tell(
        s,
        "Đã tạo phiếu demo trong phiên. Chưa gửi đến bộ phận xử lý.",
      );
    }
    case "ACTIVITY_INVITE": {
      if (
        !canChat(s, c) ||
        a.activityId !== "ACT01" ||
        s.activities.some(
          (x) =>
            x.connectionId === c!.id &&
            ["pending", "active"].includes(x.status),
        )
      )
        return state;
      s.activities.push({
        id: uid(s, "ACT"),
        connectionId: c!.id,
        activityId: "ACT01",
        status: "pending",
        selfAccepted: true,
        peerAccepted: false,
        step: 0,
        answers: [],
      });
      return tell(s, "Đang chờ nhân vật kia đồng ý hoạt động mẫu.");
    }
    case "ACTIVITY_DECIDE": {
      const act = s.activities.find((x) => x.id === a.id);
      const room = s.connections.find((x) => x.id === act?.connectionId);
      if (!act || !canChat(s, room) || act.status !== "pending") return state;
      if (!["accept", "decline", "cancel"].includes(a.outcome || ""))
        return state;
      act.peerAccepted = a.outcome === "accept";
      act.status =
        a.outcome === "accept"
          ? "active"
          : a.outcome === "decline"
            ? "declined"
            : "cancelled";
      return s;
    }
    case "ACTIVITY_ANSWER": {
      const act = s.activities.find((x) => x.id === a.id);
      const room = s.connections.find((x) => x.id === act?.connectionId);
      if (
        !act ||
        !canChat(s, room) ||
        act.status !== "active" ||
        !act.selfAccepted ||
        !act.peerAccepted ||
        act.step !== a.step ||
        act.pending ||
        act.answers[act.step] !== undefined ||
        (!questions[act.step].options.includes(a.text || "") &&
          a.outcome !== "skip")
      )
        return state;
      act.answers[act.step] = a.outcome === "skip" ? null : a.text!;
      act.reply = undefined;
      act.pending = job(
        s,
        room!.id,
        700,
        {
          type: "ACTIVITY_REPLY",
          id: act.id,
          connectionId: room!.id,
          candidateId: room!.candidateId,
          step: act.step,
        },
        room!.candidateId,
      );
      return s;
    }
    case "ACTIVITY_REPLY": {
      const act = s.activities.find((x) => x.id === a.id);
      if (
        !a.token ||
        !act ||
        !canChat(s, c) ||
        act.status !== "active" ||
        act.pending !== a.key ||
        act.step !== a.step
      )
        return state;
      act.reply = questions[act.step].reply;
      act.pending = undefined;
      return s;
    }
    case "ACTIVITY_NEXT": {
      const act = s.activities.find((x) => x.id === a.id);
      const room = s.connections.find((x) => x.id === act?.connectionId);
      if (
        !act ||
        !canChat(s, room) ||
        act.status !== "active" ||
        !act.reply ||
        act.pending ||
        act.step !== a.step
      )
        return state;
      if (act.step === 2) act.status = "completed";
      else {
        act.step++;
        act.reply = undefined;
      }
      return s;
    }
    case "ACTIVITY_STOP": {
      const act = s.activities.find((x) => x.id === a.id);
      if (!act || !["active", "pending"].includes(act.status)) return state;
      act.status = act.status === "active" ? "stopped" : "cancelled";
      if (act.pending) s.jobs = s.jobs.filter((j) => j.id !== act.pending);
      act.pending = undefined;
      return tell(s, "Đã dừng hoạt động. Bạn có thể tiếp tục trò chuyện.");
    }
    case "ACTIVITY_FEEDBACK": {
      const act = s.activities.find((x) => x.id === a.id);
      const room = s.connections.find((x) => x.id === act?.connectionId);
      if (
        !act ||
        !canChat(s, room) ||
        act.status !== "completed" ||
        act.feedback ||
        !["useful", "not-useful", "unsure", "skip"].includes(a.outcome || "")
      )
        return state;
      act.feedback = a.outcome;
      return tell(s, "Cảm ơn bạn. Lựa chọn chỉ được giữ trong phiên demo.");
    }
    case "CLOCK":
      if (!Number.isFinite(a.days) || a.days! < 0) return state;
      s.clock += a.days! * DAY;
      expire(s);
      return tell(s, "Đã tiến đồng hồ demo. Giờ hệ thống không đổi.");
    case "ERROR_ONCE":
      s.errorOnce = !s.errorOnce;
      return s;
    case "OUTCOME":
      s.outcome = a.outcome === "silent" ? "silent" : "reply";
      return s;
    case "PEER_CHANGE":
      if (!peer || s.age !== "adult") return state;
      peer.version++;
      if (a.outcome === "revoke") {
        peer.allowed = false;
        peer.consentVersion++;
      }
      close(s, peer.id);
      return tell(
        s,
        "Nhân vật đối phương đã thay hồ sơ hoặc ngừng chia sẻ. Phòng cũ đã đóng.",
      );
    case "PRESET": {
      if (a.preset === "empty" || a.preset === "insufficient") {
        s.moods = a.preset === "empty" ? [] : s.moods.slice(-2);
        return tell(s, "Đã đổi dữ liệu mẫu tâm trạng.");
      }
      if (s.age !== "adult")
        return tell(
          s,
          "Không thể dùng dữ liệu kết nối người lớn trong phiên 16–17.",
        );
      if (a.preset === "adult-ready-to-publish") {
        s.draft = sampleProfile();
        return s;
      }
      if (a.preset === "reveal-gender") {
        s.identities.gender = "Nữ";
        s.identities.genderVersion++;
        const peer = s.candidates.find((p) => p.id === "C01")!;
        peer.identity.gender = "Nữ";
        peer.identity.genderVersion++;
        s.reveals.forEach((r) => {
          const room = s.connections.find((c) => c.id === r.connectionId);
          if (
            r.field === "gender" &&
            (r.owner === "self" || room?.candidateId === "C01")
          )
            r.status = "revoked";
        });
        return tell(
          s,
          "Đã nạp trường giới tính hư cấu để kiểm tra quyền riêng từng trường.",
        );
      }
      if (
        a.preset === "inbound-request" ||
        a.preset === "stale-request" ||
        a.preset === "expired-request"
      ) {
        let next = reducer(s, { type: "REQUEST_INBOUND", candidateId: "C03" });
        const r = next.requests.find(
          (x) => x.candidateId === "C03" && x.status === "pending",
        );
        if (r && a.preset === "stale-request") r.profileVersion--;
        if (r && a.preset === "expired-request") {
          r.expires = next.clock - 1;
          expire(next);
        }
        return next;
      }
      return state;
    }
    case "DELETE_TYPE":
      if (a.outcome === "mood") s.moods = [];
      else if (a.outcome === "ai") {
        stopAI(s);
        s.ai.messages = [];
        s.bots = initialThreads();
      } else if (a.outcome === "private") {
        invalidate(s);
        s.privateItems = [];
      }
      return tell(s, "Đã xóa loại dữ liệu đã chọn trong phiên demo.");
    default:
      return state;
  }
}
export function visibleChat(s: State, id: string) {
  const c = s.connections.find((x) => x.id === id);
  return canChat(s, c) ? structuredClone(c) : undefined;
}
export function visibleReveal(
  s: State,
  connectionId: string,
  field: "displayName" | "gender",
  owner: "self" | "peer",
  recipient: "self" | "peer",
) {
  const c = s.connections.find((x) => x.id === connectionId);
  if (!canChat(s, c)) return undefined;
  const identity =
    owner === "self"
      ? s.identities
      : s.candidates.find((p) => p.id === c!.candidateId)!.identity;
  const version =
    identity[field === "displayName" ? "displayNameVersion" : "genderVersion"];
  if (
    !s.reveals.some(
      (r) =>
        r.connectionId === connectionId &&
        r.field === field &&
        r.owner === owner &&
        r.recipient === recipient &&
        r.status === "granted" &&
        r.fieldVersion === version,
    )
  )
    return undefined;
  return identity[field];
}
export function safeExport(s: State) {
  return {
    nhanVat: "An — hư cấu",
    nhomTuoi: s.age,
    quyen: s.consent,
    soMucHoSo: s.privateItems.filter(
      (x) => !["deleted", "rejected"].includes(x.status),
    ).length,
    soNgayTamTrang: new Set(s.moods.map((x) => x.date)).size,
    banDangChiaSe: s.published?.valid
      ? {
          interests: s.published.interests,
          values: s.published.values,
          style: s.published.style,
          goal: s.published.goal,
          languages: s.published.languages,
        }
      : null,
    soPhieuDemo: s.reports.length,
  };
}
