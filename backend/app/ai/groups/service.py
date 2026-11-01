"""Owner-scoped reads and views of AI groups (a group is an ``ai_conversations`` row, kind 'group')."""

from sqlalchemy import func, select

from app.ai.groups.schemas import GroupHeader, GroupMemberView, GroupView
from app.ai.models import AiConversation, AiMessageRecord
from app.ai.orchestration.models import AiGroupMember
from app.ai.persistence import message_page, owned_conversation
from app.core.errors import DomainError

MEMBER_ORDER = {"dieuphoi": 0, "nhatky": 1, "hoatdong": 2}
MAX_GROUPS = 50


def not_found() -> DomainError:
    return DomainError(404, "NOT_FOUND", "Không tìm thấy nhóm.")


async def owned_group(db, group_id, user_id, *, lock=False) -> AiConversation:
    group = await owned_conversation(db, group_id, user_id, lock=lock, kind="group")
    if group is None:
        raise not_found()
    return group


async def members_of(db, group: AiConversation) -> list[AiGroupMember]:
    rows = (await db.scalars(select(AiGroupMember).where(
        AiGroupMember.conversation_id == group.id, AiGroupMember.user_id == group.user_id,
    ))).all()
    return sorted(rows, key=lambda row: (row.joined_at, MEMBER_ORDER[row.bot_id]))


def active(members: list[AiGroupMember]) -> list[str]:
    return [row.bot_id for row in members if row.status == "active"]


async def unread(db, group: AiConversation) -> int:
    from app.ai.proactive.models import AiConversationRead

    read = await db.get(AiConversationRead, group.id)
    last = read.last_read_sequence if read is not None and read.user_id == group.user_id else 0
    return int(await db.scalar(select(func.count()).select_from(AiMessageRecord).where(
        AiMessageRecord.conversation_id == group.id, AiMessageRecord.actor == "bot",
        AiMessageRecord.sequence > last,
    )) or 0)


def header(group: AiConversation, members: list[AiGroupMember], unread_count: int = 0) -> GroupHeader:
    return GroupHeader(
        group_id=group.id, name=group.title, version=group.version, created_at=group.created_at,
        updated_at=group.updated_at, expires_at=group.expires_at, unread=unread_count,
        members=[
            GroupMemberView(bot_id=row.bot_id, status=row.status, journal_access=row.journal_access,  # type: ignore[arg-type]
                            shares_history=row.history_from_sequence == 0, joined_at=row.joined_at)
            for row in members
        ],
    )


async def group_view(db, group: AiConversation, limit=50, before=None) -> GroupView:
    members = await members_of(db, group)
    messages, has_more, running = await message_page(db, group, limit, before)
    return GroupView(
        **header(group, members).model_dump(), messages=messages,
        active_turn_id=running[0] if running else None, has_more_messages=has_more,
    )
