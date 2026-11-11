import json
from datetime import UTC, datetime
from uuid import UUID

from safevoice_shared.contracts.auth import AuthContext
from safevoice_shared.contracts.errors import NotFound, VersionConflict
from sqlalchemy import text

from app.core.uow import user_uow


class ApprovalService:
    def __init__(self, engine):
        self.engine = engine

    async def save(self, auth: AuthContext, checkpoints):
        async with user_uow(self.engine, auth) as uow:
            for checkpoint in checkpoints:
                await uow.session.execute(
                    text("""INSERT INTO app.tool_approvals(id,run_id,owner_id,tool_name,tool_call_id,arguments_preview,run_state,expires_at)
                    VALUES(:id,:run,:owner,:tool,:call,CAST(:preview AS jsonb),:state,:expires)
                    ON CONFLICT(run_id,tool_call_id) DO NOTHING"""),
                    {
                        "id": checkpoint.id,
                        "run": checkpoint.run_id,
                        "owner": auth.user_id,
                        "tool": checkpoint.tool,
                        "call": checkpoint.tool_call_id,
                        "preview": json.dumps(checkpoint.preview, ensure_ascii=False),
                        "state": checkpoint.serialized_state,
                        "expires": checkpoint.expires_at,
                    },
                )

    @staticmethod
    async def _bind_proposal(session, auth: AuthContext, approval, approved: bool) -> None:
        """Atomically tie this decision to the stored proposal it was shown for.

        The proposal id comes from the approval preview the *server* built, never from the
        model's arguments. In the same transaction as the tool approval we record approve/reject
        on the proposal; an approve that no longer matches (expired, already decided, preview or
        hash changed) aborts the whole decision, so a stale dialog can never authorise a write.
        """
        preview = approval["arguments_preview"]
        if isinstance(preview, (str, bytes)):
            preview = json.loads(preview)
        proposal_id = (preview or {}).get("proposalId") if isinstance(preview, dict) else None
        if not proposal_id:
            return  # not a proposal-backed tool (for example a diagnostic write)
        params = {
            "pid": UUID(str(proposal_id)),
            "owner": auth.user_id,
            "run": approval["run_id"],
            "approval": approval["id"],
            "call": approval["tool_call_id"],
            "approval_s": str(approval["id"]),
            "call_s": str(approval["tool_call_id"]),
            "run_s": str(approval["run_id"]),
            "owner_s": str(auth.user_id),
        }
        if approved:
            bound = await session.scalar(
                text(
                    """UPDATE app.agent_proposals p SET status='approved',decided_at=now(),
                    approval_binding=jsonb_build_object('decision','approve','approval_id',CAST(:approval_s AS text),
                      'tool_call_id',CAST(:call_s AS text),'run_id',CAST(:run_s AS text),
                      'owner_id',CAST(:owner_s AS text),'payload_sha256',p.payload_sha256)
                    WHERE p.id=:pid AND p.owner_id=:owner AND p.status='proposed'
                      AND p.approval_binding IS NULL AND p.expires_at>clock_timestamp()
                      AND p.conversation_id=(SELECT conversation_id FROM app.agent_runs
                                             WHERE id=:run AND owner_id=:owner)
                      AND (CAST(:shown AS jsonb)-'proposalId'-'expiresAt')=p.preview
                    RETURNING p.id"""
                ),
                {**params, "shown": json.dumps(preview, ensure_ascii=False)},
            )
            if bound is None:
                raise VersionConflict()
        else:
            await session.execute(
                text(
                    """UPDATE app.agent_proposals SET status='rejected',decided_at=now()
                    WHERE id=:pid AND owner_id=:owner AND status='proposed'"""
                ),
                params,
            )

    async def decide(self, auth: AuthContext, run_id: UUID, approval_id: UUID, approved: bool):
        async with user_uow(self.engine, auth) as uow:
            params = {"id": approval_id, "run": run_id, "owner": auth.user_id}
            row = (
                (
                    await uow.session.execute(
                        text(
                            "SELECT a.*,r.conversation_id,r.status AS run_status FROM app.tool_approvals a JOIN app.agent_runs r ON r.id=a.run_id AND r.owner_id=a.owner_id WHERE a.id=:id AND a.run_id=:run AND a.owner_id=:owner FOR UPDATE OF a,r"
                        ),
                        params,
                    )
                )
                .mappings()
                .first()
            )
            if not row:
                raise NotFound()
            if (
                row["status"] != "pending"
                or row["run_status"] != "awaiting_approval"
                or row["expires_at"] <= datetime.now(UTC)
            ):
                raise VersionConflict()
            await uow.session.execute(
                text(
                    "UPDATE app.tool_approvals SET status=:status,decided_at=now() WHERE id=:id AND owner_id=:owner"
                ),
                {**params, "status": "approved" if approved else "rejected"},
            )
            await self._bind_proposal(uow.session, auth, row, approved)
            await uow.session.execute(
                text(
                    "UPDATE app.agent_runs SET status='running',heartbeat_at=now() WHERE id=:run AND owner_id=:owner"
                ),
                params,
            )
            message = (
                (
                    await uow.session.execute(
                        text(
                            "SELECT id,client_message_id FROM app.messages WHERE run_id=:run AND owner_id=:owner AND role='user'"
                        ),
                        params,
                    )
                )
                .mappings()
                .one()
            )
            return dict(row), dict(message)

    async def pending(self, auth: AuthContext, run_id: UUID) -> list[dict]:
        """Approvals still open for this run, so a reloaded page can show the dialog again."""
        async with user_uow(self.engine, auth) as uow:
            run = await uow.session.scalar(
                text("SELECT status FROM app.agent_runs WHERE id=:run AND owner_id=:owner"),
                {"run": run_id, "owner": auth.user_id},
            )
            if run is None:
                raise NotFound()
            rows = (
                (
                    await uow.session.execute(
                        text(
                            "SELECT id,run_id,tool_name,tool_call_id,arguments_preview,expires_at,status "
                            "FROM app.tool_approvals WHERE run_id=:run AND owner_id=:owner "
                            "AND status='pending' AND expires_at>now() ORDER BY created_at,id"
                        ),
                        {"run": run_id, "owner": auth.user_id},
                    )
                )
                .mappings()
                .all()
            )
        out: list[dict] = []
        for row in rows:
            preview = row["arguments_preview"]
            out.append(
                {
                    "id": row["id"],
                    "run_id": row["run_id"],
                    "tool": row["tool_name"],
                    "tool_call_id": row["tool_call_id"],
                    "preview": json.loads(preview)
                    if isinstance(preview, (str, bytes))
                    else preview,
                    "expires_at": row["expires_at"],
                    "status": row["status"],
                }
            )
        return out

    async def cancel_waiting(self, auth: AuthContext, run_id: UUID) -> str:
        """Cancel a run that is waiting for the user: nothing proposed will ever be applied."""
        async with user_uow(self.engine, auth) as uow:
            params = {"run": run_id, "owner": auth.user_id}
            status = await uow.session.scalar(
                text(
                    "SELECT status FROM app.agent_runs WHERE id=:run AND owner_id=:owner FOR UPDATE"
                ),
                params,
            )
            if status is None:
                raise NotFound()
            if status != "awaiting_approval":
                return str(status)
            await uow.session.execute(
                text(
                    "UPDATE app.tool_approvals SET status='expired',decided_at=now() "
                    "WHERE run_id=:run AND owner_id=:owner AND status='pending'"
                ),
                params,
            )
            await uow.session.execute(
                text(
                    "UPDATE app.agent_proposals SET status='expired',decided_at=now() "
                    "WHERE run_id=:run AND owner_id=:owner AND status='proposed'"
                ),
                params,
            )
            await uow.session.execute(
                text(
                    "UPDATE app.agent_runs SET status='cancelled',finished_at=now() "
                    "WHERE id=:run AND owner_id=:owner AND status='awaiting_approval'"
                ),
                params,
            )
            return "cancelled"
