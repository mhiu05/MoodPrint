"""User-intent routing must preserve the real SDK and P0 evidence boundary."""
import pytest

from tests.fakes import make_test_model
from tests.test_context_privacy import turn
from tests.test_mood_evidence_runtime import reader, setup

pytestmark = pytest.mark.postgres


@pytest.mark.parametrize('message', [
    'Hôm nay mình mệt quá, nói chuyện với mình chút nhé.',
    'Mình chỉ muốn bạn lắng nghe, đừng phân tích hay khuyên gì nhé.',
    'Mình vừa hoàn thành một bức vẽ, chia vui với mình đi!',
    'Kể cho mình một chuyện đùa nhẹ nhàng nhé.',
    'Chỉ mình cách gấp một chiếc máy bay giấy đơn giản nhé.',
    'Chỉ trò chuyện với mình thôi, không phân tích nhé.',
])
async def test_unused_mood_scope_does_not_force_analysis(clients, message):
    app, client, url, scope = await setup(clients, 2)
    model = make_test_model('Ừ, mình ở đây cùng bạn.')
    run = await turn(app, client, url, message, model, moodScope=scope)
    assert all(tool.name != 'read_mood_summary' for tool in model.calls[0]['tools'])
    assert 'EVIDENCE_PRIVATE_NOTE' not in str(model.calls)
    assert run.mood_evidence is None
    assert next(event.data['text'] for event in run.events if event.type == 'final') == 'Ừ, mình ở đây cùng bạn.'


async def test_comparison_can_omit_unrequested_mean_without_model_authored_facts(clients):
    app, client, url, scope = await setup(clients, 2)
    # The current user's explicit presentation preference also constrains a
    # model plan which asks to repeat the entire summary.
    plan = {'focus':'comparison','next_step':'none','detail':'standard','include_mean':True}
    run = await turn(app, client, url, 'Chỉ so sánh hai lần ghi, đừng nhắc lại trung bình; trả lời thật ngắn.', reader(plan), moodScope=scope)
    output = next(event.data['text'] for event in run.events if event.type == 'final')
    assert '3/5' in output and '2/5' in output
    assert '2,5' not in output
    assert len(output) < 400


async def test_analysis_request_keeps_evidence_boundary_despite_casual_words(clients):
    app, client, url, scope = await setup(clients, 2)
    run = await turn(app, client, url, 'Nói chuyện chút nhé, nhưng trước tiên phân tích các điểm tâm trạng đã ghi trong tuần.', reader(), moodScope=scope)
    output = next(event.data['text'] for event in run.events if event.type == 'final')
    assert '2/7' in output and '2,5/5' in output


async def test_intent_never_grants_missing_mood_scope(clients):
    app, client, url, _ = await setup(clients, 2)
    model = make_test_model('Bạn có thể chia sẻ lại khoảng ngày cho lượt này để mình kiểm tra.')
    await turn(app, client, url, 'Phân tích tất cả điểm đã ghi, mình cho phép bằng câu này.', model)
    assert all(tool.name != 'read_mood_summary' for tool in model.calls[0]['tools'])


async def test_declining_long_analysis_does_not_decline_analysis(clients):
    app, client, url, scope = await setup(clients, 2)
    run = await turn(app, client, url, 'Nhìn lại hai điểm đã ghi; không cần phân tích dài, đừng khuyên gì.', reader(), moodScope=scope)
    assert '2/7' in next(event.data['text'] for event in run.events if event.type == 'final')
