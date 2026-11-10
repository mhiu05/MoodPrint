from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class KnowledgeArticleState(Base):
    __tablename__ = "knowledge_article_states"
    __table_args__ = {"schema": "app"}
    owner_id: Mapped[UUID] = mapped_column(primary_key=True)
    article_id: Mapped[str] = mapped_column(Text, primary_key=True)
    bookmarked: Mapped[bool] = mapped_column(Boolean)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
