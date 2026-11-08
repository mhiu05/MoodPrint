"""Execute one evaluation case against the real runtime and tools (live) and record facts.

Nothing here judges quality. It records what happened (events, tool calls, writes, citations,
latencies, usage) so deterministic assertions can run and the coding agent can grade each output.
"""

import json
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any
from uuid import UUID, uuid4

from agents import SQLiteSession
from evals.cases_io import Case
from evals.fakes import CASE_ID, OWNER, EvalDomain, RecordingKnowledge, StoreAdapter
from moodprint_agent.budget import RunToolBudget
from moodprint_agent.evidence.image import prepare_image
from moodprint_agent.evidence.reader import EvidenceReader
from moodprint_agent.roleplay.feedback import RoleplayCoach
from moodprint_agent.roleplay.models import RoleplayContext
from moodprint_agent.roleplay.scenarios import scenario_for
from moodprint_agent.runtime import CompanionRuntime
from moodprint_agent.tools.context import CompanionToolContext, ToolDeps
from moodprint_agent.tools.factory import build_registry
from moodprint_shared.config import AppConfig
from moodprint_shared.contracts.agent import AgentServices
from moodprint_shared.contracts.auth import AuthContext
from moodprint_shared.contracts.context import (
    ContextBundle,
    ContextSection,
    Provenance,
)
from moodprint_shared.contracts.streaming import StreamEvent
from openai import AsyncOpenAI

FIXTURES = Path(__file__).resolve().parent / "fixtures"
NOW = datetime(2026, 11, 8, tzinfo=UTC)


