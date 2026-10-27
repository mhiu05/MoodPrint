from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field

from app.contracts import DTO, VersionInput


class DeletionInput(VersionInput):
    scope: Literal["memories", "moods", "private_items", "all_private", "account"]
    # A guest has no password: an explicit confirmation replaces step-up. Registered accounts
    # ignore it and keep their recent-reauthentication rule.
    guest_confirmation: Literal["guest-data-v1"] | None = None


class DataJobView(DTO):
    id: UUID
    scope: str
    status: str
    version: int
    created_at: datetime


class ExportInput(DTO):
    # Joined scopes must fit data_jobs.scope (String(64)); six names use 51 characters.
    scopes: list[
        Literal["account", "private_items", "memories", "moods", "consents", "social"]
    ] = Field(min_length=1, max_length=6)
    guest_confirmation: Literal["guest-data-v1"] | None = None
