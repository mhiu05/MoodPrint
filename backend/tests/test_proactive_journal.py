"""Nhịp's yesterday-journal check-in: consent, privacy, provenance, safety (P1-13/P1-14)."""

import asyncio
import json
import logging
from datetime import date, timedelta

from sqlalchemy import select, update

from app.jobs import proactive as worker
from tests.fakes import ScriptedModel, message_output
from tests.test_proactive_executor import due_schedule, only_job, proactive_messages, ready

CANARY = "CANARY-JOURNAL-7f3a"


def local_today() -> date:
    from app.ai.proactive.schedule import local_date
    from app.infrastructure.database.models import now

    return local_date(now(), "Asia/Ho_Chi_Minh")


async def entry(app, uid, *, days_ago=1, status="saved", text="", mood=3, emotions=(), factors=()):
    from app.modules.journal.models import JournalEntry

    async with app.state.database.sessions.begin() as db:
        row = JournalEntry(user_id=uid, local_date=local_today() - timedelta(days=days_ago),
                           timezone="Asia/Ho_Chi_Minh", mood=mood, text=text, status=status,
                           emotions=list(emotions), factors=list(factors))
        db.add(row)
    return row.id


def scripted(texts, source_ids=()):
    payload = {"messages": [{"text": t, "cards": []} for t in texts],
               "source_entry_ids": [str(i) for i in source_ids]}
    return ScriptedModel([[message_output(json.dumps(payload, ensure_ascii=False))]])


def sent(model) -> str:
    return json.dumps(model.calls[-1]["input"], ensure_ascii=False)


def data(model) -> dict:
    return json.loads(model.calls[-1]["input"][0]["content"].split(": ", 1)[1])


async def test_payload_has_only_saved_yesterday_entries_of_the_owner(clients):
    app, [(_client, uid), (_other, other_uid)] = clients
    ok = await entry(app, uid, text=f"Ôn thi tới khuya {CANARY}-ok", mood=2, emotions=["mệt"],
                     factors=["học tập"])
    await entry(app, uid, status="draft", text=f"{CANARY}-draft")
    await entry(app, uid, days_ago=2, text=f"{CANARY}-old")
    await entry(app, uid, days_ago=0, text=f"{CANARY}-today")
    await entry(app, other_uid, text=f"{CANARY}-other")
    model = scripted(["Hôm qua bạn có ghi là thấy khá mệt.", "Thử nghỉ mắt 10 phút nhé."], [ok])
    ready(app, model)
    await due_schedule(app, uid, bot="nhip", journal=True)
    await worker.proactive_tick(app.state.ai)
    text = sent(model)
    assert f"{CANARY}-ok" in text
    for tag in ("draft", "old", "today", "other"):
        assert f"{CANARY}-{tag}" not in text
    journal = data(model)["journal"]
    assert journal["status"] == "entries" and journal["entriesIncluded"] == 1
    assert journal["entries"][0]["emotions"] == ["mệt"]


async def test_delivery_cites_the_entry_and_records_provenance(clients):
    from app.ai.models import AiTurn
    from app.ai.proactive.models import AiMessageSource

    app, [(_client, uid), _] = clients
    ok = await entry(app, uid, text="Đi dạo với bạn, vui", emotions=["vui"])
    ready(app, scripted(["Hôm qua bạn ghi là đi dạo với bạn và thấy vui.",
                         "Sáng nay thử nhắn cho người bạn đó một câu chào nhé."], [ok]))
    await due_schedule(app, uid, bot="nhip", journal=True)
    await worker.proactive_tick(app.state.ai)
    job = await only_job(app, uid)
    assert job.status == "delivered"
    rows = await proactive_messages(app, uid)
    last = rows[-1][0].text
    assert f"(/self/entry/{ok})" in last and "Bài viết đã tham khảo:" in last
    assert f"/self/entry/{ok}" not in rows[0][0].text
    async with app.state.database.sessions() as db:
        [source] = (await db.scalars(select(AiMessageSource))).all()
        turn = await db.get(AiTurn, job.run_id)
    assert (source.source_id, source.source_revision, source.policy) == (ok, 1, "proactive-journal-v1@0")
    assert turn.context_policy == "proactive-journal-v1"


