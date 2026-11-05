from typing import Literal

from fastapi import APIRouter, Depends, Query, Request

from app.ai.agents import DISPLAY_NAMES, V3_IDS
from app.ai.collaboration.eligibility import collaboration_eligible
from app.ai.search.policy import search_ready
from app.ai.skills.registry import AGENTS, SPECS
from app.contracts import DTO, BotId
from app.core.security import Actor, assert_purpose, require_actor, transaction

router = APIRouter()


class Capability(DTO):
    id: str
    name: str
    description: str
    available: bool
    reason: str | None = None


class PromptCapabilities(DTO):
    skills: list[Capability]
    tools: list[Capability]
    response_protocols: list[Literal[2, 3]] = [2, 3]


@router.get("/ai/prompt-capabilities", response_model=PromptCapabilities)
async def prompt_capabilities(request: Request, bot_id: BotId = Query(alias="botId"), actor: Actor = Depends(require_actor)):
    runtime, settings = request.app.state.ai, request.app.state.settings
    async with transaction(request, actor, eligible=False, lock=False) as (db, user):
        allowed = False
        try:
            await assert_purpose(db, user, "AI")
            allowed = bool(bot_id in V3_IDS and settings.v3_open_for(user.id)
                and await collaboration_eligible(db, user) and runtime.available_for(user.id)
                and (not settings.ai_search_rollout_user_ids or user.id in settings.ai_search_rollout_user_ids))
        except Exception:
            # Capability view is advisory and content-free; send/dispatch reauthorize.
            allowed = False
        skills = []
        for identity, meta in SPECS.items():
            for_agent = bot_id in AGENTS[identity]
            available = allowed and settings.ai_agent_skills_enabled and identity in runtime.skills.load() and for_agent
            reason = None if available else "Kỹ năng chưa sẵn sàng."
            if not for_agent:
                names = " và ".join(DISPLAY_NAMES[agent] for agent in AGENTS[identity])
                reason = f"Kỹ năng này dành cho trợ lý {names}."
            skills.append(Capability(id=identity, name=meta[0], description=meta[1], available=available, reason=reason))
        tools = [Capability(id=identity, name=name, description=description,
            available=allowed and search_ready(settings, provider),
            reason=None if allowed and search_ready(settings, provider) else "Tìm kiếm chưa sẵn sàng cho tài khoản này.")
            for identity, name, description, provider in (
                ("web_search", "Web Search", "Tra cứu thông tin mới có nguồn.", "openai_web"),
                ("maps_search", "Maps Search", "Tìm tối đa 5 địa điểm trong khu vực bạn nhập.", "apify"))]
        return PromptCapabilities(skills=skills, tools=tools)
