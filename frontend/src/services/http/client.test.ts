import { describe, expect, it } from "vitest";
import { createApiClient, ApiError } from "./client";

describe("authenticated API requests", () => {
  it("does not retry an outgoing account's mutation under the next account", async () => {
    let identity = "a";
    let requests = 0;
    let refreshes = 0;
    const api = createApiClient({
      baseUrl: "http://localhost:8000",
      getIdentity: () => identity,
      getToken: async () => "old",
      refreshToken: async () => {
        refreshes++;
        return "new-account-token";
      },
      onUnauthenticated: () => {},
      fetch: async () => {
        requests++;
        identity = "b";
        return new Response("{}", { status: 401 });
      },
    });
    await expect(
      api("/v1/cases", { method: "POST", body: '{"id":"outgoing-draft"}' }),
    ).rejects.toMatchObject({ code: "session_changed" });
    expect(requests).toBe(1);
    expect(refreshes).toBe(0);
  });
  it("refreshes once and preserves request body and server error details", async () => {
    const requests: RequestInit[] = [];
    let refreshes = 0;
    const api = createApiClient({
      baseUrl: "http://localhost:8000",
      getToken: async () => "old",
      refreshToken: async () => {
        refreshes++;
        return "new";
      },
      onUnauthenticated: () => {},
      fetch: async (_url, init) => {
        requests.push(init!);
        return requests.length === 1
          ? new Response("{}", { status: 401 })
          : Response.json(
              {
                error: {
                  code: "version_conflict",
                  message: "Changed",
                  requestId: "r1",
                  details: { latest: { version: 3 } },
                },
              },
              { status: 409 },
            );
      },
    });
    await expect(
      api("/v1/cases/id", {
        method: "PATCH",
        body: JSON.stringify({ version: 2 }),
      }),
    ).rejects.toMatchObject({
      status: 409,
      code: "version_conflict",
      details: { latest: { version: 3 } },
      requestId: "r1",
    });
    expect(refreshes).toBe(1);
    expect(new Headers(requests[1].headers).get("Authorization")).toBe(
      "Bearer new",
    );
    expect(requests[1].body).toBe('{"version":2}');
  });
  it("stops after a second 401 and keeps wizard drafts", async () => {
    let requests = 0;
    let expired = 0;
    sessionStorage.setItem("safevoice-case-draft-v1:a:new", "draft");
    const api = createApiClient({
      baseUrl: "http://localhost:8000",
      getToken: async () => "old",
      refreshToken: async () => "new",
      onUnauthenticated: () => {
        expired++;
      },
      fetch: async () => {
        requests++;
        return new Response("{}", { status: 401 });
      },
    });
    await expect(api("/v1/cases")).rejects.toBeInstanceOf(ApiError);
    expect(requests).toBe(2);
    expect(expired).toBe(1);
    expect(sessionStorage.getItem("safevoice-case-draft-v1:a:new")).toBe(
      "draft",
    );
  });
  it("does not send tokens to an absolute third-party URL", async () => {
    let sent = false;
    const api = createApiClient({
      baseUrl: "http://localhost:8000",
      getToken: async () => "token",
      refreshToken: async () => null,
      onUnauthenticated: () => {},
      fetch: async () => {
        sent = true;
        return Response.json({});
      },
    });
    await expect(api("https://example.test/steal")).rejects.toThrow();
    expect(sent).toBe(false);
  });
});
