"""Read-only, offline checksum/freshness verification; never restores or reads .env.

Keep manifests and real backup bytes in an access-controlled vault outside the repo.
A pass proves integrity against the supplied manifest, not source completeness,
snapshot availability, encryption/key recovery, or successful application recovery.
"""

import argparse
import hashlib
import json
import math
import re
from datetime import UTC, datetime
from pathlib import Path, PureWindowsPath

DOMAINS = ("database", "storage", "configuration", "secrets", "infrastructure")


class VerificationError(ValueError):
    """Safe machine-readable category; never include untrusted data in errors."""


def verify_manifest(path: Path, now: datetime, max_age_hours: float = 24) -> dict:
    if now.tzinfo is None or not math.isfinite(max_age_hours) or max_age_hours <= 0:
        raise VerificationError("invalid_verification_time")
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise VerificationError("invalid_manifest") from None
    if not isinstance(manifest, dict) or manifest.get("schema_version") != 1:
        raise VerificationError("invalid_manifest")
    components = manifest.get("components")
    if not isinstance(components, dict):
        raise VerificationError("invalid_manifest")
    root = path.resolve().parent
    seen = set()
    ages = []
    counts = {}
    for domain in DOMAINS:
        if domain not in components:
            raise VerificationError("missing_component")
        component = components[domain]
        if not isinstance(component, dict):
            raise VerificationError("invalid_component")
        try:
            captured = datetime.fromisoformat(component["captured_at"])
            if captured.tzinfo is None:
                raise ValueError
        except (KeyError, TypeError, ValueError):
            raise VerificationError("invalid_capture_time") from None
        age = (now - captured).total_seconds() / 3600
        if age < 0:
            raise VerificationError("capture_in_future")
        if age > max_age_hours:
            raise VerificationError("capture_outside_rpo")
        ages.append(age)
        artifacts = component.get("artifacts")
        if not isinstance(artifacts, list):
            raise VerificationError("invalid_component")
        if domain == "storage":
            expected = component.get("expected_objects")
            if type(expected) is not int or expected < 0 or expected != len(artifacts):
                raise VerificationError("storage_inventory_mismatch")
        elif not artifacts:
            raise VerificationError("empty_component")
        for artifact in artifacts:
            if not isinstance(artifact, dict):
                raise VerificationError("invalid_artifact")
            raw = artifact.get("path")
            if (not isinstance(raw, str) or not raw or "\x00" in raw
                    or Path(raw).is_absolute() or PureWindowsPath(raw).drive
                    or ".." in Path(raw).parts or ".." in PureWindowsPath(raw).parts):
                raise VerificationError("unsafe_artifact_path")
            try:
                target = (root / raw).resolve()
            except (OSError, ValueError):
                raise VerificationError("unsafe_artifact_path") from None
            if not target.is_relative_to(root) or target == root:
                raise VerificationError("unsafe_artifact_path")
            if target in seen:
                raise VerificationError("duplicate_artifact_path")
            seen.add(target)
            size = artifact.get("size_bytes")
            digest = artifact.get("sha256")
            if (type(size) is not int or size < 0 or (size == 0 and domain != "storage")
                    or not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest)):
                raise VerificationError("invalid_artifact")
            try:
                if not target.is_file():
                    raise VerificationError("artifact_unavailable")
                if target.stat().st_size != size:
                    raise VerificationError("artifact_size_mismatch")
                with target.open("rb") as stream:
                    actual = hashlib.file_digest(stream, "sha256").hexdigest()
            except OSError:
                raise VerificationError("artifact_unavailable") from None
            if actual != digest:
                raise VerificationError("artifact_digest_mismatch")
        counts[domain] = len(artifacts)
    return {
        "status": "ARTIFACT_INTEGRITY_PASS", "restore_proven": False,
        "source_completeness": "NOT_PROVEN", "cloud_resources_verified": False,
        "oldest_capture_age_hours": max(ages), "rpo_target_hours": max_age_hours,
        "artifact_counts": counts,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--now", help="Fixed ISO8601 time for reproducible offline checks")
    args = parser.parse_args()
    try:
        now = datetime.fromisoformat(args.now) if args.now else datetime.now(UTC)
        report = verify_manifest(args.manifest, now)
    except (VerificationError, ValueError) as exc:
        code = str(exc) if isinstance(exc, VerificationError) else "invalid_verification_time"
        print(json.dumps({"status": "FAIL", "error_code": code, "restore_proven": False}))
        return 1
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
