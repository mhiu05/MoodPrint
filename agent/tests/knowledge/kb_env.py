"""Where the knowledge integration tests find their loopback database.

A developer worktree may keep a named stack env (``.local/stacks/kb/test.env``); CI and the default
stack use ``.local/test.env`` or plain process variables. Every candidate is loopback-checked by the
ingest runtime before it is used.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from dotenv import dotenv_values

CANDIDATES = (Path(".local/stacks/kb/test.env"), Path(".local/test.env"))


def load_test_env() -> dict[str, str]:
    """Merge the first env file found into ``os.environ`` (without overriding) and return its values."""
    values: dict[str, str] = {}
    for path in CANDIDATES:
        if path.is_file():
            values = {k: v for k, v in dotenv_values(path).items() if v}
            break
    for key, value in values.items():
        os.environ.setdefault(key, value)
    if not (os.environ.get("TEST_ADMIN_DATABASE_URL") or os.environ.get("TEST_DATABASE_URL")):
        pytest.fail("no loopback test database is configured; start a stack and bootstrap it")
    return values


def api_database_url() -> str:
    """The ``moodprint_api`` login that searches through ``SET ROLE authenticated``."""
    load_test_env()
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.fail("TEST_DATABASE_URL is missing from the test environment")
    return url
