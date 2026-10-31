"""One check-in attempt, E1–E5 (phase-1/03 §6). No transaction ever spans the model call.

E1 authorize + admit + open run/turn/usage (owner lock) and E2 build the payload (same short
transaction) → E3 model, no connection held → E4 validate → E5 publish under the owner lock
(users → jobs → conversations), rechecking everything E1 checked plus journal provenance.
A run never creates an ``actor='self'`` message, a session or a fake user turn.
"""

import asyncio
import hashlib
import logging
import time
from dataclasses import dataclass
from datetime import timedelta
from typing import Any
from uuid import UUID, uuid4

from agents.exceptions import (
    MaxTurnsExceeded,
    ModelBehaviorError,
    OutputGuardrailTripwireTriggered,
)
from pydantic import ValidationError
from sqlalchemy import func, select, update

from app.ai.accounting import UsageSnapshot, persist_snapshot, reserve_accounting
from app.ai.availability import public_failure
from app.ai.context import PROACTIVE_JOURNAL_POLICY as JOURNAL_POLICY
from app.ai.context import PROACTIVE_TEXT_POLICY as TEXT_POLICY
from app.ai.models import AiConversation, AiMessageRecord, AiTurn
from app.ai.proactive.context import ProactivePayload, build_payload
from app.ai.proactive.models import AiMessageSource, AiProactiveJob
from app.ai.proactive.output import (
    GuardrailBlocked,
    InvalidOutput,
    Validated,
    output_type,
    validate_proactive,
)
from app.ai.proactive.policy import Decision, admit_proactive, authorize_proactive
from app.ai.proactive.provenance import source_policy
from app.ai.proactive.safety import SAFETY_TEMPLATE, distress_screen
from app.ai.prompts import PROACTIVE_PROMPT_VERSION, SELECTED_VARIANTS, prompt_version
from app.ai.schemas import AiOutput
from app.ai.usage import UsageEvent
from app.core.errors import DomainError
from app.infrastructure.database.models import AiRun, now
from app.jobs.proactive import Claimed, defer, finish, retry, transaction

log = logging.getLogger("moodprint")
TRANSIENT = {"AI_PROVIDER_UNAVAILABLE", "AI_TIMEOUT", "AI_PROVIDER_RATE_LIMIT", "AI_STORAGE_UNAVAILABLE"}
CONVERSATION_MIN_LIFETIME = timedelta(hours=48)
RECENT_USER_MESSAGE = timedelta(minutes=10)
MAX_SAVED_CONVERSATIONS = 500


class Defer(Exception):
    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


class Halt(Exception):
    """A publish-time decision (skip/cancel/retry) after the model already ran."""

    def __init__(self, decision: Decision):
        self.decision = decision
        super().__init__(decision.reason)


class Fenced(Exception):
    """Another attempt owns the job now; this one must write nothing more."""


@dataclass
class Attempt:
    claimed: Claimed
    run_id: UUID
    data_version: int
    payload: ProactivePayload
    teen: bool
    usage: UsageSnapshot
    started: float
    # Phase 2 (R2): an authorized consultation opened at E2 and its settled outcome after E3.
    opened: Any = None
    consultation: Any = None


def default_title(slot: str, local_date) -> str:
    return f"Lời hỏi thăm {'buổi sáng' if slot == 'morning' else 'buổi tối'} {local_date:%d/%m}"


async def _decide(db, claimed: Claimed, decision: Decision) -> None:
    at = now()
    if decision.outcome == "defer":
        await defer(db, claimed, reason=decision.reason, at=at)
    elif decision.outcome == "retry":
        await retry(db, claimed, error=decision.reason, at=at)
    elif decision.outcome == "cancel":
        await finish(db, claimed, "cancelled", error=decision.reason)
    else:
        await finish(db, claimed, "skipped", reason=decision.reason)


async def _settle(db, runtime, attempt: Attempt, status: str) -> None:
    if runtime.settings.ai_accounting_enabled:
        await persist_snapshot(db, attempt.run_id, runtime.worker_id, attempt.usage, terminal=True)
    await db.execute(
        update(AiRun).where(AiRun.id == attempt.run_id, AiRun.status == "running")
        .values(status=status, version=2)
    )


