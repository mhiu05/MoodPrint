// Phase 3 real-stack journeys. The model is the scripted stand-in (scripts/e2e_app.py), everything
// else is real: backend, gateway, tools, PostgreSQL rows, approvals and the browser UI.
import { randomUUID } from "node:crypto";
import AxeBuilder from "@axe-core/playwright";
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
import {
  COLORS,
  modelLog,
  sha256,
  solidPng,
  uploadImageEvidence,
} from "./helpers/phase3";

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

// E-AG-06: evidence analysis through the real stack. Backend, consent gate, Storage, derivatives,
// idempotency and the browser UI are real; only the model's answer comes from the deterministic
// HTTP-boundary fake (agent/src/moodprint_agent/testing/fake_provider.py). Nothing here says anything
// about how a real model reads a real screenshot.
test.describe("evidence analysis through the real stack (E-AG-06)", () => {
  const CONSENT_VERSION = "evidence-analysis-2026-11-08";
  const analysisCalls = () =>
    modelLog().filter((l) => l.startsWith("analysis "));

  async function openAnalysis(page: Page, email: string, png: Buffer) {
    await page.addInitScript(() =>
      localStorage.setItem("moodprint:ai-companion", "live"),
    );
    await login(page, email);
    await expect(page).toHaveURL(/\/home$/);
    await uploadImageEvidence(page, png);
    await page.goto("/ai/analysis/new");
    await expect(page.getByTestId("analysis-live")).toBeVisible();
  }
  async function pickAndConsent(page: Page) {
    await page.getByRole("radio", { name: /anh-tong-hop\.png/ }).check();
    await page.getByRole("checkbox", { name: /Tôi đồng ý gửi ảnh/ }).check();
  }
  async function evidenceFor(email: string) {
    const response = await apiJson("/v1/evidence", await tokenFor(email));
    expect(response.status).toBe(200);
    return (await response.json()).items[0] as {
      id: string;
      userEditedText: string | null;
      reviewStatus: string;
    };
  }
  async function originalBytes(email: string, evidenceId: string) {
    const signed = await (
      await apiJson(
        `/v1/evidence/${evidenceId}/download-url`,
        await tokenFor(email),
      )
    ).json();
    return Buffer.from(await (await fetch(signed.url)).arrayBuffer());
  }

  test("E-AG-06a: consent gates the request; result keeps four layers; the user's correction is stored apart and the original is untouched", async ({
    page,
  }) => {
    test.setTimeout(120000);
    const user = await createUser();
    try {
      const png = solidPng(COLORS.ok, 11);
      await openAnalysis(page, user.email, png);
      const before = analysisCalls().length;
      await page.getByRole("radio", { name: /anh-tong-hop\.png/ }).check();
      const start = page.getByRole("button", { name: "Phân tích ảnh" });
      await expect(start).toBeDisabled(); // no consent, no request
      await page.getByRole("checkbox", { name: /Tôi đồng ý gửi ảnh/ }).check();
      await expect(
        page.getByText(/không có nghĩa là dữ liệu bị xóa hoàn toàn/),
      ).toBeVisible();
      const created = page.waitForResponse(
        (r) =>
          r.url().endsWith("/v1/analyses") && r.request().method() === "POST",
      );
      await start.click();
      const analysisId = (await (await created).json()).id as string;
      const result = page.getByTestId("analysis-result");
      await expect(result).toBeVisible();
      await expect(
        result.getByText(/Mình sẽ không quên chuyện này đâu/),
      ).toBeVisible();
      await expect(
        result.getByRole("heading", { name: "Quan sát" }),
      ).toBeVisible();
      await expect(
        result.getByRole("heading", { name: "AI suy đoán (chưa xác minh)" }),
      ).toBeVisible();
      await expect(
        result.getByRole("heading", { name: "Điều chưa chắc và hạn chế" }),
      ).toBeVisible();
      expect(analysisCalls().length - before).toBe(1);

      // The user's own correction is saved separately; the AI reading is not edited.
      const evidence = await evidenceFor(user.email);
      const originalBefore = sha256(
        await originalBytes(user.email, evidence.id),
      );
      await page
        .getByRole("textbox", { name: "Nội dung bạn sửa" })
        .fill("Thật ra bạn ấy viết: mình sẽ nói với cô.");
      await page.getByRole("button", { name: "Lưu bản chỉnh" }).click();
      await expect(page.getByText("Đã lưu bản bạn chỉnh.")).toBeVisible();
      const after = await evidenceFor(user.email);
      expect(after.userEditedText).toBe(
        "Thật ra bạn ấy viết: mình sẽ nói với cô.",
      );
      expect(after.reviewStatus).toBe("corrected");
      expect(sha256(await originalBytes(user.email, evidence.id))).toBe(
        originalBefore,
      );
      const stored = await (
        await apiJson(`/v1/analyses/${analysisId}`, await tokenFor(user.email))
      ).json();
      expect(stored.status).toBe("succeeded");
      expect(JSON.stringify(stored.reading)).not.toContain(
        "Thật ra bạn ấy viết",
      );

      // Reload: the server still has the result; asking again with the same id is not a second model call.
      await page.reload();
      const again = await apiJson("/v1/analyses", await tokenFor(user.email), {
        method: "POST",
        body: JSON.stringify({
          id: analysisId,
          evidence_id: evidence.id,
          consent: { version: stored.consentVersion, accepted: true },
        }),
      });
      expect(again.status).toBe(200);
      expect((await again.json()).id).toBe(analysisId);
      expect(analysisCalls().length - before).toBe(1); // no duplicate analysis
    } finally {
      await page.close();
      await removeUser(user.email);
    }
  });

  test("E-AG-06b: no consent, someone else's evidence and an unreadable file never reach the model", async ({
    page,
  }) => {
    test.setTimeout(120000);
    const owner = await createUser();
    const other = await createUser("Gió tổng hợp");
    try {
      await openAnalysis(page, owner.email, solidPng(COLORS.ok, 21));
      const evidence = await evidenceFor(owner.email);
      const before = analysisCalls().length;

      // 1) A forged request without consent is refused by the server, not only by the button.
      const ownerToken = await tokenFor(owner.email);
      const noConsent = await apiJson("/v1/analyses", ownerToken, {
        method: "POST",
        body: JSON.stringify({
          id: randomUUID(),
          evidence_id: evidence.id,
          consent: { version: CONSENT_VERSION, accepted: false },
        }),
      });
      expect(noConsent.status).toBeGreaterThanOrEqual(400);
      expect(noConsent.status).toBeLessThan(500);

      // 2) Another user cannot analyse (or learn about) this evidence.
      const otherToken = await tokenFor(other.email);
      const foreign = await apiJson("/v1/analyses", otherToken, {
        method: "POST",
        body: JSON.stringify({
          id: randomUUID(),
          evidence_id: evidence.id,
          consent: { version: CONSENT_VERSION, accepted: true },
        }),
      });
      expect(foreign.status).toBe(404);

      // 3) A file that only claims to be an image is not offered and not analysable.
      await uploadImageEvidence(
        page,
        Buffer.from("this is not an image"),
        "kho-ng-phai-anh.png",
      );
      const items = (await (await apiJson("/v1/evidence", ownerToken)).json())
        .items as {
        id: string;
        originalFilename: string;
      }[];
      const bad = items.find(
        (i) => i.originalFilename === "kho-ng-phai-anh.png",
      );
      expect(bad).toBeTruthy();
      const corrupt = await apiJson("/v1/analyses", ownerToken, {
        method: "POST",
        body: JSON.stringify({
          id: randomUUID(),
          evidence_id: bad!.id,
          consent: { version: CONSENT_VERSION, accepted: true },
        }),
      });
      // Rejected outright, or accepted as a request that ends "failed"; never a reading, never a model call.
      if (corrupt.status < 400) {
        const failed = await corrupt.json();
        expect(failed.status).not.toBe("succeeded");
        expect(failed.reading ?? null).toBeNull();
      }
      expect(analysisCalls().length - before).toBe(0);
      await page.goto("/ai/analysis/new");
      await expect(
        page.getByRole("radio", { name: /kho-ng-phai-anh/ }),
      ).toHaveCount(0);
    } finally {
      await page.close();
      await removeUser(owner.email);
      await removeUser(other.email);
    }
  });

  test("E-AG-06c: a failing model shows a safe message, can be retried, and never produces a result", async ({
    page,
  }) => {
    test.setTimeout(120000);
    const user = await createUser();
    try {
      await openAnalysis(page, user.email, solidPng(COLORS.alwaysError, 31));
      const before = analysisCalls().length;
      await pickAndConsent(page);
      await page.getByRole("button", { name: "Phân tích ảnh" }).click();
      const alert = page.getByRole("alert");
      await expect(alert).toContainText("Dịch vụ AI tạm thời chưa phản hồi");
      await expect(page.getByTestId("analysis-result")).toHaveCount(0);
      await alert.getByRole("button", { name: "Thử lại" }).click();
      await pickAndConsent(page);
      await page.getByRole("button", { name: "Phân tích ảnh" }).click();
      await expect(page.getByRole("alert")).toContainText(
        "Dịch vụ AI tạm thời chưa phản hồi",
      );
      expect(analysisCalls().length - before).toBe(2);
      expect(await page.content()).not.toContain("e2e upstream failure");
    } finally {
      await removeUser(user.email);
    }
  });

  test("E-AG-06e: a one-time model failure recovers on retry with a new request", async ({
    page,
  }) => {
    test.setTimeout(120000);
    const user = await createUser();
    try {
      await openAnalysis(page, user.email, solidPng(COLORS.errorOnce, 41));
      const before = analysisCalls().length;
      await pickAndConsent(page);
      await page.getByRole("button", { name: "Phân tích ảnh" }).click();
      const alert = page.getByRole("alert");
      await expect(alert).toBeVisible();
      await alert.getByRole("button", { name: "Thử lại" }).click();
      await pickAndConsent(page);
      await page.getByRole("button", { name: "Phân tích ảnh" }).click();
      await expect(page.getByTestId("analysis-result")).toBeVisible();
      expect(analysisCalls().length - before).toBe(2);
    } finally {
      await removeUser(user.email);
    }
  });

  test("E-AG-06f: a transport timeout is reported as a service problem, not as a result", async ({
    page,
  }) => {
    test.setTimeout(120000);
    const user = await createUser();
    try {
      await openAnalysis(page, user.email, solidPng(COLORS.timeout, 51));
      await pickAndConsent(page);
      await page.getByRole("button", { name: "Phân tích ảnh" }).click();
      await expect(page.getByRole("alert")).toContainText(
        /chưa phản hồi|quá lâu/,
      );
      await expect(page.getByTestId("analysis-result")).toHaveCount(0);
    } finally {
      await removeUser(user.email);
    }
  });

  test.describe("lost answer", () => {
    test.use({ expectedHttpStatuses: [502] });

    test("E-AG-06d: if the answer is lost on the way back, the page recovers the stored result instead of asking again", async ({
      page,
    }) => {
      test.setTimeout(120000);
      const user = await createUser();
      try {
        await openAnalysis(page, user.email, solidPng(COLORS.ok, 61));
        const before = analysisCalls().length;
        // The server processes the request, the browser never sees the response (network drop).
        let dropped = 0;
        await page.route("**/v1/analyses", async (route) => {
          if (route.request().method() !== "POST" || dropped++ > 0)
            return route.fallback();
          await route.fetch(); // the server really processes it...
          await route.fulfill({ status: 502, body: "bad gateway" }); // ...but the answer is lost
        });
        await pickAndConsent(page);
        await page.getByRole("button", { name: "Phân tích ảnh" }).click();
        await expect(page.getByTestId("analysis-result")).toBeVisible({
          timeout: 20000,
        });
        expect(analysisCalls().length - before).toBe(1);
      } finally {
        await page.close();
        await removeUser(user.email);
      }
    });
  });
});

