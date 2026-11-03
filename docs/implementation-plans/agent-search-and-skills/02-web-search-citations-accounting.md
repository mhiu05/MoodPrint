# Web Search, Citations & Accounting Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans hoặc superpowers:subagent-driven-development để triển khai từng task. Checkbox dưới đây dành cho phiên triển khai, chưa được thực hiện.

**Goal:** Agent tự tìm thông tin mới hoặc nhận yêu cầu Web Search cho một prompt, trả lời có nguồn bấm được và tính đủ chi phí.

**Architecture:** Backend function tool `search_web` gọi một Responses/Agents SDK search run cô lập, chỉ nhận query tối thiểu từ prompt hiện tại. Backend giữ registry nguồn từ raw provider annotations rồi dựng citation của câu trả lời cuối; không giao URL authority cho model. Child model và phí hosted tool có ledger riêng, cùng tham gia budget toàn cục.

**Tech Stack:** FastAPI, Pydantic, Agents SDK 0.24.0, OpenAI Responses, SQLAlchemy/PostgreSQL, React/TypeScript.

**Spec:** [00-overview.md](00-overview.md), [01-codebase-audit.md](01-codebase-audit.md), yêu cầu Web Search của bộ plan.

## Global Constraints

- Dùng `OPENAI_API_KEY` hiện có; không tạo credential OpenAI thứ hai hoặc gửi key xuống browser.
- Giữ chat tổng 30 giây, parent tối đa 3 model requests/2 function calls; không nâng CHECK `AiUsage` để lách hạn mức.
- Chỉ direct V3 registered/adult có AI consent và protocol 3 trong đợt đầu; guest/group/proactive/consult child không có search.
- Không gửi nguyên văn nhật ký, mood note, memories, toàn lịch sử, ảnh/âm thanh cho search. Query chỉ từ nhu cầu hiện tại; không lấy dữ liệu private để làm từ khóa.
- Giữ `store=False`, tracing disabled, không retry paid dispatch có kết quả chưa rõ; chạy test thường bằng fake.

## Quyết định và interfaces

Đánh giá hai cách: gắn `WebSearchTool` thẳng vào primary dễ làm nhưng primary đang dùng JSON structured output và private context, không bảo đảm annotations còn ứng với bubble text. **Chọn wrapper cô lập**: vẫn là Responses/Agents SDK, giới hạn và provenance rõ hơn, đổi lại thêm một child model call và độ trễ.

`search_web` không nhận query tùy ý do primary model viết. Backend chuẩn bị `SearchIntent` chỉ từ prompt/options hiện tại; giữ tên chủ đề/câu hỏi công khai cần tra, loại thông tin nhận dạng/credential và không dùng history/memory/journal. Nếu không tạo được query tối thiểu an toàn thì trả `needs_query` để hỏi người dùng. Intent extraction, nếu cần model, phải ghép vào search child trong cùng request; không thêm router model riêng. Search child không có private tools/context. Auto search có tool choice auto ở primary; manual Web đảm bảo một attempt hoặc lý do không thể dùng, không chỉ thêm prompt hint rồi hy vọng model gọi.

Interfaces mới trong `backend/app/ai/search/`:

```text
SearchIntent(query: str[1..300], origin: manual|auto)
WebSearchResult(status: completed|empty|unavailable|needs_query,
                text: str, sources: list[SearchSource])
SearchSource(source_id, title<=200, url<=2048, excerpt<=600)
GroundedSegment(text: str, source_ids: list[str])
GroundedBubble(segments: list[GroundedSegment], cards: list[Card])
GroundedReply(messages: list[GroundedBubble]) // 1–4 bubbles, text/cards bounds như AiReply
WebSearchService.search(intent: SearchIntent, run: LiveRun) -> WebSearchResult
render_grounded_reply(draft: GroundedReply, sources: dict[str, SearchSource]) -> AiReply
SearchAllowance.claim(provider: 'openai_web'|'apify') -> operation_id
```

Tối đa 8 nguồn và 6.000 ký tự search result; không lưu raw webpage, raw Response, prompt, search queries hoặc provider body trong logs/usage. Query tồn tại RAM trong lượt; input digest temporary phải có salt như hiện tại. Source ID chỉ có nghĩa trong run. Grounded draft gồm bubble segments `{text, sourceIds[]}`; backend lấy title/URL từ registry đã kiểm, ghép text rồi tính `Citation.start/end` trên code points. Không tin URL hoặc offsets trên chuỗi JSON từ model. Không có nguồn hợp lệ thì nói chưa xác minh; không phát citation giả.

