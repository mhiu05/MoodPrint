"""Unlinked feedback storage: no submitter identity, constrained values, one-way cascades, strict DTOs."""

from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

FEEDBACK_COLUMNS = {
    "id",
    "rating",
    "categories",
    "comment",
    "app_version",
    "context",
    "account_kind",
    "disclosure_version",
    "created_at",
    "status",
    "version",
    "reviewed_at",
}
CATEGORIES = (
    "ease_of_use",
    "ai_quality",
    "interface",
    "performance",
    "bug",
    "missing_feature",
    "privacy_trust",
    "other",
)
FORBIDDEN_IDENTITY_COLUMNS = {
    "user_id",
    "auth_subject",
    "session_id",
    "provider_session_id",
    "ip",
    "ip_address",
    "network",
    "conversation_id",
    "run_id",
    "device",
    "user_agent",
    "url",
    "path",
    "route",
    "idempotency_key",
    "payload_digest",
}


def metadata():
    from app.infrastructure.database.models import Base
    from app.modules.feedback import models  # noqa: F401

    return Base.metadata


def test_feedback_schema_has_no_submitter_identity():
    tables = metadata().tables
    feedback = tables["moodprint.app_feedback"]
    columns = {column.name for column in feedback.columns}
    assert columns == FEEDBACK_COLUMNS
    assert not (FORBIDDEN_IDENTITY_COLUMNS & columns)
    # No foreign key leaves app_feedback, so nothing can join a retained row to a person.
    assert not feedback.foreign_keys

    events = tables["moodprint.feedback_review_events"]
    event_columns = {column.name for column in events.columns}
    assert event_columns == {
        "id",
        "feedback_id",
        "staff_id",
        "action",
        "from_status",
        "to_status",
        "resulting_version",
        "created_at",
    }
    assert {fk.column.table.name for fk in events.foreign_keys} == {"app_feedback", "users"}

    receipts = tables["moodprint.feedback_submission_receipts"]
    by_parent = {fk.column.table.name: fk.ondelete for fk in receipts.foreign_keys}
    # The cascade runs feedback -> receipt (and user -> receipt), never receipt -> feedback.
    assert by_parent == {"users": "CASCADE", "app_feedback": "CASCADE"}
    assert not any(
        fk.column.table.name == "feedback_submission_receipts"
        for table in tables.values()
        for fk in table.foreign_keys
    )


async def insert_feedback(db, **values):
    fields = {
        "rating": 5,
        "categories": "{}",
        "comment": None,
        "context": "general",
        "kind": "guest",
        "version": "test-release",
        **values,
    }
    return await db.scalar(
        text(
            "insert into moodprint.app_feedback(id,rating,categories,comment,app_version,context,"
            "account_kind,disclosure_version) values (:id,:rating,cast(:categories as text[]),"
            ":comment,:version,:context,:kind,'feedback-v1') returning id"
        ),
        {"id": uuid4(), **fields},
    )


async def count(database, table: str) -> int:
    async with database.connect() as conn:
        return await conn.scalar(text(f"select count(*) from moodprint.{table}"))


async def test_rating_alone_is_accepted_with_database_defaults(database):
    async with database.begin() as conn:
        fid = await insert_feedback(AsyncSession(bind=conn))
    async with database.connect() as conn:
        row = (
            await conn.execute(
                text(
                    "select rating, categories, comment, status, version, reviewed_at, created_at"
                    " from moodprint.app_feedback where id=:id"
                ),
                {"id": fid},
            )
        ).one()
    assert (row.rating, row.categories, row.comment) == (5, [], None)
    assert (row.status, row.version, row.reviewed_at) == ("new", 1, None)
    assert row.created_at is not None


@pytest.mark.parametrize(
    "values",
    [
        {"rating": 0},
        {"rating": 6},
        {"rating": None},
        {"categories": "{bug,bug}"},
        {"categories": "{unknown}"},
        {"categories": "{bug,NULL}"},
        {"categories": "{" + ",".join(f"c{i}" for i in range(9)) + "}"},
        {"comment": "x" * 1001},
        {"comment": "a\x01b"},
        {"comment": "a\x7fb"},
        {"comment": "a\u0085b"},
        {"comment": "a\u009fb"},
        {"context": "https://example.test/private/path"},
        {"kind": "visitor"},
        {"version": None},
    ],
    ids=lambda value: ",".join(f"{k}={str(v)[:12]!r}" for k, v in value.items()),
)
async def test_feedback_db_constraints_reject_invalid_values(database, values):
    with pytest.raises((IntegrityError, DBAPIError)):
        async with database.begin() as conn:
            await insert_feedback(AsyncSession(bind=conn), **values)
    assert await count(database, "app_feedback") == 0