async def test_consent_off_sends_no_journal_even_with_entries(clients):
    app, [(_client, uid), _] = clients
    await entry(app, uid, text=f"{CANARY}-private")
    model = scripted(["Chào buổi sáng! Bắt đầu ngày mới bằng một cốc nước nhé."])
    ready(app, model)
    await due_schedule(app, uid, bot="nhip", journal=False)
    await worker.proactive_tick(app.state.ai)
    assert CANARY not in sent(model)
    assert data(model)["journal"] == {"status": "not_enabled"}
    assert (await only_job(app, uid)).status == "delivered"


async def test_no_entries_forbids_mentioning_yesterday(clients):
    app, [(_client, uid), _] = clients
    model = scripted(["Hôm qua bạn đã cố gắng nhiều rồi, sáng nay nghỉ chút nhé."])
    ready(app, model)
    await due_schedule(app, uid, bot="nhip", journal=True)
    await worker.proactive_tick(app.state.ai)
    assert data(model)["journal"] == {"status": "no_entries"}
    job = await only_job(app, uid)
    assert (job.status, job.last_error) == ("retry", "invented_journal")
    assert await proactive_messages(app, uid) == []


async def test_citing_an_unprovided_entry_is_rejected(clients):
    from uuid import uuid4

    app, [(_client, uid), _] = clients
    await entry(app, uid, text="một ngày bình thường")
    ready(app, scripted(["Hôm qua bạn có ghi lại một ngày bình thường."], [uuid4()]))
    await due_schedule(app, uid, bot="nhip", journal=True)
    await worker.proactive_tick(app.state.ai)
    job = await only_job(app, uid)
    assert (job.status, job.last_error) == ("retry", "unsupported_source")


async def test_entry_edited_during_generation_is_regenerated_not_published(clients):
    from app.modules.journal.models import JournalEntry

    app, [(_client, uid), _] = clients
    ok = await entry(app, uid, text="bản cũ")
    model = scripted(["Hôm qua bạn có ghi lại một điều nhỏ."], [ok])
    model.hold = True
    ready(app, model)
    await due_schedule(app, uid, bot="nhip", journal=True)
    task = asyncio.create_task(worker.proactive_tick(app.state.ai))
    await asyncio.wait_for(model.started.wait(), 10)
    async with app.state.database.sessions.begin() as db:
        await db.execute(update(JournalEntry).where(JournalEntry.id == ok)
                         .values(text="bản mới", version=2))
    model.release.set()
    await task
    job = await only_job(app, uid)
    assert (job.status, job.last_error) == ("retry", "source_changed")
    assert await proactive_messages(app, uid) == []


async def test_consent_revoked_during_generation_cancels(clients):
    from app.ai.proactive.models import AiProactiveSettings

    app, [(_client, uid), _] = clients
    ok = await entry(app, uid, text="một ngày bình thường")
    model = scripted(["Hôm qua bạn có ghi lại một ngày bình thường."], [ok])
    model.hold = True
    ready(app, model)
    await due_schedule(app, uid, bot="nhip", journal=True)
    task = asyncio.create_task(worker.proactive_tick(app.state.ai))
    await asyncio.wait_for(model.started.wait(), 10)
    async with app.state.database.sessions.begin() as db:
        # What PUT /ai/proactive/settings does when journal use is switched off.
        await db.execute(update(AiProactiveSettings).values(
            journal_context_enabled=False, journal_context_version=1, version=AiProactiveSettings.version + 1))
    model.release.set()
    await task
    job = await only_job(app, uid)
    assert job.status == "cancelled"
    assert await proactive_messages(app, uid) == []


