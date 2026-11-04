import { expect, type Page } from "@playwright/test";
import { baseSession } from "./ux-fixtures";

export const CONV = "22112211-2211-4211-8211-221122112211";
export const JOB = "33113311-3311-4311-8311-331133113311";
export const SOURCE = "https://example.org/public-article";
const stamp = "2026-11-03T08:00:00Z";
export const places = [{ name: "Cà phê nhỏ", address: "Quận 3, TP.HCM", category: "Cà phê", placeId: "ChIJpublic",
  rating: 4.5, ratingCount: 12, openingHours: ["Thứ ba: 08:00–20:00"],
  mapsUrl: "https://www.google.com/maps/search/?api=1&query=cafe&query_place_id=ChIJpublic", fetchedAt: stamp, provider: "apify" }];
type SearchBot = "hoatdong" | "nhatky";
const botNames = { hoatdong: "Hoạt động", nhatky: "Nhật ký" };
type SearchFixtureOptions = { botId?: SearchBot; skillsOnly?: boolean; failFirst?: boolean; webOutcome?: "empty" | "timeout" | "rate_limit" | "budget" | "cancel"; mapsOutcome?: "pending" | "empty" | "failed" | "timed_out" | "gone" | "offlineOnce" };
export async function searchFixture(page: Page, { botId = "hoatdong", skillsOnly = false, failFirst = false, webOutcome, mapsOutcome }: SearchFixtureOptions = {}) {
  let mapsOffline = mapsOutcome === "offlineOnce";
  const seen = { sends: [] as Record<string, any>[], mapsReads: 0, capabilities: 0, cancels: 0, mapsCancels: 0, restoreMaps: () => { mapsOffline = false; } };
  let mapsCancelled = false;
  let releaseCancel!: () => void;
  const cancellation = new Promise<void>((resolve) => { releaseCancel = resolve; });
  let sendCount = 0, last: Record<string, any> = {}, run = "";
  const thread = { conversationId: CONV, botId, version: 1, persistent: true,
    title: "Thử kỹ năng", expiresAt: "2026-12-01T08:00:00Z", messages: [] as Record<string, any>[],
    activeRunId: null, activeRunVersion: null, hasMoreMessages: false };
  const bot = { botId, name: botNames[botId], role: botNames[botId], description: "Một bước nhỏ vừa sức.", starters: [], avatarKey: botId };
  await page.route("**/api/v1/**", async route => {
    const request = route.request(), url = new URL(request.url()), path = url.pathname.replace("/api/v1", "");
    const json = (value: unknown, status=200) => route.fulfill({ status, json: value });
    if (path === "/ai/prompt-capabilities") {
      seen.capabilities++;
      return json({ responseProtocols: [2,3], skills: [
        { id: "hangout", name: "Đi chơi", description: "Gợi ý hoạt động vừa sức.", available: true },
        { id: "learn-new-thing", name: "Học điều mới", description: "Thử một điều mới trong 10 phút.", available: true },
        ...[
          ["weekly-review", "Nhìn lại tuần"], ["mood-patterns", "Nhận ra mẫu cảm xúc"],
          ["guided-journal", "Viết nhật ký có gợi ý"], ["reframe-thought", "Viết lại suy nghĩ"],
        ].map(([id, name]) => ({ id, name, description: "Kỹ năng cho một lượt.", available: botId === "nhatky",
          reason: botId === "nhatky" ? null : "Kỹ năng này dành cho trợ lý Nhật ký." }))],
        tools: ["web_search", "maps_search"].map((id, i) => ({ id, name: i ? "Maps Search" : "Web Search", description: "Tìm kiếm công khai", available: !skillsOnly, reason: skillsOnly ? "Tìm kiếm chưa sẵn sàng" : null })) });
    }
    if (path === `/ai/conversations/${CONV}/messages` && request.method() === "POST") {
      last = request.postDataJSON(); seen.sends.push(last); sendCount++;
      if (failFirst && sendCount === 1) return json({ error: { code: "TEMPORARY_FAILURE", message: "Thử lại" } }, 503);
      run = `44004400-4400-4400-8400-${String(sendCount).padStart(12,"0")}`;
      thread.messages.push({ id: last.clientMessageId, actor: "self", text: last.text, cards: [], runId: run });
      thread.version++;
      return json({ runId: run, conversationId: CONV, version: thread.version, runVersion: 1, eventsUrl: `/api/v1/ai/runs/${run}/events` }, 202);
    }
    if (path === `/ai/runs/${run}/cancel` && request.method() === "POST") {
      seen.cancels++;
      thread.messages.at(-1)!.status = "cancelled";
      releaseCancel();
      return json({ runId: run, status: "cancelling", version: 2 });
    }
    if (path.endsWith("/events")) {
      const options = last.promptOptions ?? {};
      const web = options.tools?.includes("web_search") || last.text?.includes("mới nhất");
      const maps = options.tools?.includes("maps_search");
      const reuse = options.mapsSearchId;
      if (web && webOutcome === "cancel" && sendCount === 1) {
        await cancellation;
        return route.fulfill({ contentType: "text/event-stream", body: `data: ${JSON.stringify({ version: "ai-events-v3", seq: "1", type: "cancelled", data: {} })}\n\n` });
      }
      // Backend fake tests separately exercise admission/provider failures. These are
      // the grounded, uncited replies rendered when search cannot verify a fact.
      const unavailable = web && webOutcome && sendCount === 1 ? {
        empty: "Chưa tìm thấy nguồn phù hợp. Mình chưa xác minh được thông tin này.",
        timeout: "Tìm kiếm chưa phản hồi kịp. Mình chưa xác minh được thông tin này; bạn có thể thử lại sau.",
        rate_limit: "Tìm kiếm đang giới hạn lượt dùng. Mình chưa xác minh được thông tin này; bạn hãy thử lại sau ít phút.",
        budget: "Tìm kiếm đã đạt giới hạn chi phí. Mình chưa xác minh được thông tin này.",
        cancel: "",
      }[webOutcome] : "";
      const text = unavailable || (web ? "😀 Thông tin mới có nguồn." : maps && !options.area ? "Bạn muốn tìm ở khu vực nào?" : maps ? "Mình đang tìm địa điểm. Kết quả sẽ hiện trong thẻ." : reuse ? "Bạn có thể thử ghé Cà phê nhỏ để đọc sách." : "Thử học vẽ một chiếc lá trong 10 phút nhé.");
      const citations = web && !unavailable ? [{ sourceId: "s1", title: "Thông tin công khai", url: SOURCE, start: 2, end: Array.from(text).length }] : [];
      const cards = reuse ? [{ kind: "places", places }] : maps && options.area ? [{ kind: "maps_search", searchId: JOB }] : [];
      const message = { messageId: `55005500-5500-4500-8500-${String(sendCount).padStart(12,"0")}`, partIndex: 0, text, cards, citations };
      thread.messages.push({ ...message, id: message.messageId, actor: "bot", createdAt: stamp, runId: run, partCount: 1, speaker: botId, steps: [] });
      thread.version++;
      return route.fulfill({ contentType: "text/event-stream", body: [
        { type: "progress", data: {} }, { type: "final", data: { partCount: 1, messages: [message], speaker: botId, steps: [] } },
        { type: "completed", data: {} }].map((e,i) => `data: ${JSON.stringify({ version: "ai-events-v3", seq: String(i+1), ...e })}\n\n`).join("") });
    }
    if (path === `/ai/maps-searches/${JOB}/cancel`) {
      seen.mapsCancels++; mapsCancelled = true;
      return json({ searchId: JOB, status: "cancelled", version: 3, expiresAt: "2026-12-01T08:00:00Z", retryAfterSeconds: 2, places: [] });
    }
    if (path === `/ai/maps-searches/${JOB}`) {
      seen.mapsReads++;
      if (mapsOutcome === "gone") return json({ error: { code: "MAPS_NOT_FOUND", message: "Không tìm thấy kết quả còn hiệu lực." } }, 404);
      if (mapsOffline) return route.abort("internetdisconnected");
      const status = mapsCancelled ? "cancelled" : !mapsOutcome || mapsOutcome === "offlineOnce" ? "ready" : mapsOutcome;
      return json({ searchId: JOB, status, version: 2, expiresAt: "2026-12-01T08:00:00Z", retryAfterSeconds: 2, places: status === "ready" ? places : [] });
    }
    if (path === `/ai/conversations/${CONV}`) return json(thread);
    const fixed: Record<string, unknown> = {
      "/session": { ...baseSession, features: { ...baseSession.features, threeAgents: true, agentSkills: true, webSearch: !skillsOnly, mapsSearch: !skillsOnly } },
      "/bots": [bot], "/bots/legacy": [], "/ai/conversations": [thread],
      "/ai/preferences": { historyEnabled: true, semanticMemoryEnabled: false, version: 1, policyVersion: "ai-data-v1", retentionDays: 30, historyAvailable: true, semanticMemoryAvailable: false },
      "/ai/inbox": { bots: [], unreadTotal: 0, badgesEnabled: true }, "/proposals": [], "/memories": [],
    };
    if (request.method() === "GET" && path in fixed) return json(fixed[path]);
    return json({ error: { code: "NOT_FOUND", message: "No synthetic route" } }, 404);
  });
  return seen;
}
export const field = (page: Page, botId: SearchBot = "hoatdong") => page.getByRole("textbox", { name: `Tin nhắn cho ${botNames[botId]}` });
export async function openSearch(page: Page, botId: SearchBot = "hoatdong") {
  await page.goto(`/#/assistants/${botId}?conversation=${CONV}`);
  await expect(field(page, botId)).toBeVisible();
  await expect(page.getByText("Đang mở cuộc trò chuyện…")).toHaveCount(0);
}
export async function send(page: Page, text: string, botId: SearchBot = "hoatdong") {
  await field(page, botId).fill(text);
  await page.getByRole("button", { name: "Gửi tin cho AI", exact: true }).click();
  await expect(field(page, botId)).toHaveValue("");
  await expect(page.getByRole("button", { name: "Gửi tin cho AI", exact: true })).toBeDisabled();
}
