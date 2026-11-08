import { randomUUID } from "node:crypto";
import type { Page } from "@playwright/test";
import { expect } from "./fixtures";

export const password = "Synthetic-only-41!";

export function settings() {
  const supabase = process.env.E2E_SUPABASE_URL;
  const api = process.env.E2E_API_URL;
  const mail = process.env.E2E_MAIL_URL;
  const key = process.env.SUPABASE_PUBLISHABLE_KEY;
  const secret = process.env.SUPABASE_SECRET_KEY;
  if (!supabase || !api || !mail || !key || !secret)
    throw new Error("Run real E2E with python scripts/e2e_stack.py --run");
  for (const value of [supabase, api, mail])
    if (!["127.0.0.1", "localhost", "[::1]"].includes(new URL(value).hostname))
      throw new Error("Real E2E accepts loopback endpoints only");
  return { supabase, api, mail, key, secret };
}

async function authJson(path: string, body?: unknown, admin = false) {
  const config = settings();
  // Native node fetch keeps admin credentials out of browser traces and artifacts.
  const response = await fetch(`${config.supabase}/auth/v1/${path}`, {
    method: body ? "POST" : "GET",
    headers: {
      apikey: admin ? config.secret : config.key,
      ...(admin ? { Authorization: `Bearer ${config.secret}` } : {}),
      "Content-Type": "application/json",
    },
    ...(body ? { body: JSON.stringify(body) } : {}),
  });
  if (!response.ok)
    throw new Error(
      `Local Auth ${path.split("?")[0]} returned ${response.status}`,
    );
  return response.json();
}

export async function createUser(nickname = "Mây tổng hợp") {
  const email = `e2e+${randomUUID()}@example.test`;
  const user = await authJson(
    "admin/users",
    {
      email,
      password,
      email_confirm: true,
      user_metadata: { nickname, age_band: "14-17" },
    },
    true,
  );
  return { id: user.id as string, email, password };
}

export async function tokenFor(
  email: string,
  currentPassword = password,
): Promise<string> {
  const data = await authJson("token?grant_type=password", {
    email,
    password: currentPassword,
  });
  return data.access_token as string;
}

export async function apiJson(
  path: string,
  token: string,
  init: RequestInit = {},
) {
  return fetch(`${settings().api}${path}`, {
    ...init,
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
      ...init.headers,
    },
  });
}

export async function removeUser(email: string, currentPassword = password) {
  const token = await tokenFor(email, currentPassword);
  const response = await apiJson("/v1/me", token, {
    method: "DELETE",
    body: JSON.stringify({ confirm: "DELETE" }),
  });
  expect(response.status, "Synthetic account and Storage cleanup").toBe(204);
}

export async function login(
  page: Page,
  email: string,
  currentPassword = password,
) {
  await page.goto("/auth");
  await page.getByRole("textbox", { name: "Email", exact: true }).fill(email);
  await page.getByLabel("Mật khẩu", { exact: true }).fill(currentPassword);
  await page
    .locator("form")
    .filter({ has: page.getByRole("textbox", { name: "Email", exact: true }) })
    .getByRole("button", { name: "Đăng nhập", exact: true })
    .click();
}

export async function signOut(page: Page) {
  await page.goto("/settings");
  await page.getByRole("button", { name: "Đăng xuất", exact: true }).click();
  await expect(page).toHaveURL(/\/auth$/);
}

async function mailMessages(email: string): Promise<string[]> {
  const config = settings();
  const response = await fetch(
    `${config.mail}/api/v1/search?query=${encodeURIComponent(`to:${email}`)}`,
  );
  if (response.ok) {
    const data = await response.json();
    const messages = data.messages ?? data.Messages ?? [];
    const bodies = await Promise.all(
      messages.map(async (message: { ID?: string; id?: string }) => {
        const reply = await fetch(
          `${config.mail}/api/v1/message/${message.ID ?? message.id}`,
        );
        if (!reply.ok) return "";
        const item = await reply.json();
        return `${item.HTML ?? ""}\n${item.Text ?? ""}`;
      }),
    );
    return bodies;
  }
  const mailbox = encodeURIComponent(email.split("@")[0]);
  const list = await fetch(`${config.mail}/api/v1/mailbox/${mailbox}`);
  if (!list.ok) return [];
  const messages = await list.json();
  return Promise.all(
    messages.map(async (message: { id: string }) => {
      const reply = await fetch(
        `${config.mail}/api/v1/mailbox/${mailbox}/${message.id}`,
      );
      const item = await reply.json();
      return `${item.body?.html ?? ""}\n${item.body?.text ?? ""}`;
    }),
  );
}

export async function followEmail(
  page: Page,
  email: string,
  type: "signup" | "recovery",
) {
  let link = "";
  await expect
    .poll(
      async () => {
        for (const body of await mailMessages(email)) {
          const links =
            body
              .replaceAll("&amp;", "&")
              .match(/https?:[^\s"<>]+\/auth\/v1\/verify[^\s"<>]+/g) ?? [];
          const found = links.find(
            (candidate) => new URL(candidate).searchParams.get("type") === type,
          );
          if (found) {
            link = found;
            return true;
          }
        }
        return false;
      },
      { timeout: 20000, message: `Local ${type} email arrived` },
    )
    .toBe(true);
  expect(new URL(link).origin).toBe(new URL(settings().supabase).origin);
  await page.goto(link);
}

export async function createCaseViaApi(
  email: string,
  title = "Hồ sơ tổng hợp",
) {
  const token = await tokenFor(email);
  const id = randomUUID();
  const response = await apiJson("/v1/cases", token, {
    method: "POST",
    body: JSON.stringify({
      id,
      title,
      template: "TPL-FREE",
      perspective: "self",
      summary: "Một tình huống hoàn toàn hư cấu để kiểm thử.",
      status: "active",
    }),
  });
  expect(response.ok, `Create synthetic case returned ${response.status}`).toBe(
    true,
  );
  return { id, token };
}
