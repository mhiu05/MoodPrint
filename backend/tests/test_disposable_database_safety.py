"""Fail-closed checks used immediately before destructive local test setup."""

import pytest

from tests import database_target

RUN_ID = "a" * 32
DATABASE = f"moodprint_{RUN_ID}_test"
OWNER = f"moodprint_test_{RUN_ID}"


@pytest.mark.parametrize("query", ["host=remote.example", "hostaddr=192.0.2.1", "service=live"])
def test_local_url_refuses_libpq_connection_overrides(query):
    with pytest.raises(RuntimeError):
        database_target.require_local_test_database(
            f"postgresql+psycopg://{OWNER}@localhost/{DATABASE}?{query}"
        )


@pytest.mark.parametrize(
    "changed",
    [
        {"database": "unrelated_test"},
        {"user": "postgres"},
        {"session_user": "postgres"},
        {"owner": "other_owner"},
        {"marker": None},
        {"marker": f"moodprint-disposable-test:{'b' * 32}"},
    ],
)
def test_reset_refuses_unowned_database_identity(monkeypatch, changed):
    monkeypatch.setenv("MOODPRINT_TEST_RUN_ID", RUN_ID)
    identity = dict(
        database=DATABASE,
        user=OWNER,
        session_user=OWNER,
        owner=OWNER,
        marker=f"moodprint-disposable-test:{RUN_ID}",
    )
    identity.update(changed)
    with pytest.raises(RuntimeError):
        database_target._verify_identity(identity)


def test_reset_refuses_missing_run_identity(monkeypatch):
    monkeypatch.delenv("MOODPRINT_TEST_RUN_ID", raising=False)
    with pytest.raises(RuntimeError):
        database_target._verify_identity({})


def test_reset_refuses_non_test_environment_even_for_owned_database(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("MOODPRINT_TEST_RUN_ID", RUN_ID)
    with pytest.raises(RuntimeError):
        database_target._verify_identity(
            dict(
                database=DATABASE,
                user=OWNER,
                session_user=OWNER,
                owner=OWNER,
                marker=f"moodprint-disposable-test:{RUN_ID}",
            )
        )


@pytest.mark.parametrize("suffix", ["", "_012345abcdef"])
def test_reset_accepts_owned_base_and_scratch_database(monkeypatch, suffix):
    monkeypatch.setenv("MOODPRINT_TEST_RUN_ID", RUN_ID)
    database_target._verify_identity(
        dict(
            database=f"moodprint_{RUN_ID}{suffix}_test",
            user=OWNER,
            session_user=OWNER,
            owner=OWNER,
            marker=f"moodprint-disposable-test:{RUN_ID}",
        )
    )
