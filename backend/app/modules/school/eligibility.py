"""School safety eligibility is a profile row, not the frozen 18+ rule."""

from app.modules.auth.age import is_adult_eligible

SCHOOL_REQUIRED_MESSAGE = "Cần hồ sơ và xác nhận điều khoản để dùng ứng dụng này."


async def is_eligible(db, user) -> bool:
    """School profile uses ``school_profiles``. Every other profile keeps the 18+ rule."""
    if db.info.get("app_profile") != "school_safety":
        return await is_adult_eligible(db, user)
    from app.modules.school.models import SchoolProfile

    profile = await db.get(SchoolProfile, user.id)
    if profile is None:
        return False
    if user.account_kind != "guest" and profile.terms_accepted_at is None:
        return False
    return True
