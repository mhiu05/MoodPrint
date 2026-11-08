"""Authenticated Knowledge Hub routes."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Query, Request
from moodprint_shared.contracts.auth import AuthContext

from app.core.auth import get_auth
from app.core.errors import ApiError
from app.modules.knowledge.ratelimit import LIMITER
from app.modules.knowledge.schemas import CorpusRead, DocumentRead, SearchRead, SourceList
from app.modules.knowledge.service import KnowledgeService, parse_age, parse_topic

router = APIRouter(prefix="/v1/knowledge", tags=["knowledge"])
log = logging.getLogger("moodprint.knowledge.http")


def _service(request: Request) -> KnowledgeService:
    return KnowledgeService(
        request.app.state.engine, request.app.state.knowledge, request.app.state.cfg
    )


@router.get("/search", response_model=SearchRead)
async def search_knowledge(
    request: Request,
    q: str = Query(default=""),
    topic: str | None = None,
    age: str | None = None,
    language: str = "vi",
    limit: int = Query(default=5),
    auth: AuthContext = Depends(get_auth),
) -> SearchRead:
    if not LIMITER.allow(str(auth.user_id)) or LIMITER.gate.locked():
        raise ApiError("rate_limited", "Bạn đang tìm quá nhanh. Hãy thử lại sau.", 429)
    async with LIMITER.gate:
        return await _service(request).search(
            q=q,
            topic=parse_topic(topic),
            age=parse_age(age),
            language=language,
            limit=limit,
            request_id=getattr(request.state, "request_id", ""),
        )


@router.get("/documents/{document_id}", response_model=DocumentRead)
async def read_document(
    document_id: str,
    request: Request,
    auth: AuthContext = Depends(get_auth),
) -> DocumentRead:
    del auth
    return await _service(request).document(document_id)


@router.get("/sources", response_model=SourceList)
async def read_sources(request: Request, auth: AuthContext = Depends(get_auth)) -> SourceList:
    del auth
    return SourceList(await _service(request).sources())


@router.get("/corpus", response_model=CorpusRead)
async def read_corpus(request: Request, auth: AuthContext = Depends(get_auth)) -> CorpusRead:
    del auth
    return await _service(request).corpus()
