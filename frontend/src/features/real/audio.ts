/** Encode bounded mono PCM to a file whose duration the server can independently verify. */
export function encodeWav(chunks: Float32Array[], rate: number): Blob {
  const count = chunks.reduce((sum, chunk) => sum + chunk.length, 0);
  if (
    !Number.isInteger(rate) ||
    rate < 8000 ||
    rate > 48000 ||
    !count ||
    count > rate * 30
  )
    throw new Error("Invalid recording duration");
  const buffer = new ArrayBuffer(44 + count * 2),
    view = new DataView(buffer);
  const text = (offset: number, value: string) => {
    for (let i = 0; i < value.length; i++)
      view.setUint8(offset + i, value.charCodeAt(i));
  };
  text(0, "RIFF");
  view.setUint32(4, 36 + count * 2, true);
  text(8, "WAVE");
  text(12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, rate, true);
  view.setUint32(28, rate * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  text(36, "data");
  view.setUint32(40, count * 2, true);
  let offset = 44;
  for (const chunk of chunks)
    for (const value of chunk) {
      const sample = Math.max(-1, Math.min(1, value));
      view.setInt16(offset, sample < 0 ? sample * 32768 : sample * 32767, true);
      offset += 2;
    }
  return new Blob([buffer], { type: "audio/wav" });
}
