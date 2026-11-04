# 07 — Quyết định mở, mâu thuẫn, rủi ro, điều chưa xác minh

## Mâu thuẫn giữa các yêu cầu, kèm cách giải đề xuất

| # | Mâu thuẫn | Đề xuất | Quyết định liên quan |
| --- | --- | --- | --- |
| C1 | "TẤT CẢ cờ = true" ↔ "trần chi phí vẫn hoạt động, thiếu key không crash". Hai field `*_VERIFIED` là lời xác nhận đã kiểm chứng trần chi phí; `AUTH_CAPTCHA_ENABLED` phải khớp Supabase Auth | Bật 26 cờ tính năng + 2 cờ mới; giữ `false` cho 5 công tắc an toàn (bảng ở [01](01-flags.md)) | OD-01 |
| C2 | "TẤT CẢ cờ = true" ↔ ~43 file test chat với 5 trợ lý cũ (V3 + cohort rỗng làm chúng chỉ đọc) | Ghim nền test `ALL_FEATURES_OFF`; bộ test mặc định riêng | — |
| C3 | "Nới giới hạn 90 ngày" ↔ retention xóa cứng entry > 89 ngày, editor chỉ cho viết trong 90 ngày | Giữ 90 ngày; mở rộng thật nằm ở tìm ngữ nghĩa trên **toàn** cửa sổ và `limit` 5 → 6 (tối đa 8) | OD-05 |
| C4 | "Memory tự động" ↔ bất biến "memory chỉ từ proposal người dùng xác nhận" (docstring, ARCHITECTURE, `proposal_id NOT NULL`, nhãn context "Approved") | Lớp `origin='journal_auto'` có nhãn riêng ở schema, UI, context; luồng proposal không đổi | OD-07, OD-08 |
| C5 | "Công tắc tắt xử lý ngoài" ↔ chính sách "tính năng cá nhân luôn được phép" (`consent/policy.py:1-7`, AI/MEM/VOICE luôn bật) | Công tắc là **preference** trong `journal_ai_settings`, không phải consent purpose mới; mô hình consent giữ nguyên | OD-04 |
| C6 | "Xóa MATCH khỏi Privacy" ↔ hợp đồng session còn đòi purpose `MATCH` (`api/session.ts:32`; `auth/routes.py`) | Không còn màn Privacy; giữ MATCH trong hợp đồng tới sau demo | — |
| C7 | Brief "hosted ở 0020" ↔ tài liệu (0024 trong bản commit, 0028 trong bản stash) | Xác minh chỉ đọc trước JI-51; kế hoạch giả định 0028 | OD-11 |
| C8 | "Agent Settings gán skill" ↔ không có cơ chế gán; skill áp cho mọi agent V3 | Allowlist agent cứng trong registry (không cấu hình bởi người dùng) | — |
| C9 | "Agent cá nhân hóa theo nhật ký" ↔ memory theo từng trợ lý; consult Nhật ký của Điều phối đòi `journal_context_enabled` (mặc định false, `collaboration/grants.py:64`) | Không đổi trong đợt này | OD-08, OD-13 |
| C10 | "Không đổi mood scope" ↔ skill "nhìn lại tuần" cần điểm tâm trạng | Dùng trường `mood` của từng entry mà tool nhật ký trả về; skill + mood scope vẫn loại trừ nhau | — |

## Quyết định mở cho chủ dự án

