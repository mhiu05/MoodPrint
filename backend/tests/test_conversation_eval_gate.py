"""An intent-only regression must make the live evaluator fail closed."""
import pytest

from evals import conversation_live


@pytest.mark.parametrize(('rows', 'expected'), [
    ([], 1),
    ([{'status': 'COMPLETED', 'assertions': {'privacy': True}, 'intent_assertions': {'no_unrequested_mood_read': True}}], 0),
    ([{'status': 'COMPLETED', 'assertions': {'privacy': True}, 'intent_assertions': {'no_unrequested_mood_read': False}}], 1),
    ([{'status': 'COMPLETED', 'assertions': {'privacy': False}, 'intent_assertions': {'no_unrequested_mood_read': True}}], 1),
    ([{'status': 'FAILED', 'assertions': {'privacy': True}, 'intent_assertions': {'no_unrequested_mood_read': True}}], 1),
    ([{'status': 'COMPLETED', 'assertions': {'privacy': True}}], 1),
])
def test_live_exit_gate_catches_failed_intent_and_incomplete_evidence(rows, expected):
    gate = getattr(conversation_live, 'evaluation_exit_code', None)
    assert callable(gate), 'The live runner needs a testable, fail-closed exit gate'
    assert gate(rows) == expected