@pytest.mark.parametrize(
    "values",
    [
        {"comment": "x" * 1000},
        {"comment": "😀" * 1000},  # code points, not UTF-16 units
        {"comment": "dòng một\n\tdòng hai\r\n"},
        {"comment": "<script>alert('x')</script>'; drop table moodprint.users; --"},
        {"categories": "{" + ",".join(CATEGORIES) + "}"},
        {"categories": "{privacy_trust}", "context": "trial_end", "kind": "registered"},
    ],
    ids=lambda value: ",".join(f"{k}={str(v)[:12]!r}" for k, v in value.items()),
)
async def test_feedback_db_constraints_accept_every_documented_value(database, values):
    async with database.begin() as conn:
        await insert_feedback(AsyncSession(bind=conn), **values)
    assert await count(database, "app_feedback") == 1


async def test_null_semantics_cannot_bypass_the_constraints(database):
    # A NULL comment is allowed, but NULL never makes the array validators pass.
    async with database.connect() as conn:
        for sql in (
            "select moodprint.feedback_categories_valid(null)",
            "select moodprint.feedback_categories_valid(array[null]::text[])",
            "select moodprint.feedback_categories_valid(array['bug','bug']::text[])",
        ):
            assert await conn.scalar(text(sql)) is False
        assert await conn.scalar(text("select moodprint.feedback_comment_valid(null)")) is True
        assert await conn.scalar(text("select moodprint.feedback_categories_valid('{}')")) is True


async def test_receipt_deletion_keeps_feedback_and_feedback_deletion_cascades(database):
    from app.infrastructure.database.models import User

    uid, staff = uuid4(), uuid4()
    async with AsyncSession(database, expire_on_commit=False) as db, db.begin():
        db.add(User(id=uid, auth_subject=uid))
        db.add(User(id=staff, auth_subject=staff))
        await db.flush()
        feedback = await insert_feedback(db)
        await db.execute(
            text(
                "insert into moodprint.feedback_submission_receipts"
                "(id,user_id,idempotency_key,payload_digest,feedback_id)"
                " values (:id,:uid,'key-1',:digest,:fid)"
            ),
            {"id": uuid4(), "uid": uid, "digest": "a" * 64, "fid": feedback},
        )
        await db.execute(
            text(
                "insert into moodprint.feedback_review_events"
                "(id,feedback_id,staff_id,action,from_status,to_status,resulting_version)"
                " values (:id,:fid,:staff,'status','new','reviewed',2)"
            ),
            {"id": uuid4(), "fid": feedback, "staff": staff},
        )

    # Deleting the receipt (what a guest purge does) leaves the independent feedback and its audit.
    async with database.begin() as conn:
        await conn.execute(text("delete from moodprint.feedback_submission_receipts"))
    assert await count(database, "app_feedback") == 1
    assert await count(database, "feedback_review_events") == 1

    # A user delete cascades only the receipt; a staff user with review events is protected.
    async with database.begin() as conn:
        await conn.execute(
            text(
                "insert into moodprint.feedback_submission_receipts"
                "(id,user_id,idempotency_key,payload_digest,feedback_id)"
                " select :id,:uid,'key-2',:digest,id from moodprint.app_feedback"
            ),
            {"id": uuid4(), "uid": uid, "digest": "b" * 64},
        )
        await conn.execute(text("delete from moodprint.users where id=:uid"), {"uid": uid})
    assert await count(database, "feedback_submission_receipts") == 0
    assert await count(database, "app_feedback") == 1
    with pytest.raises(IntegrityError):
        async with database.begin() as conn:
            await conn.execute(text("delete from moodprint.users where id=:uid"), {"uid": staff})

    # Feedback deletion (retention) removes its receipts and review events with it.
    async with database.begin() as conn:
        await conn.execute(text("delete from moodprint.app_feedback"))
    assert await count(database, "feedback_review_events") == 0


