"""Adult policy must hold for existing cookies and direct API calls, not only onboarding."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.infrastructure.database.models import AgeDeclaration, AuthSession, User
from tests.guest_helpers import (
    FakeGuestProvider,
    add_guest,
    enable_guest_entry,
    guest_body,
    open_intent,
    post_guest,
    public_client,
)
from tests.social_helpers import key


@pytest.mark.postgres
@pytest.mark.parametrize("band", ["teen", "under16", "unknown", "adult"])
async def test_existing_cookie_without_valid_declaration_cannot_open_product(clients, band):
    app, actors = clients
    client, uid = actors[0]
    async with app.state.database.sessions.begin() as db:
        user = await db.get(User, uid)
        user.age_band = band
        declaration = await db.get(AgeDeclaration, uid)
        if declaration:
            await db.delete(declaration)
    session = await client.get("/api/v1/session")
    assert session.status_code == 200
    assert session.json()["eligible"] is False
    for path in (
        "/api/v1/moods",
        "/api/v1/journal/entries",
        "/api/v1/matching/candidates",
        "/api/v1/connections",
    ):
        response = await client.get(path)
        assert response.status_code == 403, (path, response.text)
        assert response.json()["error"]["code"] == "ELIGIBILITY_REQUIRED"
    response = await client.post("/api/v1/ai/conversations", json={"botId": "may"}, headers=key())
    assert response.status_code == 403, response.text


@pytest.mark.postgres
@pytest.mark.parametrize("years", [16, 17, 18])
async def test_guest_rejects_minor_or_unconfirmed_eighteenth_year_before_provider(clients, years):
    from zoneinfo import ZoneInfo

    app, _ = clients
    enable_guest_entry(app)
    provider = FakeGuestProvider(app)
    browser = public_client(app)
    await open_intent(browser)
    year = datetime.now(ZoneInfo("Asia/Bangkok")).year
    response = await post_guest(
        browser,
        str(uuid4()),
        guest_body(birthYear=year - years, policyVersion="self-declared-age-v2-18plus"),
    )
    assert response.status_code == 422, response.text
    assert response.json()["error"]["code"] == "GUEST_INELIGIBLE"
    assert provider.created == []
    await browser.aclose()


@pytest.mark.postgres
async def test_ineligible_guest_cookie_still_cannot_open_journal_or_ai(clients):
    app, _ = clients
    guest = await add_guest(app, age_band="teen")
    assert (await guest.client.get("/api/v1/session")).json()["eligible"] is False
    assert (await guest.client.get("/api/v1/moods")).status_code == 403
    assert (
        await guest.client.post("/api/v1/ai/conversations", json={"botId": "may"}, headers=key())
    ).status_code == 403


@pytest.mark.postgres
async def test_minor_retains_owner_export_withdrawal_and_deletion_flows(clients):
    app, actors = clients
    client, uid = actors[0]
    async with app.state.database.sessions.begin() as db:
        user = await db.get(User, uid)
        user.age_band = "teen"
        session = await db.scalar(select(AuthSession).where(AuthSession.user_id == uid))
        session.reauthenticated_at = datetime.now(UTC)
    created = await client.post(
        "/api/v1/exports", json={"scopes": ["account", "journal"]}, headers=key()
    )
    assert created.status_code == 201, created.text
    identity = created.json()["id"]
    assert (await client.get(f"/api/v1/exports/{identity}")).status_code == 200
    assert (await actors[1][0].get(f"/api/v1/exports/{identity}/download")).status_code == 404
    assert (await client.get(f"/api/v1/exports/{identity}/download")).status_code == 200
    withdrawn = await client.put(
        "/api/v1/consents/MATCH",
        json={"enabled": False, "expectedVersion": 1, "policyVersion": "v1"},
        headers=key(),
    )
    assert withdrawn.status_code == 200, withdrawn.text
    enabled = await client.put(
        "/api/v1/consents/MATCH",
        json={"enabled": True, "expectedVersion": 2, "policyVersion": "v1"},
        headers=key(),
    )
    assert enabled.status_code == 403
    view = (await client.get("/api/v1/session")).json()
    deletion = await client.post(
        "/api/v1/data-deletions",
        json={"scope": "account", "expectedVersion": view["dataVersion"]},
        headers=key(),
    )
    assert deletion.status_code == 202, deletion.text


@pytest.mark.postgres
async def test_old_adult_declaration_remains_eligible_but_future_attestation_fails(clients):
    app, actors = clients
    client, uid = actors[0]
    async with app.state.database.sessions.begin() as db:
        declaration = await db.get(AgeDeclaration, uid)
        if declaration:
            await db.delete(declaration)
            await db.flush()
        db.add(AgeDeclaration(user_id=uid, birth_year=2000, policy_version="self-declared-age-v1"))
    assert (await client.get("/api/v1/session")).json()["eligible"] is True
    assert (await client.get("/api/v1/moods")).status_code == 200
    async with app.state.database.sessions.begin() as db:
        declaration = await db.get(AgeDeclaration, uid)
        declaration.declared_at = datetime.now(UTC) + timedelta(days=1)
    assert (await client.get("/api/v1/session")).json()["eligible"] is False
    assert (await client.get("/api/v1/moods")).status_code == 403


def test_eighteenth_birthday_requires_self_attestation_not_year_inference():
    from types import SimpleNamespace

    from app.modules.auth.age import adult_eligible

    uid = uuid4()
    user = SimpleNamespace(id=uid, age_band="adult")
    declaration = SimpleNamespace(
        user_id=uid,
        birth_year=2008,
        version=1,
        policy_version="self-declared-age-v1",
        declared_at=datetime(2026, 1, 1, tzinfo=UTC),
        adult_confirmed_at=None,
    )
    # This synthetic person has a birthday on October 31; the stored year cannot establish it.
    assert not adult_eligible(user, declaration, at=datetime(2026, 10, 30, tzinfo=UTC))
    assert not adult_eligible(user, declaration, at=datetime(2026, 10, 31, tzinfo=UTC))
    declaration.adult_confirmed_at = datetime(2026, 10, 31, tzinfo=UTC)
    assert adult_eligible(user, declaration, at=datetime(2026, 10, 31, tzinfo=UTC))
    assert not adult_eligible(user, declaration, at=datetime(2026, 10, 30, tzinfo=UTC))
    declaration.adult_confirmed_at = datetime(2025, 10, 31, tzinfo=UTC)
    assert not adult_eligible(user, declaration, at=datetime(2026, 10, 31, tzinfo=UTC))
    declaration.adult_confirmed_at = datetime(2026, 10, 31, tzinfo=UTC)
    # Historic record_age assigned the attestation before the INSERT default timestamp.
    declaration.declared_at = declaration.adult_confirmed_at + timedelta(milliseconds=1)
    assert adult_eligible(user, declaration, at=datetime(2026, 11, 1, tzinfo=UTC))


@pytest.mark.postgres
async def test_old_teen_policy_cannot_regrant_access_but_same_year_adult_can_attest(clients):
    from zoneinfo import ZoneInfo

    app, actors = clients
    client, uid = actors[0]
    year = datetime.now(ZoneInfo("Asia/Bangkok")).year
    async with app.state.database.sessions.begin() as db:
        user = await db.get(User, uid)
        user.age_band = "teen"
        age = await db.get(AgeDeclaration, uid)
        age.birth_year = year - 18
        age.adult_confirmed_at = None
    assert not (await client.get("/api/v1/session")).json()["eligible"]
    payload = {
        "birthYear": year - 18,
        "confirmedMinimumAge": True,
        "confirmedAdultAge": True,
        "expectedVersion": 1,
        "policyVersion": "self-declared-age-v1",
    }
    assert (
        await client.put("/api/v1/users/me/eligibility", json=payload, headers=key())
    ).status_code == 422
    payload["policyVersion"] = "self-declared-age-v2-18plus"
    confirmed = await client.put("/api/v1/users/me/eligibility", json=payload, headers=key())
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["eligible"] and confirmed.json()["eligibilityVersion"] == 2
    assert (await client.get("/api/v1/moods")).status_code == 200


@pytest.mark.postgres
async def test_activity_catalog_is_protected_even_when_disabled(clients):
    app, actors = clients
    client, uid = actors[0]
    async with app.state.database.sessions.begin() as db:
        (await db.get(User, uid)).age_band = "teen"
    response = await client.get("/api/v1/activities/catalog")
    assert response.status_code == 403, response.text


@pytest.mark.postgres
async def test_minor_can_export_retained_ai_history_without_resuming_chat(clients):
    from app.ai.models import AiConversation

    app, actors = clients
    client, uid = actors[0]
    own, peer = uuid4(), uuid4()
    async with app.state.database.sessions.begin() as db:
        for identity, owner, title in (
            (own, uid, "OWN_PRIVATE_TITLE"),
            (peer, actors[1][1], "PEER_PRIVATE_TITLE"),
        ):
            db.add(
                AiConversation(
                    id=identity,
                    user_id=owner,
                    bot_id="may",
                    title=title,
                    expires_at=datetime.now(UTC) + timedelta(days=1),
                )
            )
        (await db.get(User, uid)).age_band = "teen"
        (
            await db.scalar(select(AuthSession).where(AuthSession.user_id == uid))
        ).reauthenticated_at = datetime.now(UTC)
    created = await client.post(
        "/api/v1/exports", json={"scopes": ["conversations"]}, headers=key()
    )
    assert created.status_code == 201, created.text
    exported = await client.get(f"/api/v1/exports/{created.json()['id']}/download")
    assert exported.status_code == 200
    assert "OWN_PRIVATE_TITLE" in exported.text and "PEER_PRIVATE_TITLE" not in exported.text
    assert (await client.get(f"/api/v1/ai/conversations/{own}/export")).status_code == 200
    assert (await actors[1][0].get(f"/api/v1/ai/conversations/{own}/export")).status_code == 404
    assert (await client.get(f"/api/v1/ai/conversations/{own}")).status_code == 403
