"""Backend composition of the analysis pipeline (REST route and Companion tool share it)."""

import asyncio
from typing import Any
from uuid import UUID, uuid5

from moodprint_agent.evidence.models import reading_summary
from moodprint_agent.evidence.orchestrator import (
    CONSENT_VERSION,
    AnalysisError,
    AnalysisOrchestrator,
    AnalysisOutcome,
    AnalysisRecord,
)
from moodprint_agent.evidence.reader import EvidenceReader, reader_version
from moodprint_agent.tools.saving import error
from moodprint_shared.config import AppConfig
from moodprint_shared.contracts.auth import AuthContext
from moodprint_shared.contracts.errors import NotFound
from openai import AsyncOpenAI

from app.core.errors import ApiError
from app.modules.analysis.fetcher import SignedUrlFetcher
from app.modules.analysis.schemas import AnalysisCreate, AnalysisRead, reading_read
from app.modules.analysis.store import SqlAnalysisStore
from app.modules.evidence.service import EvidenceService

TOOL_NAMESPACE = UUID("6f1c9c1e-6d0b-4d9a-9a52-4d6f6f6f7003")


def build_orchestrator(
    engine: Any,
    cfg: AppConfig,
    *,
    evidence: EvidenceService,
    client: AsyncOpenAI,
    storage_base_url: str,
    production: bool,
) -> tuple[AnalysisOrchestrator, SqlAnalysisStore]:
    store = SqlAnalysisStore(engine)
    orchestrator = AnalysisOrchestrator(
        cfg,
        evidence,
        store,
        SignedUrlFetcher(
            storage_base_url,
            production=production,
            max_bytes=cfg.agent.analysis_max_image_bytes,
        ),
        EvidenceReader(client, cfg),
        reader_version(),
    )
    return orchestrator, store


class AnalysisService:
    def __init__(
        self,
        engine: Any,
        cfg: AppConfig,
        evidence: EvidenceService,
        client: AsyncOpenAI | None,
        *,
        storage_base_url: str,
        production: bool,
        tasks: set[asyncio.Task[Any]],
    ) -> None:
        self.cfg, self.tasks, self.client = cfg, tasks, client
        self._engine, self._evidence = engine, evidence
        self._storage_base_url, self._production = storage_base_url, production
        self.store = SqlAnalysisStore(engine)

    def _orchestrator(self) -> AnalysisOrchestrator:
        if self.client is None:
            raise ApiError("not_ready", "Tính năng AI chưa được cấu hình.", 503)
        return build_orchestrator(
            self._engine,
            self.cfg,
            evidence=self._evidence,
            client=self.client,
            storage_base_url=self._storage_base_url,
            production=self._production,
        )[0]

    async def create(self, auth: AuthContext, body: AnalysisCreate) -> AnalysisRead:
        orchestrator = self._orchestrator()
        task = asyncio.create_task(
            orchestrator.run(
                auth,
                request_id=body.id,
                evidence_id=body.evidence_id,
                consent_accepted=body.consent.accepted,
                consent_version=body.consent.version,
            )
        )
        # A client that disconnects stops waiting; the work finishes and GET recovers it.
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)
        try:
            outcome = await asyncio.shield(task)
        except AnalysisError as failure:
            raise ApiError(failure.code, failure.message, failure.status) from None
        except NotFound:
            raise
        return self._read(outcome)

    async def get(self, auth: AuthContext, request_id: UUID) -> AnalysisRead:
        record = await self.store.get(auth, request_id)
        if record is None:
            raise NotFound()
        record = await self.store.expire_if_stale(
            auth, record, after_s=self.cfg.agent.analysis_timeout_s * 2
        )
        reading = None
        if record.status == "succeeded" and record.derivative_id is not None:
            orchestrator = self._orchestrator()
            found = await orchestrator.reading_of(auth, record)
            reading = reading_read(found) if found is not None else None
        return _read(record, reading)

    def _read(self, outcome: AnalysisOutcome) -> AnalysisRead:
        reading = reading_read(outcome.reading) if outcome.reading is not None else None
        return _read(outcome.record, reading)

    def tool_runner(self) -> "ToolAnalysisRunner":
        return ToolAnalysisRunner(self._orchestrator())


def _read(record: AnalysisRecord, reading: Any) -> AnalysisRead:
    return AnalysisRead(
        id=record.id,
        evidence_id=record.evidence_id,
        status=record.status,
        consent_version=record.consent_version,
        derivative_id=record.derivative_id,
        error_code=record.error_code,
        reading=reading,
        started_at=record.started_at,
        finished_at=record.finished_at,
    )


class ToolAnalysisRunner:
    """``AnalysisRunner`` for the Companion tool: the approval dialog is the consent."""

    def __init__(self, orchestrator: AnalysisOrchestrator) -> None:
        self._orchestrator = orchestrator

    async def analyze(
        self, auth: AuthContext, *, evidence_id: UUID, run_id: UUID
    ) -> dict[str, Any]:
        request_id = uuid5(TOOL_NAMESPACE, f"{run_id}:{evidence_id}")
        try:
            outcome = await self._orchestrator.run(
                auth,
                request_id=request_id,
                evidence_id=evidence_id,
                consent_accepted=True,
                consent_version=CONSENT_VERSION,
            )
        except AnalysisError as failure:
            return error(failure.code, failure.message)
        if outcome.reading is None:
            return error(outcome.record.error_code or outcome.record.status, retryable=True)
        return {
            "status": "succeeded",
            "analysisId": str(request_id),
            **reading_summary(outcome.reading),
        }


def tool_analysis(request: Any) -> ToolAnalysisRunner | None:
    """Per-request ``AnalysisRunner`` for the Companion, or None when no model client exists."""
    state = request.app.state
    client = getattr(getattr(state, "runtime", None), "openai_client", None)
    if client is None:
        return None
    service = AnalysisService(
        state.engine,
        state.cfg,
        EvidenceService(state.engine, state.storage, state.cfg),
        client,
        storage_base_url=state.settings.supabase_url,
        production=state.settings.app_env == "production",
        tasks=state.run_tasks,
    )
    return service.tool_runner()