async def _open(runtime, claimed: Claimed) -> Attempt | None:
    """E1 + E2 in one short transaction under the owner lock."""
    settings = runtime.settings
    async with transaction(runtime.database) as db:
        job = await db.get(AiProactiveJob, claimed.id)
        if job is None:
            return None
        authorized = await authorize_proactive(db, settings, runtime, job)
        decision = await admit_proactive(db, settings, authorized, job)
        if decision is not None:
            await _decide(db, claimed, decision)
            return None
        assert not isinstance(authorized, Decision)
        locked = await db.scalar(
            select(AiProactiveJob).where(AiProactiveJob.id == claimed.id).with_for_update()
        )
        if locked is None or locked.lease_token != claimed.lease_token or locked.status != "running":
            return None
        user = authorized.user
        payload = await build_payload(db, user, authorized.prefs, authorized.schedule, job)
        run_id = uuid4()
        db.add(AiRun(id=run_id, user_id=user.id, conversation_id=None, bot_id=job.bot_id,
                     status="running", origin="proactive", proactive_slot=job.slot))
        await db.flush()
        db.add(AiTurn(
            run_id=run_id, user_id=user.id, scope_id=job.id, conversation_id=None,
            session_id=None, client_message_id=uuid4(),
            input_digest=hashlib.sha256(f"{job.id}:{claimed.attempts}".encode()).hexdigest(),
            data_version=user.data_version,
            context_policy=JOURNAL_POLICY if payload.digests else TEXT_POLICY,
            worker_id=runtime.worker_id, lease_until=claimed.lease_until, origin="proactive",
        ))
        if settings.ai_accounting_enabled:
            await reserve_accounting(
                db, run_id, user.id, runtime.worker_id, settings.openai_model,
                prompt_version(SELECTED_VARIANTS[job.bot_id]) + "+" + PROACTIVE_PROMPT_VERSION,
            )
        opened = None
        if settings.ai_collaboration_enabled and job.bot_id == "rure" and job.slot == "morning":
            # R2 (phase-2/02 §4.2): authorize and read under this same owner lock; the
            # specialist itself runs at E3 with no connection held.
            from app.ai.collaboration.policy import Signals

            opened = await runtime.coordinator.open(
                db, user, primary_run_id=run_id,
                signals=Signals(origin="proactive", bot_id="rure", slot="morning"),
                data_version=user.data_version, seconds_remaining=45.0, worker_id=runtime.worker_id,
                local_today=job.local_date,
            )
        return Attempt(claimed, run_id, user.data_version, payload, user.age_band == "teen",
                       UsageSnapshot(), time.monotonic(), opened=opened)


async def _generate(runtime, attempt: Attempt) -> Validated:
    """E3 + E4. Holds no database connection while the provider works."""
    payload, claimed = attempt.payload, attempt.claimed
    if payload.digests and distress_screen([d.excerpt for d in payload.digests]):
        # No model call, no quote, no suggestion, no provenance (phase-1/07 §8).
        log.info("metric=proactive_safety_template")
        return Validated(parts=[AiOutput(text=SAFETY_TEMPLATE)])

    async def check() -> None:
        async with transaction(runtime.database) as db:
            job = await db.get(AiProactiveJob, claimed.id)
            if job is None or job.lease_token != claimed.lease_token:
                raise DomainError(410, "WORKER_FENCED", "Lượt hỏi thăm đã kết thúc.")
            decision = await authorize_proactive(db, runtime.settings, runtime, job, lock=False)
            if isinstance(decision, Decision):
                raise DomainError(409, "PROACTIVE_CHANGED", "Lời hỏi thăm không còn phù hợp.")

    async def observe(event: UsageEvent) -> None:
        attempt.usage.observe(event)
        if runtime.settings.ai_accounting_enabled:
            async with transaction(runtime.database) as db:
                if not await persist_snapshot(db, attempt.run_id, runtime.worker_id, attempt.usage):
                    raise DomainError(410, "WORKER_FENCED", "Lượt hỏi thăm đã kết thúc.")

    brief = None
    if attempt.opened is not None:
        from app.ai.collaboration.coordinator import still_authorized
        from app.infrastructure.database.models import User

        opened = attempt.opened

        async def collaboration_check() -> None:
            await check()
            async with transaction(runtime.database) as db:
                user = await db.get(User, claimed.user_id)
                if user is None or not await still_authorized(db, runtime.settings, user, opened.consultation):
                    raise DomainError(409, "CONTEXT_CHANGED", "Quyền hoặc dữ liệu đã thay đổi.")

        attempt.consultation = await runtime.coordinator.execute(
            opened, user_id=claimed.user_id, check=collaboration_check, worker_id=runtime.worker_id
        )
        brief = attempt.consultation.brief
    output = await runtime.provider.run_proactive(
        bot_id=claimed.bot_id, slot=claimed.slot, input_item=payload.input_item(),
        output_type=output_type(claimed.bot_id), teen=attempt.teen, on_progress=check,
        model_override=runtime.model_override, usage_observer=observe, user_id=claimed.user_id,
        extra_instructions=brief.instructions if brief else "",
    )
    return validate_proactive(output, payload)


