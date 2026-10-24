"""Create only two authorized synthetic Auth users; Admin key stays in process memory."""

import argparse
import base64
import getpass
import json
import re
import secrets
import sys
import warnings
from pathlib import Path
from uuid import UUID

import httpx
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
PROJECT_URL = "https://roznanxbiyqybjpvtilq.supabase.co"


def create_accounts(path: Path, admin_key: str, transport=None):
    values = dotenv_values(path)
    if values.get("SUPABASE_URL") != PROJECT_URL or not admin_key:
        raise ValueError("Expected project and one-time Auth Admin credential are required")
    created = 0
    with httpx.Client(
        timeout=15, follow_redirects=False, transport=transport,
        headers={"apikey": admin_key, "Authorization": f"Bearer {admin_key}"},
    ) as client:
        for actor in ("A", "B"):
            prefix = f"MOODPRINT_TEST_{actor}_"
            expected_email = f"moodprint-qa-{actor.lower()}-roznanxbiyqybjpvtilq@example.invalid"
            names = [prefix + suffix for suffix in ("EMAIL", "PASSWORD", "USER_ID")]
            if all(values.get(name) for name in names):
                if values[names[0]] != expected_email:
                    raise ValueError("Existing fixture differs; do not overwrite accounts")
                continue
            if any(values.get(name) for name in names):
                raise ValueError("Incomplete local fixture; inspect before creating another user")
            password = secrets.token_urlsafe(36)
            response = client.post(
                f"{PROJECT_URL}/auth/v1/admin/users",
                json={"email": expected_email, "password": password, "email_confirm": True},
            )
            if response.status_code not in (200, 201):
                raise ValueError(f"Auth Admin returned HTTP{response.status_code}; provider body omitted")
            payload = response.json()
            identity = str(UUID(payload["id"]))
            if payload.get("email") != expected_email:
                raise ValueError("Auth Admin response did not match the expected synthetic account")
            updates = dict(zip(names, (expected_email, password, identity), strict=True))
            content = path.read_text(encoding="utf-8")
            for name, value in updates.items():
                replacement = name + "='" + value.replace("'", "\\'") + "'"
                if re.search(r"^" + name + "=", content, re.M):
                    content = re.sub(r"^" + name + r"=.*$", lambda _, value=replacement: value, content, flags=re.M)
                else:
                    content += "\n" + replacement + "\n"
            # Persist each confirmed fixture before attempting the second; no temp files.
            path.write_text(content, encoding="utf-8")
            values.update(updates)
            created += 1
    return {
        "projectId": "roznanxbiyqybjpvtilq", "accountsConfigured": 2,
        "createdThisCall": created, "adminKeyStored": False, "passwordsPrinted": False,
        "confirmationMethod": "Auth Admin email_confirm=true; email delivery not tested",
        "networkAccessPerformed": bool(created), "liveModelCalls": 0,
    }


def configure_existing(path: Path, accounts, transport=None):
    values = dotenv_values(path)
    if values.get("SUPABASE_URL") != PROJECT_URL or not values.get("SUPABASE_PUBLISHABLE_KEY"):
        raise ValueError("Expected project and existing publishable key are required")
    if len(accounts) != 2:
        raise ValueError("Exactly two authorized test accounts are required")
    updates = {}
    identities = set()
    with httpx.Client(timeout=15, follow_redirects=False, transport=transport) as client:
        headers = {"apikey": values["SUPABASE_PUBLISHABLE_KEY"]}
        for actor, (email, password) in zip(("A", "B"), accounts, strict=True):
            response = client.post(
                f"{PROJECT_URL}/auth/v1/token?grant_type=password",
                headers=headers, json={"email": email, "password": password},
            )
            if response.status_code != 200:
                raise ValueError(f"Test account {actor} login returned HTTP{response.status_code}")
            token = response.json()["access_token"]
            verified = client.get(
                f"{PROJECT_URL}/auth/v1/user", headers={**headers, "Authorization": f"Bearer {token}"}
            )
            if verified.status_code != 200:
                raise ValueError("Could not verify the authorized test account")
            user = verified.json()
            identity = str(UUID(user["id"]))
            if identity in identities or user.get("email", "").casefold() != email.casefold():
                raise ValueError("Expected two distinct test account identities")
            identities.add(identity)
            # Revoke only this validation session; never sign out other sessions globally.
            revoked = client.post(
                f"{PROJECT_URL}/auth/v1/logout?scope=local",
                headers={**headers, "Authorization": f"Bearer {token}"},
            )
            if revoked.status_code not in (200, 204):
                raise ValueError("Temporary validation session cleanup failed")
            prefix = f"MOODPRINT_TEST_{actor}_"
            updates.update({prefix + "EMAIL": email, prefix + "USER_ID": identity,
                            prefix + "PASSWORD_B64": base64.b64encode(password.encode()).decode()})
    content = path.read_text(encoding="utf-8")
    for name, value in updates.items():
        replacement = name + "='" + value.replace("'", "\\'") + "'"
        if re.search(r"^" + name + "=", content, re.M):
            content = re.sub(r"^" + name + r"=.*$", lambda _, value=replacement: value, content, flags=re.M)
        else:
            content += "\n" + replacement + "\n"
    path.write_text(content, encoding="utf-8")
    return {"projectId": "roznanxbiyqybjpvtilq", "accountsConfigured": 2,
            "createdThisCall": 0, "adminKeyStored": False, "passwordsPrinted": False,
            "updatedVariables": list(updates), "validationSessionsRevoked": True,
            "passwordEncoding": "base64 for dotenv round-trip, not encryption",
            "networkAccessPerformed": True, "liveModelCalls": 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--create", action="store_true", help="Create the two already authorized synthetic test users")
    parser.add_argument("--configure-existing", action="store_true", help="Validate two users created by the user in Dashboard; no Admin key")
    args = parser.parse_args()
    if args.create and args.configure_existing:
        parser.error("Choose create or configure-existing")
    if not args.create and not args.configure_existing:
        print(json.dumps({"mode": "review_only", "networkAccessPerformed": False, "maximumTestUsers": 2}))
        return 0
    if not sys.stdin.isatty():
        raise ValueError("Run in a local interactive terminal for hidden one-time key input")
    with warnings.catch_warnings():
        warnings.simplefilter("error", getpass.GetPassWarning)
        if args.configure_existing:
            accounts = []
            for actor in ("A", "B"):
                email = input(f"Authorized test account {actor} email: ").strip()
                password = getpass.getpass(f"Test account {actor} password (hidden): ")
                if not password or password != getpass.getpass("Confirm password: "):
                    raise ValueError("EMPTY_OR_MISMATCHED_PASSWORD")
                accounts.append((email, password))
            report = configure_existing(ROOT / "backend/.env", accounts)
        else:
            admin_key = getpass.getpass("One-time Supabase secret/service_role key (hidden; NOT saved): ")
            report = create_accounts(ROOT / "backend/.env", admin_key)
    (ROOT / "docs/plans/validation-artifacts/supabase-auth-test-accounts.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (Exception, KeyboardInterrupt) as error:
        print(json.dumps({"status": "failed", "errorType": type(error).__name__, "secretsPrinted": False}))
        sys.exit(1)
