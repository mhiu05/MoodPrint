from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field

from app.contracts import DTO, VersionInput


class DeletionInput(VersionInput):
    scope: Literal["memories", "moods", "private_items", "all_private", "account"]


class DataJobView(DTO):
    id: UUID
    scope: str
    status: str
    version: int
    created_at: datetime


class ExportInput(DTO):
    scopes: list[Literal["account", "private_items", "memories", "moods"]] = Field(
        min_length=1, max_length=4
    )
