from fastapi import APIRouter, Depends, Path, Query, Request
from safevoice_shared.contracts.auth import AuthContext
from safevoice_shared.contracts.paging import Page

from app.core.auth import get_auth
from app.modules.knowledge_state.schemas import ArticleStatePut, ArticleStateRead
from app.modules.knowledge_state.service import KnowledgeStateService

router = APIRouter(prefix="/v1/knowledge/article-states", tags=["article state"])


def service(request: Request):
    return KnowledgeStateService(request.app.state.engine)


@router.get("", response_model=Page[ArticleStateRead])
async def list_states(
    limit: int = Query(50, ge=1, le=100),
    cursor: str | None = Query(None, max_length=2048),
    auth: AuthContext = Depends(get_auth),
    states: KnowledgeStateService = Depends(service),
):
    return await states.list(auth, limit=limit, cursor=cursor)


@router.put("/{articleId}", response_model=ArticleStateRead)
async def put_state(
    data: ArticleStatePut,
    articleId: str = Path(min_length=1, max_length=120),
    auth: AuthContext = Depends(get_auth),
    states: KnowledgeStateService = Depends(service),
):
    return await states.put(auth, articleId, data)
