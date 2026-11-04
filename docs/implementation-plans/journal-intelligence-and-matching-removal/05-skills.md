# 05 — Skill mới cho Nhật ký và Điều phối (nhóm A, cắt được)

Phạm vi: yêu cầu 5. Task JI-40. Nếu thiếu thời gian, làm tối thiểu `weekly-review` + `mood-patterns` (giá trị demo cao nhất, dùng truy xuất mới). Hai skill còn lại có cùng cơ chế nên thêm sau chỉ cần thêm file + dòng bảng.

## Cơ chế hiện tại (đã đọc code)

| Thành phần | Vị trí | Hành vi |
| --- | --- | --- |
| Registry | `backend/app/ai/skills/registry.py:19-63` | `SPECS` cứng `{id: (name, description, version)}`; đọc `skills/<id>/SKILL.md`, chặn symlink/thoát thư mục/>16 KiB/UTF-8 lỗi/khóa trùng; frontmatter phải **bằng đúng** `dict(id,name,description,version)`; lỗi ⇒ skill vắng mặt + log `metric=skill_unavailable` |
| Resolver | `skills/resolver.py:6-21` | Chỉ cho `agent in V3_IDS`; chọn tay thắng; tự nhận diện bằng từ khóa bỏ dấu cho đúng 2 skill; phủ định hoặc mơ hồ ⇒ `None` |
| Áp dụng | `search/turn.py:67-73` | Chỉ lượt `response_protocol ≥ 3`, `kind="direct"`, V3, registered, không `mood_scope`; nối `SKILL.md` vào `run.turn_instructions`, đặt `skip_delegation=True` (không planner/handoff) |
| Kiểm tùy chọn | `search/turn.py:30-49` | `promptOptions` khác rỗng đòi protocol 3, V3, `collaboration_eligible` (18+, registered, không bị treo); **skill + `moodScope` ⇒ 422 `PROMPT_OPTIONS_MOOD_SCOPE`** |
| Hợp đồng | `ai/schemas.py:96-97` | `PromptOptions.skill_id: Literal["hangout","learn-new-thing"]` |
| Capability view | `skills/routes.py:27-51` | `GET /ai/prompt-capabilities?botId=` liệt kê mọi skill cho mọi agent V3 |
| Frontend | `features/real/composer/ComposerOptions.tsx:43-60` | Menu "+" từ capability view; nhãn chip cứng `hangout ? "Đi chơi" : "Học điều mới"` (dòng 60) |
| Gán skill cho agent | — | **Không tồn tại.** Không có Agent Settings nào gán skill; skill áp cho mọi agent V3 |

Hệ quả thiết kế:
1. Skill đặt `skip_delegation=True`, nên skill cần nhật ký chạy trên Điều phối sẽ **không** đọc được nhật ký (Điều phối không có tool journal; `Capabilities(memory=True)` ở `agents.py:52`). Vì vậy cần allowlist agent cho từng skill.
2. Skill không đi cùng `moodScope` (giữ nguyên, không đổi cơ chế mood scope). "Nhìn lại tuần" dùng trường `mood` 1–5 của từng entry mà `search_journal_entries` trả về (`journal/ai.py:68-71`), không dùng `read_mood_summary`.
3. Skill chỉ có hiệu lực **một lượt** (chip bị xóa sau khi gửi, theo `11-live-release.md`). Skill nhiều bước phải viết thành một lượt.
4. Lượt skill trên Nhật ký vẫn có tool journal (tools chỉ rỗng khi `public_search`, `runtime.py:855`) và vẫn tôn trọng `journal_read_refused` (`runtime.py:514,816`).

## Skill mới

