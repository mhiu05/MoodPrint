"""Version one contracts."""

from app.api.v1.analyses import router as analyses_router
from app.api.v1.knowledge import router as knowledge_router
from app.api.v1.roleplay import router as roleplay_router

__all__ = ["analyses_router", "knowledge_router", "roleplay_router"]
