// E-AG-06: evidence analysis through the real stack. Backend, consent gate, Storage, derivatives,
// idempotency and the browser UI are real; only the model's answer comes from the deterministic
// HTTP-boundary fake (agent/src/moodprint_agent/testing/fake_provider.py). Nothing here says anything
// about how a real model reads a real screenshot.
import { randomUUID } from "node:crypto";
import type { Page } from "@playwright/test";
import { test, expect } from "./helpers/fixtures";
import {
  apiJson,
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

const CONSENT_VERSION = "evidence-analysis-2026-11-08";
const analysisCalls = () => modelLog().filter((l) => l.startsWith("analysis "));

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
    const originalBefore = sha256(await originalBytes(user.email, evidence.id));
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
    expect(JSON.stringify(stored.reading)).not.toContain("Thật ra bạn ấy viết");

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
    const bad = items.find((i) => i.originalFilename === "kho-ng-phai-anh.png");
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
