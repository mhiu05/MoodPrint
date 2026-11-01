// OpenAPI-TS 7 uses Redocly 1's callable CommonJS minimatch API. The patched
// minimatch 11 exposes named exports. Adapt that export in this generator process
// only; keep the actual patched matcher and every named API, without editing
// node_modules or changing browser/runtime code.
const { createRequire } = require("node:module");
const path = require("node:path");

const project = createRequire(path.resolve(process.cwd(), "package.json"));
const generator = createRequire(project.resolve("openapi-typescript"));
const redocly = createRequire(generator.resolve("@redocly/openapi-core"));
const resolved = redocly.resolve("minimatch");
const api = redocly(resolved);
if (typeof api !== "function") {
  if (typeof api.minimatch !== "function") throw new Error("Unsupported minimatch API");
  require.cache[resolved].exports = Object.assign(api.minimatch, api);
}
