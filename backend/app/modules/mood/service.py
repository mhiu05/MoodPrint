"""Owner-scoped mood statistics; never return private notes to the model."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select

from app.ai.schemas import MoodReadScope
from app.core.errors import DomainError
from app.infrastructure.database.models import Mood


def validate_scope(user, scope: MoodReadScope):
    today = datetime.now(ZoneInfo(user.timezone)).date()
    if scope.to_date > today or scope.from_date < today - timedelta(days=89):
        raise DomainError(422, "MOOD_SCOPE_EXPIRED", "Chọn khoảng ngày trong 90 ngày gần đây.")


async def selected_summary(db, user, scope: MoodReadScope):
    validate_scope(user, scope)
    rows = (
        await db.execute(
            select(Mood.local_date, Mood.value, Mood.version)
            .where(
                Mood.user_id == user.id,
                Mood.local_date >= scope.from_date,
                Mood.local_date <= scope.to_date,
            )
            .order_by(Mood.local_date)
        )
    ).all()
    by_day = {row.local_date: row.value for row in rows}
    return {
        "from": str(scope.from_date),
        "to": str(scope.to_date),
        "count": len(rows),
        "mean": sum(by_day.values()) / len(rows) if rows else None,
        "insightAvailable": len(rows) >= 3,
        "sourceVersions": [
            {"localDate": str(row.local_date), "version": row.version} for row in rows
        ],
        "buckets": [
            {
                "localDate": str(scope.from_date + timedelta(days=i)),
                "value": by_day.get(scope.from_date + timedelta(days=i)),
            }
            for i in range((scope.to_date - scope.from_date).days + 1)
        ],
    }
