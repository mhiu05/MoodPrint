"""Synthetic adapters and helpers. Never use with real personal data."""

from .auth import make_auth_context
from .knowledge_fixture import FixtureKnowledgeRetriever

__all__ = ["FixtureKnowledgeRetriever", "make_auth_context"]
