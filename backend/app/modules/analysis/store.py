"""PostgreSQL store for ``app.analysis_requests``. Identity columns are write-once by grant."""

import json
from datetime import UTC, datetime
from typing import Any, Literal
from uuid import UUID

from moodprint_agent.evidence.orchestrator import AnalysisRecord
from moodprint_shared.contracts.auth import AuthContext
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.uow import user_uow

_COLUMNS = (
    "id,owner_id,evidence_id,consent_version,status,source_sha256,request_sha256,"
    "derivative_id,error_code,usage,started_at,finished_at"
)


def _json(value: Any) -> Any:
    return json.loads(value) if isinstance(value, (str, bytes)) else value


def to_record(row: Any, *, created: bool = False) -> AnalysisRecord:
    return AnalysisRecord(
        id=row["id"],
        owner_id=row["owner_id"],
        evidence_id=row["evidence_id"],
        consent_version=row["consent_version"],
        status=row["status"],
        source_sha256=row["source_sha256"],
        request_sha256=row["request_sha256"],
        derivative_id=row["derivative_id"],
        error_code=row["error_code"],
        usage=_json(row["usage"]),
        started_at=row["started_at"],
        finished_at=row["finished_at"],
        created=created,
    )


class SqlAnalysisStore:
    def __init__(self, engine: AsyncEngine) -> None:
        self.engine = engine

    async def begin(
        self,
        auth: AuthContext,
        *,
        request_id: UUID,
        evidence_id: UUID,
        consent_version: str,
        source_sha256: str,
        request_sha256: str,
    ) -> AnalysisRecord:
        async with user_uow(self.engine, auth) as uow:
            inserted = (
                (
                    await uow.session.execute(
                        text(
                            "INSERT INTO app.analysis_requests(id,owner_id,evidence_id,"
                            "consent_version,consent_at,source_sha256,request_sha256) "
                            "VALUES(:id,:owner,:evidence,:consent,now(),:source,:request) "
                            "ON CONFLICT(id) DO NOTHING RETURNING " + _COLUMNS
                        ),
                        {
                            "id": request_id,
                            "owner": auth.user_id,
                            "evidence": evidence_id,
                            "consent": consent_version,
                            "source": source_sha256,
                            "request": request_sha256,
                        },
                    )
                )
                .mappings()
                .first()
            )
            if inserted is not None:
                return to_record(inserted, created=True)
            existing = (
                (
                    await uow.session.execute(
                        text(
                            f"SELECT {_COLUMNS} FROM app.analysis_requests "
                            "WHERE id=:id AND owner_id=:owner"
                        ),
                        {"id": request_id, "owner": auth.user_id},
                    )
                )
                .mappings()
                .first()
            )
        if existing is None:  # the id belongs to another owner: indistinguishable from absent
            from moodprint_shared.contracts.errors import NotFound

            raise NotFound()
        return to_record(existing)

    async def finish(
        self,
        auth: AuthContext,
        request_id: UUID,
        *,
        status: Literal["succeeded", "failed", "cancelled"],
        derivative_id: UUID | None,
        error_code: str | None,
        usage: dict[str, Any] | None,
    ) -> AnalysisRecord:
        async with user_uow(self.engine, auth) as uow:
            # Compare-and-set: only a running request can finish, and only once.
            await uow.session.execute(
                text(
                    "UPDATE app.analysis_requests SET status=:status,derivative_id=:derivative,"
                    "error_code=:error,usage=CAST(:usage AS jsonb),finished_at=now() "
                    "WHERE id=:id AND owner_id=:owner AND status='running'"
                ),
                {
                    "id": request_id,
                    "owner": auth.user_id,
                    "status": status,
                    "derivative": derivative_id,
                    "error": error_code,
                    "usage": json.dumps(usage) if usage is not None else None,
                },
            )
            row = (
                (
                    await uow.session.execute(
                        text(
                            f"SELECT {_COLUMNS} FROM app.analysis_requests "
                            "WHERE id=:id AND owner_id=:owner"
                        ),
                        {"id": request_id, "owner": auth.user_id},
                    )
                )
                .mappings()
                .first()
            )
        if row is None:
            from moodprint_shared.contracts.errors import NotFound

            raise NotFound()
        return to_record(row)

    async def get(self, auth: AuthContext, request_id: UUID) -> AnalysisRecord | None:
        async with user_uow(self.engine, auth) as uow:
            row = (
                (
                    await uow.session.execute(
                        text(
                            f"SELECT {_COLUMNS} FROM app.analysis_requests "
                            "WHERE id=:id AND owner_id=:owner"
                        ),
                        {"id": request_id, "owner": auth.user_id},
                    )
                )
                .mappings()
                .first()
            )
        return to_record(row) if row is not None else None

    async def derivative_content(
        self, auth: AuthContext, derivative_id: UUID
    ) -> dict[str, Any] | None:
        async with user_uow(self.engine, auth) as uow:
            row = (
                await uow.session.execute(
                    text(
                        "SELECT content FROM app.evidence_derivatives "
                        "WHERE id=:id AND owner_id=:owner AND kind='ai_analysis'"
                    ),
                    {"id": derivative_id, "owner": auth.user_id},
                )
            ).first()
        content = _json(row[0]) if row is not None else None
        return content if isinstance(content, dict) else None

    async def expire_if_stale(
        self, auth: AuthContext, record: AnalysisRecord, *, after_s: float
    ) -> AnalysisRecord:
        """A request left ``running`` by a crash is closed as failed, never retried silently."""
        if record.status != "running":
            return record
        if (datetime.now(UTC) - record.started_at).total_seconds() <= after_s:
            return record
        return await self.finish(
            auth,
            record.id,
            status="failed",
            derivative_id=None,
            error_code="analysis_timeout",
            usage=None,
        )
