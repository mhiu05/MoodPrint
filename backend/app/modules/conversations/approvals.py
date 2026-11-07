import json
from datetime import UTC, datetime
from uuid import UUID

from moodprint_shared.contracts.auth import AuthContext
from moodprint_shared.contracts.errors import NotFound, VersionConflict
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
