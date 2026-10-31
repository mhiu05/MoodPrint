import { describe, expect, it } from "vitest";
import { groupMessages } from "./messageGroups";

const message = (id: string, actor: "self" | "bot", runId?: string) => ({ id, actor, runId });

describe("assistant bubble groups", () => {
  it("groups adjacent bubbles of one bot run and keeps everything else single", () => {
    const groups = groupMessages([
      message("u1", "self", "r1"),
      message("b1", "bot", "r1"),
      message("b2", "bot", "r1"),
      message("b3", "bot", "r1"),
      message("u2", "self", "r2"),
      message("b4", "bot", "r2"),
    ]);
    expect(groups.map((group) => group.items.map((item) => item.id))).toEqual([
      ["u1"],
      ["b1", "b2", "b3"],
      ["u2"],
      ["b4"],
    ]);
    expect(groups[1].key).toBe("b1");
  });

  it("never merges bot messages of different runs or without a run", () => {
    const groups = groupMessages([
      message("b1", "bot", "r1"),
      message("b2", "bot", "r2"),
      message("b3", "bot"),
      message("b4", "bot"),
    ]);
    expect(groups.map((group) => group.items.length)).toEqual([1, 1, 1, 1]);
  });

  it("can group wrapped rows through a selector", () => {
    const rows = [{ message: message("b1", "bot", "r") }, { message: message("b2", "bot", "r") }];
    expect(groupMessages(rows, (row) => row.message)[0].items).toHaveLength(2);
  });
});
