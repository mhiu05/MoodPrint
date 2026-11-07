import { readdir, readFile, stat } from "node:fs/promises";
import { resolve, relative, extname } from "node:path";
const root = resolve(import.meta.dirname, "..");
async function files(directory) {
  return (
    await Promise.all(
      (await readdir(directory)).map(async (name) => {
        const path = resolve(directory, name);
        return (await stat(path)).isDirectory() ? files(path) : [path];
      }),
    )
  ).flat();
}
const source = await files(resolve(root, "src"));
const bundle = await files(resolve(root, "dist"));
const failures = [];
const secrets = [
  /sk-(?:proj-|svcacct-)[A-Za-z0-9_-]{16,}/,
  /AKIA[0-9A-Z]{16}/,
  /-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----/,
  /eyJhbGciOi[A-Za-z0-9_-]{40,}\.[A-Za-z0-9_-]{30,}\.[A-Za-z0-9_-]{20,}/,
];
const network =
  /\b(?:fetch|XMLHttpRequest|WebSocket|EventSource)\s*\(|navigator\.sendBeacon\s*\(|getUserMedia\s*\(/;
for (const path of [...source, ...bundle]) {
  if (
    ![".ts", ".tsx", ".js", ".html", ".svg", ".css"].includes(extname(path)) ||
    path.includes(".test.")
  )
    continue;
  const text = await readFile(path, "utf8");
  if (secrets.some((pattern) => pattern.test(text)))
    failures.push(`${relative(root, path)}: credential-like content`);
  if (path.startsWith(resolve(root, "src")) && network.test(text))
    failures.push(
      `${relative(root, path)}: unexpected network or microphone API`,
    );
}
const packages = JSON.parse(
  await readFile(resolve(root, "package.json"), "utf8"),
);
for (const name of Object.keys(packages.dependencies)) {
  if (/openai|supabase|aws-sdk|apify/i.test(name))
    failures.push(`Unexpected live-service dependency: ${name}`);
}
console.log(
  JSON.stringify(
    {
      sourceFiles: source.length,
      buildFiles: bundle.length,
      checks: [
        "credential patterns in source and production bundle",
        "no application HTTP/socket/telemetry/microphone calls",
        "no live-service SDK dependencies",
      ],
      failures,
    },
    null,
    2,
  ),
);
if (failures.length) process.exitCode = 1;
