// E-AG-08 / E-AG-09: cancellation and network recovery in the real browser against the real stack.
// The model stand-in is slow on demand ("trả lời chậm") or fails once ("lỗi một lần"); everything
// else (run lifecycle, SSE, cancel grace, approvals, recovery, idempotent retry) is real.
import type { Page } from "@playwright/test";
import { test, expect } from "./helpers/fixtures";
import {
  apiJson,
  createCaseViaApi,
  createUser,
  login,
  removeUser,
  tokenFor,
} from "./helpers/local";

async function openChat(page: Page, email: string) {
  await page.addInitScript(() =>
    localStorage.setItem("moodprint:ai-companion", "live"),
  );
  await login(page, email);
  await expect(page).toHaveURL(/\/home$/);
  await page.goto("/ai/chat");
  await page.getByRole("button", { name: /Cuộc trò chuyện mới/ }).click();
  await expect(page.getByTestId("chat-live")).toBeVisible();
  await expect(page.getByText(/Bạn muốn kể điều gì/)).toBeVisible();
}
async function say(page: Page, text: string) {
  // Typing while the previous run is still finishing is ignored by the UI; wait until it can send.
  await expect(page.getByRole("button", { name: "Gửi" })).toBeVisible();
  const box = page.getByRole("textbox", { name: "Điều bạn muốn kể" });
  await box.fill(text);
  await box.press("Enter");
}
function conversationId(page: Page): string {
  const id = new URL(page.url()).pathname.split("/").pop() ?? "";
  expect(id).toMatch(/^[0-9a-f-]{36}$/);
  return id;
}
async function turns(email: string, id: string) {
  const response = await apiJson(
    `/v1/conversations/${id}/messages?limit=100`,
    await tokenFor(email),
  );
  expect(response.status).toBe(200);
  return (await response.json()).items as { role: string; content: string }[];
}
async function runStatus(email: string, runId: string) {
  const response = await apiJson(`/v1/runs/${runId}`, await tokenFor(email));
  return response.status === 200
    ? ((await response.json()).status as string)
    : "none";
}

test("E-AG-08a: stopping a slow answer ends the run as cancelled, adds no answer, and the chat keeps working", async ({
  page,
}) => {
  test.setTimeout(120000);
  const user = await createUser();
  try {
    await openChat(page, user.email);
    const cancel = page.waitForRequest(
      (r) =>
        /\/v1\/runs\/[0-9a-f-]{36}\/cancel$/.test(r.url()) &&
        r.method() === "POST",
    );
    await say(page, "Hãy trả lời chậm giúp mình nhé");
    await expect(page.getByRole("button", { name: "Dừng" })).toBeVisible();
    await page.getByRole("button", { name: "Dừng" }).click();
    const runId = (await cancel)
      .url()
      .match(/runs\/([0-9a-f-]{36})\/cancel/)![1];
    await expect(page.getByRole("button", { name: "Gửi" })).toBeVisible({
      timeout: 20000,
    });
    await expect
      .poll(() => runStatus(user.email, runId), { timeout: 20000 })
      .toBe("cancelled");
    const id = conversationId(page);
    const afterCancel = await turns(user.email, id);
    expect(afterCancel.map((t) => t.role)).toEqual(["user"]); // no answer was produced or stored
    // The next message works and nothing is duplicated.
    await say(page, "Mình hỏi lại: bạn có nghe mình không?");
    await expect(page.getByText(/Mình nghe đây/)).toBeVisible({
      timeout: 20000,
    });
    const final = await turns(user.email, id);
    expect(final.map((t) => t.role)).toEqual(["user", "user", "assistant"]);
  } finally {
    await page.close();
    await removeUser(user.email);
  }
});