// E-AG-07: roleplay through the real stack. Backend, sessions, turn limits, safety exit, persistence and
// the browser UI are real; the partner's lines and the coach's feedback come from the deterministic
// model stand-in (scripted_scenarios.RuleModel + fake_provider). They prove plumbing and behaviour of
// the system around the model, not the quality of any real model's role-play.
test.describe("roleplay through the real stack (E-AG-07)", () => {
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
});

// E-AG-08 / E-AG-09: cancellation and network recovery in the real browser against the real stack.
// The model stand-in is slow on demand ("trả lời chậm") or fails once ("lỗi một lần"); everything
// else (run lifecycle, SSE, cancel grace, approvals, recovery, idempotent retry) is real.
test.describe("cancellation and network recovery (E-AG-08, E-AG-09)", () => {
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
        (await (await apiJson(`/v1/cases/${caseId}`, token)).json()).events ??
        [];
      expect(events).toEqual([]); // nothing was written
      // A second cancel is harmless, and after a reload the dialog is gone.
      expect(
        (await apiJson(`/v1/runs/${runId}/cancel`, token, { method: "POST" }))
          .status,
      ).toBe(200);
      await page.reload();
      await expect(page.getByRole("dialog")).toHaveCount(0);
      await expect(
        page.getByText(/đề xuất đang chờ bạn quyết định/),
      ).toHaveCount(0);
      expect(
        (await (await apiJson(`/v1/cases/${caseId}`, token)).json()).events ??
          [],
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
});

// E-AG-13: the live Companion screens at the eight project widths, with axe, the keyboard and reduced
// motion. Real stack, deterministic model stand-in. Reports only what was exercised here.
test.describe("accessibility, viewports and keyboard (E-AG-13)", () => {
  const WIDTHS = [320, 360, 375, 390, 430, 768, 1024, 1440];

  async function serious(page: Page, label: string) {
    const result = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa"])
      .analyze();
    const bad = result.violations.filter((v) =>
      ["serious", "critical"].includes(v.impact ?? ""),
    );
    if (bad.length)
      console.log(
        `AXE ${label}:`,
        JSON.stringify(
          bad.map((v) => ({
            id: v.id,
            impact: v.impact,
            nodes: v.nodes.slice(0, 3).map((n) => ({
              target: n.target,
              summary: n.failureSummary?.slice(0, 220),
            })),
          })),
        ),
      );
    expect(bad, `axe serious/critical on ${label}`).toEqual([]);
  }
  async function say(page: Page, text: string) {
    // Typing while the previous run is still finishing is ignored by the UI; wait until it can send.
    await expect(page.getByRole("button", { name: "Gửi" })).toBeVisible();
    const box = page.getByRole("textbox", { name: "Điều bạn muốn kể" });
    await box.fill(text);
    await box.press("Enter");
  }
  async function noOverflow(page: Page, width: number, label: string) {
    expect(
      await page.evaluate(() => document.documentElement.scrollWidth),
      `${label} at ${width}px`,
    ).toBeLessThanOrEqual(width);
  }

  test("E-AG-13a: chat, approval dialog, analysis and roleplay fit every width and pass axe; the dialog is keyboard-safe", async ({
    page,
  }) => {
    test.setTimeout(420000);
    const user = await createUser();
    try {
      await createCaseViaApi(user.email);
      await page.addInitScript(() =>
        localStorage.setItem("moodprint:ai-companion", "live"),
      );
      await page.emulateMedia({ reducedMotion: "reduce" });
      await login(page, user.email);
      await expect(page).toHaveURL(/\/home$/);
      await uploadImageEvidence(page, solidPng(COLORS.ok, 71));

      // -- chat with a pending approval --
      await page.goto("/ai/chat");
      await page.getByRole("button", { name: /Cuộc trò chuyện mới/ }).click();
      await expect(page.getByTestId("chat-live")).toBeVisible();
      await expect(page.getByText(/Bạn muốn kể điều gì/)).toBeVisible();
      await say(page, "Giúp mình ghi mốc bạn A chế giễu hôm 3/11");
      await expect(page.getByText(/CHƯA LƯU/)).toBeVisible();
      await say(page, "Ok, lưu mốc đó vào hồ sơ");
      const dialog = page.getByRole("dialog");
      await expect(dialog).toBeVisible();
      await serious(page, "approval dialog");

      // Keyboard: focus is inside the dialog, Tab cannot leave it, Esc defers without deciding.
      // A native modal dialog makes everything behind it inert: Tab cycles inside it (or leaves to the
      // browser chrome, where the active element is the body) and never reaches the page behind.
      const focusContained = () =>
        page.evaluate(
          () =>
            !!document.activeElement?.closest("dialog") ||
            document.activeElement === document.body,
        );
      expect(
        await page.evaluate(() => !!document.activeElement?.closest("dialog")),
      ).toBe(true); // initial focus is inside the dialog
      for (let i = 0; i < 8; i++) {
        await page.keyboard.press("Tab");
        expect(await focusContained(), `Tab ${i + 1} stays contained`).toBe(
          true,
        );
      }
      await page.keyboard.press("Escape");
      await expect(dialog).toHaveCount(0);
      await expect(
        page.getByText(/đề xuất đang chờ bạn quyết định/),
      ).toBeVisible(); // deferred, not decided
      await serious(page, "chat with a deferred proposal");

      // -- every width: chat (with the notice and the dialog trigger), analysis, roleplay --
      const chatUrl = page.url();
      for (const width of WIDTHS) {
        await page.setViewportSize({ width, height: 900 });
        await page.goto(chatUrl);
        await expect(page.getByTestId("chat-live")).toBeVisible();
        // A reload restores the pending proposal and opens it again.
        await expect(page.getByRole("dialog")).toBeVisible();
        await noOverflow(page, width, "approval dialog");
        await page.keyboard.press("Escape");
        await noOverflow(page, width, "chat");
        await page.goto("/ai/analysis/new");
        await expect(page.getByTestId("analysis-live")).toBeVisible();
        await page.getByRole("radio", { name: /anh-tong-hop\.png/ }).check();
        await noOverflow(page, width, "analysis");
        await page.goto("/ai/roleplay");
        await expect(page.getByTestId("roleplay-live")).toBeVisible();
        await noOverflow(page, width, "roleplay picker");
      }
      await page.setViewportSize({ width: 1280, height: 900 });

      // -- analysis result and roleplay session --
      await page.goto("/ai/analysis/new");
      await page.getByRole("radio", { name: /anh-tong-hop\.png/ }).check();
      await serious(page, "analysis consent step");
      await page.getByRole("checkbox", { name: /Tôi đồng ý gửi ảnh/ }).check();
      await page.getByRole("button", { name: "Phân tích ảnh" }).click();
      await expect(page.getByTestId("analysis-result")).toBeVisible();
      await serious(page, "analysis result");

      await page.goto("/ai/roleplay");
      await page.getByRole("radio").first().check();
      await page.getByRole("button", { name: "Bắt đầu diễn tập" }).click();
      await expect(page.getByText(/Bạn muốn kể điều gì/)).toBeVisible();
      await say(page, "Em chào cô ạ.");
      await expect(page.getByText(/nghe .* đây \(lượt 1\)/)).toBeVisible();
      await serious(page, "roleplay session");
      await page
        .getByRole("button", { name: /Kết thúc & nhận phản hồi/ })
        .click();
      await expect(page.getByTestId("roleplay-feedback")).toBeVisible();
      await serious(page, "roleplay feedback");

      // Leave nothing pending (an account with a waiting approval cannot be deleted): decline it.
      await page.goto(chatUrl);
      await page
        .getByRole("dialog")
        .getByRole("button", { name: "Không lưu" })
        .click();
      await expect(page.getByRole("dialog")).toHaveCount(0);
      // The run finishes after the decision; only then can the account be removed.
      await expect(page.getByRole("button", { name: "Gửi" })).toBeVisible();
    } finally {
      await page.close();
      await removeUser(user.email);
    }
  });

  test("E-AG-13b: new messages are announced politely and reduced motion removes the working animation", async ({
    page,
  }) => {
    test.setTimeout(120000);
    const user = await createUser();
    try {
      await page.addInitScript(() =>
        localStorage.setItem("moodprint:ai-companion", "live"),
      );
      await page.emulateMedia({ reducedMotion: "reduce" });
      await login(page, user.email);
      await expect(page).toHaveURL(/\/home$/);
      await page.goto("/ai/chat");
      await page.getByRole("button", { name: /Cuộc trò chuyện mới/ }).click();
      await expect(page.getByText(/Bạn muốn kể điều gì/)).toBeVisible();
      // The transcript is a polite live region; urgent content is not hidden inside an assertive loop.
      const log = page.getByRole("log", { name: "Tin nhắn" });
      await expect(log).toHaveAttribute("aria-live", "polite");
      await say(page, "Hãy trả lời chậm giúp mình nhé");
      await expect(page.getByRole("button", { name: "Dừng" })).toBeVisible();
      // With reduced motion nothing inside the chat keeps an infinite animation running.
      const animated = await page.evaluate(() =>
        [...document.querySelectorAll("[data-testid=chat-live] *")]
          .filter((el) => {
            const s = getComputedStyle(el);
            return (
              s.animationName !== "none" &&
              s.animationIterationCount === "infinite" &&
              parseFloat(s.animationDuration) > 0
            );
          })
          .map((el) => el.className),
      );
      expect(animated).toEqual([]);
      await page.getByRole("button", { name: "Dừng" }).click();
      await expect(page.getByRole("button", { name: "Gửi" })).toBeVisible({
        timeout: 20000,
      });
    } finally {
      await page.close();
      await removeUser(user.email);
    }
  });
});