| id | Tên | Mô tả (frontmatter) | Agent | Tự nhận diện (chuỗi đã bỏ dấu, chứa một trong) |
| --- | --- | --- | --- | --- |
| `weekly-review` | Nhìn lại tuần | Cùng nhìn lại 7 ngày qua từ chính những gì bạn đã ghi. | `nhatky` | `nhin lai tuan`, `tong ket tuan`, `tuan qua cua minh`, `tuan nay minh the nao` |
| `mood-patterns` | Nhận ra mẫu cảm xúc | Tìm điều hay đi cùng một cảm xúc trong nhật ký, không kết luận nguyên nhân. | `nhatky` | `mau cam xuc`, `hay buon khi`, `hay met khi`, `hay lo khi`, `lap di lap lai` |
| `guided-journal` | Viết nhật ký có gợi ý | Vài câu gợi ý ngắn để bạn viết vài dòng cho hôm nay. | `nhatky`, `dieuphoi` | `viet nhat ky`, `khong biet viet gi`, `goi y viet` |
| `reframe-thought` | Viết lại suy nghĩ | Nhìn một suy nghĩ khó từ góc khác, công bằng và nhẹ nhàng hơn. | `dieuphoi`, `nhatky` | `viet lai suy nghi`, `nghi theo cach khac`, `goc nhin khac` |
| `hangout` (v2 từ JI-12) | Đi chơi | (giữ) | cả 3 | (giữ) |
| `learn-new-thing` | Học điều mới | (giữ) | cả 3 | (giữ) |

Quy tắc nhận diện tự động (`resolve_skill`): giữ danh sách phủ định hiện có (`resolver.py:13-14`) ⇒ `None`; `distress_screen([prompt])` đúng ⇒ `None` **kể cả khi chọn tay** (lượt đi theo đường an toàn chung của `SHARED`); chỉ xét skill có `agent` trong allowlist; khớp đúng một skill ⇒ skill đó; 0 hoặc ≥ 2 ⇒ `None`. Hai skill cũ giữ điều kiện `requested` như hiện tại.

### Nội dung `SKILL.md` (chốt; frontmatter = cột bảng trên, `version: 1`)

`backend/app/ai/skills/weekly-review/SKILL.md`, phần thân:

```text
Bạn đang trả lời trong vai trợ lý hiện tại; không tự đổi trợ lý hoặc tạo bàn giao.
Gọi search_journal_entries một lần: from_date là 6 ngày trước hôm nay, to_date là hôm nay,
query rỗng, limit 8. Nếu người dùng không cho đọc nhật ký hoặc công cụ không dùng được,
nói rõ là chưa đọc và mời họ kể vài dòng về tuần này.
Khi có kết quả: nói đã đọc bao nhiêu trang và đây chỉ là những trang công cụ trả về; nêu 2–3
điều họ đã ghi, tách "bạn đã ghi" với "mình thấy"; điểm tâm trạng chỉ lấy từ trường mood của
từng trang, ngày không có trang là chưa có dữ liệu; kết bằng một điều nhỏ đáng giữ cho tuần tới
và tối đa một câu hỏi. Trích nguồn bằng source_entry_ids của các trang đã dùng.
Không chẩn đoán, không gán nhãn tâm lý, không suy ra nguyên nhân, không bịa ngày hay số lần.
```

`mood-patterns/SKILL.md`:

```text
Bạn đang trả lời trong vai trợ lý hiện tại; không tự đổi trợ lý hoặc tạo bàn giao.
Xác định cảm xúc hoặc trạng thái người dùng hỏi bằng chính chữ của họ. Gọi
search_journal_entries với query là chữ đó (tối đa 80 ký tự), limit 8.
Nếu có ít hơn 3 trang liên quan, nói rằng chưa đủ trang để thấy một mẫu và gợi ý ghi thêm vài
ngày. Nếu đủ, chỉ đếm trên các trang được trả về: yếu tố, cảm xúc hay thời điểm nào thường đi
cùng; dùng cách nói "thường đi cùng", nói rõ "chưa chắc cái này gây ra cái kia". Đề nghị một
quan sát nhỏ họ có thể thử ghi lại. Trích nguồn bằng source_entry_ids.
Không chẩn đoán, không gán nhãn tâm lý, không khuyên dùng thuốc.
```

