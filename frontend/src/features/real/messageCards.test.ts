import { expect, it } from "vitest";
import { renderableCards } from "./messageCards";

it("drops retired discovery while preserving supported cards and their order", () => {
  expect(renderableCards([{ kind: "discovery" }, { kind: "mood_form" }])).toEqual([{ kind: "mood_form" }]);
});
