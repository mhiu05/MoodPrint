import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative } from "node:path";
import { describe, expect, it } from "vitest";

// Production must never ship demo data, scripted peers or the legacy prototype.
const SRC = join(process.cwd(), "src");
const PROTOTYPE_IMPORT =
  /from\s+["'][^"']*(\/mocks\/|\/state\/|\/domain\/|\/pages\/|companions\/(Cards|Companions|scenarios))/;

function sources(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) return sources(path);
    return /\.(ts|tsx)$/.test(name) ? [path] : [];
  });
}

describe("production guard", () => {
  it("has no legacy prototype entry", () => {
    expect(existsSync(join(SRC, "App.tsx"))).toBe(false);
  });

  it("imports no mocks, demo state, domain oracle, pages or scripted companions", () => {
    const offenders = sources(SRC)
      .filter((file) => PROTOTYPE_IMPORT.test(readFileSync(file, "utf8")))
      .map((file) => relative(SRC, file));
    expect(offenders).toEqual([]);
  });
});
