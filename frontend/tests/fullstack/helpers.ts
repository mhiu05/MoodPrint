import {
  expect,
  type BrowserContext,
  type Page,
} from "@playwright/test";
import { randomUUID } from "node:crypto";

export const origin = "http://127.0.0.1:5174";
export const api = `${origin}/api/v1`;

/** Synthetic opaque sessions seeded by backend/tests/e2e_server.py. */
export async function session(context: BrowserContext, number: number) {
  await context.addCookies([
    {
      name: "moodprint_session",
      value: `e2e-synthetic-session-${number}`,
      url: origin,
      httpOnly: true,
      sameSite: "Strict",
    },
    {
      name: "moodprint_csrf",
      value: `e2e-synthetic-csrf-${number}`,
      url: origin,
      sameSite: "Strict",
    },
  ]);
}

export const userId = (number: number) =>
  `00000000-0000-4000-8000-${String(number).padStart(12, "0")}`;

/** A real API call as the given synthetic user, returning status and JSON. */
export async function call(
  context: BrowserContext,
  number: number,
  method: string,
  path: string,
  data?: unknown,
) {
  const response = await context.request.fetch(api + path, {
    method,
    data,
    headers:
      method === "GET"
        ? {}
        : {
            "X-CSRF-Token": `e2e-synthetic-csrf-${number}`,
            "Idempotency-Key": randomUUID(),
          },
  });
  const text = await response.text();
  return {
    status: response.status(),
    body: text ? JSON.parse(text) : undefined,
    text,
  };
}

export async function noHorizontalOverflow(page: Page) {
  await expect
    .poll(() =>
      page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth + 1,
      ),
    )
    .toBe(true);
}
