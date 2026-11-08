"""Practice sessions: create, read, finish with coach feedback, leave. Every row is owner-scoped."""

import asyncio
import json
from typing import Any
from uuid import UUID, uuid4, uuid5

from moodprint_agent.roleplay.feedback import FeedbackFailed, RoleplayCoach
from moodprint_agent.roleplay.models import RoleplayContext, RoleplayFeedback
from moodprint_agent.roleplay.scenarios import SCENARIOS, Scenario, scenario_for
from moodprint_shared.config import AppConfig
from moodprint_shared.contracts.auth import AuthContext
from moodprint_shared.contracts.errors import NotFound
from openai import AsyncOpenAI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.errors import ApiError
from app.core.uow import user_uow
from app.modules.roleplay.schemas import FeedbackRead, RoleplayCreate, RoleplayRead, ScenarioRead

CONVERSATION_NAMESPACE = UUID("6f1c9c1e-6d0b-4d9a-9a52-4d6f6f6f7004")
_COLUMNS = (
    "id,conversation_id,role,scenario_key,scenario_context,user_goal,difficulty,age_band,"
    "use_case_context,linked_case_id,status,turn_count,safety_locked,feedback,created_at,"
    "completed_at"
)
_FEEDBACK_LOCKS: dict[UUID, asyncio.Lock] = {}


def scenarios() -> list[ScenarioRead]:
    return [
        ScenarioRead(
            key=s.key, role=s.role, title=s.title, context=s.context, default_goal=s.default_goal
        )
        for s in SCENARIOS
    ]


def _json(value: Any) -> Any:
    return json.loads(value) if isinstance(value, (str, bytes)) else value


