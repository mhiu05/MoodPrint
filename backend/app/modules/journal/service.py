"""Owner-scoped journal access and transactionally durable media cleanup."""

from datetime import date, datetime, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert

from app.core.errors import DomainError
from app.modules.journal.models import JournalEntry, JournalMedia, JournalStorageDeletion
from app.modules.journal.schemas import JournalEntryDTO, JournalMediaDTO


def active_dates(user) -> tuple[date, date]:
    today = datetime.now(ZoneInfo(user.timezone)).date()
    return today - timedelta(days=89), today


def validate_date(user, local_date: date) -> None:
    start, end = active_dates(user)
    if local_date > end:
        raise DomainError(422, "FUTURE_DATE", "Không thể viết nhật ký cho ngày chưa đến.")
    if local_date < start:
        raise DomainError(422, "DATE_EXPIRED", "Chỉ có thể viết nhật ký trong 90 ngày gần đây.")


async def get_owned_entry(db, user, entry_id: UUID) -> JournalEntry:
    start, end = active_dates(user)
    row = await db.scalar(
        select(JournalEntry).where(
            JournalEntry.id == entry_id,
            JournalEntry.user_id == user.id,
            JournalEntry.local_date >= start,
            JournalEntry.local_date <= end,
        )
    )
    if row is None:
        raise DomainError(404, "NOT_FOUND", "Không tìm thấy khoảnh khắc này.")
    return row


async def entry_dto(db, row: JournalEntry) -> JournalEntryDTO:
    return (await entries_dto(db, [row]))[0]


async def entries_dto(db, rows: list[JournalEntry]) -> list[JournalEntryDTO]:
    if not rows:
        return []
    owners = {row.id: row.user_id for row in rows}
    media = (
        await db.scalars(
            select(JournalMedia)
            .where(
                JournalMedia.entry_id.in_(owners),
            )
            .order_by(JournalMedia.created_at, JournalMedia.id)
        )
    ).all()
    by_entry: dict[UUID, list[JournalMediaDTO]] = {row.id: [] for row in rows}
    for item in media:
        if item.user_id == owners[item.entry_id]:
            by_entry[item.entry_id].append(JournalMediaDTO.model_validate(item))
    result = []
    for row in rows:
        dto = JournalEntryDTO.model_validate(row)
        dto.media = by_entry[row.id]
        result.append(dto)
    return result


async def queue_media_deletion(db, media: JournalMedia) -> None:
    await db.execute(
        insert(JournalStorageDeletion)
        .values(object_path=media.object_path)
        .on_conflict_do_nothing(index_elements=[JournalStorageDeletion.object_path])
    )


async def delete_entries(db, entries: list[JournalEntry]) -> None:
    if not entries:
        return
    ids = [row.id for row in entries]
    # Query by entry instead of owner alone so malformed metadata cannot escape cleanup.
    media = (await db.scalars(select(JournalMedia).where(JournalMedia.entry_id.in_(ids)))).all()
    for item in media:
        await queue_media_deletion(db, item)
    await db.execute(delete(JournalEntry).where(JournalEntry.id.in_(ids)))


async def purge_owned_journal(db, user_id: UUID) -> None:
    entries = (await db.scalars(select(JournalEntry).where(JournalEntry.user_id == user_id))).all()
    # Include any inconsistent media owner row before its user FK is removed.
    media = (await db.scalars(select(JournalMedia).where(JournalMedia.user_id == user_id))).all()
    for item in media:
        await queue_media_deletion(db, item)
    await db.execute(delete(JournalMedia).where(JournalMedia.user_id == user_id))
    await delete_entries(db, entries)
