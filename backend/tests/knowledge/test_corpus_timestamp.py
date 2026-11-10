"""Published corpus metadata maps PostgreSQL timestamps to the existing date contract."""

from datetime import UTC, datetime, timedelta, timezone

import pytest
from app.modules.knowledge.service import KnowledgeService
from moodprint_shared.config import AppConfig


@pytest.mark.parametrize(
    "published",
    [
        datetime(2026, 11, 10, 12, 35, tzinfo=UTC),
        datetime(2026, 11, 11, 1, 35, tzinfo=timezone(timedelta(hours=7))),
    ],
)
async def test_corpus_accepts_nonmidnight_timestamptz_and_returns_utc_date(published, monkeypatch):
    service = KnowledgeService(None, None, AppConfig())

    async def one(*args):
        return {
            "version": "kb-20261109-07",
            "published_at": published,
            "documents": 57,
            "chunks": 80,
        }

    monkeypatch.setattr(service, "_one", one)
    result = await service.corpus()
    assert result.published_at.isoformat() == "2026-11-10"
    assert result.documents == 57 and result.chunks == 80
