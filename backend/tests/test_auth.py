"""JWT signatures and claims are verified before an identity can reach the DB."""

import json
import time
from uuid import uuid4

import httpx
import jwt
import pytest
from app.core.auth import JwtVerifier
from cryptography.hazmat.primitives.asymmetric import ec
from moodprint_shared.config import AppConfig
from moodprint_shared.contracts.errors import DomainError
from moodprint_shared.env import EnvSettings


@pytest.fixture
def auth_setup():
    key = ec.generate_private_key(ec.SECP256R1())
    jwk = json.loads(jwt.algorithms.ECAlgorithm.to_jwk(key.public_key()))
    jwk.update(kid="test-key", alg="ES256", use="sig")
    settings = EnvSettings(
        app_env="test",
        supabase_url="http://127.0.0.1:54321",
        supabase_publishable_key="test-public",
        supabase_secret_key="test-secret",
        database_url="postgresql+asyncpg://moodprint_api:local@127.0.0.1:54322/postgres",
    )
    claims = {
        "sub": str(uuid4()),
        "aud": "authenticated",
        "role": "authenticated",
        "iss": "http://127.0.0.1:54321/auth/v1",
        "exp": int(time.time()) + 300,
        "iat": int(time.time()),
        "session_id": str(uuid4()),
        "is_anonymous": False,
    }
    return key, jwk, settings, claims


async def verify(auth_setup, overrides=None, *, outage=False, kid="test-key", algorithm="ES256"):
    key, jwk, settings, claims = auth_setup
    claims = {**claims, **(overrides or {})}
    transport = httpx.MockTransport(
        lambda r: httpx.Response(503 if outage else 200, json={"keys": [jwk]})
    )
    token = jwt.encode(
        claims, key if algorithm == "ES256" else "x" * 64, algorithm=algorithm, headers={"kid": kid}
    )
    async with httpx.AsyncClient(transport=transport) as client:
        return await JwtVerifier(settings, AppConfig(), client).verify(token)


async def test_valid_token(auth_setup):
    auth = await verify(auth_setup)
    assert str(auth.user_id) == auth_setup[3]["sub"]
    assert auth.session_id == auth_setup[3]["session_id"]
    assert "claims_json=" not in repr(auth)


@pytest.mark.parametrize(
    "overrides",
    [
        {"exp": 1},
        {"aud": "wrong"},
        {"iss": "https://evil.example"},
        {"role": "service_role"},
        {"is_anonymous": True},
        {"sub": "invalid"},
        {"sub": None},
    ],
)
async def test_invalid_claims_rejected(auth_setup, overrides):
    with pytest.raises(Exception) as error:
        await verify(auth_setup, overrides)
    assert error.value.code == "unauthenticated"


async def test_hs256_rejected(auth_setup):
    with pytest.raises(Exception) as error:
        await verify(auth_setup, algorithm="HS256")
    assert error.value.code == "unauthenticated"


async def test_jwks_outage_returns_503_not_401(auth_setup):
    with pytest.raises(Exception) as error:
        await verify(auth_setup, outage=True)
    assert error.value.status_code == 503


async def test_unknown_kid_refetches_once(auth_setup):
    key, jwk, settings, claims = auth_setup
    requests = []

    def respond(request):
        requests.append(request)
        return httpx.Response(200, json={"keys": [jwk]})

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        verifier = JwtVerifier(settings, AppConfig(), client)
        await verifier.verify(
            jwt.encode(claims, key, algorithm="ES256", headers={"kid": "test-key"})
        )
        for _ in range(3):
            with pytest.raises(DomainError):
                await verifier.verify(
                    jwt.encode(claims, key, algorithm="ES256", headers={"kid": "unknown"})
                )
    assert len(requests) == 2


async def test_alg_none_rejected(auth_setup):
    _, _, settings, claims = auth_setup
    async with httpx.AsyncClient() as client:
        with pytest.raises(Exception) as error:
            await JwtVerifier(settings, AppConfig(), client).verify(
                jwt.encode(claims, "", algorithm="none")
            )
    assert error.value.code == "unauthenticated"


async def test_user_metadata_never_grants_role(auth_setup):
    auth = await verify(auth_setup, {"user_metadata": {"role": "admin", "owner_id": str(uuid4())}})
    assert str(auth.user_id) == auth_setup[3]["sub"]
    assert "user_metadata" not in json.loads(auth.claims_json)


async def test_sensitive_operation_rejects_deleted_user(auth_setup):
    from app.infrastructure.auth_admin import AuthAdmin

    auth = await verify(auth_setup)
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda r: httpx.Response(401))
    ) as client:
        with pytest.raises(Exception) as error:
            await AuthAdmin(auth_setup[2], client).require_live_user(auth, "test-bearer")
    assert error.value.code == "unauthenticated"
