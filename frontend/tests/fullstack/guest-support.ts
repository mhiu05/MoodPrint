import { expect, type BrowserContext, type Page } from "@playwright/test";
import { randomUUID } from "node:crypto";
import { api, origin } from "./helpers";

export async function guestCall(context: BrowserContext, method: string, path: string, data?: unknown) {
  const csrf = (await context.cookies(origin)).find(c => c.name === "moodprint_csrf")?.value;
  return context.request.fetch(api + path, { method, data, headers: {
    Origin: origin, "X-CSRF-Token": csrf || "", "Idempotency-Key": randomUUID(),
  }});
}

export async function createGuest(context: BrowserContext) {
  const intent = await context.request.post(api + "/auth/guest-intents", {
    data: {}, headers: { Origin: origin, "X-Guest-Intent": "1" },
  });
  expect(intent.status()).toBe(204);
  const response = await context.request.post(api + "/auth/guest", {
    data: { eligibility: { birthYear: 2000, confirmedMinimumAge: true, confirmedAdultAge: false,
      policyVersion: "self-declared-age-v2-18plus", expectedVersion: 0 },
      captchaToken: "synthetic-captcha-token", disclosureVersion: "guest-v1" },
    headers: { Origin: origin, "X-Guest-Intent": "1", "Idempotency-Key": randomUUID() },
  });
  expect(response.status(), await response.text()).toBe(201);
  return response.json();
}

export async function publicEntry(page: Page) {
  await page.goto("/");
  await page.getByRole("button", { name: "Dùng thử 2 giờ", exact: true }).first().click();
  await page.getByLabel("Năm sinh", { exact: true }).fill("2000");
  await page.getByRole("checkbox", { name: "Tôi xác nhận mình đã đủ 18 tuổi." }).check();
  const granted = page.waitForResponse(r => r.url().endsWith("/auth/guest") && r.request().method() === "POST");
  await page.getByRole("button", { name: "Bắt đầu dùng thử", exact: true }).click();
  const response = await granted;
  expect(response.status(), await response.text()).toBe(201);
  return response.json();
}
