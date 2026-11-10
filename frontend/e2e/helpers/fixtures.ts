import { test as base, expect, type BrowserContext } from "@playwright/test";

export { expect };

export async function guardNetwork(
  context: BrowserContext,
  real: boolean,
  frontend = process.env.E2E_BASE_URL ?? "http://127.0.0.1:5178",
) {
  const forbidden: string[] = [];
  const api = process.env.E2E_API_URL ?? "http://127.0.0.1:8008";
  const supabase = process.env.E2E_SUPABASE_URL ?? "http://127.0.0.1:54321";
  for (const value of [frontend, api, supabase]) {
    const url = new URL(value);
    if (!["127.0.0.1", "localhost", "[::1]"].includes(url.hostname))
      throw new Error("E2E browser endpoints must use loopback");
  }
  await context.route("**/*", async (route) => {
    const url = new URL(route.request().url());
    const safe =
      ["data:", "blob:"].includes(url.protocol) ||
      url.origin === new URL(frontend).origin ||
      (real &&
        (url.origin === new URL(api).origin ||
          (url.origin === new URL(supabase).origin &&
            /^\/(auth|storage)\/v1\//.test(url.pathname))));
    if (safe) await route.continue();
    else {
      // Never record query strings; signed upload/download tokens live there.
      forbidden.push(`${url.origin}${url.pathname}`);
      await route.abort("blockedbyclient");
    }
  });
  return forbidden;
}

export const test = base.extend<{
  expectedHttpStatuses: number[];
  boundaryChecks: void;
}>({
  expectedHttpStatuses: [[], { option: true }],
  boundaryChecks: [
    async ({ context, baseURL, expectedHttpStatuses }, use, info) => {
      const forbidden = await guardNetwork(
        context,
        info.project.name === "real",
        baseURL,
      );
      const errors: { text: string; url: string }[] = [];
      const emptyPlans = new Set<string>();
      const responseChecks: Promise<void>[] = [];
      context.on("page", (page) => {
        page.on("pageerror", (error) =>
          errors.push({ text: error.message, url: "" }),
        );
        page.on("response", (response) => {
          if (
            response.status() !== 404 ||
            !/\/v1\/cases\/[0-9a-f-]{36}\/plan$/.test(response.url())
          )
            return;
          responseChecks.push(
            response
              .json()
              .then((body) => {
                // This is the documented empty-plan result, not a failed mutation.
                if (
                  body.error?.code === "not_found" &&
                  body.error?.message === "Hồ sơ chưa có kế hoạch."
                )
                  emptyPlans.add(response.url());
              })
              .catch(() => {}),
          );
        });
        page.on("console", (message) => {
          if (message.type() !== "error") return;
          const text = message.text();
          if (
            expectedHttpStatuses.some((status) =>
              text.includes(`server responded with a status of ${status}`),
            )
          )
            return;
          errors.push({ text, url: message.location().url });
        });
      });
      await use();
      await Promise.all(responseChecks);
      expect(forbidden, "Requests outside the workspace allow-list").toEqual(
        [],
      );
      expect(
        errors.filter(
          ({ text, url }) =>
            !(
              emptyPlans.has(url) &&
              text.includes("server responded with a status of 404")
            ),
        ),
        "Unexpected browser errors",
      ).toEqual([]);
    },
    { auto: true },
  ],
});
