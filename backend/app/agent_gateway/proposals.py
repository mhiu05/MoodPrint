"""PostgreSQL ProposalStore and domain writers for the Companion's approved changes.

Every statement runs inside ``user_uow`` (role ``authenticated`` + verified claims), so RLS and the
composite owner foreign keys apply. State changes are compare-and-set ``UPDATE … WHERE status=…``
statements; the database cannot enforce the full transition graph (see CC-P3-001), so these
statements are the single place that does.
"""

import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from safevoice_agent.tools.proposals import (
    ApplyOutcome,
    ProposalKind,
    StoredProposal,
    event_id_for,
    payload_sha256,
)
from safevoice_shared.config import AppConfig
from safevoice_shared.contracts.auth import AuthContext
from safevoice_shared.contracts.errors import NotFound
from safevoice_shared.contracts.incidents import EventCreate
from safevoice_shared.contracts.plans import PlanUpsert
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.errors import ApiError
from app.core.uow import user_uow

_COLUMNS = (
    "id,owner_id,conversation_id,run_id,kind,target_case_id,payload,payload_sha256,preview,"
    "base_version,request_key,status,result,created_at,expires_at,approval_binding,decided_at"
)
# A run in any of these states must not start a new domain write.
_WRITABLE_RUN_STATES = ("running", "awaiting_approval")


def _json(value: Any) -> Any:
    return json.loads(value) if isinstance(value, (str, bytes)) else value


def to_stored(row: Any) -> StoredProposal:
    return StoredProposal(
        id=row["id"],
        owner_id=row["owner_id"],
        conversation_id=row["conversation_id"],
        run_id=row["run_id"],
        kind=row["kind"],
        target_case_id=row["target_case_id"],
        payload=_json(row["payload"]),
        payload_sha256=row["payload_sha256"],
        preview=_json(row["preview"]),
        base_version=row["base_version"],
        request_key=row["request_key"],
        status=row["status"],
        result=_json(row["result"]),
        created_at=row["created_at"],
        expires_at=row["expires_at"],
        approval_binding=_json(row["approval_binding"]),
        decided_at=row["decided_at"],
    )


