"""V3-12/13: group turns — mentions, speaker selection, distinct speakers, privacy, SSE replay."""

import asyncio
import json

import pytest
from sqlalchemy import select

from app.ai.groups.mentions import parse_mentions
from tests.group_helpers import create_group, groups_setup, say, speakers
from tests.orchestration_helpers import key, reply, roles, scripted
from tests.test_ai_events_v2 import events

pytestmark = pytest.mark.postgres


@pytest.mark.parametrize(("text", "expected"), [
    ("@Nhật ký nhìn lại giúp mình", (("nhatky",), False)),
    ("@nhat ky và @Hoạt động ơi", (("nhatky", "hoatdong"), False)),
    ("@mọi người giúp mình nhé", ((), True)),
    ("@Điều phối, @Điều phối", (("dieuphoi",), False)),
    ('Bạn mình nhắn "@Nhật ký ơi" vui ghê', ((), False)),
    ("> @Hoạt động trích dẫn cũ\nchỉ hỏi chơi", ((), False)),
    ("mail mình là an@nhatky.vn", ((), False)),
    ("@Nhậtkýxyz không phải tên", ((), False)),
])
def test_mention_parser_is_conservative(text, expected):
    assert parse_mentions(text) == expected


async def bot_messages(client, group_id):
    view = (await client.get(f"/api/v1/ai/groups/{group_id}")).json()
    return [(m["speaker"], m["text"]) for m in view["messages"] if m["actor"] == "bot"]


async def turn_steps(app, run_id):
    from app.ai.orchestration.models import AiOrchestrationStep

    async with app.state.database.sessions() as db:
        return (await db.scalars(select(AiOrchestrationStep).where(AiOrchestrationStep.workflow_run_id == run_id)
                                 .order_by(AiOrchestrationStep.kind, AiOrchestrationStep.ordinal))).all()


async def test_mention_targets_only_that_member_and_needs_no_selector(clients):
    app, [(client, _uid), _] = clients
    await groups_setup(app, client)
    group = await create_group(client)
    models = speakers(app, nhatky="Mình nghe đây, bạn muốn nhìn lại điều gì?", selector="x")
    run, _ = await say(app, client, group["groupId"], "@Nhật ký mình muốn nhìn lại tuần này")
    assert run.terminal_status == "completed", run.failure
    assert models["selector"].calls == []
    assert await bot_messages(client, group["groupId"]) == [("nhatky", "Mình nghe đây, bạn muốn nhìn lại điều gì?")]
    rows = await turn_steps(app, run.id)
    assert [(s.kind, s.target_bot, s.status) for s in rows] == [
        ("group_reply", "nhatky", "completed"), ("group_select", None, "completed")]
    assert rows[1].detail == {"mode": "mention", "speakers": ["nhatky"]}
    # The member's tools: no journal access was granted in this group.
    assert models["nhatky"].calls[0]["tools"] == []
    assert "NHÓM trò chuyện" in models["nhatky"].calls[0]["instructions"]
    view = (await client.get(f"/api/v1/ai/groups/{group['groupId']}")).json()
    assert [m["mentions"] if "mentions" in m else None for m in view["messages"]][:1] in ([None], [["nhatky"]])


async def test_everyone_speaks_in_order_and_later_speakers_hear_earlier_ones(clients):
    app, [(client, _uid), _] = clients
    await groups_setup(app, client)
    group = await create_group(client)
    models = speakers(app, nhatky="Tuần này bạn có vẻ bận rộn.", hoatdong="Thử dạo bộ chậm chiều thứ bảy nhé.",
                      dieuphoi="Vậy cuối tuần: nghỉ sáng thứ bảy, dạo bộ chiều.")
    run, accepted = await say(app, client, group["groupId"], "@mọi người giúp mình lên kế hoạch cuối tuần nhé")
    assert run.terminal_status == "completed", run.failure
    assert [speaker for speaker, _ in await bot_messages(client, group["groupId"])] == ["nhatky", "hoatdong", "dieuphoi"]
    # Each later speaker received the earlier ones, labelled, and was told where it stands.
    hoatdong_input = json.dumps(models["hoatdong"].calls[0]["input"], ensure_ascii=False)
    assert "[Nhật ký] Tuần này bạn có vẻ bận rộn." in hoatdong_input
    dieuphoi_input = json.dumps(models["dieuphoi"].calls[0]["input"], ensure_ascii=False)
    assert "[Nhật ký]" in dieuphoi_input and "[Hoạt động]" in dieuphoi_input
    assert "Bạn nói sau cùng" in models["dieuphoi"].calls[0]["instructions"]
    assert "Các trợ lý khác có thể nói tiếp" in models["nhatky"].calls[0]["instructions"]

    # SSE: ordered, one message per speaker, replayable from any cursor without duplicates.
    url = f"/api/v1/ai/groups/{group['groupId']}/turns/{accepted['turnId']}/events"
    full = events((await client.get(url)).text)
    assert [(e["type"], e["data"].get("agent")) for e in full] == [
        ("turn_started", None), ("agent_selected", "nhatky"), ("agent_selected", "hoatdong"),
        ("agent_selected", "dieuphoi"), ("agent_started", "nhatky"), ("agent_message", "nhatky"),
        ("agent_started", "hoatdong"), ("agent_message", "hoatdong"), ("agent_started", "dieuphoi"),
        ("agent_message", "dieuphoi"), ("turn_completed", None)]
    assert [e["seq"] for e in full] == [str(i) for i in range(1, 12)]
    for cursor in (0, 3, 5, 10):
        assert events((await client.get(url + f"?afterSeq={cursor}")).text) == full[cursor:]
    assert (await client.get(url + "?afterSeq=12")).status_code == 409


