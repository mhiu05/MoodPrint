# Phase 1 — 09. Kiểm thử và tiêu chí chấp nhận

> Chưa có test nào trong tài liệu này được chạy — tính năng chưa tồn tại. Đặc tả E2E trình duyệt đầy đủ (từng ca: tiền đề, dữ liệu, thao tác, khẳng định, chẩn đoán) nằm ở [92 §4](../92-visual-qa-and-agent-browser.md); tài liệu này định nghĩa các tầng còn lại và ánh xạ yêu cầu → test.

## 1. Tầng kiểm thử

| Tầng | Công cụ | Dữ liệu | Chạy ở |
| --- | --- | --- | --- |
| Unit backend | pytest (không DB) | Tổng hợp | Local + CI "Backend checks" |
| Integration backend | pytest + PostgreSQL disposable (`*_test`) | Tổng hợp, `ScriptedModel` ([fakes.py](../../../../backend/tests/fakes.py)) | CI |
| Migration | pytest + Alembic trên DB trống và DB có dữ liệu mẫu ở 0020 | Tổng hợp | CI "Migration chain" |
| Contract | OpenAPI export + `npm run contracts:generate` drift; test SSE v1/v2 | — | CI "Frontend and contract drift" |
| Unit frontend | Vitest | Fixture | CI |
| E2E fixture | Playwright + `page.route` (mẫu [ux-fixtures.ts](../../../../frontend/tests/e2e/ux-fixtures.ts)) | Fixture | CI |
| Fullstack | Playwright + backend thật + fake SDK model ([e2e_server.py](../../../../backend/tests/e2e_server.py)) | Tài khoản tổng hợp | CI "Full stack" |
| Load | Script tải (mẫu `scripts/load_chat_memory.py`) | Tổng hợp | Thủ công trước G1 |
| Eval | `backend/evals/` (offline + live có gate) | Tổng hợp | Thủ công, có ngân sách |

## 2. Ví dụ test (phác thảo, không phải code đã viết)

### 2.1 Unit — hợp đồng nhiều bubble

```python
@pytest.mark.parametrize("count,ok", [(0, False), (1, True), (4, True), (5, False)])
def test_companion_reply_bounds(count, ok):
    payload = {"messages": [{"text": f"Ý {i}", "cards": []} for i in range(count)]}
    if ok:
        assert len(CompanionReply.model_validate(payload).messages) == count
    else:
        with pytest.raises(ValidationError):
            CompanionReply.model_validate(payload)

def test_cards_total_capped_across_bubbles():
    bubbles = [{"text": "a", "cards": [{"kind": "mood_form"}] * 2}, {"text": "b", "cards": [{"kind": "discovery"}] * 2}]
    with pytest.raises(ValidationError):
        CompanionReply.model_validate({"messages": bubbles})
```

### 2.2 Integration — persist atomically

```python
async def test_three_bubbles_share_run_and_consecutive_sequences(client, db, fake_model):
    fake_model.reply({"messages": [{"text": "Một"}, {"text": "Hai"}, {"text": "Ba"}]})
    run = await send(client, conversation, "Xin chào")
    await wait_terminal(client, run)
    rows = await bot_rows(db, run.run_id)
    assert [r.part_index for r in rows] == [0, 1, 2]
    assert [r.sequence for r in rows] == [3, 4, 5]
    assert (await conversation_version(db)) == 5          # version == max(sequence)

async def test_cancel_before_commit_leaves_no_bubbles(client, db, held_model):
    run = await send(client, conversation, "Xin chào")
    await held_model.started.wait()
    await cancel(client, run)
    held_model.release.set()
    assert await bot_rows(db, run.run_id) == []
```

### 2.3 Integration — worker không giao trùng