class SqlProposalStore:
    def __init__(self, engine: AsyncEngine, cfg: AppConfig) -> None:
        self.engine, self.cfg = engine, cfg

    async def create(
        self,
        auth: AuthContext,
        *,
        conversation_id: UUID,
        run_id: UUID,
        kind: ProposalKind,
        target_case_id: UUID,
        payload: dict[str, Any],
        preview: dict[str, Any],
        base_version: int | None,
        request_key: str,
    ) -> StoredProposal:
        ttl = min(self.cfg.agent.proposal_ttl_s, 24 * 3600)
        try:
            async with user_uow(self.engine, auth) as uow:
                inserted = (
                    (
                        await uow.session.execute(
                            text(f"""INSERT INTO app.agent_proposals
                            (owner_id,conversation_id,run_id,kind,target_case_id,payload,payload_sha256,
                             preview,base_version,request_key,expires_at)
                            VALUES(:owner,:conv,:run,:kind,:case,CAST(:payload AS jsonb),:hash,
                             CAST(:preview AS jsonb),:base,:key,now()+make_interval(secs=>:ttl))
                            ON CONFLICT(owner_id,run_id,request_key) DO NOTHING
                            RETURNING {_COLUMNS}"""),
                            {
                                "owner": auth.user_id,
                                "conv": conversation_id,
                                "run": run_id,
                                "kind": kind,
                                "case": target_case_id,
                                "payload": json.dumps(payload, ensure_ascii=False),
                                "hash": payload_sha256(payload),
                                "preview": json.dumps(preview, ensure_ascii=False),
                                "base": base_version,
                                "key": request_key,
                                "ttl": ttl,
                            },
                        )
                    )
                    .mappings()
                    .first()
                )
                if inserted is None:  # retry of the same tool call: return the stored proposal
                    inserted = (
                        (
                            await uow.session.execute(
                                text(
                                    f"""SELECT {_COLUMNS} FROM app.agent_proposals
                                    WHERE owner_id=:owner AND run_id=:run AND request_key=:key"""
                                ),
                                {"owner": auth.user_id, "run": run_id, "key": request_key},
                            )
                        )
                        .mappings()
                        .one()
                    )
                return to_stored(inserted)
        except IntegrityError as error:  # composite FK: not this owner's conversation/run/case
            raise NotFound() from error

    async def get(self, auth: AuthContext, proposal_id: UUID) -> StoredProposal | None:
        async with user_uow(self.engine, auth) as uow:
            row = (
                (
                    await uow.session.execute(
                        text(
                            f"SELECT {_COLUMNS} FROM app.agent_proposals WHERE id=:id AND owner_id=:owner"
                        ),
                        {"id": proposal_id, "owner": auth.user_id},
                    )
                )
                .mappings()
                .first()
            )
            return to_stored(row) if row else None

    async def expire_stale(self, auth: AuthContext) -> int:
        """Housekeeping: mark overdue proposals expired (never touches terminal rows)."""
        async with user_uow(self.engine, auth) as uow:
            result = await uow.session.execute(
                text(
                    """UPDATE app.agent_proposals SET status='expired',decided_at=now()
                    WHERE owner_id=:owner AND status IN ('proposed','approved')
                    AND expires_at<=clock_timestamp()"""
                ),
                {"owner": auth.user_id},
            )
            return result.rowcount or 0  # type: ignore[attr-defined]

    async def _finish(
        self, auth: AuthContext, proposal_id: UUID, status: str, result: dict[str, Any]
    ) -> StoredProposal | None:
        """approved -> applied|failed, exactly once (compare-and-set)."""
        async with user_uow(self.engine, auth) as uow:
            row = (
                (
                    await uow.session.execute(
                        text(f"""UPDATE app.agent_proposals
                        SET status=:status,result=CAST(:result AS jsonb),
                            applied_at=CASE WHEN :status='applied' THEN now() ELSE applied_at END
                        WHERE id=:id AND owner_id=:owner AND status='approved'
                        RETURNING {_COLUMNS}"""),
                        {
                            "id": proposal_id,
                            "owner": auth.user_id,
                            "status": status,
                            "result": json.dumps(result, ensure_ascii=False),
                        },
                    )
                )
                .mappings()
                .first()
            )
        return to_stored(row) if row else await self.get(auth, proposal_id)

    async def run_may_write(self, auth: AuthContext, run_id: UUID) -> bool:
        async with user_uow(self.engine, auth) as uow:
            status = await uow.session.scalar(
                text("SELECT status FROM app.agent_runs WHERE id=:run AND owner_id=:owner"),
                {"run": run_id, "owner": auth.user_id},
            )
            return status in _WRITABLE_RUN_STATES


class _Writer:
    kind: ProposalKind

    def __init__(self, store: SqlProposalStore) -> None:
        self.store = store

    async def _precheck(
        self, auth: AuthContext, proposal_id: UUID, run_id: UUID
    ) -> tuple[StoredProposal | None, ApplyOutcome | None]:
        stored = await self.store.get(auth, proposal_id)
        if stored is None or stored.kind != self.kind:
            return None, ApplyOutcome("not_found", error="not_found")
        if stored.status == "applied":
            return stored, ApplyOutcome("applied", result=stored.result)
        if stored.status != "approved":
            return stored, ApplyOutcome("rejected", error=f"proposal_{stored.status}")
        if not stored.hash_matches():
            return stored, ApplyOutcome("failed", error="payload_mismatch")
        if stored.expired(datetime.now(UTC)):
            await self.store._finish(auth, proposal_id, "failed", {"error": "proposal_expired"})
            return stored, ApplyOutcome("expired", error="proposal_expired")
        if not await self.store.run_may_write(auth, run_id):
            return stored, ApplyOutcome("failed", error="run_not_active")
        return stored, None

    async def _applied(self, auth: AuthContext, pid: UUID, result: dict[str, Any]) -> ApplyOutcome:
        final = await self.store._finish(auth, pid, "applied", result)
        # A concurrent retry may have won the compare-and-set; both see the same result.
        return ApplyOutcome("applied", result=final.result if final and final.result else result)

    async def _failed(
        self, auth: AuthContext, pid: UUID, code: str, *, latest: int | None = None
    ) -> ApplyOutcome:
        await self.store._finish(auth, pid, "failed", {"error": code, "latestVersion": latest})
        return ApplyOutcome(
            "conflict" if latest is not None else "failed", error=code, latest_version=latest
        )


