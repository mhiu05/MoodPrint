# Agent Search & Skills — overview và đặc tả chung

Ngày khảo sát: **03/11/2026**, timezone `Asia/Bangkok`. Trạng thái: **kế hoạch đề xuất, chưa triển khai**. Mã nguồn trong working tree là căn cứ, kể cả các thay đổi frontend có sẵn trước phiên khảo sát. Không suy từ file example rằng staging đang bật/tắt cờ nào.

## Phạm vi phiên lập plan

Chỉ tạo tài liệu trong `docs/implementation-plans/agent-search-and-skills/`. Không sửa product code, dependency/lock files, `.gitignore`, env/example, AWS config hoặc dữ liệu runtime. Không đọc `backend/.env` hay secret runtime; không chạy tests, OpenAI/Apify/Google API, AWS CLI, migration hoặc deploy. Việc tra tài liệu công khai của nhà cung cấp không phải chạy provider/live test. Mọi lệnh kiểm thử và bước vận hành bên dưới đều dành cho **phiên triển khai sau**.

Yêu cầu sản phẩm được chép thành các quyết định và acceptance criteria trong bộ tài liệu này để executor không cần truy cập attachment riêng của người yêu cầu.

## Bản đồ và thứ tự triển khai

| Tài liệu | Deliverable | Phụ thuộc |
| --- | --- | --- |
| [01 — audit](01-codebase-audit.md) | File thực tế, các giới hạn và điểm khác tài liệu cũ | Đọc trước mọi subplan |
| [02 — Web Search](02-web-search-citations-accounting.md) | Responses search, citation xuyên suốt, usage và hợp đồng chung | Nền cho search contracts; có thể dùng qua backend trước menu |
| [03 — Maps Search](03-maps-search.md) | Apify adapter, job async, place cards, giới hạn tiền/thời gian | Contract citation/card/protocol của 02; adapter/job kiểm thử độc lập |
| [04 — Skills & composer](04-agent-skills-composer.md) | Registry hai skill, tự nhận ý định, dấu `+` và chip một lượt | Registry/skill không phụ thuộc provider; search menu nối 02/03 khi available |
| [05 — phối hợp mặc định bật](05-collaboration-defaults.md) | Effective policy mới cho cả tài khoản cũ/mới; bỏ UI opt-in | Độc lập 02–04; giữ cả legacy và V3 runtime |
| [06 — lịch trong từng agent](06-agent-check-in-settings.md) | Lịch sáng/tối trong info panel; bỏ mục Tài khoản | Độc lập search/skills; phối hợp với 05 ở copy và journal-context control |
| [07 — vận hành & coverage](07-rollout-credentials-and-coverage.md) | Credential, AWS, validation tương lai, rollback và ma trận coverage | Dùng tại mỗi gate |

Thứ tự khuyến nghị: 05 và 06 có thể phát hành riêng; với search làm 02 → 03 → nối composer 04. Phần registry/composer không cần chờ credential để kiểm thử bằng fake. Không gộp thành một migration khổng lồ. Mỗi thay đổi DB chọn revision kế tiếp dựa trên head lúc triển khai; head khảo sát là `0024_three_agent_groups.py`, không đặt trước số `0025` cho nhiều nhánh.

## Quyết định và giả định đề xuất

1. **Skill chạy ở agent đang mở**, bao gồm specialist đang trả lời sau handoff; không âm thầm đổi `active_agent`, chuyển route, nhập lịch sử khác hoặc ghi receipt handoff giả. Hai skill cùng dùng được ở ba V3 agent, nhưng chỉ dùng tool mà agent và backend cho phép. Legacy không mở skill/search trong đợt đầu. Group chat và proactive giữ nguyên runtime, chưa nhận search/skill selection.
2. **Skill là workflow; tool là nguồn dữ liệu.** `hangout` vẫn có thể gợi ý không cần dịch vụ ngoài; tìm địa điểm thật cần Maps; `learn-new-thing` dùng Web khi cần nội dung mới. `SKILL.md` chỉ từ registry đóng trong backend, không thực thi và không tự cấp tool.
3. **Search là khả năng trả phí theo lượt.** Manual selection yêu cầu thử dùng tool nếu đủ quyền/budget; auto để agent chọn khi cần dữ kiện mới hoặc địa điểm. Thiếu khu vực thì hỏi trước, chưa tạo actor. Không tự lấy GPS/IP location, timezone, hồ sơ hoặc nhật ký để đoán vị trí.
4. **Apify là provider Maps đầu tiên, theo luồng async.** Không dùng actor đồng bộ bên trong chat 30 giây. Kết quả đến ở card; người dùng có thể yêu cầu agent dùng kết quả trong lượt sau. Không tự khởi chạy thêm model call sau khi lượt chat đã completed. Google Places là phương án thay thế có adapter, chưa triển khai fallback tự động tính phí kép.
5. **Phối hợp bật hiệu lực cho tài khoản đủ điều kiện cũ và mới**, kể cả preference cũ `false`; bỏ UI cấu hình cạnh. Dùng policy epoch có rollback, không xóa lịch sử opt-in cũ. AI consent, journal-context opt-in, group journal access/history, eligibility, quota, budget và kill switch vẫn có hiệu lực. Đây là mặc định capability, không có nghĩa mọi prompt đều gọi specialist.
6. **Lịch vẫn thuộc `bot_id`, không thuộc conversation hoặc speaker của từng bubble.** Info của Điều phối quản lý lịch Điều phối ngay cả khi Hoạt động đang trả lời. Có đường mở info riêng Hoạt động từ banner/roster. Không tự chuyển lịch legacy.

