# 09 — Kế hoạch triển khai và đồ thị phụ thuộc

Mỗi task: đọc đặc tả → test đỏ → code → test xanh → hồi quy rộng → cập nhật tài liệu → commit nhỏ. Kết quả thật ghi ở [12](12-execution-evidence.md).

## Đồ thị phụ thuộc

```
V3-00 baseline + audit ──► V3-01 migration 0024 ──► V3-02 registry/prompts/capabilities ──► V3-03 API 3 trợ lý + legacy chỉ đọc
                                   │                         │                                     │
                                   │                         └──► V3-04 proactive 3 trợ lý + chuyển lịch cũ (explicit)
                                   │                                                               │
                                   │                         V3-05 frontend 3 trợ lý + legacy ◄────┘
                                   │                                   │
                                   │                         ═══ Gate A ═══
                                   │                                   │
                                   ├──► V3-06 quyền chia sẻ 4 cạnh V3 ─┤
                                   │                                   ▼
                                   │                 V3-07 triage + planner + policy (thuần)
                                   │                                   ▼
                                   │                 V3-08 as_tool consult (wrapper, hooks, receipts)
                                   │                                   ▼
                                   │                 V3-09 handoff (filter, child run, active_agent)
                                   │                                   ▼
                                   │                 V3-10 SSE v2 steps/speaker + UI điều phối
                                   │                                   │
                                   │                         ═══ Gate B ═══
                                   │                                   │
                                   └──► V3-11 API nhóm + thành viên ───┤
                                                                       ▼
                                                     V3-12 lượt nhóm: mention, selector, người nói tuần tự
                                                                       ▼
                                                     V3-13 SSE nhóm + replay
                                                                       ▼
                                                     V3-14 UI nhóm (danh sách, tạo, chat, picker @, panel)
                                                                       │
                                                             ═══ Gate C ═══
                                                                       ▼
                         V3-15 eval offline + live (≤ 3 USD, gpt-6-luna, Claude tự chấm) ; V3-16 hiệu năng
                                                                       ▼
                         V3-17 hồi quy toàn bộ + agent-browser 1440/768/390/360 ; V3-18 review đối kháng độc lập
                                                                       ▼
                                                             ═══ G3 ═══ (dừng)
```

## Task

| ID | Nội dung | Module chính | Test chính |
| --- | --- | --- | --- |
| V3-01 | Migration 0024 + ORM + `READY_REVISIONS` + lifecycle/guest inventory | `alembic/versions/0024_*`, `app/ai/models.py`, `app/ai/orchestration/models.py` | `test_v3_migration.py` (nâng cấp từ dữ liệu Phase 2, CHECK, RLS, xóa tài khoản, guest purge) |
| V3-02 | `app/ai/agents.py` (registry 3 + 5 legacy, capability), prompt 3 trợ lý | `registry.py`, `prompts.py`, `conversation.py`, `provider.py`, `runtime.py` | `test_three_agents.py` |
| V3-03 | `/bots`, `/bots/legacy`, tạo hội thoại, gửi tin vào hội thoại cũ (409), header `legacy` | `chat_routes.py`, `contracts.py`, `schemas.py` | `test_three_agents.py` |
| V3-04 | Proactive cho 3 trợ lý; lịch cũ bị bỏ qua (`legacy_companion`) khi cờ A bật; `POST /ai/proactive/schedules/{bot}/{slot}/migrate` | `proactive/*` | `test_v3_proactive.py` |
| V3-05 | Frontend: registry/avatars, roster 3 trợ lý, lịch sử cũ có nhãn + chỉ đọc, trang hỏi thăm | `companions/*`, `RealApp.tsx`, `checkins/*` | vitest + Playwright fixture |
| V3-06 | 4 cạnh mới trong `/ai/sharing` khi cờ A bật | `collaboration/routes.py` | `test_v3_sharing.py` |
| V3-07 | `orchestration/{triage,plan,policy}.py` | | `test_orchestration_policy.py` |
| V3-08 | `orchestration/{workflow,specialists,hooks}.py` + as_tool thật | `provider.py`, `runtime.py` | `test_orchestration_sdk.py` (SDK thật + fake model, không mock as_tool) |
| V3-09 | handoff thật + `active_agent` | | `test_orchestration_handoff.py` |
| V3-10 | SSE v2 `steps`/`speaker`, UI | `chat_routes.py`, `stream.ts`, `RealApp.tsx` | `test_orchestration_sse.py`, vitest |
| V3-11 | `app/ai/groups/{routes,service,models}.py` | | `test_groups_api.py` |
| V3-12 | `groups/{mentions,selector,turn}.py` | | `test_groups_turn.py` |
| V3-13 | `groups/events.py` | | `test_groups_sse.py` |
| V3-14 | `features/real/groups/*` | | vitest + fixture E2E + fullstack |

## Cổng

- **Gate A**: chỉ 3 trợ lý mặc định khi cờ A bật; hội thoại cũ đọc được, gửi bị chặn có nhãn; lịch cũ giữ nguyên và chỉ chuyển khi người dùng chọn; migration nâng cấp từ dữ liệu Phase 2 sạch; backend + frontend xanh.
- **Gate B**: test tích hợp chạy SDK thật (Runner, as_tool, handoff, input_filter) với model giả ở tầng `Model` — không mock `as_tool`/`handoff`; receipts phản ánh đúng lời gọi; giới hạn và hủy được kiểm.
- **Gate C**: nhóm CRUD, mention, chọn người nói, nhiều người nói, SSE replay, UI responsive; fullstack + agent-browser.
