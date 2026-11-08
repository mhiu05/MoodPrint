// Phase 3 real-stack journeys. The model is the scripted stand-in (scripts/e2e_app.py), everything
// else is real: backend, gateway, tools, PostgreSQL rows, approvals and the browser UI.
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
  // The live Companion is opt-in; the harness does not set the build flag, so switch it on here.
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
  const box = page.getByRole("textbox", { name: "Điều bạn muốn kể" });
  await box.fill(text);
  await box.press("Enter");
}
async function events(email: string, caseId: string) {
  const token = await tokenFor(email);
  const response = await apiJson(`/v1/cases/${caseId}`, token);
  expect(response.status).toBe(200);
  return ((await response.json()).events ?? []) as {
    provenance: string;
    description: string;
  }[];
}

test("E-AG-01: a cited answer shows only the verified source chip", async ({
  page,
}) => {
  const user = await createUser();
  try {
    await openChat(page, user.email);
    await say(page, "Cho mình nguồn về nhờ người lớn nhé");
    await expect(
      page.getByText(/Bạn có thể nhờ một người lớn đáng tin/),
    ).toBeVisible();
    await expect(page.getByText("Tra cứu nguồn tin cậy")).toBeVisible();
    const chip = page.getByRole("button", {
      name: /Nguồn 1: Tìm người hỗ trợ/,
    });
    await expect(chip).toBeVisible();
    await chip.click();
    await expect(
      page.getByRole("link", { name: "Xem trong Thư viện" }),
    ).toBeVisible();
    await expect(
      page.getByText(/AI · không phải người thật/).first(),
    ).toBeVisible();
  } finally {
    await removeUser(user.email);
  }
});

test("E-AG-02: nothing is written before Save; Save adds one user_confirmed event", async ({
  page,
}) => {
  const user = await createUser();
  try {
    const { id: caseId } = await createCaseViaApi(user.email);
    const writes: string[] = [];
    page.on("request", (request) => {
      if (
        request.method() !== "GET" &&
        /\/v1\/cases\/[^/]+\/events/.test(request.url())
      )
        writes.push(request.url());
    });
    await openChat(page, user.email);
    await say(page, "Giúp mình ghi mốc bạn A chế giễu hôm 3/11");
    await expect(page.getByText(/CHƯA LƯU/)).toBeVisible();
    expect(await events(user.email, caseId)).toEqual([]);
    await say(page, "Ok, lưu mốc đó vào hồ sơ");
    const dialog = page.getByRole("dialog");
    await expect(
      dialog.getByText("Bạn A nhắn tin chế giễu trong nhóm lớp."),
    ).toBeVisible();
    // Open dialog = still nothing written, and closing it does not decide anything.
    expect(await events(user.email, caseId)).toEqual([]);
    await dialog.getByRole("button", { name: "Đóng" }).click();
    await expect(
      page.getByText(/đề xuất đang chờ bạn quyết định/),
    ).toBeVisible();
    expect(await events(user.email, caseId)).toEqual([]);
    await page.getByRole("button", { name: "Xem đề xuất" }).click();
    await page
      .getByRole("dialog")
      .getByRole("button", { name: "Lưu", exact: true })
      .click();
    await expect(page.getByText("Đã lưu mốc vào hồ sơ.")).toBeVisible();
    const saved = await events(user.email, caseId);
    expect(saved).toHaveLength(1);
    expect(saved[0].provenance).toBe("user_confirmed");
    expect(writes).toEqual([]); // the browser never wrote the record itself
  } finally {
    await removeUser(user.email);
  }
});

test("E-AG-03: Don't save writes nothing", async ({ page }) => {
  const user = await createUser();
  try {
    const { id: caseId } = await createCaseViaApi(user.email);
    await openChat(page, user.email);
    await say(page, "Giúp mình ghi mốc bạn A chế giễu hôm 3/11");
    await expect(page.getByText(/CHƯA LƯU/)).toBeVisible();
    await say(page, "Ok, lưu mốc đó vào hồ sơ");
    await page
      .getByRole("dialog")
      .getByRole("button", { name: "Không lưu" })
      .click();
    await expect(page.getByText("Mình chưa lưu mốc này.")).toBeVisible();
    expect(await events(user.email, caseId)).toEqual([]);
  } finally {
    await removeUser(user.email);
  }
});

