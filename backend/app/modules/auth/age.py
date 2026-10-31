"""Global 18+ policy: server-owned self declarations, never provider metadata."""

from datetime import datetime
from zoneinfo import ZoneInfo

from app.core.errors import DomainError
from app.infrastructure.database.models import AgeDeclaration, now

AGE_POLICY_VERSION = "self-declared-age-v2-18plus"
ACCEPTED_DECLARATION_POLICIES = {"self-declared-age-v1", AGE_POLICY_VERSION}
AGE_REQUIRED_MESSAGE = "Bạn cần đủ 18 tuổi để sử dụng MoodPrint."


def adult_eligible(user, declaration, *, at: datetime | None = None) -> bool:
    """A year cannot prove a birthday; require attestation in the eighteenth year.

    Old adult declarations stay valid without a policy-only forced onboarding.
    Missing, inconsistent or future-dated evidence grants no product access.
    The legacy band vocabulary is retained for stored data/client compatibility.
    """
    at = at or now()
    if user.age_band != "adult" or declaration is None:
        return False
    if (
        declaration.user_id != user.id
        or declaration.policy_version not in ACCEPTED_DECLARATION_POLICIES
        or declaration.version is None
        or declaration.version < 1
        or type(declaration.birth_year) is not int
        or declaration.birth_year < 1900
    ):
        return False
    declared = declaration.declared_at
    confirmed = declaration.adult_confirmed_at
    if declared is None or declared.tzinfo is None or declared > at:
        return False
    if confirmed is not None and (confirmed.tzinfo is None or confirmed > at):
        return False
    if confirmed is not None and (
        confirmed.astimezone(ZoneInfo("Asia/Bangkok")).year - declaration.birth_year < 18
    ):
        return False
    years = at.astimezone(ZoneInfo("Asia/Bangkok")).year - declaration.birth_year
    return years > 18 or (years == 18 and confirmed is not None)


async def is_adult_eligible(db, user, *, at: datetime | None = None) -> bool:
    declaration = await db.get(AgeDeclaration, user.id)
    return adult_eligible(user, declaration, at=at)


def age_band(birth_year: int, confirmed_adult: bool, *, current_year: int) -> str:
    years = current_year - birth_year
    if years < 0 or (confirmed_adult and years < 18):
        raise DomainError(422, "AGE_DECLARATION_INVALID", "Năm sinh và xác nhận tuổi chưa phù hợp.")
    if years < 16:
        return "under16"
    # Historical storage labels do not grant access. Only adult is eligible,
    # with separate birthday attestation in the ambiguous eighteenth year.
    return "adult" if years > 18 or (years == 18 and confirmed_adult) else "teen"


async def record_age(db, user, body):
    if user.deletion_pending:
        raise DomainError(
            409, "DELETION_IN_PROGRESS", "Dữ liệu đang được xóa. Hãy chờ yêu cầu hoàn tất."
        )
    band = age_band(
        body.birth_year,
        body.confirmed_adult_age,
        current_year=now().astimezone(ZoneInfo("Asia/Bangkok")).year,
    )
    declaration = await db.get(AgeDeclaration, user.id)
    if (declaration.version if declaration else 0) != body.expected_version:
        raise DomainError(409, "STALE_VERSION", "Thông tin tuổi đã thay đổi. Vui lòng tải lại.")
    if declaration and declaration.birth_year != body.birth_year:
        raise DomainError(
            409, "BIRTH_YEAR_LOCKED", "Năm sinh đã được ghi nhận và không thể tự thay đổi tại đây."
        )
    if declaration and user.age_band == "adult" and band != "adult":
        raise DomainError(409, "AGE_DECLARATION_INVALID", "Điều kiện tài khoản đã được ghi nhận.")
    changed = (
        declaration is None
        or user.age_band != band
        or declaration.policy_version != body.policy_version
        or (body.confirmed_adult_age and declaration.adult_confirmed_at is None)
    )
    if declaration is None:
        declaration = AgeDeclaration(
            user_id=user.id, birth_year=body.birth_year, policy_version=body.policy_version
        )
        db.add(declaration)
    elif changed:
        declaration.version += 1
        declaration.policy_version = body.policy_version
    if changed:
        user.age_band = band
        user.data_version += 1
        if body.confirmed_adult_age:
            declaration.adult_confirmed_at = now()
    await db.flush()
    return declaration, changed
