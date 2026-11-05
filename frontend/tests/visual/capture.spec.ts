import { artifactPath } from "../artifacts";
import { expect, test, type Page } from "@playwright/test";
import { app, baseSession, room, sessionWith } from "../e2e/ux-fixtures";

// Synthetic data only. Screens are captured after their real data has settled.
const out = artifactPath("visual", process.env.CAPTURE_DIR || "../docs/ux-redesign/evidence/redesign");
const widths = (process.env.CAPTURE_WIDTHS || "320,390,768,1280,1440").split(",").map(Number);
const label = process.env.CAPTURE_LABEL || "after";

const bots = [
  { botId: "may", name: "Mây", role: "Lắng nghe & tâm sự", description: "Một khoảng nhỏ để được lắng nghe, không phán xét.", starters: ["Hôm nay mình hơi mệt", "Mình muốn kể chuyện ở lớp"], avatarKey: "may" },
  { botId: "guong", name: "Gương", role: "Nhìn lại bản thân", description: "Cùng nhìn lại một ngày bằng những câu hỏi nhẹ nhàng.", starters: ["Mình muốn nhìn lại hôm nay"], avatarKey: "guong" },
  { botId: "nhip", name: "Nhịp", role: "Theo dõi cảm xúc", description: "Đọc những ngày bạn chọn chia sẻ để cùng nhìn xu hướng.", starters: ["Tuần này mình thế nào?"], avatarKey: "nhip" },
  { botId: "rure", name: "Rủ Rê", role: "Gợi ý hoạt động", description: "Gợi ý những việc nhỏ để làm cùng người khác.", starters: ["Gợi ý mình một hoạt động"], avatarKey: "rure" },
  { botId: "caunoi", name: "Cầu Nối", role: "Chuẩn bị kết nối", description: "Giúp bạn xem lại hồ sơ tìm bạn trước khi chia sẻ.", starters: ["Mình nên giới thiệu thế nào?"], avatarKey: "caunoi" },
];
const conversation = {
  conversationId: "22222222-2222-4222-8222-222222222222", botId: "may", version: 4, persistent: true, title: "Một ngày dài ở trường",
  expiresAt: "2026-11-22T08:00:00Z", updatedAt: "2026-10-23T08:00:00Z", hasMoreMessages: false, activeRunId: null, activeRunVersion: null,
  messages: [
    { id: "m1", actor: "self", text: "Hôm nay mình hơi mệt, cả ngày học liên tục." },
    { id: "m2", actor: "bot", text: "Nghe như một ngày rất dài. Bạn muốn kể mình nghe phần nào làm bạn mệt nhất không?\n\n- Bài kiểm tra buổi sáng\n- Hay là cảm giác phải cố gắng suốt ngày?", cards: [] },
  ],
};

async function shot(page: Page, name: string, width: number) {
  await page.waitForLoadState("networkidle");
  await page.screenshot({ path: `${out}/${name}-${width}-${label}.png` });
}

for (const width of widths) {
  test(`capture ${width}`, async ({ page }) => {
    await page.setViewportSize({ width, height: width < 768 ? 844 : 900 });
    await app(page, sessionWith({ AI: false }), {
      "/bots": () => ({ json: bots }),
      "/ai/conversations": () => ({ json: [conversation] }),
      [`/ai/conversations/${conversation.conversationId}`]: () => ({ json: conversation }),
      "/ai/preferences": () => ({ json: { historyEnabled: true, semanticMemoryEnabled: false, version: 1, policyVersion: "ai-data-v1", retentionDays: 30, historyAvailable: true, semanticMemoryAvailable: true } }),
      "/moods": () => ({ json: [] }),
      "/moods/summary": () => ({ json: { from: "2026-10-17", to: "2026-10-23", count: 0, mean: null, min: null, max: null, insightAvailable: false, buckets: [] } }),
      "/users/me/identity": () => ({ json: [] }),
      "/connections": () => ({ json: [room] }),
    });
    await page.goto("/#/assistants");
    await expect(page.getByRole("link", { name: /Cầu Nối/ }).first()).toBeVisible();
    await shot(page, "assistants", width);
    await page.goto("/#/assistants/may?new=1");
    await expect(page.getByRole("textbox", { name: "Tin nhắn cho Mây" })).toBeVisible();
    await shot(page, "chat-empty", width);
    await page.goto(`/#/assistants/may?conversation=${conversation.conversationId}`);
    await expect(page.getByText("Nghe như một ngày rất dài.", { exact: false })).toBeVisible();
    await shot(page, "chat-saved", width);
    await page.getByRole("button", { name: "Thông tin cuộc trò chuyện", exact: true }).click();
    await expect(page.getByRole("heading", { name: "Thông tin cuộc trò chuyện" })).toBeFocused();
    await page.waitForTimeout(350);
    await shot(page, "chat-info", width);
    await page.keyboard.press("Escape");
    await page.goto("/#/settings");
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    await shot(page, "settings", width);
    await page.goto("/#/messages");
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    await shot(page, "messages", width);
    await page.goto("/#/self");
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    await shot(page, "mood", width);
    await page.goto("/#/memory");
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    await shot(page, "memory", width);
  });
}
