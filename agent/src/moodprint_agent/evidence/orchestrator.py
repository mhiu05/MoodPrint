"""Consent-gated evidence analysis shared by the REST endpoint and the ``analyze_evidence`` tool.

Order is the safety property: consent -> ownership and readiness -> audited signed read -> fetch the
original (internal) -> hash it -> record the request -> only then decode, derive and call the model.
No bytes leave the system before consent, and the original is only ever read.
"""

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Final, Literal, Protocol
from uuid import UUID, uuid5

from moodprint_shared.config import AppConfig
from moodprint_shared.contracts.auth import AuthContext
from moodprint_shared.contracts.evidence import DerivativeCreate, EvidenceService

from moodprint_agent.evidence.image import ImageRejected, PreparedImage, prepare_image
from moodprint_agent.evidence.models import EvidenceReading
from moodprint_agent.evidence.reader import ReaderOutput, ReadFailed

CONSENT_VERSION: Final = "evidence-analysis-2026-11-08"
DERIVATIVE_NAMESPACE: Final = UUID("6f1c9c1e-6d0b-4d9a-9a52-4d6f6f6f7002")
GENERATOR: Final = "gpt-6-luna"

AnalysisStatus = Literal["running", "succeeded", "failed", "cancelled"]


class AnalysisError(Exception):
    """A request-level refusal with a stable ``code``; ``status`` is the HTTP status to use."""

    def __init__(self, code: str, status: int, message: str) -> None:
        super().__init__(code)
        self.code, self.status, self.message = code, status, message


@dataclass(frozen=True, slots=True)
class AnalysisRecord:
    id: UUID
    owner_id: UUID
    evidence_id: UUID
    consent_version: str
    status: AnalysisStatus
    source_sha256: str
    request_sha256: str
    derivative_id: UUID | None
    error_code: str | None
    usage: dict[str, Any] | None
    started_at: datetime
    finished_at: datetime | None
    created: bool = False


class AnalysisStore(Protocol):
    """Owner-scoped persistence of ``app.analysis_requests`` (identity columns write-once)."""

    async def begin(
        self,
        auth: AuthContext,
        *,
        request_id: UUID,
        evidence_id: UUID,
        consent_version: str,
        source_sha256: str,
        request_sha256: str,
    ) -> AnalysisRecord: ...

    async def finish(
        self,
        auth: AuthContext,
        request_id: UUID,
        *,
        status: Literal["succeeded", "failed", "cancelled"],
        derivative_id: UUID | None,
        error_code: str | None,
        usage: dict[str, Any] | None,
    ) -> AnalysisRecord: ...

    async def get(self, auth: AuthContext, request_id: UUID) -> AnalysisRecord | None: ...

    async def derivative_content(
        self, auth: AuthContext, derivative_id: UUID
    ) -> dict[str, Any] | None: ...


class ImageFetcher(Protocol):
    async def fetch(self, url: str) -> bytes: ...


class Reader(Protocol):
    async def read(self, image: PreparedImage) -> ReaderOutput: ...


@dataclass(frozen=True, slots=True)
class AnalysisOutcome:
    record: AnalysisRecord
    reading: EvidenceReading | None
    usage: dict[str, int] | None


def derivative_id_for(owner_id: UUID, request_id: UUID) -> UUID:
    return uuid5(DERIVATIVE_NAMESPACE, f"{owner_id}:{request_id}")


