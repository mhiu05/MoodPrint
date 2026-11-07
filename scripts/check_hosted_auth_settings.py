"""Read-only checks for the explicitly authorized hosted Auth configuration."""

import argparse
import json
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import httpx
from dotenv import dotenv_values

EXPECTED_HOST = "xhlshihobyxrgfqrdafh.supabase.co"
ROOT = Path(__file__).resolve().parents[1]


def validate_target(url: str) -> str:
    parsed = urlsplit(url)
    if (
        parsed.scheme != "https"
        or parsed.hostname != EXPECTED_HOST
        or parsed.port not in (None, 443)
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in ("", "/")
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("SUPABASE_URL must identify the authorized project")
    return f"https://{EXPECTED_HOST}"


def assess_settings(payload: dict[str, Any]) -> dict[str, bool]:
    external = payload.get("external")
    anonymous_disabled = isinstance(external, dict) and external.get("anonymous_users") is False
    return {
        "signup_enabled": payload.get("disable_signup") is False,
        "email_confirmation_enabled": payload.get("mailer_autoconfirm") is False,
        "anonymous_signins_disabled": anonymous_disabled,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=ROOT / ".env")
    args = parser.parse_args()
    values = dotenv_values(args.env_file)
    try:
        base = validate_target(values.get("SUPABASE_URL") or "")
        key = values.get("SUPABASE_PUBLISHABLE_KEY") or ""
        if not key or "<" in key or "placeholder" in key.lower():
            raise ValueError("SUPABASE_PUBLISHABLE_KEY is missing")
        with httpx.Client(timeout=15, follow_redirects=False) as client:
            response = client.get(base + "/auth/v1/settings", headers={"apikey": key})
        if response.status_code != 200:
            print("Auth settings check failed: upstream HTTP error")
            return 1
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("Auth settings response must be an object")
        checks = assess_settings(payload)
        print(json.dumps(checks, sort_keys=True))
        return 0 if all(checks.values()) else 1
    except (ValueError, httpx.HTTPError):
        # Exception text can include credential-bearing request URLs.
        print("Auth settings check failed: check configuration or connectivity")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