test("E-AG-04: a pending proposal survives a reload and a plan can be approved", async ({
  page,
}) => {
  const user = await createUser();
  try {
    const { id: caseId } = await createCaseViaApi(user.email);
    await openChat(page, user.email);
    await say(page, "Giúp mình lập kế hoạch nói với cô");
    await expect(page.getByText(/kế hoạch CHƯA LƯU/)).toBeVisible();
    await say(page, "Ok, lưu kế hoạch giúp mình");
    await expect(page.getByRole("dialog")).toBeVisible();
    await page.reload();
    await expect(page.getByRole("dialog")).toBeVisible(); // restored from GET approvals
    await page
      .getByRole("dialog")
      .getByRole("button", { name: "Lưu", exact: true })
      .click();
    await expect(page.getByText("Đã lưu kế hoạch.")).toBeVisible();
    const plan = await apiJson(
      `/v1/cases/${caseId}/plan`,
      await tokenFor(user.email),
    );
    expect(plan.status).toBe(200);
    expect((await plan.json()).items.length).toBe(2);
  } finally {
    await removeUser(user.email);
  }
});

test("E-AG-05: a memory suggestion needs the user's Yes and then exists", async ({
  page,
}) => {
  const user = await createUser();
  try {
    await openChat(page, user.email);
    await say(page, "Hãy ghi nhớ giúp mình nhé");
    await expect(page.getByText("Ghi nhớ điều này?")).toBeVisible();
    const token = await tokenFor(user.email);
    expect((await (await apiJson("/v1/memories", token)).json()).items).toEqual(
      [],
    );
    await page.getByRole("button", { name: "Có", exact: true }).click();
    await expect(page.getByText("Ghi nhớ điều này?")).toHaveCount(0);
    const memories = (await (await apiJson("/v1/memories", token)).json())
      .items;
    expect(memories).toHaveLength(1);
  } finally {
    await removeUser(user.email);
  }
});

test("E-AG-10: another user cannot read the conversation or its run", async ({
  page,
}) => {
  const a = await createUser();
  const b = await createUser("Bạn khác");
  try {
    await openChat(page, a.email);
    await say(page, "Xin chào");
    await expect(page.getByText(/Mình nghe đây/)).toBeVisible();
    const id = page.url().split("/").pop()!;
    const token = await tokenFor(b.email);
    expect((await apiJson(`/v1/conversations/${id}`, token)).status).toBe(404);
    expect(
      (await apiJson(`/v1/conversations/${id}/messages`, token)).status,
    ).toBe(404);
    expect(
      (await apiJson(`/v1/conversations/${id}/attachments`, token)).status,
    ).toBe(404);
  } finally {
    await removeUser(a.email);
    await removeUser(b.email);
  }
});

test("E-AG-11: an urgent message shows the support block with tel:111", async ({
  page,
}) => {
  const user = await createUser();
  try {
    await openChat(page, user.email);
    await say(page, "Mình muốn chết");
    const block = page.getByRole("note", { name: "Hỗ trợ khẩn cấp" });
    await expect(block).toBeVisible();
    await expect(block.locator('a[href="tel:111"]')).toBeVisible();
  } finally {
    await removeUser(user.email);
  }
});

test("E-AG-12: the live chat fits a phone viewport without horizontal scroll", async ({
  page,
}) => {
  const user = await createUser();
  try {
    await page.setViewportSize({ width: 375, height: 700 });
    await openChat(page, user.email);
    await say(page, "Cho mình nguồn về nhờ người lớn nhé");
    await expect(page.getByRole("button", { name: /Nguồn 1/ })).toBeVisible();
    const overflow = await page.evaluate(
      () =>
        document.documentElement.scrollWidth -
        document.documentElement.clientWidth,
    );
    expect(overflow).toBeLessThanOrEqual(0);
  } finally {
    await removeUser(user.email);
  }
});
