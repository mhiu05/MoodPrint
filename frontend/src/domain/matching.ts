import type { Candidate, Profile, State } from "./types";
import { canMatch, validProfile } from "./policies";
import { interests, values, labels } from "../mocks/fixtures";
export const SCORING_VERSION = "mock-v1";
// All arithmetic remains integer/rational until the final round-half-up.
export const halfUp = (numerator: number, denominator: number) =>
  Math.floor((2 * numerator + denominator) / (2 * denominator));
export function score(a: Profile, b: Profile) {
  a = {
    ...a,
    interests: [...new Set(a.interests)],
    values: [...new Set(a.values)],
    languages: [...new Set(a.languages)],
  };
  b = {
    ...b,
    interests: [...new Set(b.interests)],
    values: [...new Set(b.values)],
    languages: [...new Set(b.languages)],
  };
  if (!validProfile(a) || !validProfile(b)) return 0;
  const fraction = (x: string[], y: string[]) => [
    x.filter((t) => y.includes(t)).length,
    new Set([...x, ...y]).size,
  ];
  const [ni, di] = fraction(a.interests, b.interests),
    [nv, dv] = fraction(a.values, b.values);
  const st =
    a.style === b.style
      ? 2
      : a.style === "balanced" || b.style === "balanced"
        ? 1
        : 0;
  return halfUp(
    45 * ni * dv * 2 + 35 * nv * di * 2 + 20 * st * di * dv,
    di * dv * 2,
  );
}
export function eligibility(a: Profile, b: Candidate) {
  return (
    b.allowed &&
    validProfile(a) &&
    validProfile(b.profile) &&
    a.goal === b.profile.goal &&
    a.languages.some((l) => b.profile.languages.includes(l))
  );
}
export function recommendations(s: State) {
  if (!canMatch(s)) return [];
  return s.candidates
    .filter(
      (c) =>
        eligibility(s.published!, c) &&
        !s.blocked.includes(c.id) &&
        !(s.cooldowns[c.id] > s.clock) &&
        !s.requests.some(
          (r) => r.candidateId === c.id && r.status === "pending",
        ) &&
        !s.connections.some(
          (r) => r.candidateId === c.id && r.status === "open",
        ),
    )
    .map((c) => ({
      // A discovery card receives only shared fields, never private identity.
      candidate: {
        id: c.id,
        alias: c.alias,
        color: c.color,
        profile: {
          interests: [...c.profile.interests],
          values: [...c.profile.values],
          style: c.profile.style,
          goal: c.profile.goal,
          languages: [...c.profile.languages],
        },
      },
      scoringVersion: SCORING_VERSION,
      profileVersion: s.published!.version,
      peerVersion: c.version,
      score: score(s.published!, c.profile),
      reasons: [
        ...Object.keys(interests)
          .filter(
            (x) =>
              s.published!.interests.includes(x) &&
              c.profile.interests.includes(x),
          )
          .map((x) => `Cùng thích ${labels[x].toLocaleLowerCase("vi")}`),
        ...Object.keys(values)
          .filter(
            (x) =>
              s.published!.values.includes(x) && c.profile.values.includes(x),
          )
          .map((x) => `Cùng coi trọng ${labels[x].toLocaleLowerCase("vi")}`),
        ...(s.published!.style === c.profile.style
          ? ["Cùng cách trò chuyện"]
          : []),
      ].slice(0, 3),
    }))
    .filter((x) => x.score >= 30)
    .sort(
      (a, b) => b.score - a.score || (a.candidate.id < b.candidate.id ? -1 : 1),
    )
    .slice(0, 5);
}
