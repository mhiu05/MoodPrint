import { expect, it } from "vitest";
import { encodeWav } from "./audio";

it("encodes clipping-safe mono PCM with independently readable sample count", async () => {
  const blob = encodeWav([new Float32Array([-2, 0, 2])], 16000);
  const view = new DataView(await blob.arrayBuffer());
  expect(view.getUint32(24, true)).toBe(16000);
  expect(view.getUint32(40, true)).toBe(6);
  expect(view.getInt16(44, true)).toBe(-32768);
  expect(view.getInt16(48, true)).toBe(32767);
});

it("rejects silence-sized empty and recordings over thirty seconds", () => {
  expect(() => encodeWav([], 16000)).toThrow();
  expect(() => encodeWav([new Float32Array(480001)], 16000)).toThrow();
});
