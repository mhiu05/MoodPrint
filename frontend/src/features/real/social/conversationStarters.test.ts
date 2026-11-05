import { describe, expect, it } from "vitest";
import type { components } from "../../../api/generated/schema";
import { selectConversationStarter } from "./conversationStarters";
import taxonomy from "../../../../../backend/app/modules/profiles/taxonomy_v2.json";

const card: components["schemas"]["CandidateCardDTO"] = {
  candidateRef: "ref",
  avatarSeed: "00aa",
  alias: "Bạn đồng hành aa",
  profileVersion: 2,
  peerVersion: 5,
  matchLabel: "some",
  scoringVersion: "rules-v2",
  profile: {
    interests: ["music", "coffee", "reading"],
    style: "balanced",
    goal: "friendship",
    strictGoal: false,
  },
  reasons: ["Cùng thích âm nhạc"],
};
describe("grounded deterministic starters (T25/T26)", () => {
  it("requires the exact server reason and the peer interest", () => {
    expect(selectConversationStarter(card, taxonomy).templateId).toMatch(
      /^starter-v1:music:[01]$/,
    );
    for (const reasons of [
      [],
      ["Cùng thích âm nhạc và cà phê"],
      ["Có sở thích gần nhau: âm nhạc"],
      ["Cùng thích Âm nhạc"],
    ]) {
      expect(
        selectConversationStarter({ ...card, reasons }, taxonomy).templateId,
      ).toMatch(/^starter-v1:generic:/);
    }
    expect(
      selectConversationStarter(
        { ...card, profile: { ...card.profile, interests: ["reading"] } },
        taxonomy,
      ).templateId,
    ).toMatch(/^starter-v1:generic:/);
  });
  it("keeps priority independent of reason ordering and ignores expiring reference", () => {
    const first = selectConversationStarter(
      { ...card, reasons: ["Cùng thích cà phê", "Cùng thích âm nhạc"] },
      taxonomy,
    );
    expect(first.templateId).toMatch(/^starter-v1:music:/);
    expect(
      selectConversationStarter(
        {
          ...card,
          candidateRef: "different-ref",
          reasons: ["Cùng thích cà phê", "Cùng thích âm nhạc"],
        },
        taxonomy,
      ),
    ).toEqual(first);
    expect(selectConversationStarter(card, taxonomy)).toEqual(
      selectConversationStarter(card, taxonomy),
    );
  });
  it("reaches both safe variants from public seeds and versions", () => {
    const variants = new Set(
      Array.from(
        { length: 20 },
        (_, i) =>
          selectConversationStarter({ ...card, peerVersion: i }, taxonomy)
            .templateId,
      ),
    );
    expect(variants).toEqual(
      new Set(["starter-v1:music:0", "starter-v1:music:1"]),
    );
  });
});