```python
async def test_two_workers_deliver_exactly_once(app_a, app_b, db, schedule_due_now, fake_model):
    await asyncio.gather(proactive_tick(app_a), proactive_tick(app_b))
    await asyncio.gather(proactive_tick(app_a), proactive_tick(app_b))
    jobs = await jobs_for(db, schedule_due_now)
    assert [j.status for j in jobs] == ["delivered"]
    assert await count_bot_runs(db, origin="proactive") == 1

async def test_crash_after_model_before_commit_redelivers_once(app, db, fake_model, monkeypatch):
    monkeypatch.setattr(executor, "publish_job", raise_once(ConnectionError))
    await proactive_tick(app)                 # model gọi, publish lỗi → lease giữ
    await advance(seconds=91)
    await proactive_tick(app)                 # reclaim, model gọi lại, publish ok
    assert await count_visible_proactive(db) == 1
    assert len(fake_model.calls) == 2
```

### 2.4 Integration — privacy nhật ký

```python
CANARY = "CANARY-JOURNAL-7f3a"

async def test_nhip_payload_only_saved_yesterday_owner_entries(db, fake_model, users):
    await journal(db, users.a, local_date=YESTERDAY, status="saved", text=f"ổn {CANARY}-ok")
    await journal(db, users.a, local_date=YESTERDAY, status="draft", text=f"{CANARY}-draft")
    await journal(db, users.a, local_date=TWO_DAYS_AGO, status="saved", text=f"{CANARY}-old")
    await journal(db, users.b, local_date=YESTERDAY, status="saved", text=f"{CANARY}-other")
    await run_job(users.a, bot="nhip", slot="morning", journal_context=True)
    sent = json.dumps(fake_model.calls[-1]["input"], ensure_ascii=False)
    assert f"{CANARY}-ok" in sent
    assert all(tag not in sent for tag in (f"{CANARY}-draft", f"{CANARY}-old", f"{CANARY}-other"))

async def test_canary_never_reaches_logs(caplog, ...):
    ...
    assert CANARY not in caplog.text
```

### 2.5 Unit frontend — parser v2

```ts
it("rejects a v2 final with an unknown field", async () => {
  const body = sse([{ v: 2, seq: 1, type: "progress", data: {} },
                    { v: 2, seq: 2, type: "final", data: { partCount: 1, messages: [{ messageId: "m", partIndex: 0, text: "Hi", cards: [], extra: 1 }] } }]);
  await expect(consumeAIEvents(url, signal, { protocol: 2, fetch: body })).rejects.toMatchObject({ code: "INVALID_AI_EVENT" });
});
```

### 2.6 E2E fixture — nhiều bubble (Playwright)

```ts
test("ba bubble hiện cùng lúc sau completed và đọc một lần", async ({ page }) => {
  await app(page, baseSession, { "/ai/runs/run-1/events": () => ({ body: sseV2(threeBubbles), contentType: "text/event-stream" }) });
  await page.goto("/#/assistants/nhip?new=1");
  await page.getByRole("textbox", { name: "Tin nhắn cho Nhịp" }).fill("Chào");
  await page.keyboard.press("Enter");
  const group = page.getByRole("group", { name: "Tin nhắn từ Nhịp, 3 phần" });
  await expect(group.locator(".message-content")).toHaveCount(3);
});
```

## 3. Ánh xạ yêu cầu → test

| Yêu cầu | Test chính | Tầng |
| --- | --- | --- |
| P1-FR-01/02 | `test_companion_reply_bounds`, eval tách bubble | Unit, eval |
| P1-FR-03 | `test_cancel_before_commit_leaves_no_bubbles`; E2E "không bubble trước completed" | Integration, E2E |
| P1-FR-04 | Property test version/sequence; E2E reload | Integration, E2E |
| P1-FR-05 | `test_ai_events_v1_joined_reply` | Contract |
| P1-FR-06 | E2E a11y nhóm bubble, copy | E2E |
| P1-FR-10 | `test_proactive_run_has_no_self_message` | Integration |
| P1-FR-11 | `test_nhip_payload_only_saved_yesterday_owner_entries` | Integration |
| P1-FR-12/13 | Validator + eval rubric | Unit, eval |
| P1-FR-14 | `test_rure_avoids_recent_kinds` | Integration |
| P1-FR-16 | `test_caunoi_requires_adult_match` | Integration |
| P1-FR-17 | `test_proactive_input_has_no_transcript` | Integration |
| P1-FR-18 | `test_distress_template_skips_model` | Integration |
| P1-FR-20…29 | `test_proactive_api.py`, `test_proactive_schedule.py`, `test_proactive_worker.py` | Unit, integration |
| P1-FR-30…36 | `test_ai_inbox.py`; E2E unread/reload/cross-tab | Integration, E2E |
| P1-NFR-01/02 | Worker test lag + missed window | Integration |
| P1-NFR-03/04 | `scripts/load_proactive.py` | Load |
| P1-NFR-05 | `test_budget_share_skips_proactive` | Integration |
| P1-NFR-06 | Canary log test | Integration |
| P1-NFR-07/08 | Copy review checklist; axe | E2E |