async def test_receipt_key_is_unique_per_owner(database):
    from app.infrastructure.database.models import User

    first, second = uuid4(), uuid4()
    async with AsyncSession(database, expire_on_commit=False) as db, db.begin():
        db.add(User(id=first, auth_subject=first))
        db.add(User(id=second, auth_subject=second))
        await db.flush()
        feedback = [await insert_feedback(db) for _ in range(3)]
        for owner, fid in ((first, feedback[0]), (second, feedback[1])):
            await db.execute(
                text(
                    "insert into moodprint.feedback_submission_receipts"
                    "(id,user_id,idempotency_key,payload_digest,feedback_id)"
                    " values (:id,:uid,'same-key',:digest,:fid)"
                ),
                {"id": uuid4(), "uid": owner, "digest": "c" * 64, "fid": fid},
            )
    with pytest.raises(IntegrityError):
        async with database.begin() as conn:
            await conn.execute(
                text(
                    "insert into moodprint.feedback_submission_receipts"
                    "(id,user_id,idempotency_key,payload_digest,feedback_id)"
                    " values (:id,:uid,'same-key',:digest,:fid)"
                ),
                {"id": uuid4(), "uid": first, "digest": "c" * 64, "fid": feedback[2]},
            )


VALID = {"rating": 4, "disclosureVersion": "feedback-v1"}


def feedback_input(**fields):
    from app.modules.feedback.schemas import FeedbackInput

    return FeedbackInput.model_validate({**VALID, **fields})


def test_dto_rating_only_and_defaults():
    body = feedback_input(rating=5)
    assert (body.rating, body.categories, body.comment, body.context) == (5, [], None, "general")


@pytest.mark.parametrize("rating", [True, False, "5", 4.5, 5.0, 0, 6, None, -1])
def test_dto_rejects_non_integer_or_out_of_range_rating(rating):
    with pytest.raises(ValidationError):
        feedback_input(rating=rating)


def test_dto_rejects_repeated_unknown_null_and_oversized_categories():
    for categories in (["bug", "bug"], ["unknown"], [None], list(CATEGORIES) + ["bug"], "bug"):
        with pytest.raises(ValidationError):
            feedback_input(categories=categories)
    # Stored in the documented order whatever order the client used.
    assert feedback_input(categories=["other", "bug", "ease_of_use"]).categories == [
        "ease_of_use",
        "bug",
        "other",
    ]


def test_dto_comment_normalization_and_boundaries():
    assert feedback_input(comment="   ").comment is None
    assert feedback_input(comment="").comment is None
    assert feedback_input(comment="  tốt  \n").comment == "tốt"
    assert feedback_input(comment="a\tb\r\nc").comment == "a\tb\r\nc"
    assert feedback_input(comment="x" * 1000).comment == "x" * 1000
    assert feedback_input(comment="😀" * 1000).comment == "😀" * 1000
    with pytest.raises(ValidationError):
        feedback_input(comment="x" * 1001)
    # The limit applies before trimming as well as after.
    with pytest.raises(ValidationError):
        feedback_input(comment=" " * 500 + "x" * 600)
    with pytest.raises(ValidationError):
        feedback_input(comment="😀" * 1001)


@pytest.mark.parametrize("bad", ["a\x00b", "a\x01b", "a\x1fb", "a\x7fb", "a\u0085b", "a\u009fb", "\ud800", "\x1f"])
def test_dto_rejects_controls_and_invalid_surrogates_even_when_trimmable(bad):
    with pytest.raises(ValidationError):
        feedback_input(comment=bad)


def test_dto_keeps_markup_and_sql_looking_text_as_plain_text():
    text_value = "<b>x</b> ' OR 1=1; -- [link](https://example.test) ${x}"
    assert feedback_input(comment=text_value).comment == text_value


@pytest.mark.parametrize(
    "extra",
    [
        {"userId": str(uuid4())},
        {"url": "https://example.test/#/private"},
        {"appVersion": "9.9"},
        {"conversationId": str(uuid4())},
        {"screenshot": "data:image/png;base64,AAAA"},
        {"context": "https://example.test"},
        {"disclosureVersion": "feedback-v2"},
    ],
)
def test_dto_rejects_identity_metadata_attachments_and_unknown_context(extra):
    with pytest.raises(ValidationError):
        feedback_input(**extra)
