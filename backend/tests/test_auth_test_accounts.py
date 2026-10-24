from uuid import uuid4

import httpx
import pytest
from dotenv import dotenv_values

from tests.test_database_operations import script


def test_admin_provision_creates_only_two_confirmed_fixtures_and_never_stores_admin_key(tmp_path, capsys):
    module = script("provision_auth_test_accounts")
    path = tmp_path / ".env"
    original = "SUPABASE_URL=https://roznanxbiyqybjpvtilq.supabase.co\nOPENAI_API_KEY='retained-canary'\n"
    path.write_text(original, encoding="utf-8")
    seen = []

    def provider(request):
        import json

        assert request.url.host == "roznanxbiyqybjpvtilq.supabase.co"
        assert request.url.path == "/auth/v1/admin/users"
        assert request.headers["apikey"] == "ADMIN-KEY-CANARY"
        assert request.headers["authorization"] == "Bearer ADMIN-KEY-CANARY"
        body = json.loads(request.content)
        assert body["email_confirm"] is True and len(body["password"]) >= 40
        seen.append(body["email"])
        return httpx.Response(200, json={"id": str(uuid4()), "email": body["email"]})

    report = module.create_accounts(path, "ADMIN-KEY-CANARY", httpx.MockTransport(provider))
    assert len(seen) == 2 and len(set(seen)) == 2
    assert report["accountsConfigured"] == 2 and report["adminKeyStored"] is False
    values = dotenv_values(path)
    assert values["MOODPRINT_TEST_A_PASSWORD"] != values["MOODPRINT_TEST_B_PASSWORD"]
    assert original in path.read_text(encoding="utf-8")
    assert "ADMIN-KEY-CANARY" not in path.read_text(encoding="utf-8") + capsys.readouterr().out
    # A second call reuses only the two stored fixtures and never creates more users.
    module.create_accounts(path, "ADMIN-KEY-CANARY", httpx.MockTransport(provider))
    assert len(seen) == 2


def test_partial_auth_provision_preserves_first_fixture_and_sanitizes_provider_error(tmp_path):
    module = script("provision_auth_test_accounts")
    path = tmp_path / ".env"
    path.write_text("SUPABASE_URL=https://roznanxbiyqybjpvtilq.supabase.co\n", encoding="utf-8")
    count = 0

    def provider(request):
        nonlocal count
        count += 1
        if count == 1:
            import json

            return httpx.Response(200, json={"id": str(uuid4()), "email": json.loads(request.content)["email"]})
        return httpx.Response(503, text="PRIVATE-PROVIDER-CANARY")

    with pytest.raises(ValueError) as error:
        module.create_accounts(path, "ADMIN-KEY-CANARY", httpx.MockTransport(provider))
    assert "PRIVATE-PROVIDER-CANARY" not in str(error.value)
    values = dotenv_values(path)
    assert values["MOODPRINT_TEST_A_PASSWORD"] and "MOODPRINT_TEST_B_PASSWORD" not in values


def test_manual_test_credentials_are_verified_without_admin_and_round_trip_special_symbols(tmp_path):
    import base64
    import json

    module = script("provision_auth_test_accounts")
    path = tmp_path / ".env"
    original = "SUPABASE_URL=https://roznanxbiyqybjpvtilq.supabase.co\nSUPABASE_PUBLISHABLE_KEY=public-fixture\nOPENAI_MODEL=retained\n"
    path.write_text(original, encoding="utf-8")
    accounts = [("a@example.invalid", "@${literal}'\\é-one"), ("b@example.invalid", "second-canary")]
    identities = {email: str(uuid4()) for email, _ in accounts}
    active = {}
    revoked = []

    def provider(request):
        assert request.headers["apikey"] == "public-fixture" and "/admin/" not in request.url.path
        if request.url.path.endswith("/token"):
            body = json.loads(request.content)
            active["email"] = body["email"]
            return httpx.Response(200, json={"access_token": "PRIVATE-TOKEN-CANARY"})
        if request.url.path.endswith("/user"):
            return httpx.Response(200, json={"id": identities[active["email"]], "email": active["email"]})
        assert request.url.path.endswith("/logout") and request.url.params["scope"] == "local"
        revoked.append(active["email"])
        return httpx.Response(204)

    report = module.configure_existing(path, accounts, httpx.MockTransport(provider))
    assert report["validationSessionsRevoked"] and len(revoked) == 2
    values = dotenv_values(path)
    assert base64.b64decode(values["MOODPRINT_TEST_A_PASSWORD_B64"]).decode() == accounts[0][1]
    assert original in path.read_text(encoding="utf-8")
    assert "PRIVATE-TOKEN-CANARY" not in path.read_text(encoding="utf-8")