async def choose_conversation(db, user, claimed: Claimed, at, retention_days: int) -> AiConversation:
    """ADR-07 / OD-01: the newest saved thread with this companion, else a new one."""
    candidate = await db.scalar(
        select(AiConversation)
        .where(
            AiConversation.user_id == user.id, AiConversation.bot_id == claimed.bot_id,
            AiConversation.expires_at > at + CONVERSATION_MIN_LIFETIME,
        )
        .order_by(AiConversation.updated_at.desc(), AiConversation.id.desc())
        .limit(1)
        .with_for_update()
    )
    if candidate is not None:
        busy = await db.scalar(
            select(AiRun.id).where(AiRun.conversation_id == candidate.id, AiRun.status == "running")
        )
        recent = await db.scalar(
            select(AiMessageRecord.id).where(
                AiMessageRecord.conversation_id == candidate.id, AiMessageRecord.actor == "self",
                AiMessageRecord.created_at > at - RECENT_USER_MESSAGE,
            ).limit(1)
        )
        if busy or recent:
            raise Defer("active_chat")
        return candidate
    saved = await db.scalar(
        select(func.count()).select_from(AiConversation).where(
            AiConversation.user_id == user.id, AiConversation.expires_at > at
        )
    )
    if saved >= MAX_SAVED_CONVERSATIONS:
        raise Halt(Decision("skip", "conversation_limit"))
    conversation = AiConversation(
        user_id=user.id, bot_id=claimed.bot_id, title=default_title(claimed.slot, claimed.local_date),
        expires_at=at + timedelta(days=min(retention_days, 30)),
    )
    db.add(conversation)
    await db.flush()
    return conversation


async def revalidate_entries(db, user, digests) -> bool:
    """Same saved/owner/90-day filter as search_for_ai, at the exact revision read at E2."""
    from zoneinfo import ZoneInfo

    from app.modules.journal.models import JournalEntry

    today = now().astimezone(ZoneInfo(user.timezone)).date()
    rows = (
        await db.execute(
            select(JournalEntry.id, JournalEntry.version).where(
                JournalEntry.user_id == user.id,
                JournalEntry.id.in_([d.entry_id for d in digests]),
                JournalEntry.status == "saved",
                JournalEntry.local_date >= today - timedelta(days=89),
                JournalEntry.local_date <= today,
            )
        )
    ).all()
    return dict(rows) == {d.entry_id: d.revision for d in digests}


async def publish(db, runtime, attempt: Attempt, validated: Validated) -> UUID:
    """E5: everything or nothing, under users → jobs → conversations."""
    claimed, settings = attempt.claimed, runtime.settings
    job = await db.get(AiProactiveJob, claimed.id)
    if job is None:
        raise Fenced()
    authorized = await authorize_proactive(db, settings, runtime, job)
    if isinstance(authorized, Decision):
        raise Halt(authorized)
    user, prefs = authorized.user, authorized.prefs
    locked = await db.scalar(
        select(AiProactiveJob).where(AiProactiveJob.id == claimed.id).with_for_update()
    )
    at = now()
    if (
        locked is None or locked.status != "running"
        or locked.lease_token != claimed.lease_token or locked.lease_until <= at
    ):
        raise Fenced()
    consultation = attempt.consultation
    if consultation is not None and consultation.brief is not None:
        # Authorization #3 for R2 under the owner lock, before anything is written.
        try:
            await runtime.coordinator.confirm(db, user, consultation, attempt.run_id, policy_name="proactive")
        except DomainError as error:
            if error.code == "SOURCE_CHANGED":
                raise Halt(Decision("retry", "source_changed")) from None
            raise Halt(Decision("cancel", "collaboration_revoked")) from None
    sources = [d for d in attempt.payload.digests if d.entry_id in validated.source_ids]
    if sources:
        if (
            not prefs.journal_context_enabled
            or user.data_version != attempt.data_version
            or not await revalidate_entries(db, user, sources)
        ):
            # The entries or the consent changed while the model ran: regenerate from fresh data.
            raise Halt(Decision("retry", "source_changed"))
    conversation = await choose_conversation(db, user, claimed, at, settings.chat_retention_days)
    base = conversation.version
    parts = validated.parts
    for index, part in enumerate(parts):
        db.add(AiMessageRecord(
            id=uuid4(), conversation_id=conversation.id, sequence=base + 1 + index, actor="bot",
            text=part.text, cards=[card.model_dump(mode="json", by_alias=True) for card in part.cards],
            run_id=attempt.run_id, part_index=index, part_count=len(parts),
        ))
    conversation.version = base + len(parts)
    conversation.updated_at = at
    for digest in sources:
        db.add(AiMessageSource(
            run_id=attempt.run_id, user_id=user.id, source_kind="journal_entry",
            source_id=digest.entry_id, source_revision=digest.revision,
            source_local_date=digest.local_date, policy=source_policy(prefs),
        ))
    turn = await db.get(AiTurn, attempt.run_id)
    if turn is None:
        raise Fenced()
    turn.conversation_id = conversation.id
    # The stamp proves which projection this message may join; journal-free text is plain text.
    used_journal = bool(consultation is not None and consultation.brief is not None and consultation.sources)
    turn.context_policy = JOURNAL_POLICY if sources or used_journal else TEXT_POLICY
    turn.data_version = user.data_version
    if settings.ai_accounting_enabled and not await persist_snapshot(
        db, attempt.run_id, runtime.worker_id, attempt.usage, terminal=True
    ):
        raise Fenced()
    # HD-05: one statement, so the partial unique on running conversations is never hit.
    completed = await db.scalar(
        update(AiRun)
        .where(AiRun.id == attempt.run_id, AiRun.status == "running")
        .values(conversation_id=conversation.id, status="completed", version=2)
        .returning(AiRun.id)
    )
    if completed is None:
        raise Fenced()
    if not await finish(db, claimed, "delivered", run_id=attempt.run_id,
                        conversation_id=conversation.id, challenge_kind=validated.challenge_kind):
        raise Fenced()
    log.info("metric=proactive_lag_seconds value=%d", max(0, round((at - claimed.due_at).total_seconds())))
    return conversation.id


