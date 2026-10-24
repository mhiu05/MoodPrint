import type { Connection, Profile, State, Token } from "./types";
import { interests, values, styles, goals, languages } from "../mocks/fixtures";
export const sessionAllowed = (s: State) =>
  s.ready && (s.age === "teen" || s.age === "adult");
export const effectiveAI = (s: State) => sessionAllowed(s) && s.consent.AI;
export const effectiveMemory = (s: State) => effectiveAI(s) && s.consent.MEM;
export const effectiveVoice = (s: State) => effectiveAI(s) && s.consent.VOICE;
export const validProfile = (p: Profile): boolean => {
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
          "version",
          "valid",
        ].includes(k),
    )
  )
    return false;
  const valid = (a: unknown, dict: object, min: number) =>
    Array.isArray(a) &&
    a.length >= min &&
    a.length === new Set(a).size &&
    a.every((x) => typeof x === "string" && Object.hasOwn(dict, x));
  return (
    valid(p.interests, interests, 3) &&
    valid(p.values, values, 2) &&
    valid(p.languages, languages, 1) &&
    Object.hasOwn(styles, p.style) &&
    Object.hasOwn(goals, p.goal) &&
    Array.isArray(p.sources) &&
    p.sources.every(
      (r) =>
        typeof r.id === "string" &&
        Number.isInteger(r.version) &&
        Object.keys(r).every((k) => ["id", "version"].includes(k)),
    )
  );
};
export const sourceValid = (s: State, p: Profile) =>
  p.sources.every((r) =>
    s.privateItems.some(
      (x) =>
        x.id === r.id &&
        x.version === r.version &&
        x.status !== "deleted" &&
        x.status !== "rejected" &&
        (x.status === "confirmed" || x.status === "edited") &&
        r.id === "PI01" &&
        p.interests.includes("reading"),
    ),
  );
export const canMatch = (s: State) =>
  sessionAllowed(s) &&
  s.age === "adult" &&
  s.consent.MATCH &&
  !!s.published?.valid &&
  validProfile(s.published) &&
  sourceValid(s, s.published);
export function canChat(s: State, c?: Connection) {
  const peer = s.candidates.find((x) => x.id === c?.candidateId);
  return (
    !!c &&
    canMatch(s) &&
    c.status === "open" &&
    c.selfAccepted &&
    c.peerAccepted &&
    !s.blocked.includes(c.candidateId) &&
    c.profileVersion === s.published?.version &&
    c.matchVersion === s.versions.MATCH &&
    peer?.allowed === true &&
    validProfile(peer.profile) &&
    s.published!.goal === peer.profile.goal &&
    s.published!.languages.some((x) => peer.profile.languages.includes(x)) &&
    c.peerVersion === peer.version &&
    c.peerConsentVersion === peer.consentVersion
  );
}
export function tokenFor(s: State, candidateId?: string): Token {
  const peer = s.candidates.find((x) => x.id === candidateId);
  return {
    epoch: s.epoch,
    ai: s.versions.AI,
    voice: s.versions.VOICE,
    match: s.versions.MATCH,
    profile: s.profileVersion,
    peer: peer?.version || 0,
    peerConsent: peer?.consentVersion || 0,
  };
}
export const tokenValid = (
  s: State,
  t: Token,
  scope: string,
  candidateId?: string,
) => {
  const now = tokenFor(s, candidateId);
  return (
    t.epoch === now.epoch &&
    (scope === "ai"
      ? t.ai === now.ai
      : scope === "voice"
        ? t.ai === now.ai && t.voice === now.voice
        : t.match === now.match &&
          t.profile === now.profile &&
          t.peer === now.peer &&
          t.peerConsent === now.peerConsent)
  );
};
export const memoryContext = (s: State) =>
  effectiveMemory(s)
    ? s.privateItems
        .filter(
          (x) =>
            x.origin === "ai" &&
            x.memoryApproved &&
            ["confirmed", "edited"].includes(x.status),
        )
        .map((x) => x.text)
    : [];
