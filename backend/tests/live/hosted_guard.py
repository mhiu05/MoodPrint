"""Refuses any hosted probe unless an owner-approved NON-PRODUCTION target is named explicitly.

Nothing here reads ``.env`` or falls back to a configured project: the target must be supplied out of
band through three environment variables and must agree with itself. Absence or mismatch refuses
before a single request is built.
"""

import os
import re
from dataclasses import dataclass
from urllib.parse import urlsplit

APPROVAL = "APPROVED_GUEST_AUTH_TARGET"
OPT_IN = "RUN_GUEST_AUTH_COMPATIBILITY"
TARGET_URL = "GUEST_AUTH_TARGET_URL"
TARGET_KEY = "GUEST_AUTH_TARGET_PUBLISHABLE_KEY"
PROJECT_REF = re.compile(r"^[a-z0-9]{20}$")


class TargetRefused(RuntimeError):
    pass


@dataclass(frozen=True)
class ApprovedTarget:
    project_ref: str
    url: str
    publishable_key: str = ""

    def __repr__(self) -> str:  # never print a key
        return f"ApprovedTarget(project_ref={self.project_ref!r})"


def require_approved_target(environ=None) -> ApprovedTarget:
    env = os.environ if environ is None else environ
    if env.get(OPT_IN) != "1":
        raise TargetRefused(f"{OPT_IN}=1 is required for any hosted request")
    approved = env.get(APPROVAL, "").strip()
    if not PROJECT_REF.match(approved):
        raise TargetRefused(f"{APPROVAL} must name the approved project reference")
    url = env.get(TARGET_URL, "").strip().rstrip("/")
    parts = urlsplit(url)
    host = parts.hostname or ""
    if parts.scheme != "https" or not host.endswith(".supabase.co"):
        raise TargetRefused(f"{TARGET_URL} must be the approved project's https supabase URL")
    if host.removesuffix(".supabase.co") != approved:
        raise TargetRefused("the target URL does not match the approved project reference")
    return ApprovedTarget(approved, url, env.get(TARGET_KEY, ""))
