import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "./helpers/fixtures";
import { createUser, login, removeUser, signOut } from "./helpers/local";

const widths = [320, 360, 375, 390, 430, 768, 1024, 1440];

test.use({ expectedHttpStatuses: [502] });

test("E-KB-01 real search, citations, diacritics, empty, retry, and layout", async ({
  page,
}) => {
  test.setTimeout(180_000);
  const first = await createUser();
  const second = await createUser();
  try {
    await login(page, first.email);
    await expect(page).toHaveURL(/\/home$/);
    await page.goto("/support/knowledge");
    await expect(page.getByTestId("knowledge-live")).toBeVisible();
    const search = page.getByRole("searchbox", { name: "Tìm trong thư viện" });
    await search.fill("bị nhắn tin dọa trong nhóm lớp");
    const result = page.getByTestId("retrieved-result").first();
    await expect(result).toBeVisible();
    await expect(result.getByTestId("citation-chip")).toBeVisible();
    await result.getByTestId("citation-chip").click();
    await expect(page).toHaveURL(/document=/);
    await expect(page.getByRole("dialog")).toBeVisible();

    await search.fill("bi nhan tin doa trong nhom lop");
    await expect(page.getByTestId("retrieved-result").first()).toBeVisible();

    await search.fill("công thức nấu phở bò");
    await expect(page.getByText("Chưa tìm thấy nguồn phù hợp")).toBeVisible();
    await expect(
      page.getByTestId("knowledge-live").getByTestId("retrieved-result"),
    ).toHaveCount(0);

    // Related school-safety cards cannot establish a missing exact legal fact.
    for (const unsupported of [
      "Mức phạt tiền khi học sinh đánh bạn là bao nhiêu?",
      "Luật chống bắt nạt ở Canada quy định gì?",
    ]) {
      await search.fill(unsupported);
      await expect(page.getByText("Chưa tìm thấy nguồn phù hợp")).toBeVisible();
      await expect(
        page.getByTestId("knowledge-live").getByTestId("retrieved-result"),
      ).toHaveCount(0);
      await expect(
        page.getByText(/Kho tri thức hiện tại chưa có đủ thông tin/),
      ).toBeVisible();
    }

    await page.route("**/v1/knowledge/search**", (route) =>
      route.fulfill({
        status: 502,
        contentType: "application/json",
        body: JSON.stringify({
          error: { code: "upstream_error", message: "Bộ tìm chưa phản hồi." },
        }),
      }),
    );
    await search.fill("bị nhắn tin dọa");
    await expect(page.getByRole("button", { name: "Thử lại" })).toBeVisible();
    await page.unroute("**/v1/knowledge/search**");

    const documentUrl = page.url();
    await signOut(page);
    await login(page, second.email);
    await expect(page).not.toHaveURL(/\/auth$/);
    await page.goto(documentUrl);
    await expect(page.getByTestId("knowledge-live")).toBeVisible();
    await expect(page.getByRole("dialog")).toBeVisible();
    await expect(page.getByText(first.email)).toHaveCount(0);

    for (const width of widths) {
      await page.setViewportSize({ width, height: 900 });
      const overflow = await page.evaluate(
        () =>
          document.documentElement.scrollWidth >
          document.documentElement.clientWidth + 1,
      );
      expect(overflow).toBe(false);
    }
    const accessibility = await new AxeBuilder({ page })
      .include("main")
      .withTags(["wcag2a", "wcag2aa"])
      .analyze();
    expect(accessibility.violations).toEqual([]);
  } finally {
    await removeUser(first.email);
    await removeUser(second.email);
  }
});