class SqlConfirmedEventWriter(_Writer):
    kind: ProposalKind = "case_event"

    def __init__(self, store: SqlProposalStore, incidents: Any) -> None:
        super().__init__(store)
        self.incidents = incidents

    async def apply(self, auth: AuthContext, *, proposal_id: UUID, run_id: UUID) -> ApplyOutcome:
        stored, early = await self._precheck(auth, proposal_id, run_id)
        if early is not None or stored is None:
            return early or ApplyOutcome("not_found", error="not_found")
        case_id = UUID(stored.payload["case_id"])
        event_id = event_id_for(stored.owner_id, stored.id)
        try:
            case = await self.incidents.get_case(auth, case_id)
        except NotFound:
            return await self._failed(auth, proposal_id, "case_not_found")
        already_written = any(e.id == event_id for e in case.events)
        # A retry after a crash finds its own event; only a first attempt can be stale.
        if (
            not already_written
            and stored.base_version is not None
            and case.version != stored.base_version
        ):
            return await self._failed(auth, proposal_id, "version_conflict", latest=case.version)
        event = stored.payload["event"]
        data = EventCreate(
            id=event_id,
            when=event["when"],
            time_precision=event["time_precision"],
            place=event["place"],
            description=event["description"],
            provenance="user_confirmed",
            evidence_ids=[UUID(i) for i in event["evidence_ids"]],
            needs_review=False,
        )
        try:
            saved = await self.incidents.add_confirmed_event(
                auth, case_id, data, proposal_id=proposal_id
            )
        except NotFound:
            return await self._failed(auth, proposal_id, "not_found")
        except ApiError as error:
            if error.status_code == 409:
                return await self._failed(auth, proposal_id, "conflict")
            raise
        return await self._applied(
            auth,
            proposal_id,
            {"eventId": str(saved.id), "caseId": str(case_id), "provenance": saved.provenance},
        )


class SqlPlanWriter(_Writer):
    kind: ProposalKind = "action_plan"

    def __init__(self, store: SqlProposalStore, plans: Any) -> None:
        super().__init__(store)
        self.plans = plans

    @staticmethod
    def _same_plan(current: Any, wanted: PlanUpsert) -> bool:
        return current.goal == wanted.goal and [
            (str(i.id), i.label, i.priority, i.reason) for i in current.items
        ] == [(str(i.id), i.label, i.priority, i.reason) for i in wanted.items]

    async def apply(self, auth: AuthContext, *, proposal_id: UUID, run_id: UUID) -> ApplyOutcome:
        stored, early = await self._precheck(auth, proposal_id, run_id)
        if early is not None or stored is None:
            return early or ApplyOutcome("not_found", error="not_found")
        case_id = UUID(stored.payload["case_id"])
        wanted = PlanUpsert.model_validate(stored.payload["plan"])
        try:
            saved = await self.plans.upsert(
                auth, case_id, wanted, expected_version=stored.base_version
            )
        except NotFound:
            return await self._failed(auth, proposal_id, "not_found")
        except ApiError as error:
            if error.code != "version_conflict":
                raise
            # Crash after the domain commit: the plan is already exactly what was approved.
            current = await self.plans.get_for_case(auth, case_id)
            if current is not None and self._same_plan(current, wanted):
                return await self._applied(
                    auth, proposal_id, {"planId": str(current.id), "version": current.version}
                )
            latest = current.version if current is not None else None
            return await self._failed(auth, proposal_id, "version_conflict", latest=latest or 0)
        return await self._applied(
            auth, proposal_id, {"planId": str(saved.id), "version": saved.version}
        )
