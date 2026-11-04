import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { expect, it } from "vitest";

it("has no product copy inviting users to retired social features", () => {
  const matches: string[] = [];
  function visit(directory: string) {
    for (const entry of readdirSync(directory, { withFileTypes: true })) {
      const path = join(directory, entry.name);
      if (entry.isDirectory()) {
        if (entry.name !== "generated") visit(path);
      } else if (/\.tsx?$/.test(entry.name) && !/\.test\./.test(entry.name)) {
        if (/[Tt]ìm bạn|bạn kết nối|hồ sơ tìm bạn|kết nối với người khác|Mở Tìm bạn/.test(readFileSync(path, "utf8"))) matches.push(path);
      }
    }
  }
  visit(join(process.cwd(), "src"));
  expect(matches).toEqual([]);
});
