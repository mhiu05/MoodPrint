import assert from "node:assert/strict";
import { createServer as httpServer } from "node:http";
import test from "node:test";
import { fileURLToPath } from "node:url";
import { createServer } from "vite";

const listen = server => new Promise(resolve => server.listen(0, "127.0.0.1", resolve));
const close = server => new Promise(resolve => server.close(resolve));

test("mock-only E2E never forwards an unhandled API request", { timeout: 15000 }, async () => {
  let forwarded = 0;
  const sentinel = httpServer((_request, response) => {
    forwarded++;
    response.writeHead(200, { "Content-Type": "application/json" });
    response.end('{"syntheticSentinel":true}');
  });
  const saved = { proxy: process.env.MOODPRINT_API_PROXY, guard: process.env.MOODPRINT_MOCK_API_ONLY };
  let vite, frontend;
  try {
    await listen(sentinel);
    process.env.MOODPRINT_API_PROXY = `http://127.0.0.1:${sentinel.address().port}`;
    process.env.MOODPRINT_MOCK_API_ONLY = "1";
    vite = await createServer({
      root: fileURLToPath(new URL("..", import.meta.url)),
      envDir: false,
      server: { middlewareMode: true, hmr: false },
    });
    frontend = httpServer((request, response) => vite.middlewares(request, response, () => {
      response.statusCode = 404;
      response.end();
    }));
    await listen(frontend);
    const response = await fetch(`http://127.0.0.1:${frontend.address().port}/api/v1/synthetic-guard-probe`, {
      headers: { Accept: "application/json" },
    });
    await response.text();
    assert.equal(forwarded, 0, "no request may reach even the synthetic API sentinel");
    assert.equal(response.status, 404);
  } finally {
    if (frontend) await close(frontend);
    await vite?.close();
    await close(sentinel);
    for (const [key, value] of [["MOODPRINT_API_PROXY", saved.proxy], ["MOODPRINT_MOCK_API_ONLY", saved.guard]]) {
      if (value === undefined) delete process.env[key];
      else process.env[key] = value;
    }
  }
});
