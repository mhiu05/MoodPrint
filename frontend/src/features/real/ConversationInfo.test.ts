import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ConversationInfo, infoFocusables, type ConversationInfoProps } from "./ConversationInfo";

afterEach(() => vi.unstubAllGlobals());
describe("agent information composition", () => {
  it("keeps the owner identity and puts agent settings after its description before management", () => {
    vi.stubGlobal("window", { matchMedia: () => ({ matches: true }) });
    const props: ConversationInfoProps = {
      open: true, botId: "dieuphoi", botName: "Điều phối", botDescription: "Mô tả trợ lý chủ quản",
      agentSettings: createElement("section", null, "Lịch của owner"), panelId: "info", title: "Chat", persistent: true,
      modeLabel: "Lưu lịch sử", retentionLabel: "30 ngày", historyStatus: "Đã lưu", pendingProposals: 0, manageBusy: false,
      triggerRef: { current: null }, onClose: () => {}, onHistory: () => {}, onRename: () => {}, onDelete: () => {}, onNew: () => {},
    };
    const html = renderToStaticMarkup(createElement(MemoryRouter, null, createElement(ConversationInfo, props)));
    expect(html).toContain('data-bot-id="dieuphoi"');
    expect(html.indexOf("Mô tả trợ lý chủ quản")).toBeLessThan(html.indexOf("Lịch của owner"));
    expect(html.indexOf("Lịch của owner")).toBeLessThan(html.indexOf("Quản lý"));
    expect(html).toContain('role="region"');
  });
  it("includes selects and textareas in the compact focus loop, excluding invisible controls", () => {
    const visible = { getClientRects: () => [1] };
    const hidden = { getClientRects: () => [] };
    const root = { querySelectorAll: vi.fn((_selector: string) => [visible, hidden]) };
    expect(infoFocusables(root as unknown as HTMLElement)).toEqual([visible]);
    const selector = root.querySelectorAll.mock.calls[0][0] as string;
    expect(selector).toContain("select:not(:disabled)");
    expect(selector).toContain("textarea:not(:disabled)");
  });
});