## 4. Ma trận quyền (bắt buộc)

| Tài khoản | Kỳ vọng lịch API | Kỳ vọng worker |
| --- | --- | --- |
| Guest | 403 `REGISTERED_REQUIRED` | Không có lịch; row giả mạo → `skipped(ineligible_account)` |
| `age_band` unknown/under16 | 403 `ELIGIBILITY_REQUIRED` (qua `transaction`) | `skipped(ineligible_account)` |
| Teen | Cho phép trừ Cầu Nối; tối ≤ 21:00 | Cầu Nối `skipped(ineligible_social)` |
| Adult không MATCH | Cầu Nối 403 `PROACTIVE_INELIGIBLE` | `skipped(ineligible_social)` |
| Adult bị social restriction | Như trên | Như trên |
| `deletion_pending` | 409 `DELETION_IN_PROGRESS` | `cancelled` |
| Suspended | 403 | `skipped(ineligible_account)` |
| `last_seen_at` > 14 ngày | Cho phép lưu | `skipped(inactive_user)` |
| AI tắt toàn hệ thống | `available=false` | `skipped(ai_unavailable)` |
| History capability tắt | `PROACTIVE_INELIGIBLE` | `skipped(no_history_capability)` |

## 5. Tải

- Kịch bản: 200 lịch đến hạn cùng một phút + 20 người dùng chat đồng thời (fake model trễ 1,5 s).
- Đo: p95 thời gian tới `final` của chat (so với baseline cùng script không bật worker), `proactive_lag_seconds`, pool checked-out tối đa, số kết nối PostgreSQL.
- Đạt: p95 chat tăng ≤ 10 %; pool không vượt 7; mọi job đến hạn được xử lý hoặc skip có lý do trong 15 phút.

## 6. Tiêu chí chấp nhận Phase 1 (Gate G1)

1. Mọi test P0 trong §3 và §4 xanh trên CI, có link run.
2. Đặc tả E2E [92 §4](../92-visual-qa-and-agent-browser.md) các ca P0 được hiện thực và xanh ở viewport 390, 768, 1440.
3. Load test §5 đạt, có số liệu thật.
4. Eval persona: 0 trường hợp bịa đọc nhật ký/sự kiện, ≥ 95 % đạt rubric bắt buộc; nếu chưa chạy live, ghi rõ và owner chấp nhận trước khi bật cho người dùng thật.
5. Rehearsal migration trên bản sao schema hosted PASS; hosted áp dụng chỉ sau duyệt.
6. `check_docs.py` PASS; tài liệu runtime/context/lifecycle cập nhật.
7. Staging: chạy ít nhất 7 ngày với ≤ 5 tài khoản thử nghiệm đã đồng ý, không có giao trùng, không rò rỉ, không giao ngoài giờ.

## 7. Bằng chứng cần lưu

Sổ `evidence/execution.md` ghi: lệnh, commit, số pass/fail, thời lượng; ảnh chụp E2E (theo quy ước dự án: không commit ảnh chat thật; chỉ dữ liệu tổng hợp); báo cáo load; báo cáo eval với chi phí ước tính thực tế từ `ai_usage`.