`guided-journal/SKILL.md`:

```text
Bạn đang trả lời trong vai trợ lý hiện tại; không tự đổi trợ lý hoặc tạo bàn giao.
Nếu tin nhắn chưa có nội dung để viết, đưa đúng ba câu gợi ý ngắn: điều nổi bật hôm nay; cảm
giác của bạn lúc này; một điều muốn giữ lại. Nếu tin nhắn đã kể chuyện, gom chính lời họ thành
một đoạn nháp ngắn, không thêm chi tiết, nói rõ đây là bản nháp chưa được lưu.
Luôn kèm card mood_form để họ tự mở trang viết. Không nói đã lưu hay đã ghi giúp.
Không đọc nhật ký cũ trừ khi người dùng yêu cầu. Không chẩn đoán.
```

`reframe-thought/SKILL.md`:

```text
Bạn đang trả lời trong vai trợ lý hiện tại; không tự đổi trợ lý hoặc tạo bàn giao.
Nhắc lại suy nghĩ khó bằng đúng một câu theo lời người dùng. Tách điều đã xảy ra với cách họ
đang diễn giải. Đưa hai cách nói lại công bằng hơn, cụ thể, không phủ nhận cảm xúc và không tô
hồng. Hỏi họ thấy cách nào gần đúng hơn, hoặc muốn sửa ra sao.
Đây không phải trị liệu: không dùng thuật ngữ lâm sàng, không chẩn đoán, không gán nhãn.
Không đọc nhật ký cho skill này.
```

Hướng dẫn an toàn chung (khủng hoảng, tự hại) đã nằm trong `SHARED` (`prompts.py`) và luôn đứng trước `turn_instructions`; resolver đã bỏ skill khi `distress_screen` đúng.

## JI-40 — Allowlist agent, 4 skill, resolver, hợp đồng, chip

**Mục tiêu:** 4 skill mới, mỗi skill chỉ dùng được với agent phù hợp, tôn trọng an toàn và lời từ chối đọc nhật ký.

**Files:** Create 4 thư mục `backend/app/ai/skills/{weekly-review,mood-patterns,guided-journal,reframe-thought}/SKILL.md`. Modify `backend/app/ai/skills/registry.py` (SPECS + `AGENTS`), `backend/app/ai/skills/resolver.py`, `backend/app/ai/skills/routes.py:41-44`, `backend/app/ai/search/turn.py:30-49,67-73`, `backend/app/ai/schemas.py:97`, `frontend/src/features/real/composer/ComposerOptions.tsx:60`, `frontend/src/features/real/composer/promptOptions.ts`. Test `backend/tests/test_agent_skills.py`, `backend/tests/test_prompt_options.py`, `backend/tests/test_guest_permissions.py:163` (giữ), `frontend/src/features/real/composer/promptOptions.test.ts`, `frontend/tests/e2e/agent-skills.spec.ts`.

**Interfaces:**
- `SPECS: dict[str, tuple[str, str, str]]` (giữ dạng, thêm 4 mục); `AGENTS: dict[str, tuple[str, ...]]` (mỗi tuple ⊆ `V3_IDS`); `SkillId = Literal["hangout","learn-new-thing","weekly-review","mood-patterns","guided-journal","reframe-thought"]` dùng cho `PromptOptions.skill_id`.
- `resolve_skill(prompt: str, manual_id: str | None, agent: str) -> str | None`: raise `ValueError("unknown skill")` (giữ) và `ValueError("skill not for agent")` (mới).
- `validate_options`: thêm `422 SKILL_NOT_FOR_AGENT` "Kỹ năng này không dành cho trợ lý hiện tại."
- Capability: `available = … and bot_id in AGENTS[identity]`; reason khi sai agent: "Kỹ năng này dành cho trợ lý {tên, nối bằng ' và '}." (tên từ `agents.DISPLAY_NAMES`).
- Frontend `skillChipLabel(skills: Capability[], id: string): string` (tên từ capability view; fallback `id`).

