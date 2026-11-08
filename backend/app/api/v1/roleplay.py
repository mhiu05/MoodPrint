"""Phase 3 owns roleplay endpoints on this registered router."""

from fastapi import APIRouter

router = APIRouter(prefix="/v1/roleplay", tags=["roleplay"])
