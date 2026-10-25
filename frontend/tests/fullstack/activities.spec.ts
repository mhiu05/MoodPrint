import { expect, test, type Locator, type Page } from "@playwright/test";
import { call, openRoom } from "./helpers";

// Real FastAPI + PostgreSQL shared activities between two browsers (users 21-28).

const dock = (page: Page, title: string) =>
  page.getByRole("region", { name: `Hoạt động chung: ${title}` });

async function invite(page: Page, title: string, setup?: (dialog: Locator) => Promise<void>) {
  await page.getByRole("button", { name: "Cùng làm gì đó?" }).click();
  const dialog = page.getByRole("dialog", { name: "Cùng làm gì đó?" });
  if (setup) await setup(dialog);
  await dialog.getByRole("button", { name: `Mời cùng chơi ${title}` }).click();
}

async function accept(page: Page, title: string) {
  await page
    .getByRole("group", { name: `Lời mời ${title}` })
    .getByRole("button", { name: "Đồng ý" })
    .click();
}

test("an icebreaker keeps answers private until both answer and resumes after a reload", async ({
  browser,
}) => {
  test.setTimeout(150_000);
  const { one, pageA, pageB, room, close } = await openRoom(browser, 21, 22);
  try {
    const title = "Câu hỏi làm quen";
    await invite(pageA, title);
    await accept(pageB, title);
    const [a, b] = [dock(pageA, title), dock(pageB, title)];
    const current = await call(one, 21, "GET", `/connections/${room}/activities/current`);
    const sessionId = current.body.id as string;
    for (let round = 1; round <= 3; round++) {
      await expect(a).toContainText(`Câu ${round}/3`);
      await expect(b).toContainText(`Câu ${round}/3`);
      if (round === 2) {
        // Stream drop, then a reload: the tab resumes the same round from the server.
        await pageB.context().setOffline(true);
        await pageB.context().setOffline(false);
        await pageB.reload();
        await expect(b).toContainText("Câu 2/3");
      }
      const secret = `TRA-LOI-B-${round}`;
      await b.getByRole("textbox", { name: /Hoặc viết vài chữ/ }).fill(secret);
      await b.getByRole("button", { name: "Gửi câu trả lời" }).click();
      await expect(b.getByRole("status")).toContainText("Đang chờ");
      // Reciprocal reveal: the answer has not reached A's screen or A's API view.
      await expect(a).toContainText("đã trả lời");
      await expect(a).not.toContainText(secret);
      const before = await call(one, 21, "GET", `/activities/${sessionId}`);
      expect(before.text).not.toContain(secret);
      await a.getByRole("radio").first().check();
      await a.getByRole("button", { name: "Gửi câu trả lời" }).click();
      await expect(a).toContainText(secret);
      const next = round === 3 ? "Xem tổng kết" : "Câu tiếp theo";
      await a.getByRole("button", { name: next }).click();
      await b.getByRole("button", { name: next }).click();
    }
    await expect(a.getByRole("heading", { name: "Hoàn thành!" })).toBeVisible();
    await expect(b.getByRole("heading", { name: "Hoàn thành!" })).toBeVisible();
    await a.getByRole("button", { name: "Thích" }).click();
    await expect(a.getByText("Cảm ơn bạn. Đánh giá này chỉ mình bạn biết.")).toBeVisible();
    // Feedback is private: the peer's view never carries it.
    const peerView = await call(pageB.context(), 22, "GET", `/activities/${sessionId}`);
    expect(peerView.text).not.toContain("liked");
    await a.getByRole("button", { name: "Tiếp tục trò chuyện" }).click();
    await expect(pageA.getByRole("textbox", { name: "Tin nhắn cho bạn kết nối" })).toBeFocused();
    await expect(
      pageA.getByRole("log").getByRole("group", { name: `Hoạt động đã qua: ${title}` }),
    ).toBeVisible();
  } finally {
    await close();
  }
});

