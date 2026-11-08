import json
from uuid import UUID, uuid4

from moodprint_agent.memory.session import make_session, repair_session
from moodprint_shared.config import AppConfig
from moodprint_shared.contracts.agent import CompanionTurn
from moodprint_shared.contracts.auth import AuthContext
from moodprint_shared.contracts.conversations import ChatMessage, TurnHandle, TurnResult
from moodprint_shared.contracts.errors import NotFound, RunInProgress
from moodprint_shared.contracts.knowledge import SourceCitation
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.errors import ApiError
from app.core.uow import user_uow
from app.modules.memory.service import dto


class ConversationService:
    def __init__(
        self,
        engine: AsyncEngine,
        cfg: AppConfig | None = None,
        *,
        prompt_version="companion_v1",
        tools_version="diagnostics_v1",
    ):
        self.engine, self.cfg = engine, cfg or AppConfig()
        self.prompt_version, self.tools_version = prompt_version, tools_version

    async def create(
        self,
        auth: AuthContext,
        id: UUID,
        title: str = "",
        *,
        linked_case_id: UUID | None = None,
        source_article_id: str | None = None,
    ):
        async with user_uow(self.engine, auth) as uow:
            params = {
                "id": id,
                "owner": auth.user_id,
                "title": title,
                "case": linked_case_id,
                "article": source_article_id,
            }
            # Phase 0 has no case service: do not accept an unvalidated domain link.
            if linked_case_id is not None:
                raise ApiError("validation_failed", "Liên kết hồ sơ chưa khả dụng.", 422)
            await uow.session.execute(
                text(
                    "INSERT INTO app.conversations(id,owner_id,title,source_article_id) VALUES(:id,:owner,:title,:article) ON CONFLICT(id) DO NOTHING"
                ),
                params,
            )
        return await self.get(auth, id)

    async def get(self, auth: AuthContext, id: UUID):
        async with user_uow(self.engine, auth) as uow:
            row = (
                (
                    await uow.session.execute(
                        text("SELECT * FROM app.conversations WHERE id=:id AND owner_id=:owner"),
                        {"id": id, "owner": auth.user_id},
                    )
                )
                .mappings()
                .first()
            )
            if not row:
                raise NotFound()
            return dict(row)

    async def list_conversations(self, auth: AuthContext, limit: int = 50):
        async with user_uow(self.engine, auth) as uow:
            return [
                dict(row)
                for row in (
                    await uow.session.execute(
                        text(
                            "SELECT * FROM app.conversations WHERE owner_id=:owner ORDER BY last_message_at DESC NULLS LAST,id LIMIT :limit"
                        ),
                        {"owner": auth.user_id, "limit": limit},
                    )
                ).mappings()
            ]

    async def begin_turn(
        self, auth: AuthContext, conversation_id: UUID, client_message_id: UUID, content: str
    ) -> TurnHandle:
        if not content.strip() or len(content) > self.cfg.agent.max_user_input_chars:
            raise ApiError("validation_failed", "Vui lòng kiểm tra độ dài tin nhắn.", 422)
        params = {
            "conversation": conversation_id,
            "owner": auth.user_id,
            "client": client_message_id,
        }
        async with user_uow(self.engine, auth) as uow:
            conversation = await uow.session.scalar(
                text(
                    "SELECT id FROM app.conversations WHERE id=:conversation AND owner_id=:owner AND status='active' FOR UPDATE"
                ),
                params,
            )
            if conversation is None:
                raise NotFound()
            existing = (
                (
                    await uow.session.execute(
                        text(
                            "SELECT m.id,m.run_id,r.status FROM app.messages m JOIN app.agent_runs r ON r.id=m.run_id AND r.owner_id=m.owner_id WHERE m.conversation_id=:conversation AND m.owner_id=:owner AND m.client_message_id=:client"
                        ),
                        params,
                    )
                )
                .mappings()
                .first()
            )
            if existing:
                if existing["status"] in ("running", "awaiting_approval"):
                    raise RunInProgress()
                answer = (
                    (
                        await uow.session.execute(
                            text(
                                "SELECT * FROM app.messages WHERE run_id=:run AND owner_id=:owner AND role='assistant' ORDER BY created_at DESC LIMIT 1"
                            ),
                            {"run": existing["run_id"], "owner": auth.user_id},
                        )
                    )
                    .mappings()
                    .first()
                )
                return TurnHandle(
                    run_id=existing["run_id"],
                    conversation_id=conversation_id,
                    message_id=existing["id"],
                    client_message_id=client_message_id,
                    replay=True,
                    existing_result=await self._stored_result(uow.session, auth, existing, answer),
                )
            active = await uow.session.scalar(
                text(
                    "SELECT id FROM app.agent_runs WHERE conversation_id=:conversation AND owner_id=:owner AND status IN ('running','awaiting_approval')"
                ),
                params,
            )
            if active:
                raise RunInProgress()
            count = await uow.session.scalar(
                text(
                    "SELECT count(*) FROM app.agent_runs WHERE owner_id=:owner AND started_at>now()-interval '1 hour'"
                ),
                params,
            )
            if count >= self.cfg.agent.messages_per_user_per_hour:
                raise ApiError(
                    "rate_limited", "Bạn đã gửi nhiều tin nhắn. Vui lòng thử lại sau.", 429
                )
            spent_today = await uow.session.scalar(
                text(
                    "SELECT COALESCE(sum(total_tokens),0) FROM app.agent_runs WHERE owner_id=:owner "
                    "AND started_at>=date_trunc('day', now() AT TIME ZONE 'UTC') AT TIME ZONE 'UTC'"
                ),
                params,
            )
            if spent_today >= self.cfg.agent.daily_token_cap_per_user:
                raise ApiError(
                    "quota_exceeded",
                    "Hôm nay bạn đã dùng hết lượt trò chuyện với AI. Hãy quay lại vào ngày mai.",
                    429,
                    details={"kind": "ai_tokens"},
                )
            run_id, message_id = uuid4(), uuid4()
            await uow.session.execute(
                text(
                    "INSERT INTO app.agent_runs(id,conversation_id,owner_id,status,model,prompt_version,tools_version) VALUES(:id,:conversation,:owner,'running',:model,:prompt,:tools)"
                ),
                {
                    **params,
                    "id": run_id,
                    "model": self.cfg.agent.companion_model,
                    "prompt": self.prompt_version,
                    "tools": self.tools_version,
                },
            )
            await uow.session.execute(
                text(
                    "INSERT INTO app.messages(id,conversation_id,owner_id,role,content,client_message_id,run_id) VALUES(:id,:conversation,:owner,'user',:content,:client,:run)"
                ),
                {**params, "id": message_id, "content": content, "run": run_id},
            )
            await uow.session.execute(
                text(
                    "UPDATE app.conversations SET last_message_at=now() WHERE id=:conversation AND owner_id=:owner"
                ),
                params,
            )
            return TurnHandle(
                run_id=run_id,
                conversation_id=conversation_id,
                message_id=message_id,
                client_message_id=client_message_id,
            )

    @staticmethod
    async def _stored_result(session, auth: AuthContext, run, answer) -> TurnResult:
        """Rebuild a finished turn exactly as it was stored: text, citations, structured output."""
        if not answer:
            return TurnResult(status=run["status"])
        raw = answer["citations"]
        citations = [
            SourceCitation.model_validate(c)
            for c in (json.loads(raw) if isinstance(raw, str) else raw)
        ]
        stored = await session.scalar(
            text(
                "SELECT structured FROM app.message_assessments WHERE message_id=:id AND owner_id=:owner"
            ),
            {"id": answer["id"], "owner": auth.user_id},
        )
        structured = None
        if stored is not None:
            structured = CompanionTurn.model_validate(
                json.loads(stored) if isinstance(stored, str) else stored
            )
        return TurnResult(
            status=run["status"],
            content=answer["content"],
            message_id=answer["id"],
            citations=citations,
            structured=structured,
        )

    async def recent_user_messages(
        self, auth: AuthContext, conversation_id: UUID, *, limit: int = 3
    ) -> list[str]:
        """The user's previous messages, oldest first, excluding the one just sent."""
        async with user_uow(self.engine, auth) as uow:
            rows = await uow.session.scalars(
                text(
                    "SELECT content FROM app.messages WHERE conversation_id=:c AND owner_id=:o AND role='user' "
                    "ORDER BY created_at DESC OFFSET 1 LIMIT :n"
                ),
                {"c": conversation_id, "o": auth.user_id, "n": limit},
            )
            return list(reversed(list(rows)))

    async def finish_turn(self, auth: AuthContext, turn: TurnHandle, result: TurnResult) -> None:
        async with user_uow(self.engine, auth) as uow:
            params = {
                "id": turn.run_id,
                "owner": auth.user_id,
                "conversation": turn.conversation_id,
            }
            row = (
                (
                    await uow.session.execute(
                        text(
                            "SELECT status FROM app.agent_runs WHERE id=:id AND owner_id=:owner AND conversation_id=:conversation FOR UPDATE"
                        ),
                        params,
                    )
                )
                .mappings()
                .first()
            )
            if not row:
                raise NotFound()
            if row["status"] not in ("running", "awaiting_approval"):
                return
            usage = result.usage
            await uow.session.execute(
                text("""UPDATE app.agent_runs SET status=:status,input_tokens=:input,
                output_tokens=:output,total_tokens=:total,request_count=:requests,
                tool_call_count=:tools,latency_ms=:latency,error_code=:error,
                heartbeat_at=now(),finished_at=CASE WHEN :status='awaiting_approval' THEN NULL ELSE now() END
                WHERE id=:id AND owner_id=:owner"""),
                {
                    **params,
                    "status": result.status,
                    "input": usage.input_tokens,
                    "output": usage.output_tokens,
                    "total": usage.total_tokens,
                    "requests": usage.requests,
                    "tools": usage.tool_calls,
                    "latency": usage.latency_ms,
                    "error": result.error_code,
                },
            )
            assistant_id = result.message_id or uuid4()
            if result.status in ("completed", "cancelled") and result.content:
                await uow.session.execute(
                    text(
                        "INSERT INTO app.messages(id,conversation_id,owner_id,role,content,run_id,citations) VALUES(:message,:conversation,:owner,'assistant',:content,:id,CAST(:citations AS jsonb)) ON CONFLICT(id) DO NOTHING"
                    ),
                    {
                        **params,
                        "message": assistant_id,
                        "content": result.content,
                        "citations": json.dumps(
                            [c.model_dump(mode="json", by_alias=True) for c in result.citations]
                        ),
                    },
                )
                if result.structured is not None:
                    await uow.session.execute(
                        text(
                            "INSERT INTO app.message_assessments(message_id,owner_id,run_id,structured) "
                            "VALUES(:message,:owner,:id,CAST(:structured AS jsonb)) "
                            "ON CONFLICT(message_id) DO NOTHING"
                        ),
                        {
                            **params,
                            "message": assistant_id,
                            "structured": result.structured.model_dump_json(),
                        },
                    )
            await uow.session.execute(
                text(
                    "UPDATE app.conversations SET last_message_at=now() WHERE id=:conversation AND owner_id=:owner"
                ),
                params,
            )

    async def open_session(self, auth: AuthContext, conversation_id: UUID):
        await self.get(auth, conversation_id)
        session = make_session(conversation_id, self.engine, self.cfg)
        async with user_uow(self.engine, auth) as uow:
            interrupted = await uow.session.scalar(
                text(
                    "SELECT id FROM app.agent_runs WHERE conversation_id=:id AND owner_id=:owner AND status='interrupted' LIMIT 1"
                ),
                {"id": conversation_id, "owner": auth.user_id},
            )
        if interrupted:
            await repair_session(session)
        return session

    async def recent_messages(
        self, auth: AuthContext, conversation_id: UUID, limit: int
    ) -> list[ChatMessage]:
        await self.get(auth, conversation_id)
        async with user_uow(self.engine, auth) as uow:
            rows = (
                await uow.session.execute(
                    text(
                        "SELECT * FROM (SELECT * FROM app.messages WHERE conversation_id=:id AND owner_id=:owner ORDER BY created_at DESC,id DESC LIMIT :limit) recent ORDER BY created_at,id"
                    ),
                    {"id": conversation_id, "owner": auth.user_id, "limit": limit},
                )
            ).mappings()
            return [dto(ChatMessage, row) for row in rows]

    async def get_run(self, auth: AuthContext, run_id: UUID):
        async with user_uow(self.engine, auth) as uow:
            row = (
                (
                    await uow.session.execute(
                        text("SELECT * FROM app.agent_runs WHERE id=:id AND owner_id=:owner"),
                        {"id": run_id, "owner": auth.user_id},
                    )
                )
                .mappings()
                .first()
            )
            if not row:
                raise NotFound()
            return dict(row)

    async def heartbeat(self, auth: AuthContext, run_id: UUID):
        async with user_uow(self.engine, auth) as uow:
            await uow.session.execute(
                text(
                    "UPDATE app.agent_runs SET heartbeat_at=now() WHERE id=:id AND owner_id=:owner AND status='running'"
                ),
                {"id": run_id, "owner": auth.user_id},
            )

    async def delete(self, auth: AuthContext, conversation_id: UUID):
        await self.get(auth, conversation_id)
        async with user_uow(self.engine, auth) as uow:
            active = await uow.session.scalar(
                text(
                    "SELECT id FROM app.agent_runs WHERE conversation_id=:id AND owner_id=:owner AND status IN ('running','awaiting_approval')"
                ),
                {"id": conversation_id, "owner": auth.user_id},
            )
            if active:
                raise RunInProgress()
            await uow.session.execute(
                text(
                    "UPDATE app.conversations SET status='archived' WHERE id=:id AND owner_id=:owner"
                ),
                {"id": conversation_id, "owner": auth.user_id},
            )
        await make_session(conversation_id, self.engine, self.cfg).clear_session()
        async with self.engine.begin() as connection:
            await connection.execute(
                text("DELETE FROM agent_store.agent_sessions WHERE session_id=:id"),
                {"id": str(conversation_id)},
            )
        async with user_uow(self.engine, auth) as uow:
            await uow.session.execute(
                text("DELETE FROM app.conversations WHERE id=:id AND owner_id=:owner"),
                {"id": conversation_id, "owner": auth.user_id},
            )