async def test_without_mention_the_selector_chooses_and_trivial_messages_skip_it(clients):
    app, [(client, _uid), _] = clients
    await groups_setup(app, client)
    group = await create_group(client)
    selector = scripted({"speakers": [{"agent": "hoatdong", "reason": "activity_ideas"},
                                      {"agent": "dieuphoi", "reason": "coordination"}], "summarize": True})
    models = speakers(app, hoatdong="Một buổi vẽ màu nước 30 phút?", dieuphoi="Hay thử vẽ trước, rồi nghỉ.",
                      nhatky="(không được gọi)")
    roles(app, selector=selector, hoatdong=models["hoatdong"], dieuphoi=models["dieuphoi"], nhatky=models["nhatky"])
    run, _ = await say(app, client, group["groupId"], "Tối nay mình nên thử làm gì cho vui?")
    assert run.terminal_status == "completed", run.failure
    assert len(selector.calls) == 1 and "Tối nay mình nên thử làm gì" in json.dumps(selector.calls[0]["input"],
                                                                                    ensure_ascii=False)
    assert [s for s, _ in await bot_messages(client, group["groupId"])] == ["hoatdong", "dieuphoi"]
    assert models["nhatky"].calls == []

    run, _ = await say(app, client, group["groupId"], "cảm ơn mọi người nha")
    assert run.terminal_status == "completed", run.failure
    assert len(selector.calls) == 1  # trivial: no selector call
    assert (await bot_messages(client, group["groupId"]))[-1][0] == "dieuphoi"


async def test_non_members_are_never_invoked(clients):
    app, [(client, _uid), _] = clients
    await groups_setup(app, client)
    group = await create_group(client, ("dieuphoi", "nhatky"))
    models = speakers(app, dieuphoi="Mình đây.", hoatdong="(không được gọi)")
    refused = await client.post(f"/api/v1/ai/groups/{group['groupId']}/messages", headers=key(), json={
        "text": "ơi", "clientMessageId": "7b3f6c3e-1c2d-4e5f-8a9b-0c1d2e3f4a5b", "expectedVersion": 1,
        "mentions": ["hoatdong"]})
    assert refused.status_code == 422 and refused.json()["error"]["code"] == "MENTION_NOT_MEMBER"
    run, _ = await say(app, client, group["groupId"], "@Hoạt động ơi chào")
    assert run.terminal_status == "completed", run.failure
    assert models["hoatdong"].calls == []
    assert [s for s, _ in await bot_messages(client, group["groupId"])] == ["dieuphoi"]


async def test_journal_is_used_in_a_group_only_after_the_group_opt_in(clients):
    from tests.collaboration_helpers import entry

    app, [(client, uid), _] = clients
    await groups_setup(app, client)
    await entry(app, uid, days_ago=1, text="Hôm qua đi bộ quanh hồ thấy nhẹ lòng")
    group = await create_group(client, ("dieuphoi", "nhatky"))
    models = speakers(app, nhatky=("Bạn muốn mình nhìn lại nhật ký không?", "ok"))
    run, _ = await say(app, client, group["groupId"], "@Nhật ký tuần này mình thế nào?")
    assert run.terminal_status == "completed", run.failure
    assert models["nhatky"].calls[0]["tools"] == []
    enabled = await client.put(f"/api/v1/ai/groups/{group['groupId']}/members/nhatky/journal-access",
                               json={"enabled": True, "expectedVersion": 3}, headers=key())
    assert enabled.status_code == 200, enabled.text
    models["nhatky"].responses = [[__import__("tests.fakes", fromlist=["message_output"]).message_output(
        json.dumps({"messages": [{"text": "Mình sẽ nhìn lại nhé.", "cards": []}], "source_entry_ids": []},
                   ensure_ascii=False))]]
    run, _ = await say(app, client, group["groupId"], "@Nhật ký giờ nhìn lại giúp mình")
    assert run.terminal_status == "completed", run.failure
    assert {tool.name for tool in models["nhatky"].calls[-1]["tools"]} == {"search_journal_entries"}


