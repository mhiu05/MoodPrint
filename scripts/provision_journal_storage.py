"""Provision only the private journal bucket, using an existing Management API token.

No application migrations, user data, or unrelated buckets are changed. Credentials never print.
"""

import argparse
import json
import os
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

MIMES = [
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/gif",
    "audio/webm",
    "audio/ogg",
    "audio/mp4",
    "audio/mpeg",
    "audio/wav",
    "video/mp4",
    "video/webm",
    "video/quicktime",
]
BUCKET = "journal-media"


def call(url, token, *, method="GET", body=None):
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    if ".supabase.co/" in url:
        headers["apikey"] = token
    data = None if body is None else json.dumps(body).encode()
    try:
        with urlopen(
            Request(url, data=data, headers=headers, method=method), timeout=30
        ) as response:
            return json.load(response)
    except HTTPError as error:
        # HTTPError string/body can contain URLs/tokens; return only the status.
        try:
            detail = json.load(error)
            code = detail.get("error", detail.get("message", ""))
            safe_code = (
                code
                if isinstance(code, str)
                and len(code) < 200
                and "eyJ" not in code
                and "sb_secret" not in code
                else ""
            )
        except Exception:
            safe_code = ""
        raise RuntimeError(
            f"Provider request failed (HTTP {error.code}, {method} {urlsplit(url).path}) {safe_code}"
        ) from None
    except URLError:
        raise RuntimeError("Provider connection failed") from None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-ref", required=True)
    parser.add_argument("--configure-local-env", action="store_true")
    args = parser.parse_args()
    if not args.project_ref.isalnum() or len(args.project_ref) != 20:
        raise RuntimeError("Invalid project ref")
    token = os.environ.get("SUPABASE_ACCESS_TOKEN", "")
    if not token:
        raise RuntimeError("SUPABASE_ACCESS_TOKEN is required")
    management = f"https://api.supabase.com/v1/projects/{args.project_ref}"
    project = call(management, token)
    keys = call(f"{management}/api-keys", token)
    service = next((key["api_key"] for key in keys if key.get("name") == "service_role"), None)
    if not service:
        raise RuntimeError("Existing server Storage credential unavailable")
    storage = f"https://{args.project_ref}.supabase.co/storage/v1"
    buckets = call(f"{storage}/bucket", service)
    existing = next((bucket for bucket in buckets if bucket["id"] == BUCKET), None)
    desired = {
        "id": BUCKET,
        "name": BUCKET,
        "public": False,
        "file_size_limit": 52428800,
        "allowed_mime_types": MIMES,
    }
    if existing is None:
        call(f"{storage}/bucket", service, method="POST", body=desired)
        action = "created"
    elif existing.get("public") is not False:
        raise RuntimeError("Existing journal bucket is public; refusing an unreviewed transition")
    else:
        # This bucket is the explicit target; preserve unrelated bucket configuration.
        call(f"{storage}/bucket/{BUCKET}", service, method="PUT", body=desired)
        action = "configured"
    verified = call(f"{storage}/bucket/{BUCKET}", service)
    if verified.get("public") is not False or int(verified.get("file_size_limit", 0)) != 52428800:
        raise RuntimeError("Bucket verification failed")
    if set(verified.get("allowed_mime_types", [])) != set(MIMES):
        raise RuntimeError("MIME allowlist verification failed")
    policies = call(
        f"{management}/database/query",
        token,
        method="POST",
        body={
            "read_only": True,
            "query": "select policyname,permissive,roles,cmd from pg_policies where schemaname='storage' "
            "and tablename='objects'",
        },
    )
    rls = call(
        f"{management}/database/query",
        token,
        method="POST",
        body={
            "read_only": True,
            "query": "select relrowsecurity from pg_class where oid='storage.objects'::regclass",
        },
    )
    restrictive = any(
        p["policyname"] == "journal_media_bff_only" and p["permissive"] == "RESTRICTIVE"
        for p in policies
    )
    # No policy + RLS enabled is default deny. Do not require broad database write permission
    # to create a bucket. For existing permissive policies, apply the reviewed restrictive fence first.
    if not rls or not rls[0]["relrowsecurity"] or (policies and not restrictive):
        raise RuntimeError(
            "Review/apply journal_media_bff_only policy before enabling journal Storage"
        )
    if args.configure_local_env:
        env_path = Path(__file__).resolve().parents[1] / "backend/.env"
        content = env_path.read_text(encoding="utf-8-sig") if env_path.exists() else ""
        lines = [
            line for line in content.splitlines() if not line.startswith("JOURNAL_STORAGE_KEY=")
        ]
        lines.append(f"JOURNAL_STORAGE_KEY={service}")
        env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "projectRef": args.project_ref,
                "projectName": project["name"],
                "bucket": BUCKET,
                "action": action,
                "private": True,
                "maxBytes": 52428800,
                "allowedMimeTypes": MIMES,
                "policyMode": "restrictive_bff_only"
                if restrictive
                else "rls_default_deny_no_object_policies",
                "localBackendConfigured": args.configure_local_env,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(
            f"Provisioning failed: {str(error) if isinstance(error, RuntimeError) else type(error).__name__}",
            file=sys.stderr,
        )
        sys.exit(1)