Các mục trên là đề xuất của người lập plan, không mô tả quyết định đã được kiểm chứng bằng live provider. Không có câu hỏi đang chặn việc lập hoặc đọc plan.

## Hợp đồng chung cần thống nhất trước khi chia task

Tên wire dùng camelCase theo `DTO`; dưới đây là hợp đồng **mới đề xuất**:

```ts
type PromptOptions = {
  skillId?: 'hangout' | 'learn-new-thing'; // tối đa một skill
  tools?: Array<'web_search' | 'maps_search'>; // unique, tối đa hai
  area?: string;                            // 2–120 ký tự, khu vực người dùng nêu
  mapsSearchId?: string;                     // kết quả job thuộc đúng owner/conversation
};
// StartRunInput thêm promptOptions?: PromptOptions, responseProtocol?: 2 | 3 (default 2).
// New UI gửi responseProtocol=3; thiếu options giữ nguyên hành vi không search của client cũ.

type Citation = {
  sourceId: string; title: string; url: string;
  start: number; end: number;                 // Unicode code points, [start,end) của bubble.text
};
// AiOutput / AIMessage / AIReplyBubble thêm citations: Citation[] = [].
// Citation không tiêu hao giới hạn 3 cards; tối đa 8/bubble, 12/turn, 8 URL/turn.
```

`PromptOptions` được chuẩn hóa trước hash idempotency và admission; mọi lựa chọn, khu vực, job ref và `responseProtocol` tham gia digest. Cùng `clientMessageId` + khác options trả conflict, không tái dùng sai lượt. Thiếu thông tin/flag không được silently nâng quyền. Lựa chọn không phải preference và không đưa vào localStorage, memory hoặc lịch proactive.

**Protocol:** mở rộng SSE bằng `?protocol=3` / `ai-events-v3` cho direct chat, giữ nguyên `final → completed` và metadata `speaker/steps/collaboration` có receipt. Không nhầm SSE v3 với product V3 (hiện product V3 dùng SSE v2). v1/v2 giữ schema cũ và không được tự phát sinh search. Direct history GET/pagination thêm `responseProtocol=3`, default2 để nhận biết client cũ. Khi client cũ replay hoặc đọc history chứa kết quả search, trả thông điệp yêu cầu tải lại ứng dụng thay cho nội dung/card đã mất citation; không hiển thị dữ kiện web thiếu nguồn. Source-backed marker phải suy được từ metadata đã lưu, không đoán từ URL trong text. Export luôn giữ đầy đủ nội dung và provenance. Không đổi group SSE trong giai đoạn này.

**Nội dung có nguồn:** registry nguồn do backend tạo; model chỉ tham chiếu `sourceId`. Với câu trả lời dùng search, dùng draft segments `{text, sourceIds[]}` nội bộ, backend ghép text và tính offsets; không chuyển offset trên JSON thô sang text bubble. Link chỉ `https`, URL chuẩn hóa có giới hạn, không credentials, localhost/private-IP, `javascript:`, `data:` hoặc URL do model tự bịa. Không fetch URL từ citation. UI bấm link ngoài với `noopener noreferrer` và `referrerPolicy=no-referrer`; journal link nội bộ giữ nguyên owner authorization.

## Giới hạn mặc định đề xuất

| Hạng mục | Mặc định ban đầu | Điều kiện |
| --- | --- | --- |
| Chat | 30 giây tổng, không nâng global timeout | Tính cả admission/queue/model/tool, hủy theo deadline còn lại |
| Web | 1 search operation/lượt; hosted `max_tool_calls=1`; 12 giây | Search child 1 model request; parent vẫn tối đa 3 request, 2 function calls |
| Maps | 1 actor/lượt; 5 kết quả trong 1 card | Start HTTP ≤3 giây; actor 60 giây, job wall deadline 90 giây |
| Paid search | 5 operations/user/ngày; 1 đang chạy/user; 2 toàn hệ thống | Web + Maps dùng chung cap, DB authority; guest chưa mở |
| Search spend | 5 USD/ngày cho toàn search, nằm trong global AI budget | Không cộng thêm ngoài `AI_DAILY_BUDGET_USD`; reserve trước dispatch; chọn mức này vì child model hiện reserve 2 USD |
| Maps liability | Tối đa 0,05 USD/actor theo cấu hình đã xác minh | Chưa tính là bound nếu actor pricing/build không hỗ trợ; khi ấy đóng Maps |
| Skill | Một skill/lượt; body ≤16 KiB/skill | Không thêm một LLM router riêng; không auto chạy tool chỉ vì chọn skill |

Không có reservation web token bound được phê duyệt thì Web Search unavailable, không giải phóng phần tiền chưa xác định. 0,05 USD là đề xuất cap Maps, không phải báo giá bảo đảm. Chi tiết accounting và giá tham chiếu ở 02/03/07.

## Cổng hoàn thành từng phase

- [ ] Có fake/mock kiểm chứng contract, failure, quota, quyền và đường rollback tương ứng; không cần provider secret trong test thường.
- [ ] Migration có upgrade/downgrade review trên DB disposable; giữ dữ liệu lịch sử và không mở thêm grant.
- [ ] UX kiểm tra cả desktop/mobile, keyboard/focus, lỗi và offline; không coi kiểm thử code là bằng chứng visual QA.
- [ ] Có rollout server-side và stop switch; sample config mới chỉ sửa trong phiên triển khai sau.
- [ ] Chỉ bật live/staging khi credential, pricing, operational config và các gate repo hiện hữu đã được kiểm riêng. Bộ plan này không chứng nhận production ready.
