import { expect, type BrowserContext, type Page } from "@playwright/test";
import { createHash, randomUUID } from "node:crypto";

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

/** The pseudonymous card alias the server derives for a pair (social/routes.py). */
export function pairAlias(a: number, b: number) {
  const seed = createHash("sha256")
    .update([userId(a), userId(b)].sort().join(":"))
    .digest("hex");
  return `Bạn đồng hành ${seed.slice(0, 6)}`;
}

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

export async function enable(page: Page, name: string) {
  await page.goto("/#/settings");
  const button = page.getByRole("button", { name: `Bật ${name}`, exact: true });
  // Wait for the rendered state before deciding; count() alone races the first render.
  await expect(
    button.or(page.getByRole("button", { name: `Tắt ${name}`, exact: true })),
  ).toBeVisible();
  if (await button.count()) await button.click();
  await expect(
    page.getByRole("button", { name: `Tắt ${name}`, exact: true }),
  ).toBeVisible();
}

export async function disable(page: Page, name: string) {
  await page.goto("/#/settings");
  await page.getByRole("button", { name: `Tắt ${name}`, exact: true }).click();
  await expect(
    page.getByRole("button", { name: `Bật ${name}`, exact: true }),
  ).toBeVisible();
}

/** Drives the five-step profile editor with the shared synthetic profile. */
export async function fillProfileEditor(page: Page) {
  await page.getByRole("button", { name: "Chỉnh hồ sơ kết nối" }).click();
  const next = page.getByRole("button", { name: "Tiếp tục", exact: true });
  for (const labels of [
    ["Đọc sách", "Âm nhạc", "Đi bộ"],
    ["Tôn trọng", "Chân thành"],
    ["Tiếng Việt"],
  ]) {
    for (const label of labels) {
      const box = page.getByRole("checkbox", { name: label, exact: true });
      if (!(await box.isChecked())) await box.check();
    }
    await next.click();
  }
  await page.getByRole("button", { name: "Xem trước hồ sơ" }).click();
  await expect(
    page.getByText("Đã lưu bản nháp.", { exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Xuất bản hồ sơ", exact: true })
    .click();
  await expect(
    page.getByText("Đã xuất bản hồ sơ.", { exact: true }),
  ).toBeVisible();
}

export async function publish(page: Page) {
  await enable(page, "tìm bạn");
  await page.goto("/#/connect?tab=profile");
  await fillProfileEditor(page);
}

/**
 * Publishes both users through the API and connects them; returns the room id.
 * English-only profiles keep these pairs out of the UI journeys' Vietnamese pool.
 */
export async function connectByApi(
  a: BrowserContext,
  aNumber: number,
  b: BrowserContext,
  bNumber: number,
  goal: "friendship" | "shared-interests",
) {
  for (const [context, number] of [
    [a, aNumber],
    [b, bNumber],
  ] as const) {
    expect(
      (
        await call(context, number, "PUT", "/consents/MATCH", {
          enabled: true,
          expectedVersion: 1,
          policyVersion: "v1",
        })
      ).status,
    ).toBe(200);
    await call(context, number, "PUT", "/profiles/matching-draft", {
      interests: ["reading", "music", "walking"],
      values: ["respect", "kindness"],
      style: "balanced",
      goal,
      languages: ["en"],
      expectedVersion: 0,
    });
    const preview = await call(
      context,
      number,
      "POST",
      "/profiles/matching-draft/preview",
    );
    const published = await call(
      context,
      number,
      "POST",
      "/profiles/published",
      {
        draftVersion: preview.body.draftVersion,
        previewDigest: preview.body.previewDigest,
        expectedPublishedVersion: 0,
      },
    );
    expect(published.status, published.text).toBe(201);
  }
  const cards = await call(a, aNumber, "GET", "/matching/candidates");
  const card = cards.body.candidates.find(
    (item: { alias: string }) => item.alias === pairAlias(aNumber, bNumber),
  );
  expect(card, JSON.stringify(cards.body)).toBeTruthy();
  const ref = card.candidateRef;
  const pending = await call(a, aNumber, "POST", "/connection-requests", {
    candidateRef: ref,
  });
  expect(pending.status, pending.text).toBe(201);
  const accepted = await call(
    b,
    bNumber,
    "POST",
    `/connection-requests/${pending.body.id}/accept`,
    { expectedVersion: pending.body.version },
  );
  expect(accepted.status, accepted.text).toBe(200);
  return accepted.body.connectionId as string;
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
