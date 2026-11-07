# MoodPrint — Repository Boundaries, Design Quality & Motion References

> Ngày cập nhật: 07/11/2026. **Chỉ là quy tắc kiến trúc và thiết kế; chưa thực thi backend, Agent SDK, API, CI/CD hoặc cloud.** Phiên bản prototype sử dụng React/Vite/TypeScript và dữ liệu mock. Không tạo source hoặc môi trường Python cho `backend/`/`agent/` trước khi được yêu cầu.

## 1. Quyết định kiến trúc

- Ba module top-level độc lập: `frontend/`, `backend/`, `agent/`.
- `backend/` là ứng dụng FastAPI dự kiến quản lý auth, accounts, incident, evidence, plans, support, knowledge, school integration và API contracts; **không** nhét implementation Agent SDK vào trong `backend/app/`.
- `agent/` là Python package độc lập dự kiến dùng OpenAI Agents SDK cho Companion, roleplay, multimodal, RAG, memory, tools, planning, tracing/evals.
- `frontend/` là ứng dụng người dùng nhìn thấy, dựng bằng mock repositories và mock workflow engine; không import runtime Python hoặc gọi OpenAI bằng key trên trình duyệt.
- **Tách source/package không bắt buộc tách service/process**: FastAPI có thể import package nội bộ `moodprint_agent` trong lần tích hợp đầu tiên, và phân tách dịch vụ chỉ sau khi có lý do vận hành cụ thể.
- `agent/` (runtime sản phẩm tương lai) khác với `.agents/`, `.claude/`, `.codex/`, `.cursor/` (cấu hình/skill cho coding agents). Đừng đồng nhất hoặc xóa nhầm.

### 1.1. Cây thư mục mục tiêu

```text
MoodPrint/
├── frontend/
│   ├── src/
│   │   ├── app/                      # navigation, providers, shells
│   │   ├── components/               # reusable primitives
│   │   ├── features/                 # home, ai, incidents, support, knowledge, school-demo
│   │   ├── animations/               # motion tokens, GSAP hooks, ThinkingOrb wrappers
│   │   ├── mocks/                    # typed data, fixtures, scripts, adapters
│   │   ├── styles/                   # global and design tokens
│   │   └── assets/
│   └── package.json
├── backend/                         # giữ riêng, chưa build
│   ├── app/                         # FastAPI API and domain modules, future
│   │   ├── api/
│   │   ├── core/
│   │   ├── modules/
│   │   ├── schemas/
│   │   ├── infrastructure/
│   │   └── agent_gateway/           # thin adapter, not SDK implementation
│   ├── alembic/                     # future database migrations
│   ├── tests/
│   └── pyproject.toml               # future only
├── agent/                           # giữ riêng, chưa build
│   ├── src/moodprint_agent/
│   │   ├── companion/
│   │   ├── orchestration/
│   │   ├── tools/
│   │   ├── knowledge/
│   │   ├── multimodal/
│   │   ├── memory/
│   │   ├── roleplay/
│   │   └── guardrails/
│   ├── evals/
│   ├── tests/
│   └── pyproject.toml               # future only
├── docs/
├── .agents/                         # skills coding agent
├── .claude/
├── .codex/
├── .cursor/
├── .mcp.json
└── skills-lock.json
```

> Chỉ tạo phần folder tree thuộc frontend và các tài liệu ở giai đoạn hiện tại. Có thể giữ `backend/README.md`, `agent/README.md` làm placeholder; Git không theo dõi thư mục trống. Không cần tạo các package rỗng, scaffold Python hoặc dependencies chỉ vì tài liệu có cây thư mục mục tiêu.

### 1.2. Future call boundary

```text
Student browser (React) -> HTTPS API (FastAPI) -> agent_gateway -> moodprint_agent package
                                            |-> auth/database/object storage
moodprint_agent -> tool interfaces -> authorized backend/domain services
moodprint_agent -> retrieval/model/voice tools (when actually enabled)
```

- Data access và external actions dùng interface được backend cho phép; agent không tự giữ Supabase service-role key hay truy cập mọi bảng.
- Pydantic/OpenAPI là ranh giới contract tương lai. Frontend mock DTO và fixtures phải giữ schema nhất quán để sau này thay mock adapter bằng HTTP adapter.
- Kiến trúc Agent SDK tương lai ưu tiên một Companion thống nhất; dùng tools, agents-as-tools hoặc handoffs *khi đánh giá chứng minh ích lợi*, không ép phải có nhiều Agent chạy trong mỗi request.

