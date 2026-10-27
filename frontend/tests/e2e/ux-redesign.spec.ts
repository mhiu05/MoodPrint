import { expect, test } from "@playwright/test";
import { app, baseSession, sessionWith } from "./ux-fixtures";

const pendingProposal = {
  id: "p-1",
  botId: "may",
  purpose: "memory",
  text: "Thích đi bộ buổi tối",
  status: "pending",
  version: 1,
  expiresAt: "2099-01-01T00:00:00Z",
};

test.describe("truthful consent recovery (F03)", () => {
  test("with AI processing off a pending proposal points to an explicit Send, not to Settings", async ({ page }) => {
    await app(page, sessionWith({ AI: false, MEM: false }), { "/proposals": () => ({ json: [pendingProposal] }) });
    await page.goto("/#/memory");
    const proposal = page.getByRole("article").filter({ hasText: "Thích đi bộ buổi tối" });
    await expect(proposal).toContainText("Quyền xử lý AI đang tắt nên chưa thể duyệt đề xuất này.");
    await expect(proposal.getByRole("link", { name: "Mở trợ lý" })).toHaveAttribute("href", "#/assistants");
    await expect(proposal.getByRole("link", { name: /quyền riêng tư/i })).toHaveCount(0);
    await expect(proposal.getByRole("button", { name: "Không lưu" })).toBeEnabled();
  });

  test("with approved memory off the page explains that approving a proposal is the way back", async ({ page }) => {
    await app(page, sessionWith({ AI: true, MEM: false }));
    await page.goto("/#/memory");
    await expect(page.getByText("Trợ lý chỉ dùng lại ghi nhớ sau khi bạn duyệt một đề xuất mới.", { exact: false })).toBeVisible();
    await expect(page.getByRole("link", { name: "Xem quyền ghi nhớ" })).toHaveCount(0);
  });

  test("with MATCH withdrawn, messages lead to reviewing and showing the matching profile", async ({ page }) => {
    await app(page, sessionWith({ MATCH: false }));
    await page.goto("/#/messages");
    await expect(page.getByRole("link", { name: "Mở hồ sơ tìm bạn" })).toHaveAttribute("href", "#/connect?tab=profile");
    await expect(page.getByText(/Hiển thị hồ sơ/)).toBeVisible();
    await expect(page.getByRole("link", { name: "Xem quyền tìm bạn" })).toHaveCount(0);
  });
});

test.describe("truthful blocking (F04)", () => {
  test("the chat block dialog states in-app irreversibility, focuses cancel and sends nothing on cancel", async ({ page }) => {
    const writes: string[] = [];
    page.on("request", (request) => {
      if (request.method() === "POST" && request.url().includes("/block")) writes.push(request.url());
    });
    await app(page, sessionWith({ AI: false }));
    await page.goto("/#/chat/room-1");
    await page.getByText("Chia sẻ và an toàn", { exact: true }).click();
    await page.getByRole("button", { name: "Chặn kết nối này", exact: true }).click();
    const dialog = page.getByRole("dialog", { name: "Chặn kết nối này?" });
    await expect(dialog).toContainText("Hai bạn sẽ không thể xem hoặc gửi tiếp tin nhắn trong kết nối này.");
    await expect(dialog).toContainText("Việc chặn không thể hoàn tác trong ứng dụng.");
    await expect(dialog).not.toContainText("Bỏ chặn");
    await expect(dialog.getByRole("button", { name: "Giữ kết nối" })).toBeFocused();
    await dialog.getByRole("button", { name: "Giữ kết nối" }).click();
    await expect(dialog).toHaveCount(0);
    expect(writes).toEqual([]);
  });
});

test.describe("service failures do not blame input (F11)", () => {
  test("a non-JSON 500 asks to retry instead of checking the content", async ({ page }) => {
    await app(page, baseSession, { "/session": () => ({ status: 500, body: "<html>proxy error</html>", contentType: "text/html" }) });
    await page.goto("/#/assistants");
    const alert = page.getByRole("alert");
    await expect(alert).toContainText("Chưa hoàn tất yêu cầu. Bạn hãy thử lại.");
    await expect(alert).not.toContainText("kiểm tra nội dung");
  });
});

test("resolved reports show a Vietnamese outcome instead of the raw enum", async ({ page }) => {
  const resolved = { id: "r1", status: "resolved", version: 3, reason: "Quấy rối", createdAt: "2026-10-23T07:00:00Z", subjectRef: "s-abcdef0123456789", reporterRef: "r-abcdef012345", evidence: [], priorActions: 1, resolution: "warned" };
  await app(page, sessionWith({}, { staff: "moderator", notices: [] }), {
    "/admin/reports": (request) => ({ json: new URL(request.url()).searchParams.get("status") === "resolved" ? [resolved, { ...resolved, id: "r2", resolution: "mystery" }] : [] }),
  });
  await page.goto("/#/admin/reports");
  await page.getByRole("button", { name: "Đã xử lý", exact: true }).click();
  await expect(page.getByText(/Kết quả: Đã cảnh báo/)).toBeVisible();
  await expect(page.getByText(/Kết quả: Đã xử lý/)).toBeVisible();
  await expect(page.getByText(/warned|mystery/)).toHaveCount(0);
});

