import path from "node:path";

/** An explicit artifact root takes precedence over every historical output path. */
export function artifactPath(relative: string, legacyPath?: string): string {
  const configured = process.env.MOODPRINT_TEST_ARTIFACT_DIR;
  if (!configured && legacyPath) return path.resolve(legacyPath);
  const root = path.resolve(configured || "evidence");
  const target = path.resolve(root, relative);
  const inside = path.relative(root, target);
  if (path.isAbsolute(relative) || inside === ".." || inside.startsWith(`..${path.sep}`) || path.isAbsolute(inside)) {
    throw new Error("Test artifacts must remain within MOODPRINT_TEST_ARTIFACT_DIR");
  }
  return target;
}
