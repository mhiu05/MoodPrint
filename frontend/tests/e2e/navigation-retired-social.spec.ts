import { expect, test } from "@playwright/test";
import { app, baseSession } from "./ux-fixtures";

for (const width of [1440, 390]) {
  test(`three personal destinations and retired route redirects at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    const socialRequests: string[] = [];
    page.on("request", (request) => {
      if (new URL(request.url()).pathname.startsWith("/api/v1/social/")) socialRequests.push(request.url());
    });
    await app(page, baseSession);
    await page.goto("/#/assistants");
    const nav = page.getByRole("navigation", { name: "Điều hướng chính" });
    await expect(nav.getByRole("link")).toHaveText(["Trợ lý", "Nhật ký", "Tài khoản"]);
    for (const route of ["connect", "messages", "chat/x"]) {
      await page.goto(`/#/${route}`);
      await expect(page).toHaveURL(/\/#\/assistants$/);
      await expect(nav.getByRole("link")).toHaveCount(3);
    }
    expect(socialRequests).toEqual([]);
  });
}

test("legacy Cầu Nối history has no invitation to the retired social UI", async ({ page }) => {
  const legacy = {
    botId: "caunoi", name: "Cầu Nối", role: "Trợ lý cũ", description: "Lịch sử trò chuyện",
    starters: [], avatarKey: "caunoi", legacy: true, replacedBy: null,
  };
  await app(page, { ...baseSession, features: { ...baseSession.features, threeAgents: true } }, {
    "/bots/legacy": () => ({ json: [legacy] }),
  });
  await page.goto("/#/assistants/caunoi");
  await expect(page.getByText(/Đây là cuộc trò chuyện cũ với Cầu Nối/)).toBeVisible();
  await expect(page.getByRole("link", { name: "Mở Tìm bạn" })).toHaveCount(0);
});