test("the first AI send explains the consent it records, next to Send", async ({ page }) => {
  await app(page, sessionWith({ AI: false }));
  await page.goto("/#/assistants/may");
  await expect(page.getByText("Khi chọn Gửi, bạn đồng ý để dịch vụ AI xử lý tin nhắn này. Bạn có thể rút quyền trong Quyền riêng tư.", { exact: true })).toBeVisible();
});

test("an unavailable AI service is not sent to Settings for a fix that does not exist there", async ({ page }) => {
  await app(page, sessionWith({}, { features: { ai: false, aiStatus: "configuration_missing", matching: true, voice: false } }));
  await page.goto("/#/assistants/may?new=1");
  const notice = page.locator(".chat-readonly");
  await expect(notice).toContainText("Trợ lý chưa được kết nối với dịch vụ AI.");
  await expect(notice.getByRole("link")).toHaveCount(0);
});

const longBots = [
  { botId: "may", name: "Mây", role: "Lắng nghe & tâm sự", description: "Một khoảng nhỏ để được lắng nghe, không phán xét và không vội vàng.", starters: ["Hôm nay mình hơi mệt"], avatarKey: "may" },
  { botId: "guong", name: "Gương", role: "Nhìn lại bản thân", description: "Cùng nhìn lại một ngày đã qua bằng những câu hỏi nhẹ nhàng.", starters: ["Mình muốn nhìn lại hôm nay"], avatarKey: "guong" },
];
const WIDTHS = [320, 375, 390, 768, 1280, 1440];

test.describe("readable foundations (V-TOKENS / V-REFLOW)", () => {
  test("body text is 16px and persona descriptions are readable without truncation at every width", async ({ page }) => {
    await app(page, baseSession, { "/bots": () => ({ json: longBots }) });
    for (const width of WIDTHS) {
      await page.setViewportSize({ width, height: width < 768 ? 844 : 900 });
      await page.goto("/#/assistants");
      const row = page.getByRole("link", { name: /Gương/ }).first();
      await expect(row).toBeVisible();
      const metrics = await page.evaluate(() => {
        const body = parseFloat(getComputedStyle(document.body).fontSize);
        const description = document.querySelector<HTMLElement>(".bot-row-text p")!;
        const role = document.querySelector<HTMLElement>(".bot-row-text small")!;
        const style = getComputedStyle(description);
        return {
          body,
          description: parseFloat(style.fontSize),
          role: parseFloat(getComputedStyle(role).fontSize),
          ellipsis: style.textOverflow === "ellipsis" && style.whiteSpace === "nowrap",
          overflow: document.documentElement.scrollWidth - innerWidth,
        };
      });
      expect(metrics.body, `body at ${width}`).toBe(16);
      expect(metrics.description, `description at ${width}`).toBeGreaterThanOrEqual(14);
      expect(metrics.role, `role at ${width}`).toBeGreaterThanOrEqual(13);
      expect(metrics.ellipsis, `description truncated at ${width}`).toBe(false);
      expect(metrics.overflow, `horizontal overflow at ${width}`).toBeLessThanOrEqual(1);
    }
  });

  test("navigation labels are readable and ordinary targets are at least 44px", async ({ page }) => {
    await app(page, baseSession, { "/bots": () => ({ json: longBots }) });
    for (const width of [320, 1280]) {
      await page.setViewportSize({ width, height: 844 });
      await page.goto("/#/messages");
      const nav = page.getByRole("navigation", { name: "Điều hướng chính" });
      const sizes = await nav.getByRole("link").evaluateAll((links) =>
        links.map((link) => ({
          font: parseFloat(getComputedStyle(link).fontSize),
          height: link.getBoundingClientRect().height,
          width: link.getBoundingClientRect().width,
        })),
      );
      for (const size of sizes) {
        expect(size.font).toBeGreaterThanOrEqual(width < 768 ? 12 : 13);
        expect(size.height).toBeGreaterThanOrEqual(44);
        expect(size.width).toBeGreaterThanOrEqual(44);
      }
    }
  });

  test("chat text, starters and composer controls are readable and touch-sized on a phone", async ({ page }) => {
    await app(page, baseSession, { "/bots": () => ({ json: longBots }) });
    await page.setViewportSize({ width: 320, height: 700 });
    await page.goto("/#/assistants/may");
    await expect(page.getByRole("textbox", { name: "Tin nhắn cho Mây" })).toBeVisible();
    const metrics = await page.evaluate(() => {
      const box = (selector: string) => document.querySelector<HTMLElement>(selector)!.getBoundingClientRect();
      const font = (selector: string) => parseFloat(getComputedStyle(document.querySelector<HTMLElement>(selector)!).fontSize);
      return {
        starterFont: font(".quick-replies button"),
        starterHeight: box(".quick-replies button").height,
        composerFont: font(".bot-composer textarea"),
        sendHeight: box(".send-button").height,
        headerRole: font(".conversation-header p"),
        overflow: document.documentElement.scrollWidth - innerWidth,
      };
    });
    expect(metrics.starterFont).toBeGreaterThanOrEqual(14);
    expect(metrics.starterHeight).toBeGreaterThanOrEqual(44);
    expect(metrics.composerFont).toBe(16);
    expect(metrics.sendHeight).toBeGreaterThanOrEqual(44);
    expect(metrics.headerRole).toBeGreaterThanOrEqual(13);
    expect(metrics.overflow).toBeLessThanOrEqual(1);
  });
});
