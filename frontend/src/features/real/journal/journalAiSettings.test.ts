import { expect, it } from "vitest";
import { noticeText, toggleLabel } from "./journalAiSettingsModel";

it("names external journal processing and the semantic search choice", () => {
  expect(noticeText()).toContain("Voyage AI");
  expect(noticeText()).toContain("bên ngoài");
  expect(toggleLabel("embedding")).toBe("Tìm theo ý nghĩa trong nhật ký");
});
