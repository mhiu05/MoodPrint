"""Bounded cleanup for the local active database; no provider/backup erasure claim."""

from datetime import timedelta

from sqlalchemy import Date, cast, delete, func, select

from app.infrastructure.database.models import AiUsage, Idempotency, Mood, User, now
from app.modules.social.models import HumanMessage


async def purge_expired(app):
    async with app.state.database.require()() as db, db.begin():
        # Retention continues after the accounting kill switch is turned off;
        # old hosted schemas can still run before the expand migration is approved.
        if await db.scalar(select(func.to_regclass("moodprint.ai_usage"))):
            ids = (await db.scalars(select(AiUsage.run_id).where(
                AiUsage.created_at <= now() - timedelta(days=90), AiUsage.state != "open",
            ).limit(1000).with_for_update(skip_locked=True))).all()
            if ids:
                await db.execute(delete(AiUsage).where(AiUsage.run_id.in_(ids)))
        # Date buckets use the owner's timezone, consistently with the mood API.
        mood_ids = (
            await db.scalars(
                select(Mood.id)
                .join(User, User.id == Mood.user_id)
                .where(Mood.local_date < cast(func.timezone(User.timezone, now()), Date) - 89)
                .order_by(Mood.id)
                .limit(1000)
                .with_for_update(of=Mood, skip_locked=True)
            )
        ).all()
        if mood_ids:
            await db.execute(delete(Mood).where(Mood.id.in_(mood_ids)))
        message_ids = (
            await db.scalars(
                select(HumanMessage.id)
                .where(HumanMessage.created_at <= now() - timedelta(days=90))
                .order_by(HumanMessage.id)
                .limit(1000)
                .with_for_update(skip_locked=True)
            )
        ).all()
        if message_ids:
            await db.execute(delete(HumanMessage).where(HumanMessage.id.in_(message_ids)))
        keys = (
            await db.scalars(
                select(Idempotency.id)
                .where(Idempotency.created_at <= now() - timedelta(hours=24))
                .order_by(Idempotency.id)
                .limit(1000)
                .with_for_update(skip_locked=True)
            )
        ).all()
        if keys:
            await db.execute(delete(Idempotency).where(Idempotency.id.in_(keys)))