async def test_distress_entry_sends_the_safety_template_without_the_model(clients):
    from app.ai.models import AiTurn
    from app.ai.proactive.models import AiMessageSource
    from app.ai.proactive.safety import SAFETY_TEMPLATE

    app, [(_client, uid), _] = clients
    await entry(app, uid, text=f"Mình không muốn sống nữa {CANARY}")
    model = scripted(["không được gọi"])
    ready(app, model)
    await due_schedule(app, uid, bot="nhip", journal=True)
    await worker.proactive_tick(app.state.ai)
    assert model.calls == []
    job = await only_job(app, uid)
    [(message, _run)] = await proactive_messages(app, uid)
    assert job.status == "delivered" and message.text == SAFETY_TEMPLATE
    async with app.state.database.sessions() as db:
        assert (await db.scalars(select(AiMessageSource))).all() == []
        assert (await db.get(AiTurn, job.run_id)).context_policy == "proactive-text-v1"


async def test_more_than_three_entries_are_counted_but_capped(clients):
    app, [(_client, uid), _] = clients
    ids = [await entry(app, uid, text=f"khoảnh khắc {i}") for i in range(5)]
    model = scripted(["Hôm qua bạn ghi lại vài khoảnh khắc.", "Sáng nay thử uống một cốc nước ấm nhé."],
                     [ids[-1]])
    ready(app, model)
    await due_schedule(app, uid, bot="nhip", journal=True)
    await worker.proactive_tick(app.state.ai)
    journal = data(model)["journal"]
    assert (journal["entriesTotal"], journal["entriesIncluded"]) == (5, 3)


async def test_evening_nhip_never_reads_the_journal(clients):
    app, [(_client, uid), _] = clients
    await entry(app, uid, days_ago=0, text=f"{CANARY}-tonight")
    await entry(app, uid, text=f"{CANARY}-yesterday")
    model = scripted(["Một ngày nữa sắp khép lại rồi. Nếu muốn, ghi lại một khoảnh khắc nhỏ nhé."])
    ready(app, model)
    await due_schedule(app, uid, bot="nhip", slot="evening", journal=True)
    await worker.proactive_tick(app.state.ai)
    assert CANARY not in sent(model)
    assert data(model)["journal"] is None


async def test_journal_text_never_reaches_logs(clients, caplog):
    app, [(_client, uid), _] = clients
    ok = await entry(app, uid, text=f"riêng tư {CANARY}")
    ready(app, scripted([f"Hôm qua bạn có ghi lại một điều riêng tư {CANARY}."], [ok]))
    await due_schedule(app, uid, bot="nhip", journal=True)
    with caplog.at_level(logging.DEBUG):
        await worker.proactive_tick(app.state.ai)
    assert (await only_job(app, uid)).status == "delivered"
    assert CANARY not in caplog.text
    assert str(uid) not in caplog.text


def test_distress_screen_positive_and_negative_cases():
    from app.ai.proactive.safety import distress_screen

    for text in ("Mình muốn chết", "khong muon song nua", "Có lúc nghĩ tới tự tử", "I want to kill myself",
                 "thoughts of self-harm", "tự làm hại bản thân"):
        assert distress_screen([text]), text
    for text in ("Từ từ rồi sẽ ổn", "tu tu lam", "Hôm nay mệt chết đi được vì chạy deadline",
                 "Tự làm hài lòng bản thân", "Đọc truyện kết thúc buồn", ""):
        assert not distress_screen([text]), text


async def test_attributing_yesterdays_entry_to_today_is_rejected(clients):
    app, [(_client, uid), _] = clients
    ok = await entry(app, uid, text="trưa ăn bún chả ngon")
    ready(app, scripted(["Sáng nay, bạn đã ghi trưa ăn bún chả ngon.", "Thử ngồi đón nắng 5 phút nhé."], [ok]))
    await due_schedule(app, uid, bot="nhip", journal=True)
    await worker.proactive_tick(app.state.ai)
    job = await only_job(app, uid)
    assert (job.status, job.last_error) == ("retry", "wrong_day")


async def test_check_ins_request_low_reasoning_effort(clients):
    app, [(_client, uid), _] = clients
    model = scripted(["Chào buổi sáng! Uống một cốc nước ấm nhé."])
    ready(app, model)
    await due_schedule(app, uid, bot="nhip")
    await worker.proactive_tick(app.state.ai)
    assert model.calls[0]["settings"].reasoning.effort == "low"
