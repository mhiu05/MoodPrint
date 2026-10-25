import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiClient, ApiError } from "./client";

function respond(status: number) {
  return new Response(
    JSON.stringify(
      status >= 400 ? { error: { code: "X", message: "m" } } : { ok: true },
    ),
    { status, headers: { "Content-Type": "application/json" } },
  );
}

describe("ApiClient idempotency intents", () => {
  afterEach(() => vi.unstubAllGlobals());

  async function keysFor(statuses: number[], distinct = false) {
    const keys: string[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (_url: string, init: RequestInit) => {
        keys.push((init.headers as Record<string, string>)["Idempotency-Key"]);
        return respond(statuses[keys.length - 1]);
      }),
    );
    const client = new ApiClient();
    client.setCsrf("csrf");
    for (const [index] of statuses.entries())
      await client
        .request("/moods/2026-10-25", {
          method: "PUT",
          body: { value: 3, note: distinct ? `n${index}` : "" },
        })
        .catch((error) => expect(error).toBeInstanceOf(ApiError));
    return keys;
  }

  it("retries an ambiguous 5xx with the same key so the server can deduplicate", async () => {
    const [first, second] = await keysFor([503, 200]);
    expect(second).toBe(first);
  });

  it("uses a fresh key after a definite 4xx rejection, which the server rolled back", async () => {
    const [first, second] = await keysFor([409, 200]);
    expect(second).not.toBe(first);
  });

  it("never accumulates rejected intents into the pending-writes limit", async () => {
    const statuses = Array.from({ length: 60 }, () => 422);
    const keys = await keysFor(statuses, true);
    expect(keys).toHaveLength(60);
  });
});
