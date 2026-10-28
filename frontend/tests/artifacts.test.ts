import { afterEach, describe, expect, it, vi } from "vitest";
import path from "node:path";
import { artifactPath } from "./artifacts";

afterEach(() => vi.unstubAllEnvs());
describe("owned test artifact root", () => {
  it("routes every legacy destination into the explicit root", () => {
    const root = path.resolve("synthetic-artifact-root");
    vi.stubEnv("MOODPRINT_TEST_ARTIFACT_DIR", root);
    expect(artifactPath("screens/mood.png", "../docs/legacy/mood.png")).toBe(path.join(root, "screens/mood.png"));
    expect(artifactPath("report.json")).toBe(path.join(root, "report.json"));
  });
  it("rejects destinations that escape the configured root", () => {
    vi.stubEnv("MOODPRINT_TEST_ARTIFACT_DIR", path.resolve("synthetic-artifact-root"));
    expect(() => artifactPath("../escape.png")).toThrow();
    expect(() => artifactPath(path.resolve("outside.png"))).toThrow();
  });
});