test("a cooperative quiz hides the answer until both choose and scores as a team", async ({
  browser,
}) => {
  test.setTimeout(150_000);
  const { one, pageA, pageB, room, close } = await openRoom(browser, 23, 24);
  try {
    const title = "Đố vui đồng đội";
    await invite(pageA, title);
    await accept(pageB, title);
    const [a, b] = [dock(pageA, title), dock(pageB, title)];
    for (let round = 1; round <= 5; round++) {
      await expect(a).toContainText(`Vòng ${round}/5`);
      await expect(b).toContainText(`Vòng ${round}/5`);
      // Earlier rounds are revealed in history; only the open round must hide the answer.
      const live = await call(one, 23, "GET", `/connections/${room}/activities/current`);
      expect(JSON.stringify(live.body.current)).not.toContain("correctIndex");
      await a.getByRole("group", { name: "Các lựa chọn" }).getByRole("button").first().click();
      await b.getByRole("group", { name: "Các lựa chọn" }).getByRole("button").first().click();
      await expect(a.getByText("Đáp án đúng").first()).toBeVisible();
      await expect(b.getByText("Đáp án đúng").first()).toBeVisible();
      const next = round === 5 ? "Xem tổng kết" : "Vòng tiếp theo";
      await a.getByRole("button", { name: next }).click();
      await b.getByRole("button", { name: next }).click();
    }
    await expect(a.getByRole("heading", { name: "Hoàn thành!" })).toBeVisible();
    await expect(b.getByRole("heading", { name: "Hoàn thành!" })).toBeVisible();
    const [scoreA, scoreB] = await Promise.all(
      [a, b].map(async (panel) => (await panel.innerText()).match(/Đội của hai bạn: (\d+)\/15/)?.[1]),
    );
    expect(scoreA).toBeDefined();
    expect(scoreA).toBe(scoreB);
  } finally {
    await close();
  }
});

test("a one-cycle shared focus session runs on server time to completion", async ({ browser }) => {
  test.setTimeout(150_000);
  const { pageA, pageB, close } = await openRoom(browser, 25, 26);
  try {
    const title = "Cùng tập trung";
    await invite(pageA, title, async (dialog) => {
      await dialog.getByRole("combobox", { name: "Số lượt" }).selectOption("1");
    });
    await accept(pageB, title);
    const [a, b] = [dock(pageA, title), dock(pageB, title)];
    // E2E_FOCUS_SECONDS (20 s) replaces the plan in the test env: 5 s start + 20 s focus.
    await expect(a).toContainText("Tập trung", { timeout: 20_000 });
    await expect(b).toContainText("Tập trung");
    await expect(a.getByRole("heading", { name: "Hoàn thành!" })).toBeVisible({ timeout: 60_000 });
    await expect(b.getByRole("heading", { name: "Hoàn thành!" })).toBeVisible({ timeout: 10_000 });
  } finally {
    await close();
  }
});

test("blocking mid-activity closes the peer's dock and the room", async ({ browser }) => {
  test.setTimeout(120_000);
  const { pageA, pageB, room, two, close } = await openRoom(browser, 27, 28);
  try {
    const title = "Câu hỏi làm quen";
    await invite(pageA, title);
    await accept(pageB, title);
    await expect(dock(pageB, title)).toContainText("Câu 1/3");
    await pageA.getByText("Chia sẻ và an toàn").click();
    await pageA.getByRole("button", { name: "Chặn kết nối này" }).click();
    await pageA
      .getByRole("dialog", { name: "Chặn kết nối này?" })
      .getByRole("button", { name: "Xác nhận chặn" })
      .click();
    await expect(pageA.getByText("Bạn đã chặn kết nối này.")).toBeVisible();
    await expect(dock(pageB, title)).toHaveCount(0, { timeout: 15_000 });
    await expect(pageB.getByText(/Cuộc trò chuyện này không còn khả dụng/)).toBeVisible();
    const after = await call(two, 28, "GET", `/connections/${room}/activities/current`);
    expect([403, 404, 410]).toContain(after.status);
  } finally {
    await close();
  }
});
