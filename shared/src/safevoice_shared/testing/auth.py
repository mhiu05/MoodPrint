import json
from uuid import UUID

from safevoice_shared.contracts.auth import AuthContext


def make_auth_context(
    user_id: UUID, *, session_id: str | None = None, aal: str = "aal1"
) -> AuthContext:
    """Build verified-shaped synthetic claims for local tests only."""
    claims = {"sub": str(user_id), "role": "authenticated", "aud": "authenticated", "aal": aal}
    if session_id is not None:
        claims["session_id"] = session_id
    return AuthContext(
        user_id=user_id,
        session_id=session_id,
        aal=aal,
        claims_json=json.dumps(claims, ensure_ascii=False),
    )
