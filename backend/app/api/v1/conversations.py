import asyncio
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Query, Request, Response
from fastapi.responses import StreamingResponse
from moodprint_shared.contracts.auth import AuthContext
from moodprint_shared.contracts.base import FrozenDTO
from moodprint_shared.contracts.conversations import ChatMessage, TurnHandle
from moodprint_shared.contracts.paging import Page
from moodprint_shared.contracts.streaming import make_event
from pydantic import Field

from app.agent_gateway.sse import RunStream, produce
from app.core.auth import get_auth
from app.core.errors import ApiError
from app.modules.conversations.approvals import ApprovalService
from app.modules.conversations.paging import FoundationPages
from app.modules.conversations.schemas import (
    SSE_RESPONSES,
    ConversationRead,
    RunCancelRead,
    RunRead,
)
from app.modules.conversations.service import ConversationService

router = APIRouter(prefix="/v1", tags=["conversations"])


def service(request: Request) -> ConversationService:
    runtime = getattr(request.app.state, "runtime", None)
    return ConversationService(
        request.app.state.engine,
        request.app.state.cfg,
        prompt_version=runtime.prompt_version if runtime else "companion_v1",
        tools_version=runtime.tools_version if runtime else "diagnostics_v1",
    )


class ConversationCreate(FrozenDTO):
    id: UUID
    title: str = Field(default="", max_length=120)
    linked_case_id: UUID | None = None
    source_article_id: str | None = None


class MessageCreate(FrozenDTO):
    client_message_id: UUID
    content: str = Field(min_length=1, max_length=4000)


class ApprovalDecision(FrozenDTO):
    decision: Literal["approve", "reject"]


def public_conversation(row):
    return {
        "id": row["id"],
        "ownerId": row["owner_id"],
        "title": row["title"],
        "linkedCaseId": row["linked_case_id"],
        "sourceArticleId": row["source_article_id"],
        "summary": row["summary"],
        "status": row["status"],
        "lastMessageAt": row["last_message_at"],
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
    }


