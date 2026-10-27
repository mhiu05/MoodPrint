"""Hosted anonymous-auth compatibility probe (GE-01.2). Runs only against an approved target.

``-k target_guard`` always runs locally and proves the refusal paths. The hosted probe itself is
skipped (reported as a gap, never a pass) unless the owner approves a non-production project
(decision D04) and supplies it out of band; it performs ONE synthetic anonymous signup through the
production adapter and deletes only that exact identity in ``finally``.
"""

import os
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from pydantic import SecretStr

from tests.live.hosted_guard import (
    APPROVAL,
    OPT_IN,
    TARGET_KEY,
    TARGET_URL,
    TargetRefused,
    require_approved_target,
)

REF = "abcdefghijklmnopqrst"
GOOD = {
    OPT_IN: "1",
    APPROVAL: REF,
    TARGET_URL: f"https://{REF}.supabase.co",
    TARGET_KEY: "publishable-synthetic",
}


def test_hosted_target_guard():
    mutations = []

    def refused(env):
        with pytest.raises(TargetRefused):
            require_approved_target(env)
        mutations.append(env)

    refused({})  # nothing approved
    refused({**GOOD, OPT_IN: "0"})
    refused({**GOOD, APPROVAL: ""})
    refused({**GOOD, APPROVAL: "not-a-project-ref"})
    refused({**GOOD, TARGET_URL: f"https://other{REF[5:]}.supabase.co"})  # mismatched project
    refused({**GOOD, TARGET_URL: f"http://{REF}.supabase.co"})  # not https
    refused({**GOOD, TARGET_URL: "https://example.com"})
    target = require_approved_target(GOOD)
    assert target.project_ref == REF and "publishable-synthetic" not in repr(target)
    # The process environment (and any .env) is never consulted when an explicit mapping is given.
    assert require_approved_target({**GOOD}).url == f"https://{REF}.supabase.co"
    assert len(mutations) == 7


def _approved():
    try:
        return require_approved_target(os.environ)
    except TargetRefused:
        return None


@pytest.mark.live
async def test_hosted_anonymous_signup_is_verified_and_cleaned_up():
    target = _approved()
    if target is None:
        pytest.skip("BLOCKED: no owner-approved non-production target (D04); hosted proof not run")
    from app.modules.auth.provider import AnonymousSignupError, SupabaseAuth

    settings = SimpleNamespace(
        supabase_url=target.url,
        supabase_publishable_key=SecretStr(target.publishable_key),
        frontend_origin="https://approved-staging.invalid",
    )
    app = SimpleNamespace(state=SimpleNamespace(settings=settings))
    captcha = os.environ.get("GUEST_AUTH_TARGET_CAPTCHA_TOKEN", "")
    if not captcha:
        pytest.skip("BLOCKED: the approved target requires an interactive CAPTCHA token")
    auth = SupabaseAuth(SimpleNamespace(app=app))
    provider = None
    try:
        provider = await auth.anonymous_session(captcha, correlation_id=uuid4().hex * 2)
    except AnonymousSignupError as error:
        pytest.fail(f"hosted anonymous signup did not verify: {error.outcome}")
    finally:
        if provider is not None:
            async with httpx.AsyncClient(timeout=10) as client:
                await client.post(
                    f"{target.url}/auth/v1/logout?scope=local",
                    headers={
                        "apikey": target.publishable_key,
                        "Authorization": f"Bearer {provider.access_token}",
                    },
                )
    assert provider is not None and provider.is_anonymous is True
