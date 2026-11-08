// E-AG-07: roleplay through the real stack. Backend, sessions, turn limits, safety exit, persistence and
// the browser UI are real; the partner's lines and the coach's feedback come from the deterministic
// model stand-in (scripted_scenarios.RuleModel + fake_provider). They prove plumbing and behaviour of
// the system around the model, not the quality of any real model's role-play.
import type { Page } from "@playwright/test";
import { test, expect } from "./helpers/fixtures";
import {
  apiJson,
  createUser,
  login,
  removeUser,
  tokenFor,
} from "./helpers/local";
import { modelLog } from "./helpers/phase3";

const coachCalls = () => modelLog().filter((l) => l.startsWith("coach "));

async function openRoleplay(page: Page, email: string) {
  await page.addInitScript(() =>
    localStorage.setItem("moodprint:ai-companion", "live"),
  );
  await login(page, email);
  await expect(page).toHaveURL(/\/home$/);
  await page.goto("/ai/roleplay");
  await expect(page.getByTestId("roleplay-live")).toBeVisible();
}
async function start(
  page: Page,
  role: RegExp | string,
  scenario: RegExp,
  difficulty = "1",
) {
  await page.getByRole("radio", { name: scenario }).first().check();
  await page.getByLabel("Độ khó").selectOption(difficulty);
  await page.getByRole("button", { name: "Bắt đầu diễn tập" }).click();
  await expect(
    page.getByText(/Diễn tập — đây không phải người thật/),
  ).toBeVisible();
  await expect(page.getByText(role).first()).toBeVisible();
  // The thread is loaded once its empty-state hint shows; sending earlier is ignored.
  await expect(page.getByText(/Bạn muốn kể điều gì/)).toBeVisible();
}
async function say(page: Page, text: string) {
  // Typing while the previous run is still finishing is ignored by the UI; wait until it can send.
  await expect(page.getByRole("button", { name: "Gửi" })).toBeVisible();
  const box = page.getByRole("textbox", { name: "Điều bạn muốn kể" });
  await box.fill(text);
  await box.press("Enter");
}
async function sessions(email: string) {
  const response = await apiJson(
    "/v1/roleplay/sessions",
    await tokenFor(email),
  );
  expect(response.status).toBe(200);
  return (await response.json()).items as {
    id: string;
    status: string;
    turnCount: number;
    role: string;
    safetyLocked: boolean;
  }[];
}