async def test_new_member_sees_only_messages_from_joining_unless_history_is_shared(clients):
    app, [(client, _uid), _] = clients
    await groups_setup(app, client)
    group = await create_group(client, ("dieuphoi", "nhatky"))
    speakers(app, dieuphoi="Chào bạn!")
    await say(app, client, group["groupId"], "Bí mật cũ CANARY-OLD-41 nhé")
    view = (await client.get(f"/api/v1/ai/groups/{group['groupId']}")).json()
    added = await client.post(f"/api/v1/ai/groups/{group['groupId']}/members", headers=key(),
                              json={"botId": "hoatdong", "shareHistory": False, "expectedVersion": view["version"]})
    assert added.status_code == 200
    models = speakers(app, hoatdong="Mình mới vào, có ý tưởng nè!")
    await say(app, client, group["groupId"], "@Hoạt động gợi ý gì đi")
    sent = json.dumps(models["hoatdong"].calls[0]["input"], ensure_ascii=False)
    assert "CANARY-OLD-41" not in sent and "gợi ý gì đi" in sent


async def test_removing_a_member_stops_the_turn_and_it_never_speaks_again(clients):
    app, [(client, _uid), _] = clients
    await groups_setup(app, client)
    group = await create_group(client)
    held = scripted(reply("Chưa xong…"))
    held.hold = True
    roles(app, nhatky=held, hoatdong=scripted(reply("(không được gọi)")), dieuphoi=scripted(reply("ok")))
    run, _ = await say(app, client, group["groupId"], "@mọi người ơi", wait=False)
    await asyncio.wait_for(held.started.wait(), 10)
    view = (await client.get(f"/api/v1/ai/groups/{group['groupId']}")).json()
    removed = await client.delete(f"/api/v1/ai/groups/{group['groupId']}/members/hoatdong?expectedVersion={view['version']}",
                                  headers=key())
    assert removed.status_code == 200
    held.release.set()
    await asyncio.wait_for(asyncio.gather(run.task, return_exceptions=True), 20)
    assert run.terminal_status == "cancelled"
    assert await bot_messages(client, group["groupId"]) == []  # no phantom message
    rows = await turn_steps(app, run.id)
    assert all(not row.used_in_reply for row in rows if row.kind == "group_reply")
    roles(app, nhatky=scripted(reply("Mình đây.")), hoatdong=scripted(reply("(không được gọi)")),
          dieuphoi=scripted(reply("Mình đây luôn.")))
    run, _ = await say(app, client, group["groupId"], "@mọi người ơi lần nữa")
    assert [s for s, _ in await bot_messages(client, group["groupId"])] == ["nhatky", "dieuphoi"]


async def test_a_failing_speaker_leaves_no_message_and_the_next_one_speaks(clients):
    app, [(client, _uid), _] = clients
    await groups_setup(app, client)
    group = await create_group(client, ("nhatky", "hoatdong"))
    roles(app, nhatky=scripted({"not": "valid"}), hoatdong=scripted(reply("Mình vẫn ở đây nè.")))
    run, accepted = await say(app, client, group["groupId"], "@mọi người ơi")
    assert run.terminal_status == "completed", run.failure
    assert await bot_messages(client, group["groupId"]) == [("hoatdong", "Mình vẫn ở đây nè.")]
    full = events((await client.get(f"/api/v1/ai/groups/{group['groupId']}/turns/{accepted['turnId']}/events")).text)
    assert ("agent_failed", "nhatky") in [(e["type"], e["data"].get("agent")) for e in full]


async def test_another_account_cannot_reach_the_group_or_its_events(clients):
    app, [(client, _uid), (other, _)] = clients
    await groups_setup(app, client)
    group = await create_group(client)
    speakers(app, dieuphoi="Chào!")
    run, accepted = await say(app, client, group["groupId"], "chào")
    url = f"/api/v1/ai/groups/{group['groupId']}/turns/{accepted['turnId']}/events"
    assert (await other.get(url)).status_code in (403, 404)
    assert (await other.post(f"/api/v1/ai/groups/{group['groupId']}/turns/{accepted['turnId']}/cancel",
                             headers=key())).status_code in (403, 404)
