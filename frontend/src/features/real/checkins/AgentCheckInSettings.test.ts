import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { ApiClient } from "../../../api/client";
import type { SessionView } from "../../../api/contracts";
import type { BotId } from "../../../companions/registry";
import { AgentCheckInSettings } from "./AgentCheckInSettings";
import { getProactiveStore, type ProactiveView } from "./useProactiveSettings";

async function render(botId: BotId, options: { legacy?: boolean; unavailable?: boolean } = {}) {
  const api = new ApiClient();
  const session = { userId: "component-fixture", features: { threeAgents: true } } as SessionView;
  const view: ProactiveView = {
    available: !options.unavailable,
    settings: { timezone: "Asia/Bangkok", quietStart: "22:00", quietEnd: "07:00", badgesEnabled: true, journalContextEnabled: false, version: 1, policyVersion: "proactive-v1" },
    limits: { dailyCap: 4, enabledSlots: 4, stepMinutes: 15, windows: { morning: ["05:00", "11:30"], evening: ["17:00", "22:30"] } },
    schedules: (["dieuphoi", "nhatky", "hoatdong", "nhip", "caunoi"] as BotId[]).flatMap((owner) => (["morning", "evening"] as const).map((slot) => ({
      botId: owner, slot, localTime: "07:30", weekdays: [1,2,3,4,5], enabled: owner === "nhatky", version: 1,
      autoPaused: owner === "nhatky", legacy: options.legacy && ["nhip", "caunoi"].includes(owner) || false,
      migrateTo: owner === "nhip" ? "nhatky" as const : null,
      eligibility: { allowed: true, reason: null },
    }))),
  };
  const request = vi.spyOn(api, "request").mockResolvedValue(view);
  await getProactiveStore(api, session.userId).load();
  return { html: renderToStaticMarkup(createElement(MemoryRouter, null, createElement(AgentCheckInSettings, { api, session, botId }))), request };
}

describe("per-agent schedule controls", () => {
  it("renders only owner slots with account-wide cap and shared timezone before the first chat", async () => {
    const { html, request } = await render("dieuphoi");
    expect(html).toContain("Lời hỏi thăm của Điều phối");
    expect(html.match(/role="switch"/g)).toHaveLength(2);
    expect(html).toContain("Đang dùng 4/4");
    expect(html).toContain("Asia/Bangkok");
    expect(html).toContain("aria-disabled=" );
    expect(html).toContain("mọi cuộc trò chuyện");
    expect(html).not.toContain("Dùng khoảnh khắc đã lưu hôm qua</span>");
    expect(html).toContain("/assistants/nhatky?panel=info&amp;section=check-ins");
    expect(request).toHaveBeenCalledTimes(1);
  });
  it("shows the single journal consent control only on the journal agent and explains cooperation", async () => {
    const { html } = await render("nhatky");
    expect(html).toContain("Dùng khoảnh khắc đã lưu hôm qua</span>");
    expect(html).toContain("tóm tắt");
    expect(html).toContain("Bật lại");
  });
  it("keeps legacy migration explicit and leaves Cầu Nối read/disable/delete only", async () => {
    const journal = await render("nhatky", { legacy: true });
    expect(journal.html).toContain("Lịch cũ");
    expect(journal.html).toContain("Chuyển sang Nhật ký");
    const bridge = await render("caunoi", { legacy: true });
    expect(bridge.html).not.toContain('role="switch"');
    expect(bridge.html).toContain("Xóa lịch");
    expect(bridge.html).not.toContain("Chuyển sang");
  });
  it("leaves information usable with a local unavailable state", async () => {
    const { html, request } = await render("hoatdong", { unavailable: true });
    expect(html).toContain("Lời hỏi thăm chưa mở");
    expect(html).not.toContain('role="switch"');
    expect(request).toHaveBeenCalledTimes(1);
  });
});
