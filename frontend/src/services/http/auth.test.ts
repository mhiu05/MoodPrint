import { beforeEach, describe, expect, it } from "vitest";
import type { SupabaseClient } from "@supabase/supabase-js";
import { createAuthPort } from "./auth";
import { useWorkspaceStore } from "../../app/store";

describe("Auth SDK boundary", () => {
  beforeEach(() => useWorkspaceStore.getState().reset());
  it("keeps registration credentials out of application state and returns the confirmation step", async () => {
    let sent: Record<string, unknown> | undefined;
    const client = {
      auth: {
        signUp: async (input: Record<string, unknown>) => {
          sent = input;
          return { data: { user: { id: "u" }, session: null }, error: null };
        },
      },
    } as unknown as Pick<SupabaseClient, "auth">;
    const result = await createAuthPort(() => client).signUp({
      email: "synthetic@example.test",
      password: "synthetic-password",
      nickname: "Mây",
      ageBand: "14–17",
      startInterest: "Ghi lại sự việc",
    });
    expect(result.needsEmailConfirmation).toBe(true);
    expect(sent).toMatchObject({
      options: {
        data: {
          nickname: "Mây",
          age_band: "14-17",
          start_interest: "Ghi lại sự việc",
        },
      },
    });
    expect(JSON.stringify(useWorkspaceStore.getState())).not.toContain(
      "synthetic-password",
    );
    expect(localStorage.getItem("moodprint-demo")).not.toContain(
      "synthetic@example.test",
    );
    expect(useWorkspaceStore.getState().user).toBeNull();
  });
  it("returns a restored session identity without exposing a token to the workspace", async () => {
    const client = {
      auth: {
        getSession: async () => ({
          data: {
            session: {
              user: { id: "restored" },
              access_token: "private-session-token",
            },
          },
          error: null,
        }),
      },
    } as unknown as Pick<SupabaseClient, "auth">;
    expect(await createAuthPort(() => client).getSession()).toEqual({
      userId: "restored",
    });
    expect(JSON.stringify(useWorkspaceStore.getState())).not.toContain(
      "private-session-token",
    );
  });
  it("maps invalid credentials to a Vietnamese recovery message", async () => {
    const client = {
      auth: {
        signInWithPassword: async () => ({
          data: { user: null, session: null },
          error: {
            code: "invalid_credentials",
            message: "Invalid login credentials",
          },
        }),
      },
    } as unknown as Pick<SupabaseClient, "auth">;
    await expect(
      createAuthPort(() => client).signIn(
        "synthetic@example.test",
        "incorrect",
      ),
    ).rejects.toThrow("quên mật khẩu");
  });
});
