import { createHash } from "node:crypto";
import { existsSync, readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { deflateSync } from "node:zlib";
import type { Page } from "@playwright/test";
import { expect } from "./fixtures";

export const companionLive = false;

// ---- deterministic model stand-in (agent/src/moodprint_agent/testing/fake_provider.py) -------------
// Top-left pixel colour of an uploaded image selects the fake provider's behaviour.
export const COLORS = {
  ok: [30, 160, 90],
  alwaysError: [255, 0, 0],
  timeout: [255, 165, 0],
  errorOnce: [0, 0, 255],
} as const;
type Rgb = readonly [number, number, number];

const crcTable = Array.from({ length: 256 }, (_, n) => {
  let c = n;
  for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
  return c >>> 0;
});
function crc32(buffer: Buffer): number {
  let c = 0xffffffff;
  for (const byte of buffer) c = crcTable[(c ^ byte) & 0xff] ^ (c >>> 8);
  return (c ^ 0xffffffff) >>> 0;
}
function chunk(type: string, data: Buffer): Buffer {
  const length = Buffer.alloc(4);
  length.writeUInt32BE(data.length);
  const body = Buffer.concat([Buffer.from(type, "ascii"), data]);
  const crc = Buffer.alloc(4);
  crc.writeUInt32BE(crc32(body));
  return Buffer.concat([length, body, crc]);
}
/** A 64x64 RGB PNG. Pixel (0,0) is exactly `rgb`; the rest carries `seed` so every test has its own bytes. */
export function solidPng(rgb: Rgb, seed: number): Buffer {
  const size = 64;
  const rows: Buffer[] = [];
  for (let y = 0; y < size; y++) {
    const row = Buffer.alloc(1 + size * 3);
    for (let x = 0; x < size; x++) {
      const special = x === 0 && y === 0;
      row[1 + x * 3] = special ? rgb[0] : (rgb[0] + seed + x) & 0xff;
      row[2 + x * 3] = special ? rgb[1] : (rgb[1] + seed * 3 + y) & 0xff;
      row[3 + x * 3] = special ? rgb[2] : (rgb[2] + seed * 7) & 0xff;
    }
    rows.push(row);
  }
  const header = Buffer.alloc(13);
  header.writeUInt32BE(size, 0);
  header.writeUInt32BE(size, 4);
  header[8] = 8; // bit depth
  header[9] = 2; // truecolour
  return Buffer.concat([
    Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
    chunk("IHDR", header),
    chunk("IDAT", deflateSync(Buffer.concat(rows))),
    chunk("IEND", Buffer.alloc(0)),
  ]);
}
export const sha256 = (data: Buffer) =>
  createHash("sha256").update(data).digest("hex");

const logPath =
  process.env.MOODPRINT_E2E_MODEL_LOG ??
  path.join(tmpdir(), "moodprint-e2e-model.log");
/** Lines the fake provider has logged so far: "<kind> <sha16> <mode>". */
export function modelLog(): string[] {
  return existsSync(logPath)
    ? readFileSync(logPath, "utf8").split("\n").filter(Boolean)
    : [];
}

/**
 * Real upload through the case wizard (resumable upload to local Storage) of one image.
 * Leaves the page on the case URL once the file shows as uploaded.
 */
export async function uploadImageEvidence(
  page: Page,
  png: Buffer,
  name = "anh-tong-hop.png",
  mimeType = "image/png",
) {
  await page.goto("/cases/new");
  await page
    .getByRole("textbox", { name: "Đặt tên hồ sơ" })
    .fill("Hồ sơ cho phân tích ảnh");
  await page.getByRole("button", { name: "Tiếp tục", exact: true }).click();
  await page
    .getByRole("textbox", { name: "Chuyện gì đã xảy ra?" })
    .fill("Một tình huống hoàn toàn hư cấu để thử phân tích ảnh.");
  await page.getByRole("button", { name: "Lưu nháp", exact: true }).click();
  await expect(page).toHaveURL(/\/cases\/[0-9a-f-]{36}$/);
  await page.getByRole("link", { name: "Bổ sung hồ sơ", exact: true }).click();
  await page.getByRole("button", { name: /Chuyện xảy ra/ }).click();
  for (let step = 2; step <= 4; step++) {
    await page.getByRole("button", { name: "Tiếp tục", exact: true }).click();
    await expect(
      page.getByText(`Bước ${step + 1}/6`, { exact: true }),
    ).toBeVisible();
  }
  await page.getByLabel("Chọn tệp bằng chứng").setInputFiles({
    name,
    mimeType,
    buffer: png,
  });
  await expect(
    page.getByRole("status").filter({ hasText: "Đã tải xong" }),
  ).toBeVisible({ timeout: 30000 });
  await expect(page.locator(".evidence-attachments li")).toHaveCount(1);
}