Search child dùng `WebSearchTool(search_context_size='low', external_web_access=True)` và hosted call cap `max_tool_calls=1`, output tối đa 1.200 tokens, timeout `min(12s, remaining-8s)`. Đọc raw `web_search_call` và `message.output_text.annotations`; giữ `url_citation` với source text tương ứng trước mọi parse/transform. `response_include` chỉ yêu cầu thêm sources khi cần. Kiểm chứng cách truyền `max_tool_calls` qua SDK 0.24.0 (`extra_args` hoặc direct `AsyncOpenAI.responses` adapter bên trong service), không giả định `ModelSettings.max_tool_calls` tồn tại. Không phụ thuộc function-tool hooks để đếm hosted call: chúng không phải một paid-call boundary đầy đủ.

Nếu dùng tool search ở direct current-agent run, không chạy thêm smart planner/consult/handoff trong cùng lượt. Một lượt search không được thay `active_agent`. Các lượt không search đi qua orchestration cũ bình thường; automatic intent phải được nhận từ prompt hiện tại trước khi chọn đường chạy. Search-intent branch được chọn trước private-memory retrieval: primary của lượt này cũng dùng projection công khai (prompt hiện tại và search results), giữ persona nhưng không nạp private history/memory/journal tools. Vì thế Nhật ký trả lời câu hỏi web qua `GroundedReply`, không ép annotations qua `NhipReply` hoặc mood-analysis renderer. Lượt có mood scope không nhận external-search selection; nếu đã đọc journal trong lượt thì đóng auto external search. Đây là giới hạn phase đầu, chưa hỗ trợ trộn phân tích journal với web trong cùng lượt.

`SearchAllowance` thuộc `LiveRun`: một operation mỗi provider, liên kết operation ID đã có để cached preflight/tool call không dispatch hoặc charge lần hai, tổng function-call budget vẫn dùng run counter hiện có. Auto search chỉ đăng ký trên lượt có public search intent; prompt không rõ thì hỏi chủ đề cần tra hoặc giữ direct chat thường, không đưa private context sang search để quyết định query.

## Files dự kiến

| Tạo | Trách nhiệm |
| --- | --- |
| `backend/app/ai/search/{__init__,schemas,policy,web,citations,accounting,models}.py` | Contract, availability/query policy, isolated adapter, source renderer, external fee ledger |
| `backend/alembic/versions/<next>_search_sources_usage.py` | `ai_messages.citations` JSONB default `[]`, content-free `ai_search_usage` |
| `frontend/src/features/real/search/{CitationText,SourceList}.tsx` | Citation inline và danh sách nguồn, không mở markdown arbitrary |
| `backend/tests/test_web_search.py`, `test_search_citations.py`, `test_search_accounting.py` | Tests mới |
| `frontend/src/api/streamSearch.test.ts`, `frontend/src/features/real/search/citations.test.ts` | Protocol/URL/offset tests mới |

Sửa `backend/app/ai/{schemas,provider,runtime,chat_routes,persistence,store,accounting}.py`, `core/config.py`, `contracts.py`, `modules/auth/routes.py`, `modules/users/{export,lifecycle}.py`, `jobs/retention.py`, `main.py`; đọc lại `context.py` để projection không cấp quyền mới. Sửa `frontend/src/api/{stream,contracts}.ts`, `features/real/{RealApp,MessageMarkdown}.tsx`, `agent-chat.css`. Generated OpenAPI/types được sinh trong phiên triển khai sau, không sửa tay. Example configs và vận hành theo [07](07-rollout-credentials-and-coverage.md).

## Accounting, cost và failure policy

`AiSearchUsage` mới: UUID operation PK, owner/run/child-run FK có index, provider `openai_web|apify`, unique `(parent_run_id, provider, ordinal)`, trạng thái `reserved|dispatched|settled|uncertain`, reservation/actual nano-USD ≥0, pricing version, call/item counts, lease/timestamps; **không nội dung/query**. Phí web ở đây; tokens search child vẫn ở `AiUsage`. Khi tính search subset, cộng tokens child đúng một lần với fee; global cộng token ledger và external ledger đúng một lần. Mọi admission/spent/liability reader phải dùng cùng aggregator, bao gồm proactive và orchestration budget-share readers, kể cả lúc search flag off.

