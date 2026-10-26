"""Deterministic assertions and actual SDK-input captures; no live provider calls."""

import json
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.ai.context import SourceState
from app.ai.evidence import (
    EvidenceEnvelope,
    MoodAnalysisPlan,
    MoodObservation,
    render_mood_analysis,
    source_instructions,
)
from app.ai.provider import SdkProvider
from app.ai.schemas import MoodReadScope
from app.core.config import Settings
from app.core.errors import DomainError
from tests.fakes import ScriptedModel, make_test_model, message_output

PLAN = {"focus": "overview", "next_step": "none"}


def bound_evidence(count=2):
    run = SimpleNamespace(
        id=uuid4(), actor=SimpleNamespace(user_id=uuid4()), data_version=7,
        mood_scope=MoodReadScope(from_date=date(2026, 10, 20), to_date=date(2026, 10, 26)),
        cancel_requested=False, terminal=False, sources={"mood": SourceState(authorization="authorized")},
    )
    run.mood_evidence = EvidenceEnvelope(
        id=uuid4(), owner_id=run.actor.user_id, run_id=run.id, data_version=7,
        from_date=run.mood_scope.from_date, to_date=run.mood_scope.to_date,
        retrieved_at=datetime.now(UTC), expires_at=datetime.now(UTC) + timedelta(minutes=1),
        observations=tuple(MoodObservation(date(2026, 10, d), v, 1) for d, v in ((20, 3), (26, 2), (23, 4))[:count]),
    )
    run.mood_evidence = replace(run.mood_evidence, observations=tuple(sorted(run.mood_evidence.observations, key=lambda r: r.local_date)))
    return run


@pytest.mark.parametrize("count", [0, 1, 2, 3])
def test_capabilities_do_not_use_arbitrary_inference_threshold(count):
    run = bound_evidence(count)
    view = run.mood_evidence.model_view()
    assert view["capabilities"] == {"description": count > 0, "observation": count >= 2, "inference": False, "inferenceMethod": None}
    assert view["statistics"]["missingDays"] == 7 - count
    assert str(run.actor.user_id) not in json.dumps(view) and str(run.id) not in json.dumps(view)
    reply = render_mood_analysis(MoodAnalysisPlan(**PLAN), run)
    assert f"{count}/7" in reply.text
    if count == 0:
        assert "Chưa có bản ghi" in reply.text and "trung bình" not in reply.text
    elif count == 1:
        assert "chưa có lần ghi khác" in reply.text
    else:
        assert "chưa phải xu hướng" in reply.text
    if count == 2:
        assert "2,5/5" in reply.text and "thấp hơn 1 điểm" in reply.text


@pytest.mark.parametrize("change", ["owner", "run", "version", "range", "expired", "cancelled", "terminal", "no_scope"])
def test_binding_expiry_and_invalidation_fail_closed(change):
    run = bound_evidence()
    if change == "owner":
        run.actor.user_id = uuid4()
    elif change == "run":
        run.id = uuid4()
    elif change == "version":
        run.data_version += 1
    elif change == "range":
        run.mood_scope = MoodReadScope(from_date=date(2026, 10, 25), to_date=date(2026, 10, 26))
    elif change == "expired":
        run.mood_evidence = replace(run.mood_evidence, expires_at=datetime.now(UTC) - timedelta(seconds=1))
    elif change == "cancelled":
        run.cancel_requested = True
    elif change == "terminal":
        run.terminal = True
    else:
        run.mood_scope = None
    with pytest.raises(DomainError, match="EVIDENCE_INVALIDATED"):
        render_mood_analysis(MoodAnalysisPlan(**PLAN), run)


@pytest.mark.parametrize("forgery", [
    {"mean": 4.9}, {"recorded_days": 7}, {"from": "2026-01-01"},
    {"trend": "improving"}, {"text": "Bạn ghi đủ bảy ngày, trung bình 5 điểm."},
])
def test_statistical_claims_are_not_model_writable(forgery):
    with pytest.raises(ValidationError):
        MoodAnalysisPlan.model_validate({**PLAN, **forgery})


async def no_progress():
    pass


@pytest.mark.parametrize("bot_id", ["may", "guong", "rure", "caunoi"])
def test_mood_specific_instructions_do_not_prime_other_personas(bot_id):
    run = bound_evidence()
    run.sources["memory"] = SourceState(authorization="revoked")
    policy = source_instructions(run, bot_id)
    assert "read_mood_summary" not in policy
    assert "khoảng ngày" not in policy
    assert '"authorization": "revoked"' in policy


def test_static_historical_evaluations_retain_frozen_prompt_inputs():
    assert source_instructions(None, "nhip") == ""


async def test_sdk_uses_private_plan_then_returns_compatible_public_output():
    run = bound_evidence()
    model = ScriptedModel([[message_output(json.dumps(PLAN))]])
    provider = SdkProvider(Settings(_env_file=None))
    output = await provider.run(bot_id="nhip", history=[{"role": "user", "content": "Bạn cứ nhận xét đi, không khuyên nhé"}], tools=[], context=run, on_progress=no_progress, model_override=model)
    assert set(output.model_dump()) == {"text", "cards"}
    assert "2,5/5" in output.text and "Bạn có thể" not in output.text
    assert "mood-evidence-v1" in model.calls[0]["instructions"]
    assert "previously_authorized means" in model.calls[0]["instructions"]


async def test_sdk_requires_a_verified_read_even_when_scope_is_present():
    run = bound_evidence()
    run.mood_evidence = None
    model = ScriptedModel([[message_output(json.dumps(PLAN))]])
    with pytest.raises(DomainError) as error:
        await SdkProvider(Settings(_env_file=None)).run(bot_id="nhip", history=[], tools=[], context=run, on_progress=no_progress, model_override=model)
    assert error.value.code == "MOOD_EVIDENCE_REQUIRED"


async def test_no_global_numerical_regex_and_explicit_no_reuse_state():
    run = bound_evidence()
    run.mood_scope = None
    run.mood_evidence = None
    run.sources["mood"] = SourceState(previous="previously_authorized")
    model = make_test_model("Bạn có 15 phút; có thể dành 5 phút nghỉ.")
    result = await SdkProvider(Settings(_env_file=None)).run(bot_id="nhip", history=[{"role": "user", "content": "Mình có 15 phút rảnh"}], tools=[], context=run, on_progress=no_progress, model_override=model)
    assert "15 phút" in result.text and "5 phút" in result.text
    state = model.calls[0]["instructions"]
    assert '"authorization": "no_current_authorization"' in state
    assert '"reuse": "not_authorized"' in state