## 2. Bốn reference chính thức và cách áp dụng

| Reference | Vai trò | Cách áp dụng MoodPrint | Không nên làm |
|---|---|---|---|
| [Impeccable](https://github.com/pbakaus/impeccable) | Design vocabulary, visual audit, polish | `PRODUCT.md` / `DESIGN.md`, critique và audit từng flow, kiểm tra visual hierarchy, content density, mobile UX | Xem Impeccable như bộ UI component hoặc source code ứng dụng |
| [GSAP](https://github.com/greensock/gsap) | Timeline/microinteraction/scroll motion | Onboarding transitions, modal/sheet, card choreography, staged analysis reveal, success feedback | Chạy animation nhiều nơi gây giật, lạm dụng scroll animation, motion làm chậm thao tác |
| [thinking-orbs](https://github.com/Jakubantalik/thinking-orbs) | Thinking/listening/loading visual for AI | Một wrapper `AgentStatusOrb` map trạng thái thực của UI mock sang `ThinkingOrb` và text label | Dùng orb để ngụ ý AI đang thật sự tìm kiếm/reasoning/tool-use khi chỉ đang replay mock |
| [OpenAI Agents SDK Python](https://github.com/openai/openai-agents-python) | Runtime agent tương lai | `agent/` Python package: tools, structured outputs, sessions, orchestration, evaluation | Cài/import SDK trong giai đoạn mock hoặc đưa Python runtime vào frontend |

### 2.1. Impeccable process

1. Chốt `PRODUCT.md` theo PRD; `DESIGN.md` theo design system MoodPrint.
2. Review từng flow: onboarding, Home, AI chat, OCR analysis, case wizard, roleplay, support, school admin.
3. Review theo thứ tự `shape` -> `critique` -> `audit` -> `polish`/`harden`/`adapt`, sau đó kiểm tra thủ công ở mobile.
4. Nếu muốn cài skills, kiểm tra phiên bản và các file mà installer định thay đổi; **giữ nguyên skills của `.claude/`, `.codex/`, `.cursor/` đã có**, không overwrite trừ khi người dùng chủ động chấp thuận.
5. `audit`/`detect` chỉ là bước rà soát bổ sung; không thay thế kiểm thử và quan sát người dùng trên thiết bị thật.

### 2.2. Motion language — GSAP

| Loại chuyển động | Mục đích | Mức tham chiếu |
|---|---|---|
| Button/tap microfeedback | Cho biết thao tác được ghi nhận | 100–180 ms, subtle |
| Card/sheet enter/exit | Giữ cảm giác liên tục trong navigation | 180–320 ms |
| Onboarding step | Giúp hiểu trang trước/sau | 250–450 ms |
| Analysis reveal | Chia nội dung phức tạp thành từng bước đọc được | 200–400 ms giữa các nhóm; không đánh đổi khả năng đọc |
| AI status orb | Thể hiện trạng thái UI mock, không phải suy nghĩ thật | Continuous only while that state is active |
| Error/important support | Giữ chú ý ở nội dung và hành động, không tạo kịch tính | Static hoặc cực ít motion |

**Quy tắc:** ưu tiên CSS cho hover/active/focus đơn giản; dùng GSAP cho timeline nhiều bước, coordinated entry, gestures hoặc sequencing phức tạp. Với React sử dụng `@gsap/react` / `useGSAP()` (cleanup khi unmount) và scoping; không animate bằng selector global; không gây layout shift; cleanup trên route transitions; tránh animation khi bàn phím mobile mở. Tôn trọng `prefers-reduced-motion` bằng bản tĩnh hoặc chuyển đổi tức thời; tránh hiệu ứng flash/strobe, không dùng motion để biểu thị nội dung bắt nạt.

### 2.3. Thinking-orbs UI contract

`thinking-orbs` hỗ trợ states như `working`, `searching`, `solving`, `listening`, `connecting`, `weaving`, `composing`, `breathing`, `shaping`; có preset 20px/64px và các cơ chế reduced motion/offscreen pause. Không cần tự viết lại shader/animation trừ khi yêu cầu thương hiệu đòi hỏi. Mọi orb phải kèm text cụ thể và phải map tới **trạng thái thực sự của workflow mock**.

| Prototype state | Orb đề xuất | Text phải hiển thị | Khi nào dừng |
|---|---|---|---|
| `idle` | không hiển thị hoặc `breathing` trang trí | `Sẵn sàng trò chuyện` | Khi người dùng nhập/gửi |
| `mock-typing` | `composing` | `Đang tạo phản hồi mô phỏng` | Khi bubble được hiển thị |
| `mock-analyzing` | `working` | `Đang phát lại phân tích mẫu` | Khi kết thúc kịch bản |
| `mock-extracting-evidence` | `searching` | `Đang hiển thị dữ liệu trích xuất mẫu` | Khi chuyển sang bước xác nhận |
| `mock-roleplay-listening` | `listening` | `Mô phỏng lượt lắng nghe` | Khi chuyển lượt diễn tập |
| `mock-completed` | ẩn orb | `Đã hoàn thành bản mô phỏng` | Ngay sau acknowledgement |
| `error`/`cancelled` | ẩn orb | `Đã dừng` / `Không thể tải kịch bản` | Ngay lập tức |

- **Không** show `searching` với thông điệp "đang tìm web" khi prototype không gọi web. Không hiển thị chain-of-thought hay giả vờ có tool calls thật.
- Cần có nút dừng/thử lại, text fallback, `aria-label`, screen-reader status (không spam mỗi frame), reduced-motion và kiểm tra hiệu năng thiết bị phổ thông.
- Orb hoạt động ở UI layer (`frontend/src/animations/`), không nằm trong `agent/` Python package.

## 3. Blueprint cho mô phỏng agent frontend

```
frontend/src/
  features/ai/
    components/ChatView.tsx
    components/RoleplayStudio.tsx
    components/AgentStatusOrb.tsx
    workflows/mockChatWorkflow.ts
    workflows/mockEvidenceAnalysis.ts
  animations/
    motionTokens.ts
    usePageTransition.ts
    useStaggeredReveal.ts
  mocks/
    agents/chat-scripts.ts
    agents/roleplay-scripts.ts
    incidents/evidence-fixtures.ts
```

- Workflow mock dùng finite states, fixtures và deterministic responses. Nếu người dùng nhập ngoài kịch bản, hiện rõ giới hạn demo và đưa những lựa chọn có thể tiếp tục; không giả mạo hội thoại AI tổng quát.
- Trạng thái UI dựa trên `idle -> pending -> result|error|cancelled`, có retry/skip và các bước xác nhận. Tránh random delay quá dài chỉ để orb đẹp.
- Case, chat, analysis và action plan cùng dùng một canonical mock store, để việc chuyển màn hình không mất bối cảnh.
- **Sản phẩm đã chốt:** Kế hoạch ứng phó là core #3 nhưng nằm trong **Hồ sơ sự việc**, route `/cases/:caseId/plan`, không có bottom tab riêng; mọi fixture plan phải gắn `caseId`.

## 4. Acceptance gates dành cho UI/motion

- [ ] 4-tab nav hoạt động trên 320, 375, 390, 430, 768 và 1440px.
- [ ] Animation không làm mất focus, mất bản nháp, che keyboard hoặc ngăn thao tác `Back`/`Skip`.
- [ ] Reduced-motion khiến mọi chức năng vẫn hoạt động và hiểu được trạng thái.
- [ ] Thinking orb, label và mock status cùng một state source; không hiển thị "đang gọi API" sai sự thật.
- [ ] Transcript/analysis vẫn dễ đọc khi animation tắt, không dựa riêng vào màu hoặc chuyển động.
- [ ] Tác vụ hỗ trợ/khẩn cấp luôn truy cập được; không bị trang trí đẩy xuống sâu hoặc chặn bởi animation.
- [ ] Audit Impeccable + kiểm tra thủ công responsive, contrast, focus, loading, empty/error states.
- [ ] Không import `openai-agents`, không cấu hình OpenAI/Supabase/Apify/Maps thật, không request ra external API trong prototype.

## 5. Source references và giới hạn

- Impeccable: https://github.com/pbakaus/impeccable — thiết kế, critique/audit/polish, docs `PRODUCT.md`/`DESIGN.md`.
- GSAP: https://github.com/greensock/gsap — `gsap`, `@gsap/react`, `useGSAP`, matchMedia.
- Thinking-orbs: https://github.com/Jakubantalik/thinking-orbs — React component, animated states, size 20/64, reduced-motion.
- OpenAI Agents SDK: https://github.com/openai/openai-agents-python — Agent, tools, sessions, handoffs, tracing và voice pipeline.

Các repository dùng làm **reference kỹ thuật/UX**, không phải yêu cầu sao chép thiết kế nguyên bản. Kiểm tra phiên bản, giấy phép và API chính thức tại thời điểm triển khai; sản phẩm không lấy tên các thư viện làm tên tính năng hiển thị cho học sinh.