def response_for(stream: RunStream):
    return StreamingResponse(
        stream.bytes(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"},
    )


def runtime_for(request: Request):
    runtime = getattr(request.app.state, "runtime", None)
    if runtime is None or (runtime.model is None and not request.app.state.settings.openai_api_key):
        raise ApiError("not_ready", "Trò chuyện AI chưa được cấu hình.", 503)
    return runtime


@router.post("/conversations", response_model=ConversationRead)
async def create(
    data: ConversationCreate,
    auth: AuthContext = Depends(get_auth),
    conversations: ConversationService = Depends(service),
):
    return public_conversation(
        await conversations.create(
            auth,
            data.id,
            data.title,
            linked_case_id=data.linked_case_id,
            source_article_id=data.source_article_id,
        )
    )


@router.get("/conversations", response_model=Page[ConversationRead])
async def listing(
    limit: int = Query(default=50, ge=1, le=100),
    cursor: str | None = Query(default=None, max_length=2048),
    auth: AuthContext = Depends(get_auth),
    conversations: ConversationService = Depends(service),
):
    return await FoundationPages(conversations.engine).conversations(
        auth, limit=limit, cursor=cursor
    )


@router.get("/conversations/{id}", response_model=ConversationRead)
async def get(
    id: UUID,
    auth: AuthContext = Depends(get_auth),
    conversations: ConversationService = Depends(service),
):
    return public_conversation(await conversations.get(auth, id))


@router.delete("/conversations/{id}", status_code=204)
async def delete(
    id: UUID,
    auth: AuthContext = Depends(get_auth),
    conversations: ConversationService = Depends(service),
):
    await conversations.delete(auth, id)
    return Response(status_code=204)


@router.get("/conversations/{id}/messages", response_model=Page[ChatMessage])
async def messages(
    id: UUID,
    limit: int = Query(default=50, ge=1, le=100),
    cursor: str | None = Query(default=None, max_length=2048),
    auth: AuthContext = Depends(get_auth),
    conversations: ConversationService = Depends(service),
):
    return await FoundationPages(conversations.engine).messages(
        auth, id, limit=limit, cursor=cursor
    )


@router.post(
    "/conversations/{id}/messages", response_class=StreamingResponse, responses=SSE_RESPONSES
)
async def send(
    id: UUID,
    data: MessageCreate,
    request: Request,
    auth: AuthContext = Depends(get_auth),
    conversations: ConversationService = Depends(service),
):
    runtime = runtime_for(request)
    turn = await conversations.begin_turn(auth, id, data.client_message_id, data.content)
    stream = RunStream()
    if turn.replay:
        result = turn.existing_result
        if result is None:
            raise ApiError("internal_error", "Chưa đọc được kết quả lượt trò chuyện.", 500)
        stream.publish(
            make_event(
                "message.completed",
                seq=1,
                run_id=turn.run_id,
                data={
                    "message_id": result.message_id or turn.message_id,
                    "content": result.content,
                    "citations": result.citations,
                    "structured": result.structured,
                },
            )
        )
        stream.publish(None)
    else:
        task = asyncio.create_task(
            produce(
                stream=stream,
                runtime=runtime,
                service=conversations,
                auth=auth,
                turn=turn,
                request_id=request.state.request_id,
                content=data.content,
                knowledge=getattr(request.app.state, "knowledge", None),
                storage=getattr(request.app.state, "storage", None),
            )
        )
        request.app.state.run_tasks.add(task)
        task.add_done_callback(request.app.state.run_tasks.discard)
    return response_for(stream)


@router.get("/runs/{id}", response_model=RunRead)
async def get_run(
    id: UUID,
    auth: AuthContext = Depends(get_auth),
    conversations: ConversationService = Depends(service),
):
    row = await conversations.get_run(auth, id)
    return {
        "id": row["id"],
        "conversationId": row["conversation_id"],
        "status": row["status"],
        "model": row["model"],
        "promptVersion": row["prompt_version"],
        "toolsVersion": row["tools_version"],
        "errorCode": row["error_code"],
        "usage": {
            "inputTokens": row["input_tokens"],
            "outputTokens": row["output_tokens"],
            "totalTokens": row["total_tokens"],
            "requests": row["request_count"],
            "toolCalls": row["tool_call_count"],
            "latencyMs": row["latency_ms"] or 0,
        },
    }


@router.post("/runs/{id}/cancel", response_model=RunCancelRead)
async def cancel(
    id: UUID,
    request: Request,
    auth: AuthContext = Depends(get_auth),
    conversations: ConversationService = Depends(service),
):
    run = await conversations.get_run(auth, id)
    if run["status"] == "running":
        request.app.state.runtime.cancel(id)
    return {"status": run["status"]}


@router.post(
    "/runs/{id}/approvals/{approvalId}", response_class=StreamingResponse, responses=SSE_RESPONSES
)
async def decide(
    id: UUID,
    data: ApprovalDecision,
    request: Request,
    approval_id: Annotated[UUID, Path(alias="approvalId")],
    auth: AuthContext = Depends(get_auth),
    conversations: ConversationService = Depends(service),
):
    runtime = runtime_for(request)
    row, message = await ApprovalService(conversations.engine).decide(
        auth, id, approval_id, data.decision == "approve"
    )
    turn = TurnHandle(
        run_id=id,
        conversation_id=row["conversation_id"],
        message_id=message["id"],
        client_message_id=message["client_message_id"],
    )
    stream = RunStream()
    task = asyncio.create_task(
        produce(
            stream=stream,
            runtime=runtime,
            service=conversations,
            auth=auth,
            turn=turn,
            request_id=request.state.request_id,
            content="",
            resume={**row, "approved": data.decision == "approve"},
            knowledge=getattr(request.app.state, "knowledge", None),
            storage=getattr(request.app.state, "storage", None),
        )
    )
    request.app.state.run_tasks.add(task)
    task.add_done_callback(request.app.state.run_tasks.discard)
    return response_for(stream)