class RoleplayService:
    def __init__(
        self, engine: AsyncEngine, cfg: AppConfig, client: AsyncOpenAI | None = None
    ) -> None:
        self.engine, self.cfg, self.client = engine, cfg, client

    def _read(self, row: Any) -> RoleplayRead:
        scenario = scenario_for(row["scenario_key"])
        feedback = _json(row["feedback"])
        return RoleplayRead(
            id=row["id"],
            conversation_id=row["conversation_id"],
            role=row["role"],
            scenario_key=row["scenario_key"],
            scenario_title=scenario.title if scenario else row["scenario_key"],
            scenario_context=row["scenario_context"],
            user_goal=row["user_goal"],
            difficulty=row["difficulty"],
            use_case_context=row["use_case_context"],
            linked_case_id=row["linked_case_id"],
            status=row["status"],
            turn_count=row["turn_count"],
            max_turns=self.cfg.agent.roleplay_max_turns,
            safety_locked=row["safety_locked"],
            feedback=FeedbackRead.model_validate(feedback) if feedback else None,
            created_at=row["created_at"],
            completed_at=row["completed_at"],
        )

    async def _row(self, session: Any, auth: AuthContext, session_id: UUID, *, lock: bool = False):
        row = (
            (
                await session.execute(
                    text(
                        f"SELECT {_COLUMNS} FROM app.roleplay_sessions "
                        f"WHERE id=:id AND owner_id=:owner{' FOR UPDATE' if lock else ''}"
                    ),
                    {"id": session_id, "owner": auth.user_id},
                )
            )
            .mappings()
            .first()
        )
        if row is None:
            raise NotFound()
        return row

    # -- create ------------------------------------------------------------------------------
    async def create(
        self, auth: AuthContext, body: RoleplayCreate, *, age_band: str | None, case_exists: bool
    ) -> RoleplayRead:
        scenario: Scenario | None = scenario_for(body.scenario_key)
        if scenario is None or scenario.role != body.role:
            raise ApiError("validation_failed", "Kịch bản hoặc vai không hợp lệ.", 422)
        if body.use_case_context and (body.linked_case_id is None or not case_exists):
            raise ApiError("validation_failed", "Cần chọn một hồ sơ của bạn để dùng tóm tắt.", 422)
        if not body.use_case_context and body.linked_case_id is not None:
            raise ApiError(
                "validation_failed", "Chỉ liên kết hồ sơ khi bạn chọn dùng tóm tắt hồ sơ.", 422
            )
        goal = body.user_goal.strip() or scenario.default_goal
        conversation_id = uuid5(CONVERSATION_NAMESPACE, f"{auth.user_id}:{body.id}")
        async with user_uow(self.engine, auth) as uow:
            session = uow.session
            await session.execute(
                text(
                    "INSERT INTO app.conversations(id,owner_id,title) VALUES(:c,:owner,:title) "
                    "ON CONFLICT(id) DO NOTHING"
                ),
                {"c": conversation_id, "owner": auth.user_id, "title": scenario.title[:120]},
            )
            await session.execute(
                text(
                    "INSERT INTO app.roleplay_sessions(id,owner_id,conversation_id,role,"
                    "scenario_key,scenario_context,user_goal,difficulty,age_band,use_case_context,"
                    "linked_case_id) VALUES(:id,:owner,:c,:role,:key,:context,:goal,:difficulty,"
                    ":age,:use_case,:case) ON CONFLICT(id) DO NOTHING"
                ),
                {
                    "id": body.id,
                    "owner": auth.user_id,
                    "c": conversation_id,
                    "role": body.role,
                    "key": scenario.key,
                    "context": scenario.context,
                    "goal": goal,
                    "difficulty": body.difficulty,
                    "age": age_band,
                    "use_case": body.use_case_context,
                    "case": body.linked_case_id,
                },
            )
            row = await self._row(session, auth, body.id)
        same = (
            row["role"] == body.role
            and row["scenario_key"] == scenario.key
            and row["user_goal"] == goal
            and row["difficulty"] == body.difficulty
            and row["use_case_context"] == body.use_case_context
            and row["linked_case_id"] == body.linked_case_id
        )
        if not same:
            raise ApiError("request_conflict", "Mã phiên này đã dùng cho một buổi khác.", 409)
        return self._read(row)

    # -- read --------------------------------------------------------------------------------
    async def get(self, auth: AuthContext, session_id: UUID) -> RoleplayRead:
        async with user_uow(self.engine, auth) as uow:
            return self._read(await self._row(uow.session, auth, session_id))

    async def list(self, auth: AuthContext, *, limit: int = 20) -> list[RoleplayRead]:
        async with user_uow(self.engine, auth) as uow:
            rows = (
                (
                    await uow.session.execute(
                        text(
                            f"SELECT {_COLUMNS} FROM app.roleplay_sessions WHERE owner_id=:owner "
                            "ORDER BY created_at DESC LIMIT :n"
                        ),
                        {"owner": auth.user_id, "n": max(1, min(limit, 50))},
                    )
                )
                .mappings()
                .all()
            )
        return [self._read(row) for row in rows]

    async def context_for(
        self, auth: AuthContext, conversation_id: UUID, *, case_summary: str | None = None
    ) -> RoleplayContext | None:
        """The persona for this conversation, or None when it is an ordinary chat."""
        async with user_uow(self.engine, auth) as uow:
            row = (
                (
                    await uow.session.execute(
                        text(
                            f"SELECT {_COLUMNS} FROM app.roleplay_sessions "
                            "WHERE conversation_id=:c AND owner_id=:owner"
                        ),
                        {"c": conversation_id, "owner": auth.user_id},
                    )
                )
                .mappings()
                .first()
            )
        if row is None:
            return None
        scenario = scenario_for(row["scenario_key"])
        return RoleplayContext(
            role=row["role"],
            scenario_key=row["scenario_key"],
            scenario_title=scenario.title if scenario else row["scenario_key"],
            scenario_context=row["scenario_context"],
            user_goal=row["user_goal"],
            difficulty=row["difficulty"],
            age_band=row["age_band"],
            case_summary=case_summary if row["use_case_context"] else None,
            safety_locked=row["safety_locked"],
        )

    async def linked_case(self, auth: AuthContext, conversation_id: UUID) -> UUID | None:
        async with user_uow(self.engine, auth) as uow:
            value = await uow.session.scalar(
                text(
                    "SELECT linked_case_id FROM app.roleplay_sessions "
                    "WHERE conversation_id=:c AND owner_id=:owner AND use_case_context"
                ),
                {"c": conversation_id, "owner": auth.user_id},
            )
        return value

    # -- finish ------------------------------------------------------------------------------
    async def complete(self, auth: AuthContext, session_id: UUID) -> RoleplayRead:
        lock = _FEEDBACK_LOCKS.setdefault(session_id, asyncio.Lock())
        try:
            async with lock:  # one coach call per session at a time (single worker)
                return await self._complete(auth, session_id)
        finally:
            if not lock.locked():
                _FEEDBACK_LOCKS.pop(session_id, None)

    async def _complete(self, auth: AuthContext, session_id: UUID) -> RoleplayRead:
        async with user_uow(self.engine, auth) as uow:
            row = await self._row(uow.session, auth, session_id)
            if row["status"] == "completed":
                return self._read(row)
            if row["status"] == "abandoned":
                raise ApiError("roleplay_abandoned", "Buổi diễn tập này đã được kết thúc.", 409)
            if row["turn_count"] < 1:
                raise ApiError(
                    "roleplay_no_turns",
                    "Hãy trò chuyện ít nhất một lượt trước khi nhận phản hồi.",
                    409,
                )
            messages = (
                (
                    await uow.session.execute(
                        text(
                            "SELECT role,content FROM app.messages WHERE conversation_id=:c "
                            "AND owner_id=:owner AND role IN ('user','assistant') "
                            "ORDER BY created_at,id"
                        ),
                        {"c": row["conversation_id"], "owner": auth.user_id},
                    )
                )
                .mappings()
                .all()
            )
        if self.client is None:
            raise ApiError("not_ready", "Tính năng AI chưa được cấu hình.", 503)
        transcript = [
            ("user" if m["role"] == "user" else "partner", m["content"]) for m in messages
        ]
        scenario = scenario_for(row["scenario_key"])
        context = RoleplayContext(
            role=row["role"],
            scenario_key=row["scenario_key"],
            scenario_title=scenario.title if scenario else row["scenario_key"],
            scenario_context=row["scenario_context"],
            user_goal=row["user_goal"],
            difficulty=row["difficulty"],
            age_band=row["age_band"],
        )
        try:
            output = await RoleplayCoach(self.client, self.cfg).feedback(context, transcript)
        except FeedbackFailed as failure:
            raise ApiError(
                failure.code, "Chưa tạo được phản hồi. Bạn có thể thử lại.", 502
            ) from None
        feedback: RoleplayFeedback = output.feedback
        async with user_uow(self.engine, auth) as uow:
            # Compare-and-set: the first completion wins; a racing one returns what was stored.
            await uow.session.execute(
                text(
                    "UPDATE app.roleplay_sessions SET status='completed',completed_at=now(),"
                    "feedback=CAST(:feedback AS jsonb) "
                    "WHERE id=:id AND owner_id=:owner AND status='active'"
                ),
                {
                    "id": session_id,
                    "owner": auth.user_id,
                    "feedback": feedback.model_dump_json(),
                },
            )
            await uow.session.execute(
                text(
                    "INSERT INTO app.audit_events(actor_id,action,entity_type,entity_id,metadata) "
                    "VALUES(:owner,'roleplay.feedback_generated','roleplay_session',:id,"
                    "CAST(:meta AS jsonb))"
                ),
                {
                    "owner": auth.user_id,
                    "id": session_id,
                    "meta": json.dumps({"usage": output.usage, "id": uuid4().hex}),
                },
            )
            return self._read(await self._row(uow.session, auth, session_id))

    async def abandon(self, auth: AuthContext, session_id: UUID) -> RoleplayRead:
        async with user_uow(self.engine, auth) as uow:
            await self._row(uow.session, auth, session_id)
            await uow.session.execute(
                text(
                    "UPDATE app.roleplay_sessions SET status='abandoned',completed_at=now() "
                    "WHERE id=:id AND owner_id=:owner AND status='active'"
                ),
                {"id": session_id, "owner": auth.user_id},
            )
            return self._read(await self._row(uow.session, auth, session_id))

    async def lock_for_safety(self, auth: AuthContext, conversation_id: UUID) -> None:
        async with user_uow(self.engine, auth) as uow:
            await uow.session.execute(
                text(
                    "UPDATE app.roleplay_sessions SET safety_locked=true "
                    "WHERE conversation_id=:c AND owner_id=:owner AND status='active'"
                ),
                {"c": conversation_id, "owner": auth.user_id},
            )