def _classify(error: BaseException) -> tuple[str, str]:
    """(action, code): retry | invalid | guardrail | failed | cancel."""
    if isinstance(error, (OutputGuardrailTripwireTriggered, GuardrailBlocked)):
        return "guardrail", "guardrail"
    if isinstance(error, InvalidOutput):
        return "invalid", error.code
    if isinstance(error, (ModelBehaviorError, ValidationError, MaxTurnsExceeded)):
        return "invalid", "invalid_output"
    if isinstance(error, DomainError):
        if error.code in ("PROACTIVE_CHANGED", "WORKER_FENCED", "CONTEXT_CHANGED"):
            return "cancel", error.code.lower()
        if error.code == "AI_UNAVAILABLE":
            return "skip", "ai_unavailable"
        return "failed", error.code.lower()[:48]
    code = public_failure(error if isinstance(error, Exception) else Exception())["code"]
    if code in TRANSIENT:
        return "retry", code
    if code == "AI_PROVIDER_CONFIGURATION":
        log.error("metric=proactive_provider_configuration")
        return "failed", "provider_configuration"
    return "retry", code


async def execute_job(runtime, claimed: Claimed) -> None:
    attempt = await _open(runtime, claimed)
    if attempt is None:
        return
    try:
        validated = await asyncio.wait_for(_generate(runtime, attempt), timeout=45)
    except Exception as error:
        action, code = _classify(error)
        log.warning("proactive_generate_error job_id=%s action=%s code=%s error_type=%s",
                    claimed.id, action, code, type(error).__name__)
        await runtime.coordinator.discard(attempt.consultation, action)
        async with transaction(runtime.database) as db:
            await _settle(db, runtime, attempt, "cancelled" if action in ("cancel", "skip") else "failed")
            if action == "guardrail":
                await finish(db, claimed, "skipped", reason="guardrail")
            elif action == "skip":
                await finish(db, claimed, "skipped", reason=code)
            elif action == "cancel":
                await finish(db, claimed, "cancelled", error=code)
            elif action == "invalid":
                if claimed.attempts >= 2:
                    await finish(db, claimed, "failed", error="invalid_output")
                else:
                    await retry(db, claimed, error=code, at=now())
            elif action == "retry":
                await retry(db, claimed, error=code, at=now())
            else:
                await finish(db, claimed, "failed", error=code)
        return
    try:
        async with transaction(runtime.database) as db:
            await publish(db, runtime, attempt, validated)
    except (Defer, Halt, Fenced) as outcome:
        await runtime.coordinator.discard(attempt.consultation, type(outcome).__name__.lower())
        async with transaction(runtime.database) as db:
            await _settle(db, runtime, attempt, "cancelled")
            if isinstance(outcome, Defer):
                await defer(db, claimed, reason=outcome.reason, at=now())
            elif isinstance(outcome, Halt):
                await _decide(db, claimed, outcome.decision)
    except Exception:
        await runtime.coordinator.discard(attempt.consultation, "storage")
        # Storage failed mid-publish: nothing committed. Close the run; the job's lease (or the
        # worker's retry) brings it back, so the user still sees the check-in exactly once.
        async with transaction(runtime.database) as db:
            await _settle(db, runtime, attempt, "failed")
        raise
    log.info(
        "proactive_execution_end job_id=%s bot=%s slot=%s duration_ms=%d input_tokens=%d output_tokens=%d",
        claimed.id, claimed.bot_id, claimed.slot, round((time.monotonic() - attempt.started) * 1000),
        attempt.usage.input_tokens, attempt.usage.output_tokens,
    )
