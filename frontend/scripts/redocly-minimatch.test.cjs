const assert = require("node:assert/strict");
const { createRequire } = require("node:module");
const path = require("node:path");
const test = require("node:test");

const project = createRequire(path.resolve(process.cwd(), "package.json"));
const generator = createRequire(project.resolve("openapi-typescript"));
const redocly = createRequire(generator.resolve("@redocly/openapi-core"));
const { readFileFromUrl } = redocly("./utils.js");

test("Redocly matches URL header globs with the patched minimatch API", async () => {
  const calls = [];
  const config = {
    headers: [
      { matches: "https://schema.example.invalid/**", name: "X-Schema", value: "synthetic" },
      { matches: "other.example.invalid/**", name: "X-Other", value: "must-not-leak" },
    ],
    customFetch: async (url, options) => {
      calls.push({ url, headers: options.headers });
      return { ok: true, text: async () => "synthetic schema", headers: { get: () => "text/plain" } };
    },
  };
  assert.deepEqual(await readFileFromUrl("https://schema.example.invalid/openapi.yaml", config), {
    body: "synthetic schema", mimeType: "text/plain",
  });
  assert.deepEqual(calls, [{
    url: "https://schema.example.invalid/openapi.yaml", headers: { "X-Schema": "synthetic" },
  }]);
  calls.length = 0;
  await readFileFromUrl("https://unmatched.example.invalid/openapi.yaml", config);
  assert.deepEqual(calls[0].headers, {});
});
