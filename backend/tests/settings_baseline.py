"""Explicit legacy capabilities for synthetic tests, never production defaults."""

from app.core.config import FEATURE_FLAGS

ALL_FEATURES_OFF: dict[str, bool] = {
    **dict.fromkeys(FEATURE_FLAGS, False),
    "chat_history_enabled": True,
}