test("E-AG-08b: cancelling while a proposal waits for approval expires it, writes nothing and survives a reload", async ({
  page,
}) => {
  test.setTimeout(120000);
  const user = await createUser();
  try {
    const { id: caseId } = await createCaseViaApi(user.email);
    await openChat(page, user.email);
    await say(page, "Giúp mình ghi mốc bạn A chế giễu hôm 3/11");
    await expect(page.getByText(/CHƯA LƯU/)).toBeVisible();
    await say(page, "Ok, lưu mốc đó vào hồ sơ");
    await expect(page.getByRole("dialog")).toBeVisible();
    await page
      .getByRole("dialog")
      .getByRole("button", { name: "Đóng" })
      .click();
    await expect(
      page.getByText(/đề xuất đang chờ bạn quyết định/),
    ).toBeVisible();
    // Find the waiting run from what the page itself asks for after a reload, then cancel it.
    const approvals = page.waitForRequest((r) =>
      /\/v1\/runs\/[0-9a-f-]{36}\/approvals$/.test(r.url()),
    );
    await page.reload();
    const runId = (await approvals)
      .url()
      .match(/runs\/([0-9a-f-]{36})\/approvals/)![1];
    const token = await tokenFor(user.email);
    const cancelled = await apiJson(`/v1/runs/${runId}/cancel`, token, {
      method: "POST",
    });
    expect(cancelled.status).toBe(200);
    expect(await runStatus(user.email, runId)).not.toBe("awaiting_approval");
    const events =
      (await (await apiJson(`/v1/cases/${caseId}`, token)).json()).events ?? [];
    expect(events).toEqual([]); // nothing was written
    // A second cancel is harmless, and after a reload the dialog is gone.
    expect(
      (await apiJson(`/v1/runs/${runId}/cancel`, token, { method: "POST" }))
        .status,
    ).toBe(200);
    await page.reload();
    await expect(page.getByRole("dialog")).toHaveCount(0);
    await expect(page.getByText(/đề xuất đang chờ bạn quyết định/)).toHaveCount(
      0,
    );
    expect(
      (await (await apiJson(`/v1/cases/${caseId}`, token)).json()).events ?? [],
    ).toEqual([]);
  } finally {
    await page.close();
    await removeUser(user.email);
  }
});

test("E-AG-09a: a one-time failure shows a retry; the retry reuses the message and yields exactly one answer", async ({
  page,
}) => {
  test.setTimeout(120000);
  const user = await createUser();
  try {
    await openChat(page, user.email);
    await say(page, "Mình muốn kể một chuyện, lỗi một lần");
    const alert = page.getByRole("alert");
    await expect(alert).toBeVisible();
    await expect(alert).not.toContainText("e2e injected");
    await alert.getByRole("button", { name: "Thử lại" }).click();
    await expect(page.getByText(/Mình nghe đây/)).toBeVisible();
    await expect(page.getByRole("alert")).toHaveCount(0);
    const stored = await turns(user.email, conversationId(page));
    expect(stored.map((t) => t.role)).toEqual(["user", "assistant"]); // the user's text was stored once
  } finally {
    await page.close();
    await removeUser(user.email);
  }
});

test("E-AG-09b: the stream is cut after run.started; the page recovers the stored answer once, and a retry replays it without a second answer", async ({
  page,
}) => {
  test.setTimeout(120000);
  const user = await createUser();
  try {
    await openChat(page, user.email);
    // The server finishes the whole run; the browser only ever sees the first event, then the
    // connection ends without a terminal event (a mid-stream network drop).
    let cut = 0;
    await page.route("**/v1/conversations/*/messages", async (route) => {
      if (route.request().method() !== "POST" || cut++ > 0)
        return route.fallback();
      const response = await route.fetch();
      const events = (await response.text()).split("\n\n");
      const head = events.filter((e) => e.startsWith("event: run.started"));
      await route.fulfill({
        status: 200,
        headers: response.headers(),
        body: head.join("\n\n") + "\n\n",
      });
    });
    await say(page, "Mình muốn kể một chuyện khi mạng chập chờn");
    const id = conversationId(page);
    // Recovery shows the stored transcript: the answer appears exactly once.
    await expect(page.getByText(/Mình nghe đây/)).toBeVisible({
      timeout: 30000,
    });
    await expect(page.getByText(/Mình nghe đây/)).toHaveCount(1);
    expect((await turns(user.email, id)).map((t) => t.role)).toEqual([
      "user",
      "assistant",
    ]);
    // "Thử lại" re-sends the same client id: the server replays the stored answer, never a second run.
    const retry = page.getByRole("button", { name: "Thử lại" });
    if (await retry.isVisible()) {
      await retry.click();
      await expect(page.getByRole("button", { name: "Gửi" })).toBeVisible();
    }
    await expect(page.getByText(/Mình nghe đây/)).toHaveCount(1);
    expect((await turns(user.email, id)).map((t) => t.role)).toEqual([
      "user",
      "assistant",
    ]);
  } finally {
    await page.close();
    await removeUser(user.email);
  }
});
