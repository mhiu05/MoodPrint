"""Anonymous provider contract: verified claims, classified outcomes, no permanent promotion.

Pure provider-adapter tests against a fake Supabase transport; no database and no external call.
"""

import base64
import json
import time
from types import SimpleNamespace
from uuid import UUID, uuid4

import httpx
import pytest
from pydantic import SecretStr

from app.core.errors import DomainError

SUPABASE = "https://example-project.supabase.co"
ISSUER = SUPABASE + "/auth/v1"
CORRELATION = "c" * 64
CAPTCHA = "synthetic-captcha-token-value"


def make_jwt(subject, session, **overrides):
    def part(value):
        return base64.urlsafe_b64encode(json.dumps(value).encode()).rstrip(b"=").decode()

    claims = {
        "sub": str(subject),
        "session_id": str(session),
        "iss": ISSUER,
        "aud": "authenticated",
        "exp": int(time.time()) + 3600,
        "is_anonymous": True,
    }
    for key, value in overrides.items():
        if value is ...:
            claims.pop(key, None)
        else:
            claims[key] = value
    return f"{part({'alg': 'none'})}.{part(claims)}.signature"


class FakeProvider:
    """Records every provider call; each scenario overrides one stage."""

    def __init__(self, *, claims=None, profile=None, signup=None, user=None, anonymous=True):
        self.uid, self.sid = uuid4(), uuid4()
        self.claims = claims or {}
        self.profile = profile or {}
        self.signup = signup
        self.user = user
        self.anonymous = anonymous
        self.calls = []

    @property
    def token(self):
        return make_jwt(self.uid, self.sid, **{"is_anonymous": self.anonymous, **self.claims})

    def handler(self, request: httpx.Request):
        path = request.url.path.removeprefix("/auth/v1")
        body = json.loads(request.content) if request.content else {}
        self.calls.append((request.method, path, dict(request.url.params), body, dict(request.headers)))
        if path == "/signup":
            if callable(self.signup):
                return self.signup(request)
            if self.signup is not None:
                return self.signup
            return httpx.Response(200, json={"access_token": self.token, "refresh_token": "never-stored"})
        if path == "/user" and request.method == "GET":
            if callable(self.user):
                return self.user(request)
            if self.user is not None:
                return self.user
            profile = {"id": str(self.uid), "is_anonymous": self.anonymous, **self.profile}
            profile = {key: value for key, value in profile.items() if value is not ...}
            return httpx.Response(200, json=profile)
        if path == "/user" and request.method == "PUT":
            return httpx.Response(200, json={})
        if path == "/token":
            return httpx.Response(200, json={"access_token": self.token})
        return httpx.Response(404, json={})

    def calls_to(self, method, path):
        return [call for call in self.calls if call[0] == method and call[1] == path]


def auth_for(fake: FakeProvider):
    from app.modules.auth.provider import SupabaseAuth

    settings = SimpleNamespace(
        supabase_url=SUPABASE,
        supabase_publishable_key=SecretStr("publishable-test"),
        frontend_origin="http://127.0.0.1:5173",
    )
    app = SimpleNamespace(
        state=SimpleNamespace(settings=settings, auth_transport=httpx.MockTransport(fake.handler))
    )
    return SupabaseAuth(SimpleNamespace(app=app))


async def test_anonymous_signup_is_verified_and_correlated():
    fake = FakeProvider()
    provider = await auth_for(fake).anonymous_session(CAPTCHA, correlation_id=CORRELATION)

    assert provider.is_anonymous is True
    assert provider.user_id == fake.uid and provider.session_id == fake.sid
    assert provider.access_token not in repr(provider)
    signups = fake.calls_to("POST", "/signup")
    assert len(signups) == 1
    _, _, params, body, headers = signups[0]
    assert body == {
        "data": {"moodprint_guest_attempt": CORRELATION},
        "gotrue_meta_security": {"captcha_token": CAPTCHA},
    }
    assert "email" not in body and "password" not in body and not params
    assert headers["apikey"] == "publishable-test"
    assert "sb-forwarded-for" not in headers
    assert len(fake.calls_to("GET", "/user")) == 1


CLAIM_FAULTS = {
    "sub_differs_from_user": {"claims": {"sub": str(uuid4())}},
    "wrong_issuer": {"claims": {"iss": "https://other.example/auth/v1"}},
    "wrong_audience": {"claims": {"aud": "anon"}},
    "audience_list_without_authenticated": {"claims": {"aud": ["anon", "service"]}},
    "expired": {"claims": {"exp": int(time.time()) - 5}},
    "non_numeric_expiry": {"claims": {"exp": "tomorrow"}},
    "boolean_expiry": {"claims": {"exp": True}},
    "missing_expiry": {"claims": {"exp": ...}},
    "session_not_uuid": {"claims": {"session_id": "not-a-uuid"}},
    "missing_session": {"claims": {"session_id": ...}},
    "claim_flag_false": {"claims": {"is_anonymous": False}},
    "claim_flag_string": {"claims": {"is_anonymous": "true"}},
    "claim_flag_missing": {"claims": {"is_anonymous": ...}},
    "profile_flag_false": {"profile": {"is_anonymous": False}},
    "profile_flag_string": {"profile": {"is_anonymous": "true"}},
    "profile_flag_missing": {"profile": {"is_anonymous": ...}},
}


@pytest.mark.parametrize("fault", sorted(CLAIM_FAULTS))
async def test_anonymous_claim_mismatch_is_denied(fault):
    from app.modules.auth.provider import AnonymousSignupError

    fake = FakeProvider(**CLAIM_FAULTS[fault])
    with pytest.raises(AnonymousSignupError) as caught:
        await auth_for(fake).anonymous_session(CAPTCHA, correlation_id=CORRELATION)

    # The provider already created an identity, so an unverifiable success is ambiguous, never a grant.
    assert caught.value.outcome == "ambiguous"
    assert len(fake.calls_to("POST", "/signup")) == 1
    assert fake.token not in str(caught.value) and CAPTCHA not in str(caught.value)


