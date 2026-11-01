import { describe, expect, it } from "vitest";
import { activeMention, EVERYONE, insertMention, keptMentions, mentionOptions, type MentionTarget } from "./mentions";

const targets: MentionTarget[] = [
  { id: "dieuphoi", name: "Điều phối" },
  { id: "nhatky", name: "Nhật ký" },
  { id: "hoatdong", name: "Hoạt động" },
  EVERYONE,
];

describe("group mention picker model", () => {
  it("opens on @ at a word start and follows the typed name", () => {
    expect(activeMention("@", 1)).toEqual({ start: 0, query: "" });
    expect(activeMention("chào @nh", 8)).toEqual({ start: 5, query: "nh" });
    expect(activeMention("chào @Nhật k", 12)).toEqual({ start: 5, query: "Nhật k" });
  });

  it("never opens inside an e-mail address, a quote or after a long run", () => {
    expect(activeMention("an@nhatky", 9)).toBeNull();
    expect(activeMention('nói "@Nh', 8)).toBeNull();
    expect(activeMention("@ không phải tên ai cả", 22)).toBeNull();
    expect(activeMention("không có", 8)).toBeNull();
  });

  it("filters with and without accents, by any word", () => {
    expect(mentionOptions(targets, "nhat").map((t) => t.id)).toEqual(["nhatky"]);
    expect(mentionOptions(targets, "Hoạt").map((t) => t.id)).toEqual(["hoatdong"]);
    expect(mentionOptions(targets, "dong").map((t) => t.id)).toEqual(["hoatdong"]);
    expect(mentionOptions(targets, "moi").map((t) => t.id)).toEqual(["all"]);
    expect(mentionOptions(targets, "")).toHaveLength(4);
  });

  it("inserts the display name and keeps the stable id only while the token remains", () => {
    const inserted = insertMention("chào @nh nhé", 5, 8, targets[1]);
    expect(inserted).toEqual({ text: "chào @Nhật ký  nhé", caret: 14 });
    expect(keptMentions(inserted.text, [targets[1]])).toEqual(["nhatky"]);
    expect(keptMentions("chào nhé", [targets[1]])).toEqual([]);
    expect(keptMentions("@mọi người ơi", [EVERYONE])).toEqual(["all"]);
  });
});
