"""Who may use companion collaboration at all. MoodPrint's minimum age is 18.

The age test is the global policy, ``is_adult_eligible(db, user)``: it also checks the stored
age declaration, so a bare ``age_band`` label never grants access.
"""

from app.infrastructure.database.models import User, now
from app.modules.auth.age import is_adult_eligible


async def collaboration_eligible(db, user: User) -> bool:
    if user.account_kind != "registered" or user.status != "active" or user.deletion_pending:
        return False
    if user.suspended_until and user.suspended_until > now():
        return False
    return await is_adult_eligible(db, user)
