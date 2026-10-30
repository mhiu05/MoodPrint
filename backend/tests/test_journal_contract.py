"""The public journal collection/detail contract must be registered in the application."""

from app.core.config import Settings
from app.main import create_app


def test_journal_crud_contract_is_registered():
    app = create_app(Settings(_env_file=None))
    paths = app.openapi()["paths"]
    assert {"get", "post"} <= set(paths.get("/api/v1/journal/entries", {}))
    assert {"get", "put", "delete"} <= set(paths.get("/api/v1/journal/entries/{entry_id}", {}))
