"""Phase 3 owns analysis endpoints on this registered router."""

from fastapi import APIRouter

router = APIRouter(prefix="/v1/analyses", tags=["analyses"])
