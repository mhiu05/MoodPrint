import secrets
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from app.ai.context import ContextStamp
from app.ai.schemas import AIMessage
from app.core.errors import DomainError


@dataclass
class Conversation:
    user_id: str
    session_id: str
    bot_id: str
    id: UUID = field(default_factory=uuid4)
    version: int = 1
    touched: float = 0
    expires_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    messages: list[AIMessage] = field(default_factory=list)
    context_stamps: dict[UUID, ContextStamp] = field(default_factory=dict)
    active_run_id: UUID | None = None
    client_runs: dict[str, tuple[str, UUID]] = field(default_factory=dict)
    persistent: bool = False
    # RAM-only salt: the content-free turn digest of a temporary chat must not be a
    # plain hash that a database reader could match against guessed messages.
    salt: str = field(default_factory=lambda: secrets.token_hex(16))
    # AI consent version and wall time at creation, so any worker can tell that a
    # withdrawal or private-data deletion handled elsewhere invalidated this copy.
    ai_consent_version: int = 0
    created_wall: datetime = field(default_factory=lambda: datetime.now(UTC))
    # Guest trials: a monotonic hard stop at the trial deadline (never extended by touch).
    hard_deadline: float | None = None
    hard_expires_at: datetime | None = None
    # V3 handoff continuation: the specialist answering, and the ids of its segment's messages.
    active_agent: str | None = None
    segment_ids: frozenset[UUID] = frozenset()


class ConversationStore:
    def __init__(self, *, clock: Callable[[], float] = time.monotonic, ttl_seconds: float = 86400):
        self.clock, self.ttl_seconds = clock, ttl_seconds
        self.conversations: dict[UUID, Conversation] = {}

    def create(
        self,
        user_id: str,
        session_id: str,
        bot_id: str,
        *,
        hard_deadline: float | None = None,
        hard_expires_at: datetime | None = None,
    ) -> Conversation:
        self.sweep()
        if (
            len(self.conversations) >= 1000
            or sum(c.user_id == user_id for c in self.conversations.values()) >= 10
        ):
            raise DomainError(
                429, "CONVERSATION_LIMIT", "Hãy kết thúc một cuộc trò chuyện trước khi mở thêm."
            )
        c = Conversation(
            user_id, session_id, bot_id, hard_deadline=hard_deadline, hard_expires_at=hard_expires_at
        )
        self.touch(c)
        self.conversations[c.id] = c
        return c

    def touch(self, c: Conversation) -> None:
        c.touched = self.clock()
        c.expires_at = datetime.now(UTC) + timedelta(seconds=self.ttl_seconds)
        if c.hard_expires_at is not None:
            c.expires_at = min(c.expires_at, c.hard_expires_at)

    def get(self, identity: UUID, user_id: str, session_id: str) -> Conversation:
        c = self.conversations.get(identity)
        if c is None:
            raise DomainError(410, "CONVERSATION_EXPIRED", "Phiên trò chuyện đã kết thúc.")
        if c.user_id != user_id or c.session_id != session_id:
            raise DomainError(404, "NOT_FOUND", "Không tìm thấy cuộc trò chuyện.")
        if self.clock() - c.touched >= self.ttl_seconds or (
            c.hard_deadline is not None and self.clock() >= c.hard_deadline
        ):
            del self.conversations[identity]
            raise DomainError(410, "CONVERSATION_EXPIRED", "Phiên trò chuyện đã kết thúc.")
        self.touch(c)
        return c

    def sweep(self) -> None:
        for identity, c in list(self.conversations.items()):
            if self.clock() - c.touched >= self.ttl_seconds or (
                c.hard_deadline is not None and self.clock() >= c.hard_deadline
            ):
                del self.conversations[identity]

    def clear(self) -> None:
        self.conversations.clear()
