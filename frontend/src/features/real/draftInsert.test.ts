import { describe, expect, it } from "vitest";
import { insertAtSelection } from "./draftInsert";

describe("insertAtSelection", () => {
  it("fills an empty draft", () => {
    expect(insertAtSelection("", 0, 0, "Chào bạn")).toEqual({ ok: true, next: "Chào bạn", caret: 8 });
  });
  it("keeps existing text and separates the suggestion with one space", () => {
    expect(insertAtSelection("Mình đang", 9, 9, "buồn")).toEqual({ ok: true, next: "Mình đang buồn", caret: 14 });
  });
  it("does not double an existing separator", () => {
    expect(insertAtSelection("Mình ", 5, 5, "buồn")).toEqual({ ok: true, next: "Mình buồn", caret: 9 });
  });
  it("replaces only the selected range and preserves the unselected text", () => {
    const result = insertAtSelection("Xin chào XYZ nhé", 9, 12, "bạn");
    expect(result).toEqual({ ok: true, next: "Xin chào bạn nhé", caret: 12 });
  });
  it("separates a suggestion inserted before trailing text", () => {
    expect(insertAtSelection("hello world", 5, 5, "there")).toEqual({ ok: true, next: "hello there world", caret: 11 });
  });
  it("rejects an insertion that would pass the limit without touching the draft", () => {
    const draft = "a".repeat(495);
    expect(insertAtSelection(draft, 495, 495, "123456789")).toEqual({ ok: false });
  });
  it("accepts an insertion that lands exactly on the limit", () => {
    const result = insertAtSelection("a".repeat(490), 490, 490, "b".repeat(9));
    expect(result.ok && result.next.length).toBe(500);
  });
});