async def test_anonymous_signup_rejects_a_permanent_identity():
    from app.modules.auth.provider import AnonymousSignupError

    fake = FakeProvider(anonymous=False)
    with pytest.raises(AnonymousSignupError) as caught:
        await auth_for(fake).anonymous_session(CAPTCHA, correlation_id=CORRELATION)
    assert caught.value.outcome == "ambiguous"


SIGNUP_OUTCOMES = {
    "captcha_failed": (httpx.Response(400, json={"error_code": "captcha_failed"}), "rejected", 422),
    "anonymous_disabled": (
        httpx.Response(422, json={"error_code": "anonymous_provider_disabled"}),
        "rejected",
        503,
    ),
    "rate_limited": (httpx.Response(429, json={"error_code": "over_request_rate_limit"}), "rejected", 429),
    "unknown_client_error": (httpx.Response(403, json={"msg": "raw provider body"}), "rejected", 503),
    "server_error": (httpx.Response(500, json={"msg": "boom"}), "ambiguous", 503),
    "bad_gateway": (httpx.Response(502, text="<html>gateway</html>"), "ambiguous", 503),
    "success_without_token": (httpx.Response(200, json={"user": {}}), "ambiguous", 503),
    "success_with_invalid_body": (httpx.Response(200, text="not json"), "ambiguous", 503),
    "success_with_array_body": (httpx.Response(200, json=["x"]), "ambiguous", 503),
}


@pytest.mark.parametrize("name", sorted(SIGNUP_OUTCOMES))
async def test_signup_outcomes_are_classified_without_retry(name):
    from app.modules.auth.provider import AnonymousSignupError

    response, outcome, status = SIGNUP_OUTCOMES[name]
    fake = FakeProvider(signup=response)
    with pytest.raises(AnonymousSignupError) as caught:
        await auth_for(fake).anonymous_session(CAPTCHA, correlation_id=CORRELATION)

    assert caught.value.outcome == outcome and caught.value.status == status
    assert isinstance(caught.value, DomainError)
    assert len(fake.calls_to("POST", "/signup")) == 1, "signup must never be retried"
    assert not fake.calls_to("GET", "/user") or outcome == "ambiguous"
    assert "raw provider body" not in str(caught.value.message) + str(caught.value)


@pytest.mark.parametrize(
    "failure", [httpx.ReadTimeout("slow"), httpx.ConnectError("down"), httpx.RemoteProtocolError("cut")]
)
async def test_signup_transport_failure_is_ambiguous(failure):
    from app.modules.auth.provider import AnonymousSignupError

    def broken(request):
        raise failure

    fake = FakeProvider(signup=broken)
    with pytest.raises(AnonymousSignupError) as caught:
        await auth_for(fake).anonymous_session(CAPTCHA, correlation_id=CORRELATION)
    assert caught.value.outcome == "ambiguous"
    assert len(fake.calls_to("POST", "/signup")) == 1


@pytest.mark.parametrize(
    "failure", [httpx.ReadTimeout("slow"), httpx.Response(401, json={}), httpx.Response(503, json={})]
)
async def test_user_lookup_failure_after_signup_is_ambiguous(failure):
    from app.modules.auth.provider import AnonymousSignupError

    def handler(request):
        if isinstance(failure, Exception):
            raise failure
        return failure

    fake = FakeProvider(user=handler)
    with pytest.raises(AnonymousSignupError) as caught:
        await auth_for(fake).anonymous_session(CAPTCHA, correlation_id=CORRELATION)
    assert caught.value.outcome == "ambiguous"
    assert len(fake.calls_to("POST", "/signup")) == 1


async def test_registered_verification_requires_an_explicit_permanent_flag():
    fake = FakeProvider(anonymous=False)
    provider = await auth_for(fake).verify_token(fake.token)
    assert provider.is_anonymous is False
    assert provider.access_token not in repr(provider)

    for faulty in (
        FakeProvider(anonymous=False, claims={"is_anonymous": ...}),
        FakeProvider(anonymous=False, profile={"is_anonymous": ...}),
        FakeProvider(anonymous=False, claims={"aud": "anon"}),
        FakeProvider(anonymous=False, claims={"exp": int(time.time()) - 1}),
    ):
        with pytest.raises(DomainError) as caught:
            await auth_for(faulty).verify_token(faulty.token)
        assert caught.value.code == "AUTH_UNAVAILABLE"


async def test_permanent_paths_reject_anonymous_sessions():
    fake = FakeProvider()
    auth = auth_for(fake)

    with pytest.raises(DomainError) as password:
        await auth.password_session("someone@example.com", "correct horse battery")
    assert password.value.status == 403 and password.value.code == "REGISTERED_REQUIRED"

    with pytest.raises(DomainError) as recovery:
        await auth.update_password(fake.token, "a-much-longer-new-password")
    assert recovery.value.status == 403 and recovery.value.code == "REGISTERED_REQUIRED"
    # A bearer token must never become a conversion route: the permanent PUT /user is never sent.
    assert fake.calls_to("PUT", "/user") == []


async def test_permanent_update_still_works_for_registered_tokens():
    fake = FakeProvider(anonymous=False)
    subject = await auth_for(fake).update_password(fake.token, "a-much-longer-new-password")
    assert subject == fake.uid and isinstance(subject, UUID)
    assert len(fake.calls_to("PUT", "/user")) == 1
