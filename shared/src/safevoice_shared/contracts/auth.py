from dataclasses import dataclass, field
from uuid import UUID

from .base import AgeBand as AgeBand


@dataclass(frozen=True, slots=True)
class AuthContext:
    user_id: UUID
    session_id: str | None
    aal: str | None
    claims_json: str = field(repr=False)
