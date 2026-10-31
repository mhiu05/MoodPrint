import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiClient, ApiError, errorMessage } from "./client";

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

describe("error guidance", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("notifies eligibility denial without treating it as logout or transient retry", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ error: { code: "ELIGIBILITY_REQUIRED", message: "Bạn cần đủ 18 tuổi để sử dụng MoodPrint." } }), { status: 403 })));
    const client = new ApiClient();
    let denied = 0;
    client.onEligibilityDenied = () => { denied += 1; };
    client.onUnauthorized = () => { throw new Error("must preserve account-management session"); };
    await expect(client.request("/journal/entries")).rejects.toMatchObject({ code: "ELIGIBILITY_REQUIRED" });
    expect(denied).toBe(1);
  });

  async function failure(response: Response | Error) {
    vi.stubGlobal("fetch", vi.fn(async () => {
      if (response instanceof Error) throw response;
      return response;
    }));
    return new ApiClient().request("/session").catch((error: unknown) => error);
  }

  it("asks to retry a non-JSON server failure without blaming the input", async () => {
    const error = await failure(new Response("<html>proxy</html>", { status: 500, headers: { "Content-Type": "text/html" } }));
    expect(errorMessage(error)).toBe("Chưa hoàn tất yêu cầu. Bạn hãy thử lại.");
  });

  it("keeps the server's own message for a validation error", async () => {
    const error = await failure(new Response(JSON.stringify({ error: { code: "VALIDATION_ERROR", message: "Dữ liệu chưa hợp lệ." } }), { status: 422, headers: { "Content-Type": "application/json" } }));
    expect(errorMessage(error)).toBe("Dữ liệu chưa hợp lệ.");
  });

  it("explains an unreachable service without promising that input survived", async () => {
    const error = await failure(new TypeError("Failed to fetch"));
    expect(errorMessage(error)).toBe("Chưa thể kết nối. Bạn hãy thử lại.");
  });

  it("keeps retry metadata from a database outage and does not replay login", async () => {
    const fetchMock = vi.fn(async (url: string) => {
      if (String(url).endsWith("/auth/login"))
        return new Response(JSON.stringify({ error: { code: "DATABASE_BUSY", message: "MoodPrint đang hơi đông.", retryable: true, requestId: "req-9" } }), {
          status: 503,
          headers: { "Content-Type": "application/json", "Retry-After": "2", "X-Request-ID": "req-9" },
        });
      return respond(200);
    });
    vi.stubGlobal("fetch", fetchMock);
    const client = new ApiClient();
    const error = await client.request("/auth/login", { method: "POST", body: { email: "a@b.c", password: "secret" }, publicWrite: true }).catch((reason: unknown) => reason);
    expect(error).toMatchObject({ status: 503, code: "DATABASE_BUSY", retryable: true, requestId: "req-9", retryAfter: "2" });
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("blocks private writes while a session is unconfirmed and still allows the session read", async () => {
    const fetchMock = vi.fn(async () => respond(200));
    vi.stubGlobal("fetch", fetchMock);
    const client = new ApiClient();
    client.setCsrf("csrf");
    client.setPrivateHold(() => true);
    await expect(client.request("/journal/entries", { method: "POST", body: { text: "private" } })).rejects.toMatchObject({ code: "CONNECTION_PAUSED" });
    expect(fetchMock).not.toHaveBeenCalled();
    await expect(client.request("/session")).resolves.toEqual({ ok: true });
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});