Reserve dưới budget advisory lock hiện tại `664201,1`, theo thứ tự owner → budget lock → ledger; không giữ DB trong network I/O. Child model hiện dùng conservative reservation 2 USD/ledger; web fee tham chiếu 0,01 USD/call. Trước khi mở paid flag, xác minh bound của search content tokens/usage, pricing/premiums và đưa vào pricing version; thiếu bound đóng feature. Không coi `search_context_size=low` là token cap. Timeout sau dispatch giữ liability uncertain, không refund về 0. Crash/restart chỉ reconcile, không replay search. Dữ liệu tài chính chưa xác định tiếp tục chặn budget dù đã tắt feature hoặc xóa chat; account deletion bỏ nội dung/định danh theo cơ chế liability detached tương thích cách repo xử lý guest.

Giá tham chiếu tại ngày khảo sát: **10 USD/1.000 calls + search-content tokens theo model**; 100 calls có phí tool khoảng 1 USD chưa gồm token. Giá không phải bound vận hành. [OpenAI pricing](https://developers.openai.com/api/docs/pricing). Source model repo `gpt-6-luna` có công bố hỗ trợ Responses/web search; không cần tự đổi model, nhưng phải xác minh account/SDK thật ở gate tùy chọn. [Model documentation](https://developers.openai.com/api/docs/models/gpt-6-luna).

Lỗi timeout/rate-limit/no results/budget exhausted trả trạng thái an toàn và câu trả lời có mức chắc chắn đúng. Manual selection bị chặn báo rõ lý do; không âm thầm đổi sang Maps/Google/provider khác. Cancel phải dừng/drain child; revalidate AI consent, session, eligibility, data version trước dispatch và publish. Không emit raw tool result hoặc provider exception ra SSE.

## Tasks có thể kiểm chứng

### Implementation ruling 2026-11-03

`safe_query` uses a closed canonical public-topic projection (initial technology/science/learning
topics), never a pass-through of arbitrary prompt prose. Unknown topics return `needs_query`.
This intentionally narrows initial search coverage to prevent names and disclosures from leaving
the current prompt. Extend the reviewed topic registry for broader coverage; do not weaken it
into a growing denylist. Every saved bubble carries a backend `source_backed` marker, so old
clients redact an entire source-backed turn even when a paginated bubble has no inline citation.
Ordinary model history stops at that boundary; explicit Maps reuse is separately authorized.

Continuation ruling 2026-11-03: the projection gained closed slots, still copying zero user words:
more reviewed topic labels, one public gazetteer place (34 provincial units + major destinations)
and one time label (e.g. "thời tiết tại Hà Nội hôm nay"). Streets, schools and homes are dropped.
A disclosure (`private_prompt`) returns `needs_query`; an unregistered public topic returns
`unsupported_topic` with an explicit "not searched" instruction, both before any paid attempt.
A default protocol-2 send without options keeps the pre-search idempotency digest input, so a
retry that spans the rollout still matches its original turn.

### W1 — Contract, source persistence và negotiation

**Files:** schemas/models/migration/persistence/store/chat_routes/export; stream/contracts; tests multi-message và streamSearch.

**Interfaces:** tạo `Citation`, `PromptOptions`, `StartRunInput.responseProtocol`, `ai-events-v3` đúng [00](00-overview.md); `AiOutput/AiReply/AIMessage` truyền citation end-to-end.

- [x] Viết failing cases: hai options khác nhau cùng client ID conflict; thiếu fields dùng defaults; citation surviving live → saved/reload → page → export; temp không ghi prose; emoji/Vietnamese offsets đúng. Thêm protocol 1/2 search-replay/history placeholder, protocol3 giữ speaker/steps và mọi new-UI history GET/pagination đều có `responseProtocol=3`.
- [x] Thêm migration additive có JSON array/size constraints, cập nhật mọi constructor/copy/final builder; v1/v2 non-search byte-compatible. Chỉ protocol 3 được search; schema validators chặn unknown fields, oversize, source URL không hợp lệ.
- [x] Chạy `uv run --locked pytest tests/test_multi_message_contract.py tests/test_multi_message_persistence.py tests/test_search_citations.py -q` từ backend và `npx.cmd vitest run src/api/streamSearch.test.ts` từ frontend. Mong đợi pass, fake only. Review migration downgrade không xóa dữ liệu trước khi rollback flags.

### W2 — Bounded search service và admission tài chính

**Files:** search service/accounting/policy/models, provider/runtime/accounting, config; tests web/search accounting/budget.

**Interfaces:** `WebSearchService.search`, `SearchIntent`, `WebSearchResult`; search child `AiRun` một request, fee operation idempotent.

- [x] Fake adapter test snapshot chỉ có public query, `store=False`, hosted cap 1, retries 0, timeout≤12; 2 model/tool limits của parent giữ nguyên. Test manual attempt, auto fresh-info, không cần search, thiếu query và private-context refusal.
- [x] Test reserve đồng thời qua hai DB sessions không vượt global/sub-budget; duplicate hosted event không double charge; unknown usage/cancel sau dispatch/restart không refund; xóa account không xóa unresolved liability. Implement aggregate vào mọi budget reader, không chỉ `reserve_accounting`.
- [x] Implement adapter qua SDK/Responses với raw annotations, gated `AI_WEB_SEARCH_ENABLED=false`, pricing guard, shared search rate/daily/concurrency limits. Nếu SDK không serialize cap đúng, dùng isolated Responses adapter; không nâng dependency ngầm.
- [x] Chạy `uv run --locked pytest tests/test_web_search.py tests/test_search_accounting.py tests/test_usage_accounting.py tests/test_budget_reservations.py -q`; mong đợi pass, chứng minh không có real outbound request qua HTTP fake/spies.

### W3 — Grounded rendering và chat UI

**Files:** citations renderer, provider output adaptation, RealApp, CitationText/SourceList, CSS, MessageMarkdown tests, E2E mới `frontend/tests/e2e/search.spec.ts`.

**Interfaces:** `render_grounded_reply`; UI nhận citations độc lập cards, giữ `/self/entry/<uuid>`.

- [x] Test provider annotation trên raw output không dùng trực tiếp làm bubble offset; dangling source ID, malformed URL, localhost/IP, userinfo, surrogate/emoji, duplicate URL, multi-bubble và output không có nguồn.
- [x] Render citation inline bấm được và source list có title/domain; dùng structured text spans, giữ markdown hiện có mà không cho mọi model markdown link thành anchor. Test không có raw HTML/media, không fetch URL và không tự mở tab.
- [x] Offline acceptance: E2E manual/auto/no search, reload source links, empty/timeout/rate limit/budget/cancel; backend/stream fixtures kiểm SSE replay và v1/v2 unchanged. Keyboard/mobile và số liệu ở [evidence](implementation-evidence.md), mục Independent review. Đây không phải live-provider verification. Acceptance: citations rõ ràng/bấm được theo [OpenAI web search output guidance](https://developers.openai.com/api/docs/guides/tools-web-search#output-and-citations).

## Review Focus và acceptance

1. JSON output mất annotations → W2 raw-event fixtures, W3 source-backed segments.
2. Emoji/formatting đổi offsets → W1/W3 code-point tests; không dùng JS UTF-16 offset trực tiếp.
3. Search sau journal read làm rò nội dung → W2 taint/isolated-input tests, tool unavailable khi không có safe query.
4. Hosted search không đi qua function hooks → W2 đếm provider items, server cap, double-charge test.
5. Client cũ/parser strict → W1 protocol negotiation/replay; W3 test unsupported protocol không tạo search mới.

Chấp nhận khi mọi task có bằng chứng fake pass; người dùng manual hoặc auto tìm được dữ kiện mới có nguồn xuyên live/reload/export; không vượt thời gian/quota/liability và không ảnh hưởng orchestration non-search. Rollout tắt mặc định, schema → frontend protocol 3 → backend cohort → auto/manual. Kill switch ngừng dispatch mới, không ngừng settlement/retention. Credential/AWS steps dùng [07](07-rollout-credentials-and-coverage.md): chỉ key OpenAI hiện có và thêm flags/pricing đã review vào cùng runtime parameter; không thêm IAM chỉ vì Web Search.