| ID | Câu hỏi | Khuyến nghị | Ảnh hưởng nếu chọn khác |
| --- | --- | --- | --- |
| OD-01 | Giữ `false` cho `AUTH_CAPTCHA_ENABLED`, `COOKIE_SECURE`, `PROVIDER_FORCE_IPV4`, `AI_WEB_SEARCH_TOKEN_BOUND_VERIFIED`, `APIFY_MAPS_CHARGE_BOUND_VERIFIED`? | Giữ | Bật captcha mặc định: dev không đăng nhập được, prod raise. Bật hai attestation: mở khóa search khi chưa kiểm chứng trần chi phí |
| OD-02 | `AI_DAILY_BUDGET_USD` mặc định 0 = không trần toàn cục. Đổi mặc định? | Không đổi mặc định; bắt buộc đặt > 0 trên môi trường demo (báo cáo stash ghi hosted dùng USD 20/ngày) | Đổi mặc định ảnh hưởng mọi môi trường và test budget |
| OD-03 | Route backend social/matching/activities sau khi gỡ UI | Giữ mounted cho demo, gỡ sau demo | 404 cho route ghi: +0,5 ngày + sửa test; gỡ hẳn: ~15 file test backend |
| OD-04 | Thông báo + công tắc xử lý nhật ký bằng Voyage: (a) opt-out mặc định bật (theo brief), (b) opt-in như semantic memory, (c) không có công tắc | (a), thông báo ở mục Tài khoản | (b): gần như không ai bật nên demo phải bật tay. (c): chỉ gỡ component, API giữ |
| OD-05 | Mở rộng cửa sổ > 90 ngày? | Không trong đợt này | Phải đổi retention, editor, chính sách dữ liệu và tài liệu quyền riêng tư |
| OD-06 | Guest có embedding/memory tự động? | Không | Cần đường guest paid (reservation) như `embeddings.py:198-237` |
| OD-07 | Memory tự động khi sửa entry / tắt công tắc | Sửa entry: xóa memory chưa sửa, giữ memory người dùng đã sửa (vẫn liên kết, bị xóa khi entry bị xóa). Tắt: giữ memory đã có, có nút xóa hàng loạt | Xóa hết khi sửa/tắt: đơn giản hơn nhưng mất chỉnh sửa của người dùng |
| OD-08 | Điều phối có thấy memory tự động của Nhật ký? | Không (giữ bất biến theo trợ lý) | Có: đổi `_memory_scope`, copy `Memory.tsx:261`, test privacy |
| OD-09 | 5 file auth/landing chưa commit trong `stash@{0}` đụng copy JI-11 (`Auth.tsx`, `GuestEntry.tsx`) | Chủ dự án commit/merge stash vào `main` trước JI-11, hoặc chấp nhận rebase sau | Không giải quyết thì xung đột khi merge |
| OD-10 | Backfill memory tự động cho entry cũ | 14 ngày gần nhất | 0: chỉ entry mới. 89: tối đa chi phí |
| OD-11 | Ngày demo, phương án A (hosted) hay B (local), cửa sổ bảo trì | A nếu còn ≥ 2 ngày; B dự phòng | Ngày demo quyết định cut line (ước lượng theo ngày công, chạy song song bằng subagent rút được thời gian lịch): ≥ 16,5 ngày công → làm hết; 13–16,5 → cắt nhóm B; 11,5–13 → cắt cả A và B; < 11,5 → thu hẹp phần bắt buộc theo thứ tự: bỏ JI-24 chế độ Voyage live (giữ fake), JI-13 chỉ xóa spec social (moderation viết lại sau), JI-21 giữ API và bỏ UI công tắc (OD-04) |
| OD-12 | Hosted có `VOYAGE_API_KEY`? | Cung cấp trước JI-51 | Không có: truy xuất chạy chế độ từ khóa + gần nhất, demo vẫn chạy nhưng không có tìm theo ý nghĩa |
| OD-13 | Mặc định `journal_context_enabled=true` khi collaboration defaults bật, để Điều phối consult được nhật ký? | Không đổi | Đổi: mở rộng dữ liệu nhật ký sang luồng Điều phối cho mọi người dùng, cần review privacy |
| OD-14 | Thêm control cho `semanticMemoryEnabled` (hiện không có UI) vào mục Tài khoản mới? | Sau demo | Bật được tìm memory theo ý nghĩa |
| OD-15 | Mâu thuẫn cấu hình **tường minh** (ví dụ `AI_COLLABORATION_ENABLED=true` + `AI_MULTI_MESSAGE_ENABLED=false`) có còn raise? | Còn raise (lỗi của người vận hành); giá trị mặc định thì clamp | "Không bao giờ raise": mất fail-fast cho cấu hình sai |
| OD-16 | Cleanup sau demo: xóa nhánh cờ tắt, gỡ backend matching, migration drop 0011–0013 | Lên kế hoạch riêng sau demo, có backup và SQL review | — |