def _section(kind: Any, text: str, source: str, stale: bool = False) -> ContextSection:
    return ContextSection(
        kind=kind,
        text=text,
        tokens=max(1, len(text) // 3),
        priority=500,
        provenance=[
            Provenance(source_kind=source, source_id=str(uuid4()), retrieved_at=NOW, stale=stale)
        ],
    )


def _bundle(case: Case) -> ContextBundle:
    sections = [
        _section(
            "identity",
            json.dumps({"nickname": "Minh", "age_band": None, "locale": "vi"}, ensure_ascii=False),
            "profile",
        )
    ]
    if case.setup.attach_case:
        sections.append(
            _section(
                "domain",
                json.dumps(
                    {
                        "label": "[người dùng kể]",
                        "case_id": str(CASE_ID),
                        "title": "Chuyện nhóm chat lớp",
                        "status": "active",
                        "events": 0,
                        "updated": "2026-11-07",
                    },
                    ensure_ascii=False,
                    separators=(",", ":"),
                ),
                "case_summary",
            )
        )
    sections += [_section("memory", m, "approved_memory") for m in case.setup.memories]
    sections += [
        _section("memory", m, "approved_memory", stale=True) for m in case.setup.stale_memories
    ]
    return ContextBundle(sections=sections, total_tokens=sum(s.tokens for s in sections))


def _context(
    case: Case, domain: EvalDomain, cfg: AppConfig, conversation_id: UUID
) -> CompanionToolContext:
    return CompanionToolContext(
        auth=AuthContext(OWNER, "eval", "aal1", json.dumps({"sub": str(OWNER)})),
        request_id=f"eval-{case.id}",
        conversation_id=conversation_id,
        run_id=uuid4(),
        age_band=None,
        services=AgentServices(
            incidents=domain,  # type: ignore[arg-type]
            evidence=domain,  # type: ignore[arg-type]
            plans=domain,  # type: ignore[arg-type]
            memory=domain,  # type: ignore[arg-type]
            knowledge=domain.knowledge,
        ),
        context=_bundle(case),
        budget=RunToolBudget(cfg.agent.max_tool_calls_per_run),
        deps=ToolDeps(proposals=StoreAdapter(domain), events=domain, plans=domain),  # type: ignore[arg-type]
        knowledge_timeout_s=7.0,
        memory_candidates_max=cfg.memory.extraction_max_candidates_per_run,
    )


class TurnRecorder:
    def __init__(self) -> None:
        self.names: list[str] = []
        self.tools: list[str] = []
        self.deltas: list[str] = []
        self.assistant: str | None = None
        self.citations: list[str] = []
        self.urgency = "none"
        self.status = "failed"
        self.error_code: str | None = None
        self.ttft_ms: int | None = None
        self.usage: dict[str, int] = {}
        self.approval: dict[str, Any] | None = None
        self._start = perf_counter()

    def add(self, event: StreamEvent) -> None:
        self.names.append(event.event)
        data: Any = event.data
        if event.event == "message.delta" and self.ttft_ms is None:
            self.ttft_ms = int((perf_counter() - self._start) * 1000)
        elif event.event == "tool.started":
            self.tools.append(data.tool)
        elif event.event == "message.completed":
            self.assistant = data.content
            self.citations = [c.title for c in data.citations]
            if data.structured is not None:
                self.urgency = data.structured.urgency
        elif event.event == "approval.required":
            self.approval = {"tool": data.tool, "preview": data.preview}
        elif event.event == "run.usage":
            self.usage = {
                k: int(getattr(data, k))
                for k in ("input_tokens", "output_tokens", "total_tokens", "requests", "tool_calls")
            }
        elif event.event == "run.completed":
            self.status = data.status
        elif event.event == "run.failed":
            self.status, self.error_code = "failed", data.code

    def dump(self, user: str) -> dict[str, Any]:
        return {
            "user": user,
            "assistant": self.assistant,
            "tools": self.tools,
            "citations": self.citations,
            "urgency": self.urgency,
            "status": self.status,
            "error_code": self.error_code,
            "ttft_ms": self.ttft_ms,
            "latency_ms": int((perf_counter() - self._start) * 1000),
            "usage": self.usage,
            "event_names": self.names,
            "approval": self.approval,
        }


def _domain_for(case: Case) -> EvalDomain:
    corpus = case.setup.corpus
    return EvalDomain(
        case_note=case.setup.case_note,
        knowledge=RecordingKnowledge(poison=corpus == "poisoned", empty=corpus == "empty"),
    )


async def _new_tool_outputs(session: SQLiteSession, seen: list[int]) -> list[str]:
    """Tool outputs written to the session since the last call (truncated; for diagnosis/grading)."""
    items = await session.get_items()
    fresh = items[seen[0] :]
    seen[0] = len(items)
    outputs: list[str] = []
    for item in fresh:
        if isinstance(item, dict) and item.get("type") == "function_call_output":
            outputs.append(str(item.get("output", ""))[:400])
    return outputs


async def run_chat_case(
    case: Case, repeat: int, cfg: AppConfig, client: AsyncOpenAI
) -> dict[str, Any]:
    domain = _domain_for(case)
    runtime = CompanionRuntime(cfg, build_registry(cfg), openai_client=client)
    session = SQLiteSession(f"{case.id}-{repeat}-{uuid4().hex[:6]}")
    conversation_id = uuid4()
    decisions = list(case.expect.approvals)
    turns: list[dict[str, Any]] = []
    prior: list[str] = []
    seen_items = [0]
    writes_before_decision = 0
    asked: bool | None = None
    for text in case.turns:
        ctx = _context(case, domain, cfg, conversation_id)
        turn = TurnRecorder()
        async for event in runtime.stream_turn(
            ctx=ctx, user_input=text, session=session, prior_user_messages=prior
        ):
            turn.add(event)
        prior.append(text)
        record = turn.dump(text)
        record["tool_outputs"] = await _new_tool_outputs(session, seen_items)
        turns.append(record)
        # The user's decisions are simulated exactly as the approval service would apply them.
        while turn.status == "awaiting_approval" and decisions:
            writes_before_decision += domain.writes
            pending = runtime.pending_approvals(ctx.run_id)[0]
            decision = decisions.pop(0)
            proposal_id = UUID(str(pending.preview["proposalId"]))
            # A-25: before the save, either the model asked/confirmed in an earlier answer or the
            # user explicitly asked to save in this turn (both are acceptable asking-first paths).
            earlier = [t["assistant"] or "" for t in turns[:-1]]
            asked = any("?" in answer for answer in earlier) or "lưu" in text.lower()
            domain.decide(proposal_id, decision == "approve")
            follow = TurnRecorder()
            async for event in runtime.resume_after_approval(
                ctx=ctx,
                serialized_state=pending.serialized_state,
                approved=decision == "approve",
                session=session,
                tool_call_id=pending.tool_call_id,
            ):
                follow.add(event)
            record = follow.dump(f"[{decision}]")
            record["tool_outputs"] = await _new_tool_outputs(session, seen_items)
            turns.append(record)
            turn = follow
    # A pending approval nobody decided must not have written anything.
    if turns and turns[-1]["status"] == "awaiting_approval":
        writes_before_decision += domain.writes
    return {
        "turns": turns,
        "writes": domain.writes,
        "writes_before_decision": writes_before_decision,
        "candidates": [c.content for c in domain.candidates],
        "retrieved_citation_titles": sorted(
            {c.citation.title for r in domain.knowledge.results for c in r.chunks}
        ),
        "knowledge_statuses": [r.status for r in domain.knowledge.results],
        "asked_before_save": asked,
        "guard_refusals": 0,
    }


async def run_screenshot_case(
    case: Case, repeat: int, cfg: AppConfig, client: AsyncOpenAI
) -> dict[str, Any]:
    data = (FIXTURES / f"{case.image}.png").read_bytes()
    prepared = prepare_image(
        data,
        allowed_mime=cfg.agent.analysis_allowed_mime,
        max_bytes=cfg.agent.analysis_max_image_bytes,
        max_px=cfg.agent.analysis_max_image_px,
    )
    started = perf_counter()
    output = await EvidenceReader(client, cfg).read(prepared)
    reading = output.reading.model_dump(mode="json")
    return {
        "turns": [
            {
                "user": f"[image {case.image}]",
                "assistant": json.dumps(reading, ensure_ascii=False),
                "tools": [],
                "citations": [],
                "urgency": "none",
                "status": "completed",
                "error_code": None,
                "ttft_ms": None,
                "latency_ms": int((perf_counter() - started) * 1000),
                "usage": output.usage,
                "event_names": ["run.started", "message.completed", "run.usage", "run.completed"],
                "approval": None,
            }
        ],
        "writes": 0,
        "writes_before_decision": 0,
        "retrieved_citation_titles": [],
        "knowledge_statuses": [],
        "asked_before_save": None,
        "guard_refusals": 0,
        "reading": reading,
        "reader_version": output.version,
        "source_sha256": prepared.source_sha256,
    }


async def run_roleplay_case(
    case: Case, repeat: int, cfg: AppConfig, client: AsyncOpenAI
) -> dict[str, Any]:
    scenario = scenario_for(case.scenario or "")
    if scenario is None:
        raise ValueError(f"unknown scenario {case.scenario}")
    role_play = RoleplayContext(
        role=scenario.role,
        scenario_key=scenario.key,
        scenario_title=scenario.title,
        scenario_context=scenario.context,
        user_goal=scenario.default_goal,
        difficulty=case.difficulty,
        age_band=None,
    )
    domain = _domain_for(case)
    runtime = CompanionRuntime(cfg, build_registry(cfg), openai_client=client)
    session = SQLiteSession(f"{case.id}-{repeat}-{uuid4().hex[:6]}")
    conversation_id = uuid4()
    turns: list[dict[str, Any]] = []
    transcript: list[tuple[str, str]] = []
    prior: list[str] = []
    for text in case.turns:
        ctx = _context(case, domain, cfg, conversation_id)
        ctx.mode, ctx.roleplay = "roleplay", role_play
        turn = TurnRecorder()
        async for event in runtime.stream_turn(
            ctx=ctx, user_input=text, session=session, prior_user_messages=prior
        ):
            turn.add(event)
        prior.append(text)
        turns.append(turn.dump(text))
        transcript += [("user", text), ("partner", turn.assistant or "")]
    started = perf_counter()
    feedback = await RoleplayCoach(client, cfg).feedback(role_play, transcript)
    return {
        "turns": turns,
        "writes": 0,
        "writes_before_decision": 0,
        "retrieved_citation_titles": [],
        "knowledge_statuses": [],
        "asked_before_save": None,
        "guard_refusals": 0,
        "feedback": feedback.feedback.model_dump(mode="json"),
        "feedback_usage": feedback.usage,
        "feedback_latency_ms": int((perf_counter() - started) * 1000),
    }


async def run_case(case: Case, repeat: int, cfg: AppConfig, client: AsyncOpenAI) -> dict[str, Any]:
    if case.suite == "screenshot":
        return await run_screenshot_case(case, repeat, cfg, client)
    if case.suite == "roleplay":
        return await run_roleplay_case(case, repeat, cfg, client)
    return await run_chat_case(case, repeat, cfg, client)
