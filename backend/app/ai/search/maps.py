from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field

from app.ai.schemas import PlaceResult as PlaceResult
from app.contracts import DTO


class MapsSearchView(DTO):
    search_id: UUID
    status: Literal["starting", "pending", "ready", "empty", "failed", "timed_out", "cancelled", "expired"]
    version: int
    expires_at: datetime
    retry_after_seconds: int = 2
    places: list[PlaceResult] = Field(default_factory=list, max_length=5)
    error_code: str | None = None