## Rủi ro lớn nhất (xếp theo mức độ)

1. **Thứ tự migrate/deploy sai làm hosted 503.** Image hiện tại chỉ chấp nhận 0028; image mới đòi 0029. Giảm thiểu: image tương thích C chấp nhận cả hai, cổng bảo trì, rollback F → C ([06](06-verification-and-release.md)).
2. **Đổi mặc định làm đổi hành vi prod ở mọi key vắng trong runtime SSM** (worker proactive, guest, admin route, collaboration defaults, STT…). Nội dung SSM v24 chưa xác minh. Giảm thiểu: chạy `check_config.py` của image mới với runtime env, so với image cũ trước khi bỏ cổng; đặt tường minh những gì muốn tắt.
3. **Quyền riêng tư: gửi văn bản nhật ký ra Voyage theo mặc định.** Giảm thiểu: thông báo rõ, công tắc, chỉ người 18+ đã đăng ký, chỉ entry `saved`, xóa vector theo cascade; dữ liệu đã gửi không thu hồi được ở nhà cung cấp (ghi rõ trong thông báo). Cần chủ dự án duyệt (OD-04).
4. **Memory tự động sai hoặc nhạy cảm.** Giảm thiểu: bắt trích dẫn nguyên văn, lọc lâm sàng/PII, bỏ qua entry distress, nhãn riêng, sửa/xóa dễ, cắt được (nhóm B).
5. **Khối lượng sửa test lớn hơn dự kiến** (43+ file chat legacy, ~20 spec e2e/fullstack). Giảm thiểu: ghim nền, red run có danh sách chính thức, cut line.
6. **Chi phí khi mọi cờ bật và budget = 0:** orchestration/collaboration chỉ có cap theo người; extraction thêm 1 call/entry. Giảm thiểu: OD-02, cap/ngày, `journal_auto_memory_budget_share`.
7. **Độ trễ:** embed truy vấn thêm tới 3 s vào lượt Nhật ký (timeout lượt 30 s). Giảm thiểu: timeout cứng + fallback; đo p95 ở JI-24.
8. **Xung đột với stash của chủ dự án** (OD-09).
9. **Worker trong process API tranh pool/event loop** (pool 5+2). Giảm thiểu: batch nhỏ, không giữ kết nối khi gọi provider, theo dõi `metric=db_pool_checked_out`.
10. **Backend social còn gọi được** bởi tài khoản đã bật MATCH trước đây (thấp; OD-03).
11. **Entry > 7.000 ký tự bị cắt khi embed** làm giảm recall phần cuối (thấp; chunking sau demo).

## Điều không thể xác minh bằng đọc code

- Revision Alembic thật trên hosted và số hàng hiện có. Tài liệu mâu thuẫn; bản mới nhất (0028) chỉ nằm trong báo cáo chưa commit ở `stash@{0}`.
- Nội dung runtime SecureString (cờ nào đặt tường minh, có `VOYAGE_API_KEY` hay không, `AI_DAILY_BUDGET_USD` thực tế).
- Báo cáo deploy trong stash có chính xác hay không (image digest, kết quả CI ghi ở đó chưa được kiểm lại).
- Giá và giới hạn tốc độ hiện tại của Voyage `voyage-4-lite` và của model dùng để trích memory; chính sách lưu giữ dữ liệu của Voyage.
- Chất lượng truy xuất trên nhật ký tiếng Việt thật (bộ đo JI-24 dùng dữ liệu tổng hợp); hành vi model với skill/prompt mới (cần eval live).
- Danh sách chính xác test fail sau khi đổi mặc định (xác định bằng red run JI-01); thời gian chạy CI trên nhánh mới; test deploy chỉ chạy được trên Linux.
- Có client nào ngoài SPA gọi route social hay không (kỳ vọng không có).
- Ngày demo và lịch cửa sổ bảo trì.
- Hiệu năng quét cosine chính xác ở quy mô dữ liệu lớn hơn hiện tại (hiện ~7 tài khoản theo báo cáo stash).
