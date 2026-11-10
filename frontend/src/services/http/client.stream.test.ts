import { describe, expect, it, vi } from "vitest";
import { createApiClient, ApiError, type ClientOptions } from "./client";

function client(overrides: Partial<ClientOptions> = {}) {
  return createApiClient({
    baseUrl: "http://localhost:8000/",
    getToken: async () => "old",
    refreshToken: async () => "new",
    onUnauthenticated: () => {},
    ...overrides,
  });
}

describe("authenticated stream transport", () => {
  it("refreshes once, preserves the request, and leaves the successful body unread", async () => {
    const requests: { url: unknown; init: RequestInit }[] = [];
    const refreshToken = vi.fn(async () => "new");
    const response = new Response("event: heartbeat\ndata: {}\n\n", {
      headers: { "Content-Type": "text/event-stream" },
    });
    const controller = new AbortController();
    const api = client({
      refreshToken,
      fetch: async (url, init) => {
        requests.push({ url, init: init! });
        return requests.length === 1
          ? Response.json({}, { status: 401 })
          : response;
      },
    });
    const result = await api.stream("/v1/conversations/id/messages", {
      method: "POST",
      headers: { Accept: "text/event-stream" },
      body: '{"content":"synthetic"}',
      signal: controller.signal,
    });
    expect(result).toBe(response);
    expect(result.bodyUsed).toBe(false);
    expect(await result.text()).toBe("event: heartbeat\ndata: {}\n\n");
    expect(refreshToken).toHaveBeenCalledTimes(1);
    expect(requests).toHaveLength(2);
    for (const [index, { url, init }] of requests.entries()) {
      expect(url).toBe("http://localhost:8000/v1/conversations/id/messages");
      expect(init).toMatchObject({
        method: "POST",
        body: '{"content":"synthetic"}',
        signal: controller.signal,
        credentials: "omit",
        cache: "no-store",
      });
      const headers = new Headers(init.headers);
      expect(headers.get("Authorization")).toBe(
        index ? "Bearer new" : "Bearer old",
      );
      expect(headers.get("Content-Type")).toBe("application/json");
      expect(headers.get("Accept")).toBe("text/event-stream");
    }
  });

  it("expires the session after the refreshed token also receives 401", async () => {
    const fetch = vi.fn(async () => Response.json({}, { status: 401 }));
    const refreshToken = vi.fn(async () => "new");
    const onUnauthenticated = vi.fn();
    const api = client({ fetch, refreshToken, onUnauthenticated });
    await expect(api.stream("/v1/conversations")).rejects.toBeInstanceOf(
      ApiError,
    );
    expect(fetch).toHaveBeenCalledTimes(2);
    expect(refreshToken).toHaveBeenCalledTimes(1);
    expect(onUnauthenticated).toHaveBeenCalledTimes(1);
  });

  it.each(["missing", "rejected"])(
    "expires the session when refresh is %s",
    async (kind) => {
      const fetch = vi.fn(async () => Response.json({}, { status: 401 }));
      const onUnauthenticated = vi.fn();
      const api = client({
        fetch,
        onUnauthenticated,
        refreshToken: async () => {
          if (kind === "rejected") throw Error("expired");
          return null;
        },
      });
      await expect(api.stream("/v1/conversations")).rejects.toMatchObject({
        status: 401,
      });
      expect(fetch).toHaveBeenCalledTimes(1);
      expect(onUnauthenticated).toHaveBeenCalledTimes(1);
    },
  );

  it.each(["request", "refresh"])(
    "rejects account changes during %s without a second fetch",
    async (stage) => {
      let identity = "outgoing";
      const fetch = vi.fn(async () => {
        if (stage === "request") identity = "incoming";
        return Response.json({}, { status: 401 });
      });
      const onUnauthenticated = vi.fn();
      const api = client({
        getIdentity: () => identity,
        fetch,
        onUnauthenticated,
        refreshToken: async () => {
          identity = "incoming";
          return "incoming-token";
        },
      });
      await expect(api.stream("/v1/conversations")).rejects.toMatchObject({
        code: "session_changed",
      });
      expect(fetch).toHaveBeenCalledTimes(1);
      expect(onUnauthenticated).not.toHaveBeenCalled();
    },
  );

  it("rejects an outgoing response after the account changes", async () => {
    let identity = "outgoing";
    const api = client({
      getIdentity: () => identity,
      fetch: async () => {
        identity = "incoming";
        return new Response("private stream");
      },
    });
    await expect(api.stream("/v1/conversations")).rejects.toMatchObject({
      code: "session_changed",
    });
  });

  it("maps an unsuccessful stream envelope before exposing the response", async () => {
    const api = client({
      fetch: async () =>
        Response.json(
          {
            error: {
              code: "run_in_progress",
              message: "Already running",
              requestId: "request-1",
              details: { runId: "run-1" },
            },
          },
          { status: 409 },
        ),
    });
    await expect(
      api.stream("/v1/conversations/id/messages"),
    ).rejects.toMatchObject({
      name: "ApiError",
      status: 409,
      code: "run_in_progress",
      message: "Already running",
      requestId: "request-1",
      details: { runId: "run-1" },
    });
  });

  it("maps non-JSON errors using the response request ID", async () => {
    const api = client({
      fetch: async () =>
        new Response("unavailable", {
          status: 503,
          headers: { "X-Request-ID": "request-2" },
        }),
    });
    await expect(api.stream("/v1/conversations")).rejects.toMatchObject({
      status: 503,
      code: "upstream_error",
      requestId: "request-2",
    });
  });

  it("preserves AbortError when the caller aborts an in-flight fetch", async () => {
    const controller = new AbortController();
    const api = client({
      fetch: async (_url, init) =>
        new Promise<Response>((_resolve, reject) => {
          init!.signal!.addEventListener(
            "abort",
            () => reject(init!.signal!.reason),
            { once: true },
          );
          controller.abort(new DOMException("Cancelled", "AbortError"));
        }),
    });
    await expect(
      api.stream("/v1/conversations", { signal: controller.signal }),
    ).rejects.toMatchObject({ name: "AbortError" });
  });

  it("does not retry when the caller aborts while refresh is in flight", async () => {
    const controller = new AbortController();
    const fetch = vi.fn(async () => Response.json({}, { status: 401 }));
    const onUnauthenticated = vi.fn();
    const api = client({
      fetch,
      onUnauthenticated,
      refreshToken: async () => {
        controller.abort(new DOMException("Cancelled", "AbortError"));
        return "new";
      },
    });
    await expect(
      api.stream("/v1/conversations", { signal: controller.signal }),
    ).rejects.toMatchObject({ name: "AbortError" });
    expect(fetch).toHaveBeenCalledTimes(1);
    expect(onUnauthenticated).not.toHaveBeenCalled();
  });

  it("maps a network failure without expiring the session", async () => {
    const onUnauthenticated = vi.fn();
    const api = client({
      onUnauthenticated,
      fetch: async () => {
        throw new TypeError("offline");
      },
    });
    await expect(api.stream("/v1/conversations")).rejects.toMatchObject({
      status: 0,
      code: "network_error",
    });
    expect(onUnauthenticated).not.toHaveBeenCalled();
  });

  it("does not add a JSON content type to a bodyless stream", async () => {
    let headers: Headers | undefined;
    const api = client({
      fetch: async (_url, init) => {
        headers = new Headers(init!.headers);
        return new Response(null, { status: 204 });
      },
    });
    expect((await api.stream("/v1/conversations")).status).toBe(204);
    expect(headers!.get("Content-Type")).toBeNull();
  });

  it("shares an in-flight refresh between JSON and stream requests", async () => {
    let finishRefresh!: (token: string) => void;
    const refreshed = new Promise<string>((resolve) => {
      finishRefresh = resolve;
    });
    let signalBothUnauthorized!: () => void;
    const bothUnauthorized = new Promise<void>((resolve) => {
      signalBothUnauthorized = resolve;
    });
    let unauthorized = 0;
    const refreshToken = vi.fn(() => refreshed);
    const api = client({
      refreshToken,
      fetch: async (url, init) => {
        if (new Headers(init!.headers).get("Authorization") === "Bearer old") {
          unauthorized++;
          if (unauthorized === 2) signalBothUnauthorized();
          return Response.json({}, { status: 401 });
        }
        return String(url).endsWith("/stream")
          ? new Response("streamed")
          : Response.json({ ok: true });
      },
    });
    const json = api("/v1/me");
    const stream = api.stream("/v1/stream");
    await bothUnauthorized;
    await Promise.resolve();
    finishRefresh("new");
    expect(await json).toEqual({ ok: true });
    expect(await (await stream).text()).toBe("streamed");
    expect(refreshToken).toHaveBeenCalledTimes(1);
  });

  it("does not send a token after identity changes during token lookup", async () => {
    let identity = "outgoing";
    const fetch = vi.fn(async () => new Response());
    const api = client({
      getIdentity: () => identity,
      fetch,
      getToken: async () => {
        identity = "incoming";
        return "outgoing-token";
      },
    });
    await expect(api.stream("/v1/conversations")).rejects.toMatchObject({
      code: "session_changed",
    });
    expect(fetch).not.toHaveBeenCalled();
  });

  it("does not fetch when the signal is already aborted", async () => {
    const controller = new AbortController();
    controller.abort(new DOMException("Cancelled", "AbortError"));
    const fetch = vi.fn(async () => new Response());
    await expect(
      client({ fetch }).stream("/v1/conversations", {
        signal: controller.signal,
      }),
    ).rejects.toMatchObject({ name: "AbortError" });
    expect(fetch).not.toHaveBeenCalled();
  });

  it("preserves cancellation while reading an error envelope", async () => {
    const controller = new AbortController();
    const response = new Response(null, { status: 409 });
    response.json = async () => {
      controller.abort(new DOMException("Cancelled", "AbortError"));
      throw controller.signal.reason;
    };
    const api = client({ fetch: async () => response });
    await expect(
      api.stream("/v1/conversations", { signal: controller.signal }),
    ).rejects.toMatchObject({ name: "AbortError" });
  });

  it("rejects account changes while reading an error envelope", async () => {
    let identity = "outgoing";
    const response = new Response(null, { status: 409 });
    response.json = async () => {
      identity = "incoming";
      return { error: { code: "run_in_progress", message: "Private error" } };
    };
    const api = client({
      getIdentity: () => identity,
      fetch: async () => response,
    });
    await expect(api.stream("/v1/conversations")).rejects.toMatchObject({
      code: "session_changed",
    });
  });

  it("sets the JSON content type when the request has an empty body", async () => {
    let headers: Headers | undefined;
    const api = client({
      fetch: async (_url, init) => {
        headers = new Headers(init!.headers);
        return new Response();
      },
    });
    await api.stream("/v1/conversations", { method: "POST", body: "" });
    expect(headers!.get("Content-Type")).toBe("application/json");
  });

  it.each([
    "https://example.test/steal",
    "//example.test/v1/steal",
    "/health",
    "/v1",
    "/v1/\\steal",
    "/v1/\r\nsteal",
  ])("rejects invalid path %j before reading tokens", async (path) => {
    const getToken = vi.fn(async () => "secret");
    const fetch = vi.fn(async () => new Response());
    await expect(client({ getToken, fetch }).stream(path)).rejects.toThrow();
    expect(getToken).not.toHaveBeenCalled();
    expect(fetch).not.toHaveBeenCalled();
  });
});
