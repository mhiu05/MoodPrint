"""Product decision 24Oct2026: self-declared16+ for private use,18+ for social."""

from zoneinfo import ZoneInfo

from app.core.errors import DomainError
from app.infrastructure.database.models import AgeDeclaration, now


def age_band(birth_year: int, confirmed_adult: bool, *, current_year: int) -> str:
    years = current_year - birth_year
    if years < 0 or (confirmed_adult and years < 18):
        raise DomainError(422, "AGE_DECLARATION_INVALID", "Năm sinh và xác nhận tuổi chưa phù hợp.")
    if years < 16:
        return "under16"
    # Year alone is ambiguous until the birthday;16 is explicitly attested in
    # every request.18 needs a separate attestation in that boundary year.
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
    if not declaration and user.age_band != "unknown":
        raise DomainError(409, "ELIGIBILITY_ALREADY_SET", "Điều kiện tài khoản đã được ghi nhận.")
    if declaration and user.age_band == "adult" and band != "adult":
        raise DomainError(409, "AGE_DECLARATION_INVALID", "Điều kiện tài khoản đã được ghi nhận.")
    changed = declaration is None or user.age_band != band
    if declaration is None:
        declaration = AgeDeclaration(
            user_id=user.id, birth_year=body.birth_year, policy_version=body.policy_version
        )
        db.add(declaration)
    elif changed:
        declaration.version += 1
    if changed:
        user.age_band = band
        user.data_version += 1
        if body.confirmed_adult_age:
            declaration.adult_confirmed_at = now()
    await db.flush()
    return declaration, changed
