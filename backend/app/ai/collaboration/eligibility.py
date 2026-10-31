"""Who may use companion collaboration at all. MoodPrint's minimum age is 18.

INTEGRATION (feat/friendship-discovery-18plus): that branch adds
``app.modules.auth.age.is_adult_eligible(db, user)``, which also checks the age declaration.
After rebasing, replace the age test below with ``await is_adult_eligible(db, user)``; the
account-state checks stay. Until then the strict ``age_band == 'adult'`` test is used — never the
older 16+ ``('teen', 'adult')`` rule.
"""

from app.infrastructure.database.models import User, now


async def collaboration_eligible(db, user: User) -> bool:
    if user.account_kind != "registered" or user.status != "active" or user.deletion_pending:
        return False
    if user.suspended_until and user.suspended_until > now():
        return False
    return user.age_band == "adult"