- [ ] **Bước 1: Test đỏ**
  - `test_registry_loads_six_trusted_skills`: `set(load()) == {6 id}`; `"source_entry_ids" in instructions("weekly-review")`; mọi skill mới chứa "Không chẩn đoán".
  - `test_agent_allowlists_are_subsets_of_v3`; `AGENTS["weekly-review"] == ("nhatky",)`.
  - `test_resolution_table` (parametrize `(prompt, agent, expected)`): ("Nhìn lại tuần này giúp mình","nhatky","weekly-review"), (cùng câu,"dieuphoi",None), ("Mình hay buồn khi nào, xem mẫu cảm xúc giúp","nhatky","mood-patterns"), ("Hôm nay không biết viết gì","dieuphoi","guided-journal"), ("Giúp mình nghĩ theo cách khác về chuyện này","dieuphoi","reframe-thought"), ("Nhìn lại tuần và viết nhật ký","nhatky",None) (mơ hồ), ("Không muốn nhìn lại tuần","nhatky",None).
  - `test_manual_skill_for_the_wrong_agent_is_rejected`: `promptOptions.skillId="weekly-review"` gửi tới `hoatdong` ⇒ 422 `SKILL_NOT_FOR_AGENT`, không tạo run.
  - `test_weekly_review_reads_the_last_seven_days_and_cites`: fake model gọi tool với `from_date=today-6`, `to_date=today`; `run.skill_id=="weekly-review"`, `run.workflow is None`; bubble cuối có "Bài viết đã tham khảo:".
  - `test_skill_turn_respects_journal_refusal` (Review Focus 3): skill chọn tay + "đừng đọc nhật ký của mình" ⇒ tool trả `403 JOURNAL_READ_DENIED`, lượt `completed`, không citation.
  - `test_distress_prompt_drops_even_a_manual_skill`.
  - `test_skill_with_mood_scope_is_still_rejected` (bất biến hiện có, `PROMPT_OPTIONS_MOOD_SCOPE`).
  - `test_capabilities_are_per_agent` (`GET /ai/prompt-capabilities?botId=hoatdong` ⇒ `weekly-review.available is False`, reason đúng chuỗi).
  - `promptOptions.test.ts`: `skillChipLabel(view.skills,"weekly-review") === "Nhìn lại tuần"`.
  - `agent-skills.spec.ts`: thêm ca chọn "Nhìn lại tuần" trong Nhật ký ⇒ chip hiện đúng tên, gửi ⇒ chip biến mất; trong Hoạt động skill đó bị disabled có `title` lý do.
- [ ] **Bước 2:** `uv run --locked pytest -q tests/test_agent_skills.py tests/test_prompt_options.py`; `npm.cmd test -- promptOptions` → FAIL.
- [ ] **Bước 3:** Cài đặt; export OpenAPI, `npm.cmd run contracts:generate`.
- [ ] **Bước 4:** chạy lại + `tests/test_guest_permissions.py tests/test_search_*.py tests/test_three_agents.py`; `npx.cmd playwright test tests/e2e/agent-skills.spec.ts --config playwright.owned.config.ts`.
- [ ] **Bước 5:** Commit `feat(ai): journal and planning skills with per-agent allowlists`.

**Chấp nhận:** 6 skill nạp được; không skill nào cấp tool mới; mọi bất biến cũ (`test_agent_skills.py` 4 test cũ) vẫn pass.
**Rủi ro:** tự nhận diện bằng từ khóa có thể bắt nhầm. Đã giới hạn theo agent và loại mơ hồ; chọn tay luôn có sẵn. Chất lượng câu trả lời chỉ đo được bằng eval live (06, tùy chọn).
**Rollback:** xóa thư mục skill ⇒ registry bỏ qua và log `skill_unavailable` (registry fail-closed). Hoặc `AI_AGENT_SKILLS_ENABLED=false` để tắt mọi skill.
