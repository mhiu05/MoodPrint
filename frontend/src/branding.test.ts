import { readFileSync, readdirSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

function screens(directory: string): string[] {
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const path = resolve(directory, entry.name);
    return entry.isDirectory()
      ? screens(path)
      : path.endsWith(".tsx")
        ? [path]
        : [];
  });
}

describe("MoodPrint identity", () => {
  it("uses the current name and favicon in browser metadata", () => {
    const html = readFileSync("index.html", "utf8");
    expect(html).toMatch(/<title>MoodPrint/);
    expect(html).toContain('href="/moodprint.svg"');
    expect(html).not.toMatch(/Me2We/i);
  });

  it("keeps retired branding out of active screen text and accessible names", () => {
    for (const path of screens(resolve("src"))) {
      expect(readFileSync(path, "utf8"), path).not.toMatch(/Me2We|ME2WE/);
    }
  });
});