class AnalysisOrchestrator:
    def __init__(
        self,
        cfg: AppConfig,
        evidence: EvidenceService,
        store: AnalysisStore,
        fetcher: ImageFetcher,
        reader: Reader,
        reader_version: str,
    ) -> None:
        self._cfg, self._evidence, self._store = cfg, evidence, store
        self._fetcher, self._reader, self._reader_version = fetcher, reader, reader_version

    async def run(
        self,
        auth: AuthContext,
        *,
        request_id: UUID,
        evidence_id: UUID,
        consent_accepted: bool,
        consent_version: str,
    ) -> AnalysisOutcome:
        if not consent_accepted or consent_version != CONSENT_VERSION:
            raise AnalysisError(
                "consent_required", 422, "Cần đồng ý gửi ảnh này cho AI đọc trước khi phân tích."
            )
        cfg = self._cfg.agent
        meta = await self._evidence.get(auth, evidence_id)  # NotFound for another owner
        if meta.upload_status != "uploaded":
            raise AnalysisError("evidence_not_ready", 409, "Tệp chưa sẵn sàng để phân tích.")
        if meta.kind != "image" or (meta.stored_mime_type or "") not in cfg.analysis_allowed_mime:
            raise AnalysisError("unsupported_media", 415, "Chỉ phân tích ảnh JPEG, PNG hoặc WebP.")
        if meta.byte_size is not None and meta.byte_size > cfg.analysis_max_image_bytes:
            raise AnalysisError("object_too_large", 413, "Ảnh quá lớn để phân tích.")
        # An existing request is answered before any new signed read or provider call is made.
        existing = await self._store.get(auth, request_id)
        if existing is not None:
            return await self._replay(auth, existing, evidence_id, consent_version)

        signed = await self._evidence.open_read_url(auth, evidence_id, "evidence_analysis")
        try:
            original = await self._fetcher.fetch(signed.url)
        except ImageRejected as error:
            raise AnalysisError(error.code, 413, "Không tải được ảnh để phân tích.") from None
        source_sha = hashlib.sha256(original).hexdigest()
        request_sha = hashlib.sha256(
            json.dumps(
                {
                    "evidence": str(evidence_id),
                    "consent": consent_version,
                    "reader": self._reader_version,
                    "source": source_sha,
                },
                sort_keys=True,
            ).encode()
        ).hexdigest()
        record = await self._store.begin(
            auth,
            request_id=request_id,
            evidence_id=evidence_id,
            consent_version=consent_version,
            source_sha256=source_sha,
            request_sha256=request_sha,
        )
        if not record.created:
            return await self._replay(auth, record, evidence_id, consent_version, request_sha)
        try:
            prepared = prepare_image(
                original,
                allowed_mime=cfg.analysis_allowed_mime,
                max_bytes=cfg.analysis_max_image_bytes,
                max_px=cfg.analysis_max_image_px,
            )
            output = await self._reader.read(prepared)
        except ImageRejected as error:
            return await self._fail(auth, request_id, error.code)
        except ReadFailed as error:
            return await self._fail(auth, request_id, error.code)
        derivative_id = derivative_id_for(auth.user_id, request_id)
        content: dict[str, Any] = {
            "reading": output.reading.model_dump(mode="json"),
            "source": {
                "mime": prepared.source_mime,
                "bytes": prepared.source_bytes,
                "sha256": prepared.source_sha256,
            },
            "derivative": {
                "sha256": prepared.derivative_sha256,
                "width": prepared.width,
                "height": prepared.height,
            },
            "consent_version": consent_version,
            "analysis_request_id": str(request_id),
        }
        await self._evidence.add_derivative(
            auth,
            evidence_id,
            DerivativeCreate(
                id=derivative_id,
                kind="ai_analysis",
                content=content,
                generator=GENERATOR,
                generator_version=output.version,
                source_sha256=prepared.source_sha256,
            ),
        )
        final = await self._store.finish(
            auth,
            request_id,
            status="succeeded",
            derivative_id=derivative_id,
            error_code=None,
            usage=dict(output.usage),
        )
        return AnalysisOutcome(final, output.reading, output.usage)

    async def _fail(self, auth: AuthContext, request_id: UUID, code: str) -> AnalysisOutcome:
        final = await self._store.finish(
            auth, request_id, status="failed", derivative_id=None, error_code=code, usage=None
        )
        return AnalysisOutcome(final, None, None)

    async def _replay(
        self,
        auth: AuthContext,
        record: AnalysisRecord,
        evidence_id: UUID,
        consent_version: str,
        request_sha: str | None = None,
    ) -> AnalysisOutcome:
        if (
            record.evidence_id != evidence_id
            or record.consent_version != consent_version
            or (request_sha is not None and record.request_sha256 != request_sha)
        ):
            raise AnalysisError(
                "request_conflict", 409, "Mã yêu cầu này đã dùng cho một phân tích khác."
            )
        reading: EvidenceReading | None = None
        if record.status == "succeeded" and record.derivative_id is not None:
            reading = await self.reading_of(auth, record)
        return AnalysisOutcome(record, reading, None)

    async def reading_of(self, auth: AuthContext, record: AnalysisRecord) -> EvidenceReading | None:
        if record.derivative_id is None:
            return None
        content = await self._store.derivative_content(auth, record.derivative_id)
        raw = content.get("reading") if content else None
        return EvidenceReading.model_validate(raw) if isinstance(raw, dict) else None