test("E-AG-07a: pick a scenario, hold a multi-turn conversation in one persona, finish, get grounded feedback that survives a reload", async ({
  page,
}) => {
  test.setTimeout(120000);
  const user = await createUser();
  try {
    await openRoleplay(page, user.email);
    // The list comes from the backend; pick the first parent scenario.
    await expect(page.getByRole("radio").first()).toBeVisible();
    await start(page, /Phụ huynh|phụ huynh/, /Phụ huynh/);
    await expect(page.getByText(/Lượt 0\//)).toBeVisible();
    await say(page, "Mẹ ơi, con có chuyện muốn kể nhưng con sợ mẹ giận.");
    await expect(page.getByText(/Mẹ nghe con đây \(lượt 1\)/)).toBeVisible();
    await say(page, "Con bị mấy bạn trêu trên mạng mấy tuần nay.");
    await expect(page.getByText(/Mẹ nghe con đây \(lượt 2\)/)).toBeVisible();
    await say(page, "Con muốn mẹ nghe con nói hết trước.");
    await expect(page.getByText(/Mẹ nghe con đây \(lượt 3\)/)).toBeVisible();
    // Persona consistency: every partner line is the same persona, never a tool or another role.
    const partnerLines = await page
      .getByText(/nghe con đây \(lượt \d\)/)
      .allTextContents();
    expect(partnerLines).toHaveLength(3);
    expect(partnerLines.every((line) => line.startsWith("Mẹ nghe con"))).toBe(
      true,
    );
    await expect(page.getByText(/Lượt 3\//)).toBeVisible();

    const before = coachCalls().length;
    await page
      .getByRole("button", { name: /Kết thúc & nhận phản hồi/ })
      .click();
    const feedback = page.getByTestId("roleplay-feedback");
    await expect(feedback).toBeVisible();
    await expect(feedback.getByText("Điều bạn làm tốt")).toBeVisible();
    // The coach quotes only what the student really said.
    await expect(
      feedback.getByText(/Mẹ ơi, con có chuyện muốn kể/),
    ).toBeVisible();
    expect(coachCalls().length - before).toBe(1);
    const stored = (await sessions(user.email))[0];
    expect(stored.status).toBe("completed");
    expect(stored.turnCount).toBe(3);

    // Reload keeps the finished session and its feedback; no second coach call.
    await page.reload();
    await expect(page.getByTestId("roleplay-feedback")).toBeVisible();
    expect(coachCalls().length - before).toBe(1);

    // Start another practice: the page returns to the picker.
    await page
      .getByRole("button", { name: "Luyện một tình huống khác" })
      .click();
    await expect(page.getByText("Chọn tình huống")).toBeVisible();
  } finally {
    await page.close();
    await removeUser(user.email);
  }
});

test("E-AG-07b: an urgent message leaves the role at once, shows the 111 block and locks the session", async ({
  page,
}) => {
  test.setTimeout(120000);
  const user = await createUser();
  try {
    await openRoleplay(page, user.email);
    await start(page, /./, /Giáo viên/);
    await say(page, "Em chào cô, em muốn nhờ cô giúp.");
    await expect(page.getByText(/Cô nghe em đây \(lượt 1\)/)).toBeVisible();
    await say(page, "Em muốn chết, em không chịu nổi nữa.");
    await expect(
      page.getByText(/Tổng đài Quốc gia bảo vệ trẻ em 111/).first(),
    ).toBeVisible();
    await expect(
      page.getByRole("link", { name: /tel:111|111/ }).first(),
    ).toBeVisible();
    // The partner never answered the urgent message in character.
    await expect(page.getByText(/Cô nghe em đây \(lượt 2\)/)).toHaveCount(0);
    await expect
      .poll(async () => (await sessions(user.email))[0]?.safetyLocked)
      .toBe(true);
  } finally {
    await page.close();
    await removeUser(user.email);
  }
});

test.describe("coach failure", () => {
  // The coach request failing is answered with 502 by the API: that status is the expected behaviour here.
  test.use({ expectedHttpStatuses: [502] });

  test("E-AG-07c: a failed turn and a failed feedback request keep the session and tell the student what happened", async ({
    page,
  }) => {
    test.setTimeout(120000);
    const user = await createUser();
    try {
      await openRoleplay(page, user.email);
      await start(page, /./, /Giáo viên/);
      await say(page, "Em muốn hỏi cô một chuyện, lỗi mô hình");
      await expect(page.getByRole("alert").first()).toContainText(
        /Chưa thể hoàn tất|thử lại/i,
      );
      // The session is still active and usable.
      await say(page, "Em xin phép hỏi lại cô ạ.");
      await expect(page.getByText(/Cô nghe em đây/)).toBeVisible();
      await say(page, "Em cần cô giúp, lỗi phản hồi");
      await expect(page.getByText(/Cô nghe em đây \(lượt 2\)/)).toBeVisible();
      await page
        .getByRole("button", { name: /Kết thúc & nhận phản hồi/ })
        .click();
      await expect(
        page.getByRole("alert").filter({ hasText: /./ }).first(),
      ).toBeVisible();
      await expect(page.getByTestId("roleplay-feedback")).toHaveCount(0);
      const [stored] = await sessions(user.email);
      expect(stored.status).toBe("active"); // nothing was lost; the student can try again or leave
      await page
        .getByRole("button", { name: /Thoát, không cần phản hồi/ })
        .click();
      await expect
        .poll(async () => (await sessions(user.email))[0]?.status)
        .toBe("abandoned");
    } finally {
      await page.close();
      await removeUser(user.email);
    }
  });
});

test("E-AG-07d: restart after leaving, and cancel a slow partner turn", async ({
  page,
}) => {
  test.setTimeout(120000);
  const user = await createUser();
  try {
    await openRoleplay(page, user.email);
    await start(page, /./, /Giáo viên/);
    await say(page, "Mình muốn thử nói trả lời chậm một chút");
    await expect(page.getByRole("button", { name: "Dừng" })).toBeVisible();
    await page.getByRole("button", { name: "Dừng" }).click();
    await expect(page.getByRole("button", { name: "Gửi" })).toBeVisible({
      timeout: 15000,
    });
    await expect(page.getByText(/nghe .* đây \(lượt/)).toHaveCount(0); // nothing was added by the partner
    await page
      .getByRole("button", { name: /Thoát, không cần phản hồi/ })
      .click();
    await expect(page.getByText("Buổi luyện đã kết thúc")).toBeVisible();
    // A fresh session can be started afterwards.
    await page.goto("/ai/roleplay");
    await page.getByRole("radio").first().check();
    await page.getByRole("button", { name: "Bắt đầu diễn tập" }).click();
    await expect(
      page.getByText(/Diễn tập — đây không phải người thật/),
    ).toBeVisible();
    const all = await sessions(user.email);
    expect(all.map((s) => s.status).sort()).toEqual(["abandoned", "active"]);
  } finally {
    await page.close();
    await removeUser(user.email);
  }
});
