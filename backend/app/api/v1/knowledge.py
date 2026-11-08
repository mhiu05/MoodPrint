"""Phase 2 Knowledge Hub API seam; retrieval routes are added after G2."""

from fastapi import APIRouter

router = APIRouter(prefix="/v1/knowledge", tags=["knowledge"])
